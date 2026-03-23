"""Integration-style tests: run_normalization outcomes (draft vs publishable) with a fake DB."""
from __future__ import annotations

import copy
import os
import sys
import unittest
import uuid
from typing import Any, Callable, Dict, List, Optional

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_document_intake import DOC_TYPE_POLICY_SUMMARY, SCOPE_LONG_TERM
from backend.services.policy_normalization import run_normalization
from backend.services.policy_normalization_errors import PolicyNormalizationPayloadInvalid


class _FakePolicyDB:
    """Minimal DB surface used by run_normalization (atomic txn semantics)."""

    def __init__(self) -> None:
        self.policies: List[Dict[str, Any]] = []
        self.versions: List[Dict[str, Any]] = []
        self.benefit_rows: List[Dict[str, Any]] = []
        self.exclusion_rows: List[Dict[str, Any]] = []
        self.normalization_drafts: Dict[str, Dict[str, Any]] = {}

    def run_policy_normalization_transaction(self, fn: Callable[[Any], None]) -> None:
        snap = (
            copy.deepcopy(self.policies),
            copy.deepcopy(self.versions),
            copy.deepcopy(self.benefit_rows),
            copy.deepcopy(self.exclusion_rows),
            copy.deepcopy(self.normalization_drafts),
        )
        try:
            fn(object())
        except Exception:
            self.policies, self.versions, self.benefit_rows, self.exclusion_rows, self.normalization_drafts = snap
            raise

    def list_company_policies(self, company_id: str) -> List[Dict[str, Any]]:
        return [p for p in self.policies if p.get("company_id") == company_id]

    def create_company_policy(self, **kwargs: Any) -> None:
        kwargs.pop("connection", None)
        self.policies.append(dict(kwargs))

    def list_policy_versions(self, policy_id: str) -> List[Dict[str, Any]]:
        return [v for v in self.versions if v.get("policy_id") == policy_id]

    def create_policy_version(self, **kwargs: Any) -> None:
        kwargs.pop("connection", None)
        self.versions.append(dict(kwargs))

    def insert_policy_benefit_rule(self, rule: Dict[str, Any], *, connection: Any = None) -> str:
        _ = connection
        rid = str(uuid.uuid4())
        self.benefit_rows.append({**rule, "id": rid})
        return rid

    def insert_policy_exclusion(self, row: Dict[str, Any], *, connection: Any = None) -> str:
        _ = connection
        eid = str(uuid.uuid4())
        self.exclusion_rows.append({**row, "id": eid})
        return eid

    def insert_policy_evidence_requirement(self, row: Dict[str, Any], *, connection: Any = None) -> str:
        _ = connection
        return str(uuid.uuid4())

    def insert_policy_rule_condition(self, row: Dict[str, Any], *, connection: Any = None) -> str:
        _ = connection
        return str(uuid.uuid4())

    def insert_policy_assignment_applicability(self, row: Dict[str, Any], *, connection: Any = None) -> str:
        _ = connection
        return str(uuid.uuid4())

    def insert_policy_family_applicability(self, row: Dict[str, Any], *, connection: Any = None) -> str:
        _ = connection
        return str(uuid.uuid4())

    def insert_policy_source_link(self, row: Dict[str, Any], *, connection: Any = None) -> None:
        _ = connection
        return None

    def update_policy_version_normalization_draft(
        self,
        version_id: str,
        draft: Dict[str, Any],
        *,
        request_id: Optional[str] = None,
        normalization_state: Optional[str] = None,
        connection: Any = None,
    ) -> None:
        _ = connection
        self.normalization_drafts[str(version_id)] = draft
        for v in self.versions:
            if str(v.get("version_id")) == str(version_id):
                if normalization_state is not None:
                    v["normalization_state"] = normalization_state
                break


def _base_doc(
    *,
    doc_id: str,
    company_id: str,
    processing_status: str = "complete",
    det_type: str = "assignment_policy",
    det_scope: str = SCOPE_LONG_TERM,
) -> Dict[str, Any]:
    return {
        "id": doc_id,
        "company_id": company_id,
        "processing_status": processing_status,
        "detected_document_type": det_type,
        "detected_policy_scope": det_scope,
        "extracted_metadata": {},
        "filename": "x.pdf",
        "mime_type": "application/pdf",
        "storage_path": "key/x.pdf",
        "raw_text": "placeholder body for normalization tests",
    }


def _clause(
    cid: str,
    *,
    ctype: str = "unknown",
    raw: str = "",
    hints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "id": cid,
        "policy_document_id": None,
        "clause_type": ctype,
        "raw_text": raw,
        "normalized_hint_json": hints or {},
        "confidence": 0.8,
    }


class RunNormalizationOutcomeTests(unittest.TestCase):
    def test_summary_known_scope_empty_layer2_draft_publishable_false(self) -> None:
        doc_id = str(uuid.uuid4())
        company_id = str(uuid.uuid4())
        doc = _base_doc(doc_id=doc_id, company_id=company_id, det_type=DOC_TYPE_POLICY_SUMMARY)
        clauses = [
            _clause(
                str(uuid.uuid4()),
                ctype="scope",
                raw="General principles of the mobility program.",
            )
        ]
        db = _FakePolicyDB()
        out = run_normalization(db, doc, clauses, request_id="t1")
        self.assertTrue(out.get("normalized"))
        self.assertFalse(out.get("publishable"))
        self.assertEqual(out.get("readiness_status"), "draft_no_benefits_or_exclusions")
        self.assertTrue(isinstance(out.get("readiness_issues"), list))
        self.assertEqual(len(db.versions), 1)
        self.assertIn("normalization_draft", out)
        nd = out["normalization_draft"]
        self.assertEqual(nd["schema_version"], 1)
        self.assertEqual(nd["document_metadata"]["detected_document_type"], DOC_TYPE_POLICY_SUMMARY)
        self.assertTrue(len(nd["clause_candidates"]) >= 1)
        self.assertEqual(len(nd["rule_candidates"]["benefit_rules"]), 0)
        self.assertEqual(nd["readiness"]["publish_readiness"]["status"], "not_ready")
        self.assertIn(str(out["policy_version_id"]), db.normalization_drafts)

    def test_exclusion_only_publishable(self) -> None:
        doc_id = str(uuid.uuid4())
        company_id = str(uuid.uuid4())
        doc = _base_doc(doc_id=doc_id, company_id=company_id)
        clauses = [
            _clause(str(uuid.uuid4()), ctype="exclusion", raw="Tax equalization does not apply in host country X.")
        ]
        db = _FakePolicyDB()
        out = run_normalization(db, doc, clauses, request_id="t2")
        self.assertTrue(out.get("publishable"))
        self.assertEqual(out.get("readiness_status"), "publishable")
        self.assertEqual(len(db.exclusion_rows), 1)

    def test_one_benefit_rule_publishable(self) -> None:
        doc_id = str(uuid.uuid4())
        company_id = str(uuid.uuid4())
        doc = _base_doc(doc_id=doc_id, company_id=company_id)
        clauses = [
            _clause(
                str(uuid.uuid4()),
                ctype="benefit",
                raw="Company provides housing allowance up to 5000 USD per month for eligible assignments.",
            )
        ]
        db = _FakePolicyDB()
        out = run_normalization(db, doc, clauses, request_id="t3")
        self.assertTrue(out.get("publishable"))
        self.assertGreater(len(db.benefit_rows), 0)

    def test_processing_failed_blocks_before_persist(self) -> None:
        doc_id = str(uuid.uuid4())
        company_id = str(uuid.uuid4())
        doc = _base_doc(doc_id=doc_id, company_id=company_id, processing_status="failed")
        clauses = [
            _clause(
                str(uuid.uuid4()),
                ctype="benefit",
                raw="Company provides housing allowance up to 5000 USD per month.",
            )
        ]
        db = _FakePolicyDB()
        with self.assertRaises(PolicyNormalizationPayloadInvalid) as ctx:
            run_normalization(db, doc, clauses, request_id="t4")
        self.assertEqual(ctx.exception.error_code, "NORMALIZATION_BLOCKED")
        self.assertEqual(len(db.versions), 0)

    def test_unknown_scope_empty_layer2_blocked(self) -> None:
        doc_id = str(uuid.uuid4())
        company_id = str(uuid.uuid4())
        doc = _base_doc(doc_id=doc_id, company_id=company_id, det_scope="unknown")
        clauses = [
            _clause(str(uuid.uuid4()), ctype="scope", raw="Narrative with no mappable benefits."),
        ]
        db = _FakePolicyDB()
        with self.assertRaises(PolicyNormalizationPayloadInvalid) as ctx:
            run_normalization(db, doc, clauses, request_id="t5")
        self.assertEqual(ctx.exception.error_code, "NORMALIZATION_BLOCKED")
        self.assertEqual(len(db.versions), 0)


if __name__ == "__main__":
    unittest.main()
