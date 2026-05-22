"""[P5-9 H2] Audit log row on every policy assistant retrieval.

Hard contract enforced here:
  - Every successful retrieval writes exactly one row into ``audit_log``
    with ``action_type='policy.queried'`` and ``target_type='policy_assistant'``.
  - ``target_id`` = the opaque session token (NOT the raw question).
  - ``metadata_json`` contains the SHA-256 question hash, company_id,
    retrieved chunk_ids, and an ISO retrieved_at timestamp.
  - The raw question text never appears in metadata_json under any key.
  - Audit-write failures must NOT break the retrieval — they're logged
    and swallowed (covered by a separate broken-engine test).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Force the deterministic fallback path — answer() needs no LLM client.
os.environ.pop("OPENAI_API_KEY", None)

from backend.services.policy_query_answering import (  # noqa: E402
    answer_company_scoped_policy_query,
    _hash_question,
)


AUDIT_LOG_SCHEMA = """
CREATE TABLE audit_log (
    id            TEXT NOT NULL,
    actor_user_id TEXT NOT NULL,
    action_type   TEXT NOT NULL,
    target_type   TEXT NOT NULL,
    target_id     TEXT,
    metadata_json TEXT,
    created_at    TEXT NOT NULL
);
"""


class _FakeDb:
    """Thin fake exposing only the methods the retrieval path touches.

    The `engine` attribute is a real in-memory sqlite engine so the
    audit_log INSERT actually executes against a table we can inspect.
    """

    def __init__(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            conn.execute(text(AUDIT_LOG_SCHEMA))
        self._canonical_audit_logs: List[Dict[str, Any]] = []
        self._document = {
            "id": "doc-1",
            "company_id": "company-1",
            "title": "Acme Policy",
            "filename": "acme-policy.pdf",
            "extraction_status": "extracted",
        }
        self._chunks = [
            {
                "id": "chunk-1",
                "company_id": "company-1",
                "canonical_policy_document_id": "doc-1",
                "chunk_index": 0,
                "section_path": "Assignment > Mobility premium",
                "structure_type": "paragraph",
                "text_content": "Mobility premium of 10% applies for all LTA assignments.",
            },
        ]
        self._facts: List[Dict[str, Any]] = []

    # ── Methods the retrieval path calls ────────────────────────────────────

    def get_canonical_policy_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        return self._document if doc_id == self._document["id"] else None

    def get_active_canonical_policy_document_for_company(self, company_id: str):
        return self._document if company_id == self._document["company_id"] else None

    def list_canonical_policy_document_chunks(self, doc_id: str, *, company_id=None):
        return [c for c in self._chunks if c["canonical_policy_document_id"] == doc_id]

    def list_canonical_policy_facts(self, doc_id: str, *, company_id=None, tier=None):
        return [f for f in self._facts if f["canonical_policy_document_id"] == doc_id]

    def insert_canonical_policy_query_audit_log(self, **kwargs: Any) -> str:
        self._canonical_audit_logs.append(kwargs)
        return f"audit-{len(self._canonical_audit_logs)}"


def _read_audit_rows(engine) -> List[Dict[str, Any]]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, actor_user_id, action_type, target_type, "
                "target_id, metadata_json, created_at FROM audit_log"
            )
        ).mappings().fetchall()
    return [dict(row) for row in rows]


class PolicyQueryAuditLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = _FakeDb()

    def test_retrieval_writes_audit_log_row(self) -> None:
        question = "What is the mobility premium?"
        result = answer_company_scoped_policy_query(
            self.db,
            company_id="company-1",
            user_id="user-emp-1",
            user_role="EMPLOYEE",
            query=question,
            session_id="session-abc",
        )
        rows = _read_audit_rows(self.db.engine)
        self.assertEqual(len(rows), 1, f"expected 1 audit row, got {rows}")
        row = rows[0]
        self.assertEqual(row["actor_user_id"], "user-emp-1")
        self.assertEqual(row["action_type"], "policy.queried")
        self.assertEqual(row["target_type"], "policy_assistant")
        self.assertEqual(row["target_id"], "session-abc")
        self.assertTrue(row["id"], "audit row must have a non-empty uuid id")
        self.assertTrue(row["created_at"], "audit row must have created_at set")

        metadata = json.loads(row["metadata_json"])
        self.assertEqual(metadata["company_id"], "company-1")
        self.assertEqual(metadata["question_hash"], _hash_question(question))
        self.assertEqual(
            metadata["question_hash"],
            hashlib.sha256(question.lower().encode("utf-8")).hexdigest(),
            "hash must use lowercased+whitespace-collapsed canonical form",
        )
        self.assertEqual(metadata["chunk_ids"], result["retrieved_chunk_ids"])
        self.assertIn("retrieved_at", metadata)

    def test_raw_question_never_appears_in_metadata(self) -> None:
        question = "what's the policy for passport AB1234567"
        answer_company_scoped_policy_query(
            self.db,
            company_id="company-1",
            user_id="user-emp-1",
            user_role="EMPLOYEE",
            query=question,
            session_id="session-pii",
        )
        rows = _read_audit_rows(self.db.engine)
        self.assertEqual(len(rows), 1)
        metadata_blob = rows[0]["metadata_json"] or ""

        # The raw question and the embedded passport number must not
        # appear anywhere in the audit row — even as a substring.
        self.assertNotIn(question, metadata_blob)
        self.assertNotIn(question.lower(), metadata_blob)
        self.assertNotIn("passport", metadata_blob.lower())
        self.assertNotIn("AB1234567", metadata_blob)

        # And there must be no field named "query" / "query_text" /
        # "question" carrying any plaintext.
        metadata = json.loads(metadata_blob)
        for forbidden in ("query", "query_text", "question", "raw_query"):
            self.assertNotIn(forbidden, metadata)

    def test_session_id_is_generated_when_not_supplied(self) -> None:
        result = answer_company_scoped_policy_query(
            self.db,
            company_id="company-1",
            user_id="user-emp-1",
            user_role="EMPLOYEE",
            query="mobility premium?",
        )
        self.assertTrue(result.get("session_id"))
        rows = _read_audit_rows(self.db.engine)
        self.assertEqual(rows[0]["target_id"], result["session_id"])

    def test_audit_write_failure_does_not_break_retrieval(self) -> None:
        # Drop the audit_log table so the INSERT raises. The retrieval
        # must still return a sane answer.
        with self.db.engine.begin() as conn:
            conn.execute(text("DROP TABLE audit_log"))
        result = answer_company_scoped_policy_query(
            self.db,
            company_id="company-1",
            user_id="user-emp-1",
            user_role="EMPLOYEE",
            query="mobility premium?",
        )
        self.assertIn("answer", result)
        self.assertEqual(result["canonical_policy_document_id"], "doc-1")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
