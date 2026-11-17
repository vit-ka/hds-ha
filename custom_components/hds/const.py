"""Constants for the Half Decent Scale integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "hds"
NAME: Final = "Half Decent Scale"
STORAGE_VERSION: Final = 1

# The scale powers off after 15 idle minutes, so a 5-minute probe sees every session at least twice.
SCAN_INTERVAL: Final = timedelta(minutes=5)
# A connected WebSocket client restarts the scale's auto-off countdown, so `status` is asked once
# per wake, and again only this often while the scale stays awake on battery (docs/adr/0001).
RECHECK_INTERVAL: Final = timedelta(minutes=30)
# An asleep scale never answers; don't wait long for it.
PROBE_TIMEOUT: Final = 5
STATUS_TIMEOUT: Final = 10
RELEASE_INTERVAL: Final = timedelta(hours=6)
RELEASE_TIMEOUT: Final = 30
# The same signed catalog the scale's own "WiFi Update" menu reads.
MANIFEST_URL: Final = "https://github.com/decentespresso/openscale/releases/latest/download/manifest.json"
RELEASE_URL: Final = "https://github.com/decentespresso/openscale/releases/tag/v{version}"
