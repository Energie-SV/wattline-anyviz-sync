"""
Discovery-Skript: Zeigt verfügbare Quantities für Zähler 50206503647
"""

import requests
import os
from datetime import datetime, timedelta, timezone

WATTLINE_BASE_URL      = os.environ.get("WATTLINE_BASE_URL", "https://energiedatenportal.wattline.com")
WATTLINE_CLIENT_ID     = "api"
WATTLINE_CLIENT_SECRET = os.environ.get("WATTLINE_CLIENT_SECRET", "")
WATTLINE_USERNAME      = os.environ.get("WATTLINE_USERNAME", "")
WATTLINE_PASSWORD      = os.environ.get("WATTLINE_PASSWORD", "")

MEASUREMENT_IDS = [
    "0195ff97-9957-7676-a5b9-5f09089540cd",
    "0195ff97-9957-7676-a5b9-5f0924b2dd3d",
    "0195ff97-9957-7676-a5b9-5f0a800d37dc",
]

def get_token():
    resp = requests.post(
        f"{WATTLINE_BASE_URL}/auth/realms/wattline/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": WATTLINE_CLIENT_ID,
            "client_secret": WATTLINE_CLIENT_SECRET,
            "username": WATTLINE_USERNAME,
            "password": WATTLINE_PASSWORD,
        }, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]

if __name__ == "__main__":
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)

    for mid in MEASUREMENT_IDS:
        print(f"\nMeasurement: {mid}")
        # Measurement-Details abrufen
        r = requests.get(
            f"{WATTLINE_BASE_URL}/measurements/{mid}",
            params={"include": "measurementTypes,quantities,units"},
            headers=headers, timeout=30
        )
        if r.ok:
            data = r.json().get("data", {})
            print(f"  Typ: {data.get('measurementType', {}).get('name', '-')}")
            for q in data.get("quantities", []):
                print(f"  Quantity: {q.get('key')} / {q.get('name')}")

        # Readings ohne quantity-Filter testen
        for qty in ["energy_sum", "power", "reactive_energy_sum", "energy_delivered", "energy_received"]:
            r2 = requests.get(
                f"{WATTLINE_BASE_URL}/measurements/{mid}/readings",
                params={
                    "quantity": qty,
                    "time(gte)": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "time(lt)": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "limit": 1,
                },
                headers=headers, timeout=30
            )
            if r2.ok and r2.json().get("data"):
                val = r2.json()["data"][0].get("quantityValues", [])
                print(f"  ✓ quantity={qty} → {val}")
            elif r2.status_code == 400:
                print(f"  ✗ quantity={qty} → nicht verfügbar")
            else:
                print(f"  ? quantity={qty} → {r2.status_code}")
