"""
E1b (AIQ-929) — policy_documents upload → LLM value-extraction → persist.

Proves the new ``_run_policy_value_extraction`` wiring drives a *classified*
policy document through the LLM extractor and persists per-field-confidence
benefits to the real ``policy_extracted_benefits`` table, keyed by the
policy_document id (the canonical E1b lineage), and advances the document past
``processing_status='classified'`` to ``'normalized'``. Fail-soft behaviour
(LLM unavailable / raising) must never fail the upload or move the status.

Self-contained: in-memory SQLite patched into ``backend.database.db.engine``;
the LLM extractor is stubbed (no network, no ANTHROPIC_API_KEY needed). Belongs
in the deterministic CI job (DATABASE_URL=sqlite there).
"""
from __future__ import annotations

import os
import sys
import unittest

# Must be set before backend.main is imported (rate limits + query-counter event
# listener that errors against a patched engine).
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# backend/conftest.py installs a MagicMock at sys.modules["backend.database"] so
# *unit* tests don't need a DB. We exercise the real Database *methods*
# (replace_policy_benefits / update_policy_document / get_policy_document), so
# force-load the real module if the mock is still installed and grab the real
# Database *class* — instantiating it gives a genuine instance that we point at an
# in-memory schema and swap into backend.main.db per-test.
#
# Ordering contract (shared with the sibling real-DB tests test_policy_propagation
# / test_policy_config_matrix_propagation): real-DB tests bind backend.main to a
# real Database; the curated CI list keeps those siblings *before* this file, so
# backend.main is already imported against a real DB by the time we get here.
import importlib  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

if isinstance(sys.modules.get("backend.database"), MagicMock):
    sys.modules.pop("backend.database", None)
    sys.modules["backend.database"] = importlib.import_module("backend.database")
from backend.database import Database  # noqa: E402  (real class)

import backend.main as main  # noqa: E402
import backend.app.services.llm_policy_extractor as llm_extractor  # noqa: E402


SCHEMA = """
CREATE TABLE policy_documents (
    id                 TEXT PRIMARY KEY,
    company_id         TEXT,
    processing_status  TEXT,
    raw_text           TEXT,
    extraction_error   TEXT,
    extracted_metadata TEXT,
    processed_at       TEXT,
    updated_at         TEXT
);
CREATE TABLE policy_extracted_benefits (
    id               TEXT PRIMARY KEY,
    policy_id        TEXT NOT NULL,
    service_category TEXT NOT NULL,
    benefit_key      TEXT NOT NULL,
    benefit_label    TEXT NOT NULL,
    eligibility      TEXT,
    limits           TEXT,
    notes            TEXT,
    source_quote     TEXT,
    source_section   TEXT,
    confidence       REAL,
    updated_by       TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Two benefits with deliberately *different* confidences — the criterion is a
# non-flat confidence distribution on the persisted rows.
_FAKE_EXTRACTION = {
    "policy_meta": {"title": "Relocation Policy"},
    "benefits": [
        {
            "service_category": "relocation",
            "benefit_key": "temporary_housing",
            "benefit_label": "Temporary housing",
            "eligibility": {"who": "all assignees"},
            "limits": {"months": 3},
            "notes": None,
            "source_quote": "Company provides up to 3 months temporary housing.",
            "source_section": "4.1",
            "confidence": 0.92,
        },
        {
            "service_category": "support",
            "benefit_key": "language_training",
            "benefit_label": "Language training",
            "eligibility": None,
            "limits": None,
            "notes": "inferred",
            "source_quote": None,
            "source_section": None,
            "confidence": 0.30,
        },
    ],
    "extracted_by": "ai",
}


class E1bExtractionPersistTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.strip().split(";"):
                if stmt.strip():
                    conn.execute(text(stmt))
            conn.execute(
                text(
                    "INSERT INTO policy_documents (id, company_id, processing_status, raw_text) "
                    "VALUES (:id, :cid, 'classified', :rt)"
                ),
                {"id": "doc-x", "cid": "co-1", "rt": "Relocation policy text...\nline two"},
            )
        # Swap backend.main.db for a dedicated Database bound to our in-memory
        # schema for the duration of the test. The helper resolves `db` from
        # backend.main's module globals at call time, so this fully controls which
        # engine it writes through — robust against the cross-test Database
        # singleton divergence the real-DB harness can otherwise leak.
        self._orig_db = main.db
        self._test_db = Database()  # real instance; __init__ just binds an engine
        self._test_db.engine = self.engine
        main.db = self._test_db
        # Stub the LLM extractor (imported lazily inside the helper).
        self._orig_extract = llm_extractor.extract_policy_with_llm

    def tearDown(self) -> None:
        main.db = self._orig_db
        llm_extractor.extract_policy_with_llm = self._orig_extract

    def _status(self) -> str:
        with self.engine.connect() as conn:
            return conn.execute(
                text("SELECT processing_status FROM policy_documents WHERE id = 'doc-x'")
            ).scalar()

    def _benefit_rows(self) -> list:
        return self._test_db.list_policy_benefits("doc-x")

    def test_extraction_persists_benefits_with_confidence_and_advances_status(self) -> None:
        llm_extractor.extract_policy_with_llm = lambda lines, company_id=None: _FAKE_EXTRACTION

        ok = main._run_policy_value_extraction(
            doc_id="doc-x",
            raw_text="Relocation policy text...\nline two",
            company_id="co-1",
            updated_by="hr-1",
        )

        self.assertTrue(ok)
        rows = self._benefit_rows()
        self.assertEqual(len(rows), 2)
        # All persisted under the document id (canonical E1b lineage).
        self.assertTrue(all(r["policy_id"] == "doc-x" for r in rows))
        confidences = sorted(r["confidence"] for r in rows)
        self.assertTrue(all(c is not None for c in confidences))
        # Non-flat: the two confidences differ.
        self.assertNotEqual(confidences[0], confidences[1])
        self.assertEqual(confidences, [0.30, 0.92])
        # Status advanced out of 'classified' to the constraint-valid 'normalized'.
        self.assertEqual(self._status(), "normalized")

    def test_extraction_skips_when_llm_unavailable(self) -> None:
        # extract_policy_with_llm returns None when ANTHROPIC_API_KEY is unset.
        llm_extractor.extract_policy_with_llm = lambda lines, company_id=None: None

        ok = main._run_policy_value_extraction(
            doc_id="doc-x", raw_text="text", company_id="co-1", updated_by="hr-1"
        )

        self.assertFalse(ok)
        self.assertEqual(self._benefit_rows(), [])
        self.assertEqual(self._status(), "classified")  # untouched

    def test_extraction_is_fail_soft_on_error(self) -> None:
        def _boom(lines, company_id=None):
            raise RuntimeError("anthropic exploded")

        llm_extractor.extract_policy_with_llm = _boom

        ok = main._run_policy_value_extraction(
            doc_id="doc-x", raw_text="text", company_id="co-1", updated_by="hr-1"
        )

        self.assertFalse(ok)  # never raises
        self.assertEqual(self._benefit_rows(), [])
        self.assertEqual(self._status(), "classified")  # upload not failed
        with self.engine.connect() as conn:
            err = conn.execute(
                text("SELECT extraction_error FROM policy_documents WHERE id = 'doc-x'")
            ).scalar()
        self.assertIn("value_extraction_failed", err or "")


if __name__ == "__main__":
    unittest.main()
