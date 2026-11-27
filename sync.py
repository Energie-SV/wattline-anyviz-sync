"""
Wattline → GitHub Pages JSON-Synchronisation.
Schlüssel in der data.json sind sprechende Namen (nicht die UUIDs).
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


WATTLINE_BASE_URL = os.environ.get(
    "WATTLINE_BASE_URL", "https://energiedatenportal.wattline.com"
)
WATTLINE_CLIENT_ID = "api"
WATTLINE_CLIENT_SECRET = os.environ.get("WATTLINE_CLIENT_SECRET", "")
WATTLINE_USERNAME = os.environ.get("WATTLINE_USERNAME", "")
WATTLINE_PASSWORD = os.environ.get("WATTLINE_PASSWORD", "")

# Name in AnyViz → Wattline-Messpunkt-ID
MEASUREMENTS = {
    "MAR32": "0195ff97-9957-7676-a5b9-5f09089540cd",
    "KSH": "019545df-597e-7606-9aa7-92db14323b14",
    "Maternushaus_Bezug": "0195ff74-cf60-7342-bce2-8e913a61e6ba",
    "Maternushaus_Einspeisung": "0195ff9c-2d10-7141-887a-df161bea1364",
}

QUANTITY_KEY = "energy_sum"
OUTPUT_FILE = Path("docs/data.json")
LOOKBACK_HOURS = 168  # 7 Tage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def get_wattline_token() -> str:
    url = (
        f"{WATTLINE_BASE_URL}/auth/realms/wattline"
        "/protocol/openid-connect/token"
    )
    resp = requests.post(
        url,
        data={
            "grant_type": "password",
            "client_id": WATTLINE_CLIENT_ID,
            "client_secret": WATTLINE_CLIENT_SECRET,
            "username": WATTLINE_USERNAME,
            "password": WATTLINE_PASSWORD,
        },
        timeout=30,
    )
    resp.raise_for_status()
    log.info("Wattline-Token erhalten.")
    return resp.json()["access_token"]


def get_readings(
    token: str, measurement_id: str, start: datetime, end: datetime
) -> list:
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
        url = body.get("links", {}).get("next")
        params = {}

    return all_readings


def extract_value(reading: dict):
    for quantity_value in reading.get("quantityValues", []):
        value = quantity_value.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value, quantity_value.get("unit", "")
    return None, None


def parse_timestamp(timestamp):
    if not isinstance(timestamp, str) or not timestamp:
        return None

    if timestamp.endswith("Z"):
        timestamp = timestamp[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError:
        return None

    # Zeitstempel ohne Zeitzonenangabe als UTC behandeln.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def run_sync():
    log.info("=== Starte Wattline → GitHub Pages Sync ===")

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=LOOKBACK_HOURS)
    log.info("Abfragezeitraum: %s bis %s", start.isoformat(), end.isoformat())

    token = get_wattline_token()
    results = {}
    timeseries = {}

    for name, measurement_id in MEASUREMENTS.items():
        log.info("Verarbeite %s (%s)", name, measurement_id)

        try:
            readings = get_readings(token, measurement_id, start, end)
            log.info("  %d Messwerte von der API erhalten.", len(readings))

            if not readings:
                log.info("  Keine Messwerte.")
                continue

            points = []
            invalid_timestamps = 0

            for reading in readings:
                value, unit = extract_value(reading)
                if value is None:
                    continue

                timestamp = reading.get("start") or reading.get("time")
                parsed = parse_timestamp(timestamp)
                if parsed is None:
                    invalid_timestamps += 1
                    continue

                points.append((parsed, timestamp, value, unit))

            if invalid_timestamps:
                log.warning(
                    "  %d Werte ohne gültigen Zeitstempel übersprungen.",
                    invalid_timestamps,
                )

            if not points:
                log.warning("  Keine gültigen Zeitreihenwerte.")
                continue

            points.sort(key=lambda point: point[0])

            _, timestamp, value, unit = points[-1]
            results[name] = {"value": value, "unit": unit, "time": timestamp}
            log.info("  Neuester Wert: %s %s @ %s", value, unit, timestamp)

            timeseries[name] = [
                {"time": timestamp, "value": value}
                for _, timestamp, value, _ in points
            ]
            log.info("  %d Zeitreihenwerte gespeichert.", len(points))

        except Exception as exc:
            log.error("  Fehler bei %s: %s", name, exc)

    output = {
        "updated": end.isoformat(),
        "latest": results,
        "timeseries": timeseries,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2)

    log.info("Gespeichert: %s", OUTPUT_FILE)
    log.info("=== Sync beendet ===")


if __name__ == "__main__":
    run_sync()
