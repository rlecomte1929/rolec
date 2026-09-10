"""HR can remove a relocation case (DELETE /api/hr/assignments/{id}).

BUG-260910-1E93: GET /api/hr/assignments/{id} already resolves assignment PK *or*
relocation-case UUID. DELETE only looked up the assignment PK, then passed the URL
id into delete_assignment — so a case-id (or a mixed dashboard/command-center id)
404'd and HR could not remove the case.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi.testclient import TestClient

from backend.main import app, get_current_user
import backend.main as main_mod

_HR = {"id": "hr-1", "role": "HR", "company": "co-1", "is_admin": False, "auth_uuid": None}


class _Db:
    def __init__(self):
        self.assignment = {
            "id": "asg-1",
            "case_id": "case-1",
            "canonical_case_id": "case-1",
            "hr_user_id": "hr-1",
        }
        self.deleted = []

    def get_assignment_by_id(self, aid, request_id=None, include_archived=False):
        return dict(self.assignment) if aid == "asg-1" else None

    def get_assignment_by_case_id(self, cid, request_id=None):
        if cid in ("asg-1", "case-1"):
            return dict(self.assignment)
        return None

    def delete_assignment(self, assignment_id, *, actor_id=None):
        self.deleted.append((assignment_id, actor_id))
        return assignment_id == "asg-1"


@pytest.fixture()
def fake_db(monkeypatch):
    d = _Db()
    monkeypatch.setattr(main_mod.db, "get_assignment_by_id", d.get_assignment_by_id)
    monkeypatch.setattr(main_mod.db, "get_assignment_by_case_id", d.get_assignment_by_case_id)
    monkeypatch.setattr(main_mod.db, "delete_assignment", d.delete_assignment)
    monkeypatch.setattr(main_mod, "_hr_can_access_assignment", lambda assignment, user: True)
    monkeypatch.setattr(main_mod, "_deny_if_impersonating", lambda user: None)
    monkeypatch.setattr(main_mod, "_effective_user", lambda user, role=None: user)
    return d


@pytest.fixture()
def client(fake_db):
    app.dependency_overrides[get_current_user] = lambda: _HR
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def test_delete_by_assignment_id(client, fake_db):
    r = client.delete("/api/hr/assignments/asg-1")
    assert r.status_code == 200
    assert r.json()["deleted"] == "asg-1"
    assert fake_db.deleted == [("asg-1", "hr-1")]


def test_delete_by_relocation_case_id(client, fake_db):
    """The id HR copied from a case URL must still soft-delete the assignment."""
    r = client.delete("/api/hr/assignments/case-1")
    assert r.status_code == 200, r.text
    assert fake_db.deleted == [("asg-1", "hr-1")]
    assert r.json()["deleted"] == "asg-1"


def test_delete_unknown_is_404(client, fake_db):
    r = client.delete("/api/hr/assignments/nope")
    assert r.status_code == 404
    assert fake_db.deleted == []
