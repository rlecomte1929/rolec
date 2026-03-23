"""HR policy review payload: service + serializer integration with a fake DB."""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from typing import Any, Dict, List, Optional

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_document_intake import DOC_TYPE_POLICY_SUMMARY, SCOPE_LONG_TERM
from backend.services.policy_hr_review_service import build_hr_policy_review_payload
from backend.services.policy_hr_review_serializer import (
    HR_POLICY_REVIEW_SCHEMA_VERSION,
    serialize_hr_policy_review_payload,
)


class _FakeHRReviewDB:
    def __init__(self) -> None:
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.clauses: Dict[str, List[Dict[str, Any]]] = {}
        self.versions_by_source: Dict[str, List[Dict[str, Any]]] = {}
        self.policies: Dict[str, Dict[str, Any]] = {}
        self.versions_by_policy: Dict[str, List[Dict[str, Any]]] = {}
        self.published_by_policy: Dict[str, Dict[str, Any]] = {}
        self.benefits: Dict[str, List[Dict[str, Any]]] = {}
        self.exclusions: Dict[str, List[Dict[str, Any]]] = {}
        self.conditions: Dict[str, List[Dict[str, Any]]] = {}
        self.evidence: Dict[str, List[Dict[str, Any]]] = {}
        self.assignment_applicability: Dict[str, List[Dict[str, Any]]] = {}
        self.family: Dict[str, List[Dict[str, Any]]] = {}

    def get_policy_document(self, doc_id: str, request_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return self.documents.get(doc_id)

    def list_policy_document_clauses(
        self, doc_id: str, clause_type: Optional[str] = None, request_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return list(self.clauses.get(doc_id, []))

    def list_policy_versions_by_source_document(self, document_id: str) -> List[Dict[str, Any]]:
        return list(self.versions_by_source.get(document_id, []))

    def get_company_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        return self.policies.get(policy_id)

    def get_latest_policy_version(self, policy_id: str) -> Optional[Dict[str, Any]]:
        vs = self.versions_by_policy.get(policy_id, [])
        return vs[0] if vs else None

    def get_published_policy_version(self, policy_id: str) -> Optional[Dict[str, Any]]:
        return self.published_by_policy.get(policy_id)

    def list_policy_benefit_rules(self, policy_version_id: str) -> List[Dict[str, Any]]:
        return list(self.benefits.get(policy_version_id, []))

    def list_policy_exclusions(self, policy_version_id: str) -> List[Dict[str, Any]]:
        return list(self.exclusions.get(policy_version_id, []))

    def list_policy_rule_conditions(self, policy_version_id: str) -> List[Dict[str, Any]]:
        return list(self.conditions.get(policy_version_id, []))

    def list_policy_evidence_requirements(self, policy_version_id: str) -> List[Dict[str, Any]]:
        return list(self.evidence.get(policy_version_id, []))

    def list_policy_assignment_applicability(self, policy_version_id: str) -> List[Dict[str, Any]]:
        return list(self.assignment_applicability.get(policy_version_id, []))

    def list_policy_family_applicability(self, policy_version_id: str) -> List[Dict[str, Any]]:
        return list(self.family.get(policy_version_id, []))


def _doc(
    doc_id: str,
    company_id: str,
    *,
    det_type: str = "assignment_policy",
    det_scope: str = SCOPE_LONG_TERM,
    processing_status: str = "complete",
) -> Dict[str, Any]:
    return {
        "id": doc_id,
        "company_id": company_id,
        "processing_status": processing_status,
        "detected_document_type": det_type,
        "detected_policy_scope": det_scope,
        "extracted_metadata": {},
        "filename": "policy.pdf",
        "mime_type": "application/pdf",
        "storage_path": "k/policy.pdf",
        "raw_text": "body",
    }


def _clause(cid: str, *, ctype: str = "unknown", raw: str = "", hints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "id": cid,
        "policy_document_id": None,
        "clause_type": ctype,
        "raw_text": raw,
        "normalized_hint_json": hints or {},
        "confidence": 0.8,
    }


class PolicyHRReviewTests(unittest.TestCase):
    def test_summary_only_document_synthesized_draft_publish_blocked(self) -> None:
        doc_id = str(uuid.uuid4())
        company_id = str(uuid.uuid4())
        policy_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        db = _FakeHRReviewDB()
        db.documents[doc_id] = _doc(doc_id, company_id, det_type=DOC_TYPE_POLICY_SUMMARY)
        db.clauses[doc_id] = [
            _clause(str(uuid.uuid4()), ctype="scope", raw="General principles of the mobility program."),
        ]
        db.policies[policy_id] = {"id": policy_id, "company_id": company_id, "title": "Mobility"}
        ver = {
            "id": version_id,
            "policy_id": policy_id,
            "source_policy_document_id": doc_id,
            "version_number": 1,
            "status": "auto_generated",
            "normalization_draft_json": None,
        }
        db.versions_by_source[doc_id] = [ver]
        db.versions_by_policy[policy_id] = [ver]

        payload = build_hr_policy_review_payload(db, document_id=doc_id)
        out = serialize_hr_policy_review_payload(payload)
        self.assertEqual(out["schema_version"], HR_POLICY_REVIEW_SCHEMA_VERSION)
        self.assertEqual(out["review"]["normalization_draft_source"], "synthesized")
        self.assertTrue(out["review"]["has_persisted_version"])
        self.assertEqual(out["detected_classification"]["detected_document_type"], DOC_TYPE_POLICY_SUMMARY)
        self.assertGreaterEqual(len(out["clause_candidates"]), 1)
        self.assertEqual(out["layer2_publishable"]["counts"]["benefit_rules"], 0)
        self.assertEqual(out["layer2_publishable"]["counts"]["exclusions"], 0)
        self.assertEqual(out["readiness"]["publish_readiness"]["status"], "not_ready")
        self.assertIn("issues", out)
        self.assertFalse(out["employee_visibility"]["employee_sees_published_policy_matrix"])

    def test_exclusion_only_layer2_and_readiness(self) -> None:
        doc_id = str(uuid.uuid4())
        company_id = str(uuid.uuid4())
        policy_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        db = _FakeHRReviewDB()
        db.documents[doc_id] = _doc(doc_id, company_id)
        db.clauses[doc_id] = [
            _clause(str(uuid.uuid4()), ctype="exclusion", raw="Tax equalization does not apply in host country X."),
        ]
        db.policies[policy_id] = {"id": policy_id, "company_id": company_id, "title": "Mobility"}
        ver = {
            "id": version_id,
            "policy_id": policy_id,
            "source_policy_document_id": doc_id,
            "version_number": 1,
            "status": "auto_generated",
            "normalization_draft_json": None,
        }
        db.versions_by_source[doc_id] = [ver]
        db.versions_by_policy[policy_id] = [ver]
        db.exclusions[version_id] = [
            {
                "id": str(uuid.uuid4()),
                "domain": "tax",
                "benefit_key": None,
                "description": "Tax equalization does not apply in host country X.",
                "auto_generated": True,
            }
        ]

        payload = build_hr_policy_review_payload(db, document_id=doc_id)
        self.assertEqual(payload["layer2_publishable"]["counts"]["exclusions"], 1)
        self.assertEqual(payload["readiness"]["normalization_readiness"]["status"], "ready")
        self.assertIn(payload["readiness"]["publish_readiness"]["status"], ("partial", "ready"))
        self.assertGreaterEqual(len(payload["rule_candidates"].get("exclusions") or []), 1)

    def test_structured_benefit_document(self) -> None:
        doc_id = str(uuid.uuid4())
        company_id = str(uuid.uuid4())
        policy_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        db = _FakeHRReviewDB()
        db.documents[doc_id] = _doc(doc_id, company_id)
        db.clauses[doc_id] = [
            _clause(
                str(uuid.uuid4()),
                ctype="benefit",
                raw="Company provides housing allowance up to 5000 USD per month for eligible assignments.",
            )
        ]
        db.policies[policy_id] = {"id": policy_id, "company_id": company_id, "title": "Mobility"}
        ver = {
            "id": version_id,
            "policy_id": policy_id,
            "source_policy_document_id": doc_id,
            "version_number": 1,
            "status": "auto_generated",
            "normalization_draft_json": None,
        }
        db.versions_by_source[doc_id] = [ver]
        db.versions_by_policy[policy_id] = [ver]
        db.benefits[version_id] = [
            {
                "id": str(uuid.uuid4()),
                "benefit_key": "housing_allowance",
                "benefit_category": "cash",
                "calc_type": "fixed_amount",
                "amount_value": 5000.0,
                "amount_unit": "per_month",
                "currency": "USD",
                "frequency": "per_assignment",
                "description": "Housing allowance",
                "auto_generated": True,
            }
        ]

        payload = build_hr_policy_review_payload(db, document_id=doc_id)
        self.assertEqual(payload["layer2_publishable"]["counts"]["benefit_rules"], 1)
        brc = payload["rule_candidates"].get("benefit_rules") or []
        self.assertGreaterEqual(len(brc), 1)
        self.assertEqual(brc[0].get("benefit_key"), "housing_allowance")

    def test_starter_template_policy_id_only(self) -> None:
        company_id = str(uuid.uuid4())
        policy_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        db = _FakeHRReviewDB()
        db.policies[policy_id] = {"id": policy_id, "company_id": company_id, "title": "Starter template"}
        ver = {
            "id": version_id,
            "policy_id": policy_id,
            "source_policy_document_id": None,
            "version_number": 1,
            "status": "draft",
            "normalization_draft_json": None,
        }
        db.versions_by_policy[policy_id] = [ver]
        db.benefits[version_id] = [
            {
                "id": str(uuid.uuid4()),
                "benefit_key": "relocation_allowance",
                "benefit_category": "cash",
                "calc_type": "fixed_amount",
                "amount_value": 10000.0,
                "amount_unit": "lump_sum",
                "currency": "USD",
                "frequency": "once",
                "description": "Relocation allowance",
                "auto_generated": False,
            }
        ]

        payload = build_hr_policy_review_payload(db, policy_id=policy_id)
        self.assertIsNone(payload["source_document"])
        self.assertEqual(payload["detected_classification"]["detected_document_type"], "starter_template")
        self.assertEqual(payload["layer2_publishable"]["counts"]["benefit_rules"], 1)
        self.assertEqual(len(payload["clause_candidates"]), 0)
        self.assertEqual(payload["review"]["document_id"], None)


if __name__ == "__main__":
    unittest.main()
