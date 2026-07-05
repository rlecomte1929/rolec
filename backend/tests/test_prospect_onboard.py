"""Track B — prospect onboarding endpoint input-validation guards.

The happy path creates a company + HR profile + Supabase invite across the legacy DB
layer; those paths are exercised by existing company/person tests. Here we lock the
request-validation branches that run BEFORE any DB write (so they're deterministic and
DB-independent), plus route registration."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.main import app as prod_app, require_admin, onboard_prospect, ProspectOnboardRequest


def _client():
    app = FastAPI()
    app.post("/api/admin/prospects/{prospect_id}/onboard")(onboard_prospect)
    app.dependency_overrides[require_admin] = lambda: {"id": "admin-1", "role": "ADMIN"}
    return TestClient(app)


def test_missing_hr_email_is_422():
    # hr_email is required by the pydantic model.
    resp = _client().post("/api/admin/prospects/p1/onboard", json={})
    assert resp.status_code == 422


def test_invalid_hr_email_is_400():
    # Validation (no "@") runs before any DB access.
    resp = _client().post("/api/admin/prospects/p1/onboard", json={"hr_email": "not-an-email"})
    assert resp.status_code == 400


def test_defaults_send_welcome_true():
    body = ProspectOnboardRequest(hr_email="hr@acme.com")
    assert body.send_welcome is True


def test_route_registered_on_prod_app():
    paths = {(r.path, "POST") for r in prod_app.routes if getattr(r, "path", "") == "/api/admin/prospects/{prospect_id}/onboard" and "POST" in (getattr(r, "methods", None) or set())}
    assert paths, "onboard route must be registered on the prod app"
