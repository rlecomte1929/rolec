"""Autopilot Phase 2 — the funnel-event endpoint fired by the autofix-validate workflow.

(The edge-function + workflow changes — AUTOPILOT_FIX_ENABLED gate, open-PR dedup, merge cap,
batch-merge flag — are Deno/YAML and validated statically; only the backend endpoint is unit-tested.)
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi.testclient import TestClient

from backend.app.services import autopilot_events as ev


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    from backend.main import app
    return TestClient(app)


def test_route_registered():
    from backend.main import app
    assert "/api/crons/autopilot-event" in {r.path for r in app.routes}


def test_requires_secret(client):
    r = client.post("/api/crons/autopilot-event", json={"event_type": ev.MERGED})
    assert r.status_code == 401


def test_rejects_unknown_event(client):
    r = client.post("/api/crons/autopilot-event",
                    headers={"Authorization": "Bearer s3cret"},
                    json={"event_type": "autopilot.not_a_real_event"})
    assert r.status_code == 422


def test_records_known_event(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(ev, "emit",
                        lambda et, **k: seen.update(event_type=et, entity_id=k.get("entity_id")))
    r = client.post("/api/crons/autopilot-event",
                    headers={"Authorization": "Bearer s3cret"},
                    json={"event_type": ev.MERGED, "entity_id": "AIQ-1"})
    assert r.status_code == 200, r.text
    assert r.json()["recorded"] is True
    assert seen == {"event_type": ev.MERGED, "entity_id": "AIQ-1"}
