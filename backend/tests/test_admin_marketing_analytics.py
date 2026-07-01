import os
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.app import auth_deps


@pytest.fixture
def admin_client():
    app.dependency_overrides[auth_deps.get_current_user] = lambda: {
        "id": "admin-1", "email": "admin@relopass.com", "role": "ADMIN", "is_admin": True,
    }  # require_admin checks user["is_admin"], not the role field
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_funnel_shape(admin_client):
    r = admin_client.get("/api/admin/marketing-analytics/funnel")
    assert r.status_code == 200
    body = r.json()
    assert set(["landing_page_view", "landing_cta_click", "lead_captured"]).issubset(body["events"].keys())
    assert "cta_rate_pct" in body["rates"] and "capture_rate_pct" in body["rates"]
    assert isinstance(body["daily"], list)
