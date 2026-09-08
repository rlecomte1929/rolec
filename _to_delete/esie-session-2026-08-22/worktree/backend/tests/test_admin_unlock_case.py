"""Regression guard: unlock-case must reactivate a relocation case WITHOUT
null-overwriting its other columns.

`admin_unlock_case` used to call `db.upsert_relocation_case(case_id, company_id=…,
employee_id=…, status='active', stage=…, host/home_country=…)` with fields from the
request payload — and `upsert_relocation_case` blind-UPDATEs every column, so a bare
reactivate (case_id + status only) wiped company_id/employee_id/stage/countries to NULL.
The fix routes through a status-only setter. SQLite can't show the corruption, so this is
a source/behaviour-level guard (matches test_admin_500_regressions.py)."""
import inspect

import backend.main as main_mod
from backend.db import cases as cases_mod


def test_unlock_case_uses_status_only_setter():
    src = inspect.getsource(main_mod.admin_unlock_case)
    assert "upsert_relocation_case" not in src, "unlock-case must not use the null-overwriting upsert"
    assert "set_relocation_case_status" in src, "unlock-case must route through the status-only setter"


def test_set_relocation_case_status_is_status_only():
    src = inspect.getsource(cases_mod.CasesMixin.set_relocation_case_status)
    # The UPDATE must touch only status + updated_at — never the identity/location columns.
    for forbidden in ("company_id", "employee_id", "stage", "host_country", "home_country"):
        assert f"{forbidden} =" not in src, f"status-only setter must not write {forbidden}"
    assert "SET status = :status" in src
    assert "updated_at = :now" in src
