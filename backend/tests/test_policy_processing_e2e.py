"""
End-to-end backend tests: policy processing across summary upload, starter template,
and structured upload paths.

Requires local SQLite (default DATABASE_URL) with migrations applied — same as other
TestClient tests. Each scenario uses an isolated company + HR/employee users.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from datetime import datetime

from fastapi.testclient import TestClient
from passlib.context import CryptContext  # matches backend/main.py login hashing
from sqlalchemy import text

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.abspath(os.path.join(_TESTS_DIR, ".."))
_REPO_ROOT = os.path.abspath(os.path.join(_BACKEND_ROOT, ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.dev_seed_auth import ensure_dev_seed_auth_user  # noqa: E402
from backend.main import app, db  # noqa: E402
from backend.services.policy_comparison_readiness import (  # noqa: E402
    invalidate_comparison_readiness_cache,
)
from backend.services.policy_rule_comparison_readiness import (  # noqa: E402
    evaluate_rule_comparison_readiness,
)
from backend.tests.fixtures.policy_processing_e2e_fixtures import (  # noqa: E402
    structured_assignment_document_updates,
    structured_policy_clauses,
    summary_only_clauses,
    summary_only_document_updates,
)

_pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
_E2E_PASSWORD_HASH = _pwd_ctx.hash("Passw0rd!")


def _create_company_for_e2e(company_id: str, name: str) -> None:
    """
    db.create_company uses information_schema (Postgres). For local SQLite, insert explicitly.
    """
    now = datetime.utcnow().isoformat()
    if db.engine.dialect.name == "sqlite":
        with db.engine.begin() as conn:
            col_rows = conn.execute(text("PRAGMA table_info(companies)")).fetchall()
            col_names = {r[1] for r in col_rows}
            row: dict = {"id": company_id, "name": name, "created_at": now}
            if "country" in col_names:
                row["country"] = "SG"
            if "size_band" in col_names:
                row["size_band"] = "1-50"
            if "updated_at" in col_names:
                row["updated_at"] = now
            if "status" in col_names:
                row["status"] = "active"
            if "plan_tier" in col_names:
                row["plan_tier"] = "low"
            keys = [k for k in row if k in col_names]
            vals = {k: row[k] for k in keys}
            qcols = ", ".join(keys)
            qplace = ", ".join(f":{k}" for k in keys)
            conn.execute(text(f"INSERT INTO companies ({qcols}) VALUES ({qplace})"), vals)
    else:
        db.create_company(company_id, name, "SG", "1-50", "", "", "")


def _login(client: TestClient, email: str, password: str = "Passw0rd!") -> str:
    res = client.post("/api/auth/login", json={"identifier": email, "password": password})
    assert res.status_code == 200, res.text
    return str(res.json()["token"])


def _bootstrap_isolated_tenant(client: TestClient, *, label: str) -> dict:
    """Fresh company, HR + employee auth, case + assignment; returns ids and tokens."""
    suffix = uuid.uuid4().hex[:10]
    company_id = str(uuid.uuid4())
    _create_company_for_e2e(company_id, f"E2E {label} {suffix}")

    hr_email = f"e2e-{label}-hr-{suffix}@relopass.test"
    emp_email = f"e2e-{label}-emp-{suffix}@relopass.test"
    hr_uid = str(uuid.uuid4())
    emp_uid = str(uuid.uuid4())

    hr_uid = ensure_dev_seed_auth_user(
        db,
        user_id=hr_uid,
        email=hr_email,
        password_hash=_E2E_PASSWORD_HASH,
        role="HR",
        name="E2E HR",
    )
    emp_uid = ensure_dev_seed_auth_user(
        db,
        user_id=emp_uid,
        email=emp_email,
        password_hash=_E2E_PASSWORD_HASH,
        role="EMPLOYEE",
        name="E2E Employee",
    )
    db.ensure_profile_record(hr_uid, hr_email, "HR", "E2E HR", company_id)
    db.ensure_profile_record(emp_uid, emp_email, "EMPLOYEE", "E2E Employee", company_id)
    db.create_hr_user(str(uuid.uuid4()), company_id, hr_uid, {"can_manage_policy": True})

    case_id = str(uuid.uuid4())
    db.create_case(case_id, hr_uid, {"label": f"e2e-{label}"}, company_id=company_id)
    db.upsert_relocation_case(
        case_id,
        company_id,
        None,
        "active",
        "intake",
        "SG",
        "US",
    )
    assignment_id = str(uuid.uuid4())
    db.create_assignment(
        assignment_id,
        case_id,
        hr_uid,
        emp_uid,
        emp_email,
        "assigned",
    )

    hr_token = _login(client, hr_email)
    emp_token = _login(client, emp_email)
    return {
        "company_id": company_id,
        "hr_uid": hr_uid,
        "emp_uid": emp_uid,
        "hr_email": hr_email,
        "emp_email": emp_email,
        "hr_token": hr_token,
        "emp_token": emp_token,
        "case_id": case_id,
        "assignment_id": assignment_id,
    }


def _seed_policy_document(
    *,
    company_id: str,
    uploaded_by: str,
    doc_updates: dict,
    clauses: list,
) -> str:
    doc_id = str(uuid.uuid4())
    db.create_policy_document(
        doc_id,
        company_id,
        uploaded_by,
        "e2e-policy.pdf",
        "application/pdf",
        f"e2e/{doc_id}.pdf",
    )
    db.update_policy_document(doc_id, **doc_updates)
    db.upsert_policy_document_clauses(doc_id, clauses)
    return doc_id


class PolicyProcessingE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_a_summary_only_normalize_and_employee_entitlements(self) -> None:
        t = _bootstrap_isolated_tenant(self.client, label="summary")
        doc_id = _seed_policy_document(
            company_id=t["company_id"],
            uploaded_by=t["hr_uid"],
            doc_updates=summary_only_document_updates(),
            clauses=summary_only_clauses(),
        )
        res = self.client.post(
            f"/api/hr/policy-documents/{doc_id}/normalize",
            headers={"Authorization": f"Bearer {t['hr_token']}"},
        )
        self.assertNotEqual(res.status_code, 500, res.text)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body.get("ok"))
        self.assertTrue(body.get("normalized"))
        self.assertFalse(body.get("publishable"))
        self.assertIsNotNone(body.get("normalization_draft"))
        pr = body.get("policy_readiness") or {}
        cr = (pr.get("comparison_readiness") or {}).get("status") or ""
        self.assertIn(
            cr.lower(),
            ("partial", "not_ready"),
            msg=f"comparison_readiness.status={cr!r} policy_readiness={pr}",
        )
        ent = self.client.get(
            f"/api/employee/assignments/{t['assignment_id']}/entitlements",
            headers={"Authorization": f"Bearer {t['emp_token']}"},
        )
        self.assertEqual(ent.status_code, 200, ent.text)
        ep = ent.json()
        self.assertIn("entitlements", ep)
        self.assertIn(ep.get("policy_status", ""), ("draft_only", "normalized_not_publishable", "no_policy"))

    def test_b_starter_template_publish_comparison_and_entitlements(self) -> None:
        t = _bootstrap_isolated_tenant(self.client, label="starter")
        init = self.client.post(
            "/api/hr/company-policy/initialize-from-template",
            headers={"Authorization": f"Bearer {t['hr_token']}"},
            json={"template_key": "standard", "comparison_ready_structure": True},
        )
        self.assertEqual(init.status_code, 200, init.text)
        data = init.json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("version_status"), "draft")
        policy_id = str(data["policy_id"])
        version_id = str(data["policy_version_id"])
        self.assertGreaterEqual(int(data.get("benefit_rules_created") or 0), 5)

        rules = db.list_policy_benefit_rules(version_id)
        self.assertEqual(len(rules), 5)
        for r in rules:
            rr = evaluate_rule_comparison_readiness(r)
            self.assertIn(rr.get("level"), ("full", "partial", "not_ready"))

        pub = self.client.post(
            f"/api/company-policies/{policy_id}/versions/{version_id}/publish",
            headers={"Authorization": f"Bearer {t['hr_token']}"},
        )
        self.assertEqual(pub.status_code, 200, pub.text)
        invalidate_comparison_readiness_cache(version_id)

        ent = self.client.get(
            f"/api/employee/assignments/{t['assignment_id']}/entitlements",
            headers={"Authorization": f"Bearer {t['emp_token']}"},
        )
        self.assertEqual(ent.status_code, 200, ent.text)
        ej = ent.json()
        self.assertEqual(ej.get("policy_status"), "published_comparison_ready")
        keys = {e.get("service_key") for e in (ej.get("entitlements") or [])}
        for sk in (
            "visa_support",
            "temporary_housing",
            "home_search",
            "school_search",
            "household_goods_shipment",
        ):
            self.assertIn(sk, keys)

        cmp_body = {
            "selected_services": [
                {"service_key": "temporary_housing", "estimated_cost": 2000, "currency": "USD", "duration_months": 12},
                {"service_key": "household_goods_shipment", "estimated_cost": 500, "currency": "USD"},
            ]
        }
        eng = self.client.post(
            f"/api/employee/assignments/{t['assignment_id']}/service-comparison-engine",
            headers={"Authorization": f"Bearer {t['emp_token']}"},
            json=cmp_body,
        )
        self.assertEqual(eng.status_code, 200, eng.text)
        ej2 = eng.json()
        self.assertTrue((ej2.get("comparison_readiness") or {}).get("comparison_ready"))
        rows = ej2.get("effective_service_comparison") or []
        by_sk = {r.get("service_key"): r for r in rows}
        self.assertEqual(by_sk.get("temporary_housing", {}).get("comparison_status"), "within_envelope")
        self.assertEqual(by_sk.get("household_goods_shipment", {}).get("comparison_status"), "within_envelope")

    def test_c_structured_upload_normalize_publish_entitlements_and_comparison(self) -> None:
        t = _bootstrap_isolated_tenant(self.client, label="structured")
        doc_id = _seed_policy_document(
            company_id=t["company_id"],
            uploaded_by=t["hr_uid"],
            doc_updates=structured_assignment_document_updates(),
            clauses=structured_policy_clauses(),
        )
        res = self.client.post(
            f"/api/hr/policy-documents/{doc_id}/normalize",
            headers={"Authorization": f"Bearer {t['hr_token']}"},
        )
        self.assertNotEqual(res.status_code, 500, res.text)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body.get("ok"))
        self.assertTrue(body.get("normalized"))
        self.assertTrue(body.get("publishable"), body)
        self.assertTrue(body.get("published"), body)
        pr = body.get("policy_readiness") or {}
        self.assertEqual((pr.get("publish_readiness") or {}).get("status"), "ready")
        version_id = str(body["policy_version_id"])
        excl = db.list_policy_exclusions(version_id)
        self.assertGreaterEqual(len(excl), 1)
        br = db.list_policy_benefit_rules(version_id)
        self.assertGreaterEqual(len(br), 1)

        invalidate_comparison_readiness_cache(version_id)

        ent = self.client.get(
            f"/api/employee/assignments/{t['assignment_id']}/entitlements",
            headers={"Authorization": f"Bearer {t['emp_token']}"},
        )
        self.assertEqual(ent.status_code, 200, ent.text)
        ej = ent.json()
        self.assertEqual(ej.get("policy_status"), "published_comparison_ready")

        cmp_body = {
            "selected_services": [
                {"service_key": "visa_support", "estimated_cost": 1500, "currency": "USD"},
                {"service_key": "household_goods_shipment", "estimated_cost": 25000, "currency": "USD"},
            ]
        }
        eng = self.client.post(
            f"/api/employee/assignments/{t['assignment_id']}/service-comparison-engine",
            headers={"Authorization": f"Bearer {t['emp_token']}"},
            json=cmp_body,
        )
        self.assertEqual(eng.status_code, 200, eng.text)
        ej2 = eng.json()
        rows = ej2.get("effective_service_comparison") or []
        by_sk = {r.get("service_key"): r for r in rows}
        self.assertEqual(by_sk.get("visa_support", {}).get("comparison_status"), "within_envelope")
        self.assertEqual(by_sk.get("household_goods_shipment", {}).get("comparison_status"), "exceeds_envelope")


if __name__ == "__main__":
    unittest.main()
