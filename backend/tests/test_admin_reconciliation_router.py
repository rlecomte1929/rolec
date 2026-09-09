"""Characterisation tests for /api/admin/reconciliation (WS1 Task 1.5).

Happy-path calls monkeypatch ``backend.database.db`` methods; non-admin
callers must 403. Auth override starts on the inline ``backend.main``
dependency and is repointed to ``backend.app.auth_deps`` after extraction.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.database import db  # noqa: E402
from backend.main import app  # noqa: E402
from backend.main import get_current_user  # noqa: E402

_PREFIX = "/api/admin/reconciliation"
_ADMIN = {"id": "admin-recon-1", "email": "admin@example.com", "role": "ADMIN", "is_admin": True}
_NON_ADMIN = {"id": "hr-recon-1", "email": "hr@example.com", "role": "HR", "is_admin": False}

_ENDPOINTS = (
    ("GET", f"{_PREFIX}/report", None),
    ("POST", f"{_PREFIX}/backfill-test-company", None),
    (
        "POST",
        f"{_PREFIX}/link-person-company",
        {"profile_id": "p1", "company_id": "c1"},
    ),
    (
        "POST",
        f"{_PREFIX}/link-assignment-company",
        {"assignment_id": "a1", "company_id": "c1", "reason": "repair orphan"},
    ),
    (
        "POST",
        f"{_PREFIX}/link-assignment-person",
        {"assignment_id": "a1", "profile_id": "p1"},
    ),
    (
        "POST",
        f"{_PREFIX}/link-policy-company",
        {"policy_id": "pol1", "company_id": "c1"},
    ),
    ("POST", f"{_PREFIX}/rebuild-test-company-graph", None),
)


class _CountResult:
    def __init__(self, n: int = 0) -> None:
        self._mapping = {"n": n}

    def fetchone(self) -> "_CountResult":
        return self


class _FakeConn:
    def execute(self, *_a, **_k) -> _CountResult:
        return _CountResult(0)

    def __enter__(self) -> "_FakeConn":
        return self

    def __exit__(self, *_a) -> bool:
        return False


class _FakeEngine:
    def connect(self) -> _FakeConn:
        return _FakeConn()


def _patch_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "get_reconciliation_report", lambda: {"companies": [], "ok": True})
    monkeypatch.setattr(db, "log_audit", lambda *_a, **_k: None)
    monkeypatch.setattr(
        db,
        "run_admin_reconciliation_backfill_test_company",
        lambda _name: {"summary": {"linked": 1}, "ok": True},
    )
    monkeypatch.setattr(db, "get_profile_record", lambda _pid: {"id": _pid})
    monkeypatch.setattr(db, "get_company", lambda _cid: {"id": _cid})
    monkeypatch.setattr(db, "admin_reassign_employee_company", lambda *_a, **_k: None)
    monkeypatch.setattr(db, "get_assignment_by_id", lambda _aid: {"id": _aid})
    monkeypatch.setattr(db, "admin_fix_assignment_company_linkage", lambda *_a, **_k: None)
    monkeypatch.setattr(db, "attach_employee_to_assignment", lambda *_a, **_k: None)
    monkeypatch.setattr(db, "get_company_policy", lambda _pid: {"id": _pid})
    monkeypatch.setattr(db, "admin_link_policy_company", lambda *_a, **_k: None)
    monkeypatch.setattr(db, "TEST_COMPANY_FIXED_ID", "test-company-id", raising=False)
    monkeypatch.setattr(db, "engine", _FakeEngine())
    monkeypatch.setattr(db, "rebuild_test_company_graph", lambda: {"reassigned": 2})


def _request(client: TestClient, method: str, path: str, body: dict | None):
    if method == "GET":
        return client.get(path)
    return client.post(path, json=body)


@pytest.fixture
def admin_client(monkeypatch: pytest.MonkeyPatch):
    _patch_db(monkeypatch)
    app.dependency_overrides[get_current_user] = lambda: dict(_ADMIN)
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def non_admin_client(monkeypatch: pytest.MonkeyPatch):
    _patch_db(monkeypatch)
    app.dependency_overrides[get_current_user] = lambda: dict(_NON_ADMIN)
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.mark.parametrize("method,path,body", _ENDPOINTS)
def test_admin_happy_path(admin_client: TestClient, method: str, path: str, body: dict | None):
    response = _request(admin_client, method, path, body)
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    if path.endswith("/report"):
        assert payload["ok"] is True
        assert payload["companies"] == []
    elif path.endswith("/backfill-test-company"):
        assert payload["ok"] is True
        assert payload["summary"] == {"linked": 1}
    elif path.endswith("/rebuild-test-company-graph"):
        assert payload["ok"] is True
        assert payload["summary"]["reassigned"] == 2
        assert payload["before"]["profiles"] == 0
        assert payload["after"]["profiles"] == 0
    else:
        assert payload == {"ok": True}


@pytest.mark.parametrize("method,path,body", _ENDPOINTS)
def test_non_admin_forbidden(non_admin_client: TestClient, method: str, path: str, body: dict | None):
    response = _request(non_admin_client, method, path, body)
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin only"
