"""/health exposes the deployed git commit (from Render's RENDER_GIT_COMMIT) so the
autopilot canary can confirm a merged fix is live before validating it."""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient

from backend.main import app


def test_health_exposes_commit(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "deadbeef1234")
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json()["commit"] == "deadbeef1234"


def test_health_commit_defaults_unknown(monkeypatch):
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    r = TestClient(app).get("/health")
    assert r.json()["commit"] == "unknown"
