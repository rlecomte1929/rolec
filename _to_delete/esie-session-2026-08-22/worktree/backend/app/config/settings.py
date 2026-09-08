"""
VEN-02 — Runtime environment settings for the vendor-discovery system.

Central, documented home for the discovery runtime env vars. Every value is read via
``os.getenv`` with a safe default, so this module imports cleanly with **zero env vars set**
(no crash, no side effects).

NOTE on the hot path: the live fetchers in ``backend/app/services/maps_discovery.py`` read
``os.getenv(...)`` at CALL time (so tests can monkeypatch the env per-case and so an operator
can flip a key without a redeploy). The module-level snapshots below are the documented
keys/defaults for discoverability and for callers that only need the configured value at
import time — they are NOT the source the hot path reads.

Discovery is OFF by default (``DISCOVERY_PROVIDER='disabled'``) → $0 until deliberately enabled.
"""
import os

# Google Places Text Search (v1) API key. Unset → the google_places provider is "not configured".
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

# Apify API token — the alternative discovery provider. Unset → apify is "not configured".
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")

# Which provider the discovery system uses: "google_places" | "apify" | "disabled" (default).
DISCOVERY_PROVIDER = (os.getenv("DISCOVERY_PROVIDER") or "disabled").strip().lower()
