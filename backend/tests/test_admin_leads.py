import os
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app import auth_deps
from backend.app.db import Base, SessionLocal, engine
from backend.app.models import Lead

# The SQLite test harness may not have run init_db(); ensure ORM tables exist.
Base.metadata.create_all(bind=engine)


@pytest.fixture
def admin_client():
    app.dependency_overrides[auth_deps.get_current_user] = lambda: {
        "id": "admin-1", "email": "admin@relopass.com", "role": "ADMIN", "is_admin": True,
    }
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_lead(**kw):
    s = SessionLocal()
    lead = Lead(id=str(uuid.uuid4()), email=kw.get("email", "a@b.com"),
                company_domain=kw.get("company_domain"), status=kw.get("status", "new"),
                source="marketing_site", tags=[])
    s.add(lead); s.commit(); lid = lead.id; s.close()
    return lid


def test_list_leads_returns_seeded(admin_client):
    lid = _seed_lead(email="lister@acme.com")
    r = admin_client.get("/api/admin/leads")
    assert r.status_code == 200
    assert any(row["id"] == lid for row in r.json()["leads"])


def test_patch_lead_status(admin_client):
    lid = _seed_lead(email="patch@acme.com")
    r = admin_client.patch(f"/api/admin/leads/{lid}", json={"status": "qualified"})
    assert r.status_code == 200
    assert r.json()["status"] == "qualified"


def test_patch_rejects_bad_status(admin_client):
    lid = _seed_lead(email="bad@acme.com")
    r = admin_client.patch(f"/api/admin/leads/{lid}", json={"status": "banana"})
    assert r.status_code == 422 or r.status_code == 400


def test_stats_shape(admin_client):
    _seed_lead(email="stat@acme.com")
    r = admin_client.get("/api/admin/leads/stats")
    assert r.status_code == 200
    body = r.json()
    assert "total" in body and "new_this_week" in body and "by_status" in body


def test_list_leads_and_prospects_ok_when_is_test_column_missing(admin_client):
    """PR-1: readers must 200 if 20261146000000 has not been applied yet."""
    from sqlalchemy import text

    s = SessionLocal()
    try:
        s.execute(text("ALTER TABLE leads DROP COLUMN is_test"))
        s.execute(text("ALTER TABLE prospect_candidates DROP COLUMN is_test"))
        s.commit()
    except Exception as exc:  # pragma: no cover — dialect without DROP COLUMN
        s.rollback()
        pytest.skip(f"cannot drop is_test for presence-guard test: {exc}")
    finally:
        s.close()

    try:
        r_leads = admin_client.get("/api/admin/leads")
        r_prospects = admin_client.get("/api/admin/prospects")
        assert r_leads.status_code == 200, r_leads.text
        assert r_prospects.status_code == 200, r_prospects.text
    finally:
        s = SessionLocal()
        try:
            s.execute(text("ALTER TABLE leads ADD COLUMN is_test BOOLEAN NOT NULL DEFAULT 0"))
        except Exception:
            s.rollback()
        try:
            s.execute(text(
                "ALTER TABLE prospect_candidates ADD COLUMN is_test BOOLEAN NOT NULL DEFAULT 0"
            ))
        except Exception:
            s.rollback()
        s.commit()
        s.close()
