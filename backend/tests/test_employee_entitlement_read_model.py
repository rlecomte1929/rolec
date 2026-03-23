"""Employee entitlement read model: policy maturity + per-service rows (fake DB)."""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from typing import Any, Dict, List, Optional

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.employee_entitlement_read_model import build_employee_entitlement_read_model
from backend.services.employee_entitlement_serializer import (
    EMPLOYEE_ENTITLEMENT_SCHEMA_VERSION,
    serialize_employee_entitlement_payload,
)


class _FakeEntitlementsDB:
    def __init__(self) -> None:
        self.companies_policies: Dict[str, List[Dict[str, Any]]] = {}
        self.versions: Dict[str, List[Dict[str, Any]]] = {}
        self.published: Dict[str, Dict[str, Any]] = {}
        self.benefits: Dict[str, List[Dict[str, Any]]] = {}
        self.exclusions: Dict[str, List[Dict[str, Any]]] = {}
        self.family: Dict[str, List[Dict[str, Any]]] = {}
        self._resolved: Dict[str, Dict[str, Any]] = {}
        self._resolved_benefits: Dict[str, List[Dict[str, Any]]] = {}
        self._resolved_exclusions: Dict[str, List[Dict[str, Any]]] = {}

    def list_company_policies(self, company_id: str) -> List[Dict[str, Any]]:
        return list(self.companies_policies.get(company_id, []))

    def list_policy_versions(self, policy_id: str) -> List[Dict[str, Any]]:
        return list(self.versions.get(str(policy_id), []))

    def get_published_policy_version(self, policy_id: str) -> Optional[Dict[str, Any]]:
        return self.published.get(str(policy_id))

    def get_policy_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        for vs in self.versions.values():
            for v in vs:
                if str(v.get("id")) == str(version_id):
                    return v
        return None

    def list_policy_benefit_rules(self, policy_version_id: str) -> List[Dict[str, Any]]:
        return list(self.benefits.get(str(policy_version_id), []))

    def list_policy_exclusions(self, policy_version_id: str) -> List[Dict[str, Any]]:
        return list(self.exclusions.get(str(policy_version_id), []))

    def list_policy_rule_conditions(self, policy_version_id: str) -> List[Dict[str, Any]]:
        return []

    def list_policy_evidence_requirements(self, policy_version_id: str) -> List[Dict[str, Any]]:
        return []

    def list_policy_assignment_applicability(self, policy_version_id: str) -> List[Dict[str, Any]]:
        return []

    def list_policy_family_applicability(self, policy_version_id: str) -> List[Dict[str, Any]]:
        return list(self.family.get(str(policy_version_id), []))

    def list_policy_tier_overrides(self, policy_version_id: str) -> List[Dict[str, Any]]:
        return []

    def list_hr_benefit_rule_overrides(self, policy_version_id: str) -> List[Dict[str, Any]]:
        return []

    def get_policy_document(self, document_id: str, request_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return None

    def upsert_resolved_assignment_policy(
        self,
        assignment_id: str,
        case_id: Optional[str],
        company_id: str,
        policy_id: str,
        policy_version_id: str,
        canonical_case_id: Optional[str],
        resolution_status: str,
        resolution_context: Dict[str, Any],
        benefits: List[Dict[str, Any]],
        exclusions: List[Dict[str, Any]],
    ) -> str:
        rid = "resolved-1"
        self._resolved[str(assignment_id)] = {
            "id": rid,
            "assignment_id": assignment_id,
            "policy_version_id": policy_version_id,
            "resolved_at": "2020-01-01T00:00:00",
        }
        self._resolved_benefits[rid] = [dict(b) for b in benefits]
        self._resolved_exclusions[rid] = list(exclusions)
        return rid

    def get_resolved_assignment_policy(self, assignment_id: str) -> Optional[Dict[str, Any]]:
        return self._resolved.get(str(assignment_id))

    def list_resolved_policy_benefits(self, resolved_policy_id: str) -> List[Dict[str, Any]]:
        return list(self._resolved_benefits.get(str(resolved_policy_id), []))

    def list_resolved_policy_exclusions(self, resolved_policy_id: str) -> List[Dict[str, Any]]:
        return list(self._resolved_exclusions.get(str(resolved_policy_id), []))


def _benefit_rule(
    rid: str,
    benefit_key: str,
    *,
    amount: float = 100.0,
) -> Dict[str, Any]:
    return {
        "id": rid,
        "benefit_key": benefit_key,
        "amount_value": amount,
        "currency": "USD",
        "amount_unit": "flat",
        "frequency": "once",
        "metadata_json": {},
        "review_status": None,
    }


class EmployeeEntitlementReadModelTests(unittest.TestCase):
    def _assignment_context(self, company_id: str) -> tuple:
        assignment = {
            "id": "asgn-1",
            "case_id": "case-1",
            "canonical_case_id": "case-1",
        }
        case = {"company_id": company_id, "hr_user_id": None}
        return assignment, case

    def test_no_company_policy(self) -> None:
        db = _FakeEntitlementsDB()
        cid = str(uuid.uuid4())
        assignment, case = self._assignment_context(cid)
        out = build_employee_entitlement_read_model(
            db, assignment["id"], assignment, case, None, None
        )
        self.assertEqual(out["policy_status"], "no_policy")
        self.assertIsNone(out["policy_source"])
        self.assertEqual(out["entitlements"], [])
        self.assertFalse(out["comparison_readiness"].get("evaluated", True))
        ser = serialize_employee_entitlement_payload(out)
        self.assertEqual(ser["schema_version"], EMPLOYEE_ENTITLEMENT_SCHEMA_VERSION)

    def test_starter_template_unpublished_with_rules(self) -> None:
        db = _FakeEntitlementsDB()
        cid = str(uuid.uuid4())
        pid = str(uuid.uuid4())
        vid = str(uuid.uuid4())
        db.companies_policies[cid] = [
            {
                "id": pid,
                "company_id": cid,
                "title": "Starter",
                "template_source": "default_platform_template",
                "template_name": "starter_v1",
            }
        ]
        db.versions[pid] = [
            {"id": vid, "policy_id": pid, "version_number": 1, "status": "draft"},
        ]
        db.benefits[vid] = [_benefit_rule("br1", "immigration", amount=1)]
        assignment, case = self._assignment_context(cid)
        out = build_employee_entitlement_read_model(
            db, assignment["id"], assignment, case, None, None
        )
        self.assertEqual(out["policy_status"], "normalized_not_publishable")
        self.assertEqual(out["policy_source"], "starter_template")
        self.assertFalse(out["comparison_readiness"].get("comparison_ready"))
        self.assertIn("NO_PUBLISHED_POLICY", out["comparison_readiness"].get("comparison_blockers", []))
        keys = {e["service_key"] for e in out["entitlements"]}
        self.assertIn("visa_support", keys)

    def test_normalized_draft_only_uploaded_summary_no_layer2(self) -> None:
        db = _FakeEntitlementsDB()
        cid = str(uuid.uuid4())
        pid = str(uuid.uuid4())
        vid = str(uuid.uuid4())
        db.companies_policies[cid] = [
            {
                "id": pid,
                "company_id": cid,
                "title": "Summary",
                "template_source": "company_uploaded",
            }
        ]
        db.versions[pid] = [
            {"id": vid, "policy_id": pid, "version_number": 1, "status": "auto_generated"},
        ]
        assignment, case = self._assignment_context(cid)
        out = build_employee_entitlement_read_model(
            db, assignment["id"], assignment, case, None, None
        )
        self.assertEqual(out["policy_status"], "draft_only")
        self.assertEqual(out["policy_source"], "company_uploaded")
        self.assertEqual(out["entitlements"], [])

    def test_published_not_comparison_ready_missing_key(self) -> None:
        db = _FakeEntitlementsDB()
        cid = str(uuid.uuid4())
        pid = str(uuid.uuid4())
        vid = str(uuid.uuid4())
        db.companies_policies[cid] = [
            {"id": pid, "company_id": cid, "title": "Live", "template_source": "company_uploaded"},
        ]
        pub_ver = {"id": vid, "policy_id": pid, "version_number": 1, "status": "published"}
        db.versions[pid] = [pub_ver]
        db.published[pid] = pub_ver
        db.benefits[vid] = [
            _benefit_rule("b1", "temporary_housing", amount=100),
            _benefit_rule("b2", "schooling", amount=200),
        ]
        assignment, case = self._assignment_context(cid)
        out = build_employee_entitlement_read_model(
            db, assignment["id"], assignment, case, None, None
        )
        self.assertEqual(out["policy_status"], "published_not_comparison_ready")
        self.assertFalse(out["comparison_readiness"].get("comparison_ready"))
        self.assertTrue(out["comparison_readiness"].get("evaluated"))
        for e in out["entitlements"]:
            self.assertFalse(e["comparison_readiness"]["comparison_ready"])

    def test_published_comparison_ready(self) -> None:
        db = _FakeEntitlementsDB()
        cid = str(uuid.uuid4())
        pid = str(uuid.uuid4())
        vid = str(uuid.uuid4())
        db.companies_policies[cid] = [
            {"id": pid, "company_id": cid, "title": "Live", "template_source": "company_uploaded"},
        ]
        pub_ver = {"id": vid, "policy_id": pid, "version_number": 1, "status": "published"}
        db.versions[pid] = [pub_ver]
        db.published[pid] = pub_ver
        db.benefits[vid] = [
            _benefit_rule("b1", "temporary_housing", amount=5000),
            _benefit_rule("b2", "schooling", amount=3000),
            _benefit_rule("b3", "shipment", amount=4000),
        ]
        assignment, case = self._assignment_context(cid)
        out = build_employee_entitlement_read_model(
            db, assignment["id"], assignment, case, None, None
        )
        self.assertEqual(out["policy_status"], "published_comparison_ready")
        self.assertTrue(out["comparison_readiness"].get("comparison_ready"))
        self.assertTrue(out["comparison_readiness"].get("evaluated"))
        school = next(e for e in out["entitlements"] if e["service_key"] == "school_search")
        self.assertTrue(school["comparison_readiness"]["comparison_ready"])
        self.assertIsNotNone(school.get("effective_limit"))

    def test_family_specific_school_rule_single_vs_accompanied(self) -> None:
        db = _FakeEntitlementsDB()
        cid = str(uuid.uuid4())
        pid = str(uuid.uuid4())
        vid = str(uuid.uuid4())
        db.companies_policies[cid] = [{"id": pid, "company_id": cid, "title": "Fam"}]
        pub_ver = {"id": vid, "policy_id": pid, "version_number": 1, "status": "published"}
        db.versions[pid] = [pub_ver]
        db.published[pid] = pub_ver
        db.benefits[vid] = [
            _benefit_rule("b1", "temporary_housing", amount=100),
            _benefit_rule("b2", "schooling", amount=200),
            _benefit_rule("b3", "shipment", amount=300),
        ]
        db.family[vid] = [{"benefit_rule_id": "b2", "family_status": "accompanied"}]
        assignment, case = self._assignment_context(cid)
        single_profile: Dict[str, Any] = {}
        out_single = build_employee_entitlement_read_model(
            db, assignment["id"], assignment, case, None, single_profile
        )
        sk_single = {e["service_key"] for e in out_single["entitlements"]}
        self.assertNotIn("school_search", sk_single)

        family_profile = {"spouse": {"fullName": "Pat Doe"}}
        out_fam = build_employee_entitlement_read_model(
            db, assignment["id"], assignment, case, None, family_profile
        )
        sk_fam = {e["service_key"] for e in out_fam["entitlements"]}
        self.assertIn("school_search", sk_fam)


if __name__ == "__main__":
    unittest.main()
