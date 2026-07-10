"""
Wattline → GitHub Pages JSON Synchronisation
"""

import requests
import logging
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os

WATTLINE_BASE_URL      = os.environ.get("WATTLINE_BASE_URL", "https://energiedatenportal.wattline.com")
WATTLINE_CLIENT_ID     = "api"
WATTLINE_CLIENT_SECRET = os.environ.get("WATTLINE_CLIENT_SECRET", "")
WATTLINE_USERNAME      = os.environ.get("WATTLINE_USERNAME", "")
WATTLINE_PASSWORD      = os.environ.get("WATTLINE_PASSWORD", "")

MEASUREMENT_IDS = [
    "0195ff97-9957-7676-a5b9-5f09089540cd",
]

QUANTITY_KEY    = "energy_sum"
OUTPUT_FILE     = "docs/data.json"
LOOKBACK_HOURS  = 168  # 7 Tage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def get_wattline_token() -> str:
    url = f"{WATTLINE_BASE_URL}/auth/realms/wattline/protocol/openid-connect/token"
    resp = requests.post(url, data={
        "grant_type": "password",
        "client_id": WATTLINE_CLIENT_ID,
        "client_secret": WATTLINE_CLIENT_SECRET,
        "username": WATTLINE_USERNAME,
        "password": WATTLINE_PASSWORD,
    }, timeout=30)
    resp.raise_for_status()
    log.info("Wattline Token erhalten.")
    return resp.json()["access_token"]


def get_readings(token: str, measurement_id: str, start: datetime, end: datetime) -> list:
    url = f"{WATTLINE_BASE_URL}/measurements/{measurement_id}/readings"
    params = {
        "quantity": QUANTITY_KEY,
        "time(gte)": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "time(lt)":  end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 1000,
    }
    headers = {"Authorization": f"Bearer {token}"}
    all_readings = []
    while url:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        body = resp.json()
        all_readings.extend(body.get("data", []))
        url = body.get("links", {}).get("next")
        params = {}
    return all_readings


def extract_value(reading: dict):
    for qv in reading.get("quantityValues", []):
        if isinstance(qv.get("value"), (int, float)):
            return qv["value"], qv.get("unit", "")
    return None, None


def run_sync():
    log.info("=== Starte Wattline → GitHub Pages Sync ===")

    end   = datetime.now(timezone.utc)
    start = end - timedelta(hours=LOOKBACK_HOURS)

    token = get_wattline_token()

    results = {}
    timeseries = {}

    for mid in MEASUREMENT_IDS:
        log.info("Verarbeite Measurement %s", mid)
        try:
            readings = get_readings(token, mid, start, end)
            log.info("  %d Readings erhalten.", len(readings))

            if not readings:
                log.info("  Keine Messwerte.")
                continue

            # Erstes Reading loggen um Struktur zu sehen
            log.info("  Beispiel-Reading: %s", json.dumps(readings[0]))

            # Letzter Wert
            last = readings[-1]
            value, unit = extract_value(last)

            # Zeitstempel – Wattline verwendet "time" auf oberster Ebene
            timestamp = last.get("time") or last.get("timestamp") or last.get("date") or ""
            log.info("  Letzter Wert: %s %s @ %s", value, unit, timestamp)

            if value is not None:
                results[mid] = {
                    "value": value,
                    "unit": unit,
                    "time": timestamp,
                }

            # Zeitreihe
            series = []
            for r in readings:
                v, u = extract_value(r)
                ts = r.get("time") or r.get("timestamp") or r.get("date") or ""
                if v is not None:
                    series.append({"time": ts, "value": v})
            timeseries[mid] = series
            log.info("  %d Zeitreihenwerte gespeichert.", len(series))

        except Exception as e:
            log.error("  Fehler: %s", e)

    output = {
        "updated": end.isoformat(),
        "zaehler": "50206503647",
        "latest": results,
        "timeseries": timeseries,
    }

    Path("docs").mkdir(exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    log.info("Gespeichert: %s", OUTPUT_FILE)
    log.info("=== Sync beendet ===")


if __name__ == "__main__":
    run_sync()
