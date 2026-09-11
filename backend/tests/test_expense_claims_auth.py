"""[AIQ-2271] Tenant scoping for expense claims POST/PATCH."""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from unittest import mock

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import expense_claims as router_module  # noqa: E402
from backend.app.routers.expense_claims import (  # noqa: E402
    ExpenseClaimCreate,
    ExpenseClaimLineIn,
    ExpenseClaimPatch,
    create_expense_claim,
    patch_expense_claim,
)
from fastapi import HTTPException  # noqa: E402

SCHEMA = """
CREATE TABLE expense_claims (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  company_id TEXT NOT NULL,
  employee_user_id TEXT,
  status TEXT NOT NULL DEFAULT 'draft',
  hr_note TEXT,
  created_at TEXT,
  updated_at TEXT,
  submitted_at TEXT,
  resolved_at TEXT,
  resolved_by_user_id TEXT
);
CREATE TABLE expense_claim_lines (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL,
  benefit_key TEXT NOT NULL,
  amount REAL NOT NULL,
  currency TEXT NOT NULL,
  cap_currency TEXT,
  fx_rate_to_cap REAL,
  fx_rate_date TEXT,
  amount_in_cap_currency REAL,
  receipt_ocr_id TEXT,
  vendor_name TEXT,
  expense_date TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE audit_logs (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  old_value_json TEXT,
  new_value_json TEXT,
  actor_type TEXT NOT NULL,
  actor_id TEXT,
  created_at TEXT
);
"""


def _user(uid, role, company_id, is_admin=False):
    return {"id": uid, "role": role, "company": company_id, "is_admin": is_admin}


class ExpenseClaimAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        self.engine_patcher = mock.patch.object(router_module.db, "engine", self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)
        self.profile_patcher = mock.patch.object(
            router_module.db, "get_profile_record", return_value={"company_id": None}
        )
        self.profile_patcher.start()
        self.addCleanup(self.profile_patcher.stop)
        self.case_access_patcher = mock.patch.object(
            router_module, "require_case_access", return_value={}
        )
        self.case_access_patcher.start()
        self.addCleanup(self.case_access_patcher.stop)
        self.hr_company_patcher = mock.patch.object(
            router_module.db, "get_hr_company_id", return_value=None
        )
        self.hr_company_patcher.start()
        self.addCleanup(self.hr_company_patcher.stop)
        self.assignment_patcher = mock.patch.object(
            router_module.db, "get_assignment_for_employee", return_value=None
        )
        self.assignment_patcher.start()
        self.addCleanup(self.assignment_patcher.stop)
        self.notify_hr = mock.patch.object(router_module, "_notify_hr_submitted")
        self.notify_hr.start()
        self.addCleanup(self.notify_hr.stop)
        self.notify_emp = mock.patch.object(router_module, "_notify_employee_decision")
        self.notify_emp.start()
        self.addCleanup(self.notify_emp.stop)
        self.audit = mock.patch.object(router_module, "_audit")
        self.audit.start()
        self.addCleanup(self.audit.stop)

    def test_hr_other_company_cannot_patch(self):
        company_a = str(uuid.uuid4())
        company_b = str(uuid.uuid4())
        emp = _user("emp-1", "employee", company_a)
        body = ExpenseClaimCreate(
            status="submitted",
            lines=[
                ExpenseClaimLineIn(
                    benefit_key="installation_allowance",
                    amount=10,
                    currency="EUR",
                    cap_currency="EUR",
                )
            ],
        )
        created = create_expense_claim("case-1", body, emp)
        hr_b = _user("hr-b", "HR", company_b)
        with self.assertRaises(HTTPException) as ctx:
            patch_expense_claim(
                created["id"],
                ExpenseClaimPatch(status="approved"),
                hr_b,
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_hr_same_company_can_approve(self):
        company_a = str(uuid.uuid4())
        emp = _user("emp-1", "employee", company_a)
        created = create_expense_claim(
            "case-1",
            ExpenseClaimCreate(
                status="submitted",
                lines=[
                    ExpenseClaimLineIn(
                        benefit_key="installation_allowance",
                        amount=10,
                        currency="EUR",
                        cap_currency="EUR",
                    )
                ],
            ),
            emp,
        )
        hr_a = _user("hr-a", "HR", company_a)
        updated = patch_expense_claim(
            created["id"], ExpenseClaimPatch(status="approved"), hr_a
        )
        self.assertEqual(updated["status"], "approved")

    def test_require_case_access_called_on_create(self):
        company_a = str(uuid.uuid4())
        emp = _user("emp-1", "employee", company_a)
        create_expense_claim(
            "case-owned",
            ExpenseClaimCreate(
                status="draft",
                lines=[
                    ExpenseClaimLineIn(
                        benefit_key="installation_allowance",
                        amount=10,
                        currency="EUR",
                    )
                ],
            ),
            emp,
        )
        router_module.require_case_access.assert_called_with("case-owned", emp)


if __name__ == "__main__":
    unittest.main()
