"""
Route contract for GET /api/employee/cases/{case_id}/immigration-snapshot:
ownership is enforced BEFORE any snapshot is built, a denial propagates (no data
leaks on cross-case access), and visa_type passes through to the builder.
"""
import pytest
from fastapi import HTTPException

import backend.app.routers.employee_immigration_snapshot as route


def test_checks_ownership_then_builds(monkeypatch):
    seen = {}
    monkeypatch.setattr(route, "require_case_access", lambda cid, user: seen.setdefault("access", (cid, user)))
    monkeypatch.setattr(route, "build_immigration_snapshot", lambda cid, visa_type: {"covered": True, "cid": cid, "visa": visa_type})

    out = route.get_immigration_snapshot("case-1", visa_type="work", user={"id": "emp-1"})

    assert seen["access"] == ("case-1", {"id": "emp-1"})  # ownership was checked
    assert out == {"covered": True, "cid": "case-1", "visa": "work"}  # builder result + visa passthrough


def test_ownership_denial_propagates_and_blocks_build(monkeypatch):
    def deny(cid, user):
        raise HTTPException(status_code=403, detail="not your case")

    def must_not_build(*a, **k):
        raise AssertionError("snapshot built despite denied ownership")

    monkeypatch.setattr(route, "require_case_access", deny)
    monkeypatch.setattr(route, "build_immigration_snapshot", must_not_build)

    with pytest.raises(HTTPException) as exc:
        route.get_immigration_snapshot("someone-elses-case", user={"id": "emp-1"})
    assert exc.value.status_code == 403
