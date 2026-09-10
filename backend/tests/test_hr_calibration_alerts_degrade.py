"""GET /api/hr/calibration-alerts must not 500 the HR dashboard (BUG-260910-C7B0)."""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from fastapi.testclient import TestClient

from backend.main import app
from backend.app.auth_deps import require_admin_or_hr


def test_calibration_alerts_missing_table_returns_empty():
    app.dependency_overrides[require_admin_or_hr] = lambda: {
        "id": "hr-1",
        "role": "HR",
        "company": "co-1",
    }
    try:
        client = TestClient(app)
        r = client.get("/api/hr/calibration-alerts")
        assert r.status_code == 200, r.text
        assert r.json() == []
    finally:
        app.dependency_overrides.pop(require_admin_or_hr, None)
