"""Transactional normalization persistence + publish gate markers."""
from __future__ import annotations

import copy
import os
import sys
import unittest
import uuid
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.exc import OperationalError

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_document_intake import DOC_TYPE_POLICY_SUMMARY, SCOPE_LONG_TERM
from backend.services.policy_normalization import run_normalization
from backend.services.policy_normalization_errors import PolicyNormalizationPayloadInvalid
from backend.services.policy_normalization_states import (
    NORMALIZATION_STATE_COMPLETE,
    NORMALIZATION_STATE_DRAFT,
    NORMALIZATION_STATE_IN_PROGRESS,
)
from backend.services.policy_publish_gate import (
    PUBLISH_BLOCKED_NORMALIZATION_INCOMPLETE,
    PUBLISH_BLOCKED_SOURCE_DOCUMENT_FAILED,
    evaluate_employee_publish_blockers,
)


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


def _doc(
    doc_id: str,
    company_id: str,
    *,
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


class _TransactionalFakePolicyDB:
    """Fake DB with atomic run_policy_normalization_transaction (rollback on error)."""

    def __init__(self, *, fail_on: Optional[str] = None) -> None:
        self.policies: List[Dict[str, Any]] = []
        self.versions: List[Dict[str, Any]] = []
        self.benefit_rows: List[Dict[str, Any]] = []
        self.exclusion_rows: List[Dict[str, Any]] = []
        self.normalization_drafts: Dict[str, Dict[str, Any]] = {}
        self._fail_on = fail_on

    def list_company_policies(self, company_id: str) -> List[Dict[str, Any]]:
        return [p for p in self.policies if p.get("company_id") == company_id]

    def list_policy_versions(self, policy_id: str) -> List[Dict[str, Any]]:
        return [v for v in self.versions if v.get("policy_id") == policy_id]

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

    def create_company_policy(self, **kwargs: Any) -> None:
        conn = kwargs.pop("connection", None)
        _ = conn
        if self._fail_on == "company_policy":
            raise OperationalError("INSERT company_policies", {}, Exception("simulated company_policy failure"))
        self.policies.append(dict(kwargs))

    def create_policy_version(self, **kwargs: Any) -> None:
        kwargs.pop("connection", None)
        if self._fail_on == "policy_version":
            raise OperationalError("INSERT policy_versions", {}, Exception("simulated policy_version failure"))
        self.versions.append(dict(kwargs))

    def insert_policy_benefit_rule(self, rule: Dict[str, Any], *, connection: Any = None) -> str:
        _ = connection
        if self._fail_on == "layer2":
            raise OperationalError("INSERT policy_benefit_rules", {}, Exception("simulated layer2 failure"))
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


class PolicyNormalizationPersistenceTests(unittest.TestCase):
    def test_success_marks_normalized_draft_or_complete(self) -> None:
        doc_id = str(uuid.uuid4())
        company_id = str(uuid.uuid4())
        doc = _doc(doc_id=doc_id, company_id=company_id, det_type=DOC_TYPE_POLICY_SUMMARY)
        clauses = [_clause(str(uuid.uuid4()), ctype="scope", raw="General mobility principles.")]
        db = _TransactionalFakePolicyDB()
        out = run_normalization(db, doc, clauses, request_id="p1")
        self.assertTrue(out.get("normalized"))
        self.assertEqual(len(db.versions), 1)
        st = out.get("normalization_state")
        self.assertIn(st, (NORMALIZATION_STATE_DRAFT, NORMALIZATION_STATE_COMPLETE))
        self.assertEqual(db.versions[0].get("normalization_state"), st)

    def test_failure_before_policy_version_leaves_no_version(self) -> None:
        doc_id = str(uuid.uuid4())
        company_id = str(uuid.uuid4())
        doc = _doc(doc_id=doc_id, company_id=company_id)
        clauses = [
            _clause(
                str(uuid.uuid4()),
                ctype="benefit",
                raw="Company provides housing allowance up to 5000 USD per month.",
            )
        ]
        db = _TransactionalFakePolicyDB(fail_on="policy_version")
        with self.assertRaises(PolicyNormalizationPayloadInvalid) as ctx:
            run_normalization(db, doc, clauses, request_id="p2")
        self.assertEqual(ctx.exception.persistence_stage, "normalization_transaction")
        self.assertEqual(len(db.versions), 0)
        self.assertEqual(len(db.benefit_rows), 0)
        self.assertEqual(len(db.policies), 0)

    def test_failure_after_version_before_layer2_completes_rollbacks(self) -> None:
        doc_id = str(uuid.uuid4())
        company_id = str(uuid.uuid4())
        doc = _doc(doc_id=doc_id, company_id=company_id)
        clauses = [
            _clause(
                str(uuid.uuid4()),
                ctype="benefit",
                raw="Company provides housing allowance up to 5000 USD per month.",
            )
        ]
        db = _TransactionalFakePolicyDB(fail_on="layer2")
        with self.assertRaises(PolicyNormalizationPayloadInvalid):
            run_normalization(db, doc, clauses, request_id="p3")
        self.assertEqual(len(db.versions), 0)
        self.assertEqual(len(db.benefit_rows), 0)

    def test_publish_gate_rejects_in_progress_marker(self) -> None:
        class _Mini:
            def get_policy_version(self, vid: str) -> Dict[str, Any]:
                return {
                    "id": vid,
                    "source_policy_document_id": str(uuid.uuid4()),
                    "auto_generated": True,
                    "normalization_state": NORMALIZATION_STATE_IN_PROGRESS,
                }

            def list_policy_benefit_rules(self, vid: str) -> List[Dict[str, Any]]:
                return [{"id": "1", "benefit_key": "temporary_housing"}]

            def list_policy_exclusions(self, vid: str) -> List[Dict[str, Any]]:
                return []

            def get_policy_document(self, did: str, request_id: Any = None) -> Dict[str, Any]:
                return {"id": did, "processing_status": "complete"}

        block = evaluate_employee_publish_blockers(_Mini(), str(uuid.uuid4()))
        self.assertIsNotNone(block)
        assert block is not None
        self.assertEqual(block[0], PUBLISH_BLOCKED_NORMALIZATION_INCOMPLETE)

    def test_publish_gate_rejects_failed_source_doc_after_normalized_complete(self) -> None:
        class _Mini:
            def get_policy_version(self, vid: str) -> Dict[str, Any]:
                return {
                    "id": vid,
                    "source_policy_document_id": "d1",
                    "auto_generated": True,
                    "normalization_state": NORMALIZATION_STATE_COMPLETE,
                }

            def list_policy_benefit_rules(self, vid: str) -> List[Dict[str, Any]]:
                return [{"id": "1", "benefit_key": "temporary_housing"}]

            def list_policy_exclusions(self, vid: str) -> List[Dict[str, Any]]:
                return []

            def get_policy_document(self, did: str, request_id: Any = None) -> Dict[str, Any]:
                return {"id": did, "processing_status": "failed"}

        block = evaluate_employee_publish_blockers(_Mini(), str(uuid.uuid4()))
        self.assertIsNotNone(block)
        assert block is not None
        self.assertEqual(block[0], PUBLISH_BLOCKED_SOURCE_DOCUMENT_FAILED)


if __name__ == "__main__":
    unittest.main()
