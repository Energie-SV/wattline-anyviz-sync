"""
Wattline-Auflistung: Messlokation / MaLo  ->  Measurement-UUID

Einmal-Lauf, um die Measurement-UUIDs weiterer Lieferstellen zu finden.
Nutzt dieselbe Anmeldung wie sync.py (gleiche GitHub-Secrets).

Ausgabe:
  - in das Action-Log (vollständiger Beispiel-Datensatz + kompakte Liste)
  - als Markdown-Tabelle in die Action-Zusammenfassung (Schritt-Summary)
"""

import os
import json
import requests

BASE          = os.environ.get("WATTLINE_BASE_URL", "https://energiedatenportal.wattline.com")
CLIENT_ID     = "api"
CLIENT_SECRET = os.environ.get("WATTLINE_CLIENT_SECRET", "")
USERNAME      = os.environ.get("WATTLINE_USERNAME", "")
PASSWORD      = os.environ.get("WATTLINE_PASSWORD", "")


def get_token() -> str:
    url = f"{BASE}/auth/realms/wattline/protocol/openid-connect/token"
    r = requests.post(url, data={
        "grant_type":    "password",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "username":      USERNAME,
        "password":      PASSWORD,
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def fetch_all(token: str, path: str) -> list:
    """Holt alle Einträge eines Endpunkts, inkl. Pagination (data/links.next)."""
    url = f"{BASE}{path}"
    params = {"limit": 1000}
    headers = {"Authorization": f"Bearer {token}"}
    items = []
    while url:
        r = requests.get(url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        body = r.json()
        if isinstance(body, list):
            items.extend(body)
            break
        items.extend(body.get("data", []))
        url = body.get("links", {}).get("next")
        params = {}
    return items


def compact(d: dict) -> dict:
    """Nur die einfachen Felder eines Datensatzes, verschachtelte IDs/Namen eine Ebene tief."""
    out = {}
    if not isinstance(d, dict):
        return {"_wert": d}
    for k, v in d.items():
        if isinstance(v, (str, int, float, bool)):
            if v not in ("", None):
                out[k] = v
        elif isinstance(v, dict):
            for sub in ("id", "name", "label", "number"):
                if isinstance(v.get(sub), (str, int, float)):
                    out[f"{k}.{sub}"] = v[sub]
        elif isinstance(v, list):
            out[k] = f"[{len(v)} Einträge]"
    return out


def label_of(m: dict) -> str:
    for k in ("name", "label", "description", "displayName", "title"):
        if m.get(k):
            return str(m[k])
    return ""


def malo_of(m: dict) -> str:
    for k in ("marketLocationId", "malo", "maLo", "meteringPointId", "number", "meteringPointNumber"):
        if m.get(k):
            return str(m[k])
    mp = m.get("meteringPoint")
    if isinstance(mp, dict):
        for k in ("number", "marketLocationId", "malo", "name", "id"):
            if mp.get(k):
                return str(mp[k])
    return ""


def dump_endpoint(token: str, path: str) -> list:
    print("=" * 72)
    print("ENDPUNKT:", path)
    print("=" * 72)
    try:
        items = fetch_all(token, path)
    except Exception as e:
        print("  FEHLER:", e, "\n")
        return []
    print(f"  {len(items)} Einträge\n")
    if items:
        print("  --- Beispiel-Datensatz (vollständig, zum Prüfen der Feldnamen) ---")
        print(json.dumps(items[0], indent=2, ensure_ascii=False)[:3000])
        print("\n  --- Kompakt (ein Eintrag pro Zeile) ---")
        for it in items:
            print("   ", json.dumps(compact(it), ensure_ascii=False))
    print()
    return items


def main():
    token = get_token()
    print("Wattline-Token OK.\n")

    dump_endpoint(token, "/shared-metering-points")
    measurements = dump_endpoint(token, "/measurements")

    # Markdown-Tabelle in die Action-Zusammenfassung schreiben
    rows = []
    for m in measurements:
        if not isinstance(m, dict):
            continue
        rows.append((m.get("id", ""), label_of(m), malo_of(m)))

    lines = [
        "## Wattline Measurements → UUIDs",
        "",
        f"{len(rows)} Measurements gefunden. Kopiere die passenden UUIDs in `MEASUREMENT_IDS` in `sync.py`.",
        "",
        "| Measurement-UUID | Bezeichnung | MaLo / Messlokation |",
        "| --- | --- | --- |",
    ]
    for uuid, label, malo in rows:
        lines.append(f"| `{uuid}` | {label} | {malo} |")
    lines.append("")
    lines.append("_Sind Bezeichnung/MaLo leer? Dann im Log oben den Beispiel-Datensatz prüfen "
                 "und die Feldnamen anpassen._")
    md = "\n".join(lines)

    print(md)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(md + "\n")


if __name__ == "__main__":
    main()
