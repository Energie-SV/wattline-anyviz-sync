"""
Discovery-Skript: Zeigt alle verfügbaren
  - Wattline Messpunkte + Messreihen
  - AnyViz Tag-Definitionen

Hilfreich um das MEASUREMENT_TAG_MAP in config.py zu befüllen.
"""

import requests
from config import (
    WATTLINE_BASE_URL, WATTLINE_CLIENT_ID, WATTLINE_CLIENT_SECRET,
    WATTLINE_USERNAME, WATTLINE_PASSWORD,
    ANYVIZ_BASE_URL, ANYVIZ_API_KEY
)


def get_wattline_token():
    url = f"{WATTLINE_BASE_URL}/auth/realms/wattline/protocol/openid-connect/token"
    resp = requests.post(url, data={
        "grant_type": "password",
        "client_id": WATTLINE_CLIENT_ID,
        "client_secret": WATTLINE_CLIENT_SECRET,
        "username": WATTLINE_USERNAME,
        "password": WATTLINE_PASSWORD,
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def discover_wattline(token: str):
    headers = {"Authorization": f"Bearer {token}"}

    print("\n" + "="*60)
    print("WATTLINE – Messpunkte (shared-metering-points)")
    print("="*60)
    resp = requests.get(
        f"{WATTLINE_BASE_URL}/shared-metering-points",
        params={"include": "nodeAttributeKeys", "limit": 100},
        headers=headers, timeout=30
    )
    resp.raise_for_status()
    for mp in resp.json().get("data", []):
        print(f"  ID:         {mp['id']}")
        print(f"  BusinessID: {mp.get('businessId', '-')}")
        print()

        # Messreihen für diesen Messpunkt
        r2 = requests.get(
            f"{WATTLINE_BASE_URL}/measurements",
            params={
                "effectiveSharedMeteringPoint": mp["id"],
                "include": "measurementTypes,quantities,units",
                "limit": 100
            },
            headers=headers, timeout=30
        )
        if r2.ok:
            for m in r2.json().get("data", []):
                print(f"    Measurement-ID: {m['id']}")
                # OBIS-Code / Typ wenn vorhanden
                mt = m.get("measurementType", {})
                print(f"    Typ:            {mt.get('name', '-')}")
                print()


def discover_anyviz():
    print("\n" + "="*60)
    print("ANYVIZ – Tag-Definitionen")
    print("="*60)
    headers = {"Authorization": f"Bearer {ANYVIZ_API_KEY}"}
    resp = requests.get(f"{ANYVIZ_BASE_URL}/api/TagDefinition", headers=headers, timeout=30)
    resp.raise_for_status()
    for tag in resp.json():
        print(f"  Tag-ID:      {tag['Id']}")
        print(f"  Name:        {tag['DisplayName']}")
        print(f"  Einheit:     {tag.get('Unit', '-')}")
        print(f"  Datentyp:    {tag.get('DataType', '-')}")
        print()


if __name__ == "__main__":
    print("Starte Discovery...")
    token = get_wattline_token()
    discover_wattline(token)
    discover_anyviz()
    print("\nFertig. Trage die IDs in config.py → MEASUREMENT_TAG_MAP ein.")
