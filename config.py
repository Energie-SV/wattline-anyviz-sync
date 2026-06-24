"""
Konfiguration für die Wattline → AnyViz Synchronisation.

Zugangsdaten werden aus Umgebungsvariablen gelesen –
lokal aus einer .env-Datei, in GitHub Actions aus Secrets.
"""

import os

# ── Wattline ───────────────────────────────────────────────────────────────────
WATTLINE_BASE_URL      = os.environ.get("WATTLINE_BASE_URL", "https://energiedatenportal.wattline.com")
WATTLINE_CLIENT_ID     = "api"
WATTLINE_CLIENT_SECRET = os.environ.get("WATTLINE_CLIENT_SECRET", "")
WATTLINE_USERNAME      = os.environ.get("WATTLINE_USERNAME", "")
WATTLINE_PASSWORD      = os.environ.get("WATTLINE_PASSWORD", "")

# Welche Messgröße übertragen? z.B. "energy_sum", "power"
QUANTITY_KEY = "energy_sum"

# ── AnyViz ────────────────────────────────────────────────────────────────────
ANYVIZ_BASE_URL = os.environ.get("ANYVIZ_BASE_URL", "https://portal.anyviz.io/project/DEIN-PROJEKT")
ANYVIZ_API_KEY  = os.environ.get("ANYVIZ_API_KEY", "")

# ── Mapping: Wattline Measurement-ID → AnyViz Tag-ID ─────────────────────────
# Erst mit discover.py die IDs ermitteln, dann hier eintragen:
MEASUREMENT_TAG_MAP: dict[str, int] = {
    # "019104a0-9bc5-7004-8fc0-7d9eac2fbfb9": 42,
}

# ── Sync-Verhalten ─────────────────────────────────────────────────────────────
SYNC_LOOKBACK_HOURS = 24
STATE_FILE = "sync_state.json"
