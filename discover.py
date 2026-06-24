"""
Discovery-Skript: Zeigt alle verfügbaren
  - Wattline Messpunkte + Messreihen
  - AnyViz Tag-Definitionen
"""

import requests
import os

WATTLINE_BASE_URL      = os.environ.get("WATTLINE_BASE_URL", "https://energiedatenportal.wattline.com")
WATTLINE_CLIENT_ID     = "api"
WATTLINE_CLIENT_SECRET = os.environ.get("WATTLINE_CLIENT_SECRET", "")
WATTLINE_USERNAME      = os.environ.get("WATTLINE_USERNAME", "")
WATTLINE_PASSWORD      = os.environ.get("WATTLINE_PASSWORD", "")
ANYVIZ_BASE_URL        = os.environ.get("ANYVIZ_BASE_URL", "")
ANYVIZ_API_KEY         = os.environ.get("ANYVIZ_API_KEY", "")


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
    print("WATTLINE – Messpunkte")
    print("="*60)
    resp = requests.get(
        f"{WATTLINE_BASE_URL}/shared-metering-points",
        params={"limit": 100},
        headers=headers, timeout=30
    )
    resp.raise_for_status()
    for mp in resp.json().get("data", []):
        print(f"  Messpunkt-ID: {mp['id']}")
        print(f"  BusinessID:   {mp.get('businessId', '-')}")

        r2 = requests.get(
            f"{WATTLINE_BASE_URL}/measurements",
            params={"effectiveSharedMeteringPoint": mp["id"], "limit": 100},
            headers=headers, timeout=30
        )
        if r2.ok:
            for m in r2.json().get("data", []):
                print(f"    → Measurement-ID: {m['id']}")
        print()


def discover_anyviz():
    print("\n" + "="*60)
    print("ANYVIZ – Tag-Definitionen")
    print("="*60)
    
    # ApiKey als Query-Parameter (laut AnyViz Dokumentation)
    url = f"{ANYVIZ_BASE_URL}/api/TagDefinition"
    params = {"ApiKey": ANYVIZ_API_KEY}
    
    print(f"  Anfrage an: {url}")
    resp = requests.get(url, params=params, timeout=30)
    print(f"  HTTP Status: {resp.status_code}")
    
    if not resp.ok:
        print(f"  Fehler-Antwort: {resp.text[:500]}")
        resp.raise_for_status()
    
    tags = resp.json()
    if not tags:
        print("  Keine Tags gefunden.")
        return
    for tag in tags:
        print(f"  Tag-ID:   {tag['Id']}")
        print(f"  Name:     {tag['DisplayName']}")
        print(f"  Einheit:  {tag.get('Unit', '-')}")
        print()


if __name__ == "__main__":
    print("Starte Discovery...")
    token = get_wattline_token()
    discover_wattline(token)
    discover_anyviz()
    print("\nFertig.")
