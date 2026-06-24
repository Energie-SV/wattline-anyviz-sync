"""
Wattline → AnyViz Synchronisation
Liest historische Messwerte (readings) von der Wattline API
und schreibt sie als TagValues in AnyViz.

Wird als Cronjob ausgeführt, z.B. stündlich:
    0 * * * * /usr/bin/python3 /path/to/sync.py
"""

import requests
import logging
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import (
    WATTLINE_BASE_URL, WATTLINE_CLIENT_ID, WATTLINE_CLIENT_SECRET,
    WATTLINE_USERNAME, WATTLINE_PASSWORD,
    ANYVIZ_BASE_URL, ANYVIZ_API_KEY,
    MEASUREMENT_TAG_MAP, QUANTITY_KEY,
    SYNC_LOOKBACK_HOURS, STATE_FILE
)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("sync.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


# ── Wattline Auth ──────────────────────────────────────────────────────────────

def get_wattline_token() -> str:
    """OAuth2 Password-Grant gegen Wattline Keycloak."""
    url = f"{WATTLINE_BASE_URL}/auth/realms/wattline/protocol/openid-connect/token"
    data = {
        "grant_type": "password",
        "client_id": WATTLINE_CLIENT_ID,
        "client_secret": WATTLINE_CLIENT_SECRET,
        "username": WATTLINE_USERNAME,
        "password": WATTLINE_PASSWORD,
    }
    resp = requests.post(url, data=data, timeout=30)
    resp.raise_for_status()
    token = resp.json()["access_token"]
    log.info("Wattline Token erhalten.")
    return token


# ── Wattline Daten abrufen ─────────────────────────────────────────────────────

def get_readings(token: str, measurement_id: str, start: datetime, end: datetime) -> list[dict]:
    """
    Liefert alle Messwerte (readings) einer Messreihe im Zeitraum [start, end].
    Paginiert automatisch über 'links.next'.
    """
    url = f"{WATTLINE_BASE_URL}/measurements/{measurement_id}/readings"
    params = {
        "quantity": QUANTITY_KEY,
        "time(gte)": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "time(lt)": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 1000,
    }
    headers = {"Authorization": f"Bearer {token}"}
    all_readings = []

    while url:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        all_readings.extend(body.get("data", []))
        # Paginierung: nächste Seite
        url = body.get("links", {}).get("next")
        params = {}  # next-URL enthält bereits alle Parameter

    log.info("  %d Messwerte für Measurement %s abgerufen.", len(all_readings), measurement_id)
    return all_readings


# ── AnyViz schreiben ───────────────────────────────────────────────────────────

def write_to_anyviz(tag_id: int, value: float) -> None:
    """Schreibt einen einzelnen Wert in einen AnyViz-Tag (aktueller Wert)."""
    url = f"{ANYVIZ_BASE_URL}/api/TagValue"
    headers = {
        "Content-Type": "application/json",
    }
    params = {"id": tag_id, "ApiKey": ANYVIZ_API_KEY}
    resp = requests.put(url, params=params, headers=headers,
                        data=json.dumps(value), timeout=30)
    resp.raise_for_status()


# ── State: letzter erfolgreicher Sync ─────────────────────────────────────────

def load_last_sync() -> datetime:
    """Lädt den Zeitstempel des letzten Syncs aus einer JSON-Datei."""
    path = Path(STATE_FILE)
    if path.exists():
        with open(path) as f:
            data = json.load(f)
        ts = datetime.fromisoformat(data["last_sync"])
        log.info("Letzter Sync: %s", ts.isoformat())
        return ts
    # Erster Lauf: letzten N Stunden nachladen
    fallback = datetime.now(timezone.utc) - timedelta(hours=SYNC_LOOKBACK_HOURS)
    log.info("Kein State gefunden – Fallback: %s", fallback.isoformat())
    return fallback


def save_last_sync(ts: datetime) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump({"last_sync": ts.isoformat()}, f)
    log.info("State gespeichert: %s", ts.isoformat())


# ── Hauptlogik ─────────────────────────────────────────────────────────────────

def run_sync() -> None:
    log.info("=== Starte Wattline → AnyViz Sync ===")

    # Zeitfenster bestimmen
    start = load_last_sync()
    end = datetime.now(timezone.utc)

    # Wattline Token holen
    token = get_wattline_token()

    errors = 0
    for measurement_id, tag_id in MEASUREMENT_TAG_MAP.items():
        log.info("Verarbeite Measurement %s → AnyViz Tag %s", measurement_id, tag_id)
        try:
            readings = get_readings(token, measurement_id, start, end)
            if not readings:
                log.info("  Keine neuen Messwerte.")
                continue

            # Den letzten (aktuellsten) Wert in AnyViz schreiben
            # Wattline liefert quantityValues pro Zeitstempel
            last_reading = readings[-1]
            quantity_values = last_reading.get("quantityValues", [])

            value_to_write = None
            for qv in quantity_values:
                # Numerischen Wert suchen (nicht Status-Strings wie "MEASURED")
                if isinstance(qv.get("value"), (int, float)):
                    value_to_write = qv["value"]
                    break

            if value_to_write is None:
                log.warning("  Kein numerischer Wert gefunden in letztem Reading.")
                continue

            log.info("  Schreibe Wert %.4f in Tag %s.", value_to_write, tag_id)
            write_to_anyviz(tag_id, value_to_write)

        except requests.HTTPError as e:
            log.error("  HTTP-Fehler: %s", e)
            errors += 1
        except Exception as e:
            log.error("  Unerwarteter Fehler: %s", e)
            errors += 1

    # State nur speichern wenn kein schwerwiegender Fehler
    if errors == 0:
        save_last_sync(end)
    else:
        log.warning("%d Fehler aufgetreten – State wird NICHT aktualisiert.", errors)

    log.info("=== Sync beendet ===")


if __name__ == "__main__":
    run_sync()
