import os
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.auth_deps import get_current_user
import backend.app.routers.product_track as product_track
import backend.app.routers.admin_product_metrics as admin_product_metrics

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _as_user(user):
    app.dependency_overrides[get_current_user] = lambda: user


# ── POST /api/track (authenticated product-event sink) ───────────────────────

def test_track_rejects_unknown_event():
    _as_user({"id": "u1", "is_admin": False})
    r = client.post("/api/track", json={"event": "definitely_not_allowed"})
    assert r.status_code == 400


def test_track_persists_only_allowlisted_pii_free_keys(monkeypatch):
    _as_user({"id": "u1", "is_admin": False})
    captured = {}

    def fake_emit(event_name, **kw):
        captured["event"] = event_name
        captured["kw"] = kw

    monkeypatch.setattr(product_track, "emit_event", fake_emit)

    r = client.post("/api/track", json={
        "event": "wizard_step_completed",
        "properties": {
            "case_id": "c1", "step_number": 2, "step_name": "about_you",
            "duration_seconds": 12,
            # These must be dropped — not in the allow-list:
            "full_name": "Jane Doe", "email": "jane@example.com", "note": "secret",
        },
    })
    assert r.status_code == 200
    assert captured["event"] == "wizard_step_completed"
    extra = captured["kw"].get("extra") or {}
    assert extra.get("step_name") == "about_you"
    assert extra.get("duration_seconds") == 12
    # PII / non-allowlisted keys never reach the sink:
    assert "full_name" not in extra and "email" not in extra and "note" not in extra
    # case_id is routed to its own param, not left in extra:
    assert "case_id" not in extra
    assert captured["kw"].get("case_id") == "c1"


# ── GET /api/admin/product-metrics (admin read) ──────────────────────────────

def test_product_metrics_aggregates_and_rates(monkeypatch):
    _as_user({"id": "admin1", "is_admin": True})
    monkeypatch.setattr(
        admin_product_metrics.db, "count_analytics_events_by_name",
        lambda since: {
            "wizard_step_completed": 20, "wizard_completed": 5,
            "estimate_review_opened": 10, "exception_request_submitted": 4,
            "exception_request_decided": 2, "case_created": 8,
        },
    )
    monkeypatch.setattr(admin_product_metrics.db, "list_analytics_events", lambda **kw: [])

    r = client.get("/api/admin/product-metrics?days=30")
    assert r.status_code == 200
    body = r.json()
    assert body["events"]["wizard_completed"] == 5
    assert body["events"]["case_created"] == 8
    # wizard_completed / wizard_step_completed = 5/20 = 25%
    assert body["rates"]["wizard_completion_pct"] == 25.0
    # exception_request_submitted / estimate_review_opened = 4/10 = 40%
    assert body["rates"]["exception_request_pct"] == 40.0


def test_product_metrics_requires_admin():
    _as_user({"id": "u1", "is_admin": False})
    r = client.get("/api/admin/product-metrics")
    assert r.status_code == 403
