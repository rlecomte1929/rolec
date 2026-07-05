"""
VEN-02 (AIQ-1397) — the discovery settings module imports with zero env vars set.
"""
from __future__ import annotations

import importlib
import os
import sys


def _reload_settings():
    sys.modules.pop("backend.app.config.settings", None)
    return importlib.import_module("backend.app.config.settings")


def test_import_ok_and_key_none_when_unset(monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    monkeypatch.delenv("DISCOVERY_PROVIDER", raising=False)
    settings = _reload_settings()
    # VC: importing GOOGLE_PLACES_API_KEY does not raise; unset → None.
    assert settings.GOOGLE_PLACES_API_KEY is None
    assert settings.APIFY_API_TOKEN is None
    # Discovery is off by default → $0.
    assert settings.DISCOVERY_PROVIDER == "disabled"


def test_reads_env_when_set(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key")
    monkeypatch.setenv("DISCOVERY_PROVIDER", "Google_Places")
    settings = _reload_settings()
    assert settings.GOOGLE_PLACES_API_KEY == "test-key"
    assert settings.DISCOVERY_PROVIDER == "google_places"  # normalized (lower/strip)


def test_import_never_crashes_on_garbage(monkeypatch):
    # No int() parsing at module level, so any string is import-safe.
    monkeypatch.setenv("DISCOVERY_PROVIDER", "  WEIRD  ")
    settings = _reload_settings()
    assert settings.DISCOVERY_PROVIDER == "weird"


def teardown_module(_module):
    # Leave a clean import for the rest of the suite.
    sys.modules.pop("backend.app.config.settings", None)
    os.environ.pop("GOOGLE_PLACES_API_KEY", None)
    os.environ.pop("APIFY_API_TOKEN", None)
    os.environ.pop("DISCOVERY_PROVIDER", None)
