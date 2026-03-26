"""Tests for policy assistant document import pipeline and case context."""
from __future__ import annotations

import os
import sys
import unittest
import uuid

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.policy_assistant_case_context_service import (  # noqa: E402
    build_policy_assistant_context,
    fact_applies_to_case_profile,
    get_source_chunks_for_fact_ids,
)
from backend.services.policy_fact_extraction_service import extract_minimal_policy_facts  # noqa: E402
from backend.services.policy_knowledge_snapshot_service import PolicyKnowledgeSnapshotService  # noqa: E402
from backend.services.policy_text_extraction_service import build_chunks  # noqa: E402


class PolicyAssistantImportTests(unittest.TestCase):
    def test_chunk_builds_sections(self) -> None:
        text = "SHORT-TERM POLICY\n\nHousing: up to USD 5,000 per month for eligible employees.\n"
        chunks = build_chunks(text)
        self.assertTrue(len(chunks) >= 1)
        self.assertIn("text_content", chunks[0])
        self.assertIn("USD", chunks[0]["text_content"])

    def test_extract_minimal_policy_facts_traceability(self) -> None:
        cid = str(uuid.uuid4())
        chunks = [
            {
                "id": cid,
                "chunk_index": 0,
                "text_content": (
                    "Long-term assignment: housing allowance up to USD 4,000 per month. "
                    "Approval required from HR. Spouse travel not covered."
                ),
                "section_title": "Benefits",
                "page_number": 1,
            }
        ]
        facts = extract_minimal_policy_facts(chunks)
        self.assertTrue(facts)
        for f in facts:
            self.assertEqual(f["source_chunk_id"], cid)
            self.assertTrue(f.get("source_quote"))
        types = {f["fact_type"] for f in facts}
        self.assertTrue(types & {"benefit", "allowance_cap", "approval_requirement", "excluded_item"})

    def test_soft_language_and_destination_hints_in_applicability(self) -> None:
        cid = str(uuid.uuid4())
        chunks = [
            {
                "id": cid,
                "chunk_index": 0,
                "text_content": (
                    "Short-term assignment to Singapore: costs may be reimbursed subject to approval "
                    "from HR. Exceptional cases at the discretion of mobility."
                ),
                "section_title": "STA",
                "page_number": 2,
            }
        ]
        facts = extract_minimal_policy_facts(chunks)
        self.assertTrue(facts)
        merged_app = {}
        for f in facts:
            merged_app.update(f.get("applicability_json") or {})
            if f.get("ambiguity_flag"):
                pass
        self.assertTrue(any(f.get("ambiguity_flag") for f in facts))
        self.assertIn("destination_countries", merged_app)

    def test_fact_applicability_filter_assignment_type(self) -> None:
        fact = {
            "applicability_json": {"assignment_types": ["long_term"]},
        }
        profile_ok = {"assignment_type": "long_term"}
        profile_bad = {"assignment_type": "short_term"}
        self.assertTrue(fact_applies_to_case_profile(fact, profile_ok))
        self.assertFalse(fact_applies_to_case_profile(fact, profile_bad))

    def test_snapshot_supersedes_prior_active(self) -> None:
        class _Db:
            def __init__(self) -> None:
                self.activate_calls: list = []
                self.snapshots: list = []
                self.facts: list = []

            def insert_policy_knowledge_snapshot(self, *a, **k):
                sid = str(uuid.uuid4())
                self.snapshots.append({"id": sid, "status": k.get("status", "failed")})
                return sid

            def insert_policy_fact(self, snapshot_id, fact_type, category, **kwargs):
                self.facts.append({"snapshot_id": snapshot_id, "fact_type": fact_type})

            def activate_policy_knowledge_snapshot(
                self, new_snapshot_id, company_id, policy_document_id, activated_by_user_id
            ):
                self.activate_calls.append((company_id, new_snapshot_id, policy_document_id, activated_by_user_id))

            def mark_policy_snapshot_failed(self, snapshot_id: str) -> None:
                pass

            def policy_assistant_tables_available(self) -> bool:
                return True

        db = _Db()
        svc = PolicyKnowledgeSnapshotService(db)  # type: ignore[arg-type]
        doc_id = str(uuid.uuid4())
        company_id = "co1"
        facts = [
            {
                "fact_type": "benefit",
                "category": "housing",
                "normalized_value_json": {},
                "applicability_json": {},
                "ambiguity_flag": True,
                "confidence_score": 0.3,
                "source_chunk_id": "chunk-1",
                "source_quote": "x",
            }
        ]
        sid = svc.create_snapshot_from_document(company_id, doc_id, facts, activate=True)
        self.assertEqual(len(db.activate_calls), 1)
        self.assertEqual(db.activate_calls[0][0], company_id)
        self.assertEqual(db.activate_calls[0][1], sid)
        self.assertEqual(db.facts[0]["snapshot_id"], sid)

    def test_get_source_chunks_for_fact_ids_empty(self) -> None:
        class _Db:
            policy_assistant_tables_available = lambda self: False  # noqa: E731

        out = get_source_chunks_for_fact_ids(_Db(), [])  # type: ignore[arg-type]
        self.assertEqual(out, [])

    def test_build_policy_assistant_context_no_tables(self) -> None:
        class _Db:
            policy_assistant_tables_available = lambda self: False  # noqa: E731

            engine = None

        ctx = build_policy_assistant_context(_Db(), str(uuid.uuid4()))  # type: ignore[arg-type]
        self.assertFalse(ctx.get("policy_knowledge_available"))


if __name__ == "__main__":
    unittest.main()
