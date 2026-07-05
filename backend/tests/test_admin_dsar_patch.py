"""DSAR erasure-request lifecycle PATCH (A4) — validation guard.

The happy-path state transition needs the prod `erasure_requests` table (raw SQL, not an
ORM model, so absent from the SQLite test DB); this covers the DB-free validation branch
and the action→status contract."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth_deps import require_admin
from backend.app.routers import admin_dsar


def _client():
    app = FastAPI()
    app.include_router(admin_dsar.router)
    app.dependency_overrides[require_admin] = lambda: {"id": "admin-1", "role": "ADMIN"}
    return TestClient(app)


def test_patch_rejects_unknown_action():
    # Unknown action is rejected before any DB access.
    resp = _client().patch("/api/admin/erasure-requests/req-1", json={"action": "nuke"})
    assert resp.status_code == 400


def test_action_status_contract():
    assert admin_dsar._ACTION_STATUS == {
        "approve": "approved",
        "reject": "rejected",
        "complete": "completed",
    }
