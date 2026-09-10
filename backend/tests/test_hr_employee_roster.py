"""HR roster: remove and edit employees (BUG-260910-C7B0).

DELETE/PATCH used to look up employees.id only while GET also accepted
profile_id. Integrity errors on DELETE surfaced as an unhandled 500.
"""
from __future__ import annotations

import os

os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from backend.main import app, get_current_user
import backend.main as main_mod

_HR = {"id": "hr-1", "role": "HR", "company": "co-1", "is_admin": False, "auth_uuid": None}


class _Db:
    def __init__(self):
        self.employees = {
            "emp-1": {
                "id": "emp-1",
                "company_id": "co-1",
                "profile_id": "prof-1",
                "band": "manager",
                "assignment_type": "Long-Term",
                "status": "active",
            }
        }
        self.deleted = []
        self.updated = []
        self.raise_integrity = False

    def get_employee_for_company(self, employee_id, company_id):
        emp = self.employees.get(employee_id)
        if emp and emp["company_id"] == company_id:
            return dict(emp)
        return None

    def get_employee_by_profile_for_company(self, profile_id, company_id):
        for emp in self.employees.values():
            if emp["profile_id"] == profile_id and emp["company_id"] == company_id:
                return dict(emp)
        return None

    def update_employee_limited(self, employee_id, company_id, **fields):
        emp = self.employees.get(employee_id)
        if not emp:
            emp = self.get_employee_by_profile_for_company(employee_id, company_id)
        if not emp or emp["company_id"] != company_id:
            return False
        for k, v in fields.items():
            if v is not None:
                emp[k] = v
        self.updated.append((emp["id"], fields))
        return True

    def delete_employee_for_company(self, employee_id, company_id):
        if self.raise_integrity:
            raise IntegrityError("statement", {}, Exception("fk"))
        emp = self.employees.get(employee_id)
        if not emp:
            emp = self.get_employee_by_profile_for_company(employee_id, company_id)
        if not emp or emp["company_id"] != company_id:
            return False
        self.deleted.append(emp["id"])
        del self.employees[emp["id"]]
        return True

    def log_audit(self, *args, **kwargs):
        return None


@pytest.fixture()
def fake_db(monkeypatch):
    d = _Db()
    monkeypatch.setattr(main_mod, "_get_hr_company_id", lambda user: "co-1")
    monkeypatch.setattr(main_mod, "_deny_if_impersonating", lambda user: None)
    monkeypatch.setattr(main_mod, "_effective_user", lambda user, role=None: user)
    monkeypatch.setattr(main_mod.db, "get_employee_for_company", d.get_employee_for_company)
    monkeypatch.setattr(main_mod.db, "get_employee_by_profile_for_company", d.get_employee_by_profile_for_company)
    monkeypatch.setattr(main_mod.db, "update_employee_limited", d.update_employee_limited)
    monkeypatch.setattr(main_mod.db, "delete_employee_for_company", d.delete_employee_for_company)
    monkeypatch.setattr(main_mod.db, "log_audit", d.log_audit)
    return d


@pytest.fixture()
def client(fake_db):
    app.dependency_overrides[get_current_user] = lambda: _HR
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def test_delete_employee_by_roster_id(client, fake_db):
    r = client.delete("/api/hr/employees/emp-1")
    assert r.status_code == 204, r.text
    assert fake_db.deleted == ["emp-1"]


def test_delete_employee_by_profile_id(client, fake_db):
    r = client.delete("/api/hr/employees/prof-1")
    assert r.status_code == 204, r.text
    assert fake_db.deleted == ["emp-1"]


def test_patch_employee_by_profile_id(client, fake_db):
    r = client.patch("/api/hr/employees/prof-1", json={"status": "inactive"})
    assert r.status_code == 200, r.text
    assert fake_db.updated == [("emp-1", {"band": None, "assignment_type": None, "status": "inactive"})]


def test_delete_employee_integrity_is_409_not_500(client, fake_db):
    fake_db.raise_integrity = True
    r = client.delete("/api/hr/employees/emp-1")
    assert r.status_code == 409, r.text
    assert "relocation case" in r.json()["detail"].lower()
