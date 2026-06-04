"""
P2-06d · Tests for the corridor-corpus → immigration_requirements mapper.

Fixture-free: builds tiny in-memory corpus dicts and asserts the mapping +
the generated SQL shape. No DB, no network. Also runs the two real corpus
files (committed under corpus/) through the mapper to pin the expected row
counts the task's validation criteria depend on.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

# scripts/ is importable as `scripts.<mod>` from backend/ (pytest.ini sets pythonpath=.)
_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from scripts.ingest_corridor_corpus import (  # noqa: E402
    COLUMNS,
    CONFLICT_KEY,
    build_sql,
    map_corpus,
    map_document,
)

_REPO_ROOT = _BACKEND.parent
_CORPUS_DIR = _REPO_ROOT / "corpus"


class MapDocumentTests(unittest.TestCase):
    def test_full_document_maps_every_column(self):
        doc = {
            "id": "us_fr_lsv_passport",
            "corridor_from": "US", "corridor_to": "FR", "visa_type": "long_stay_visa",
            "employee_type": "any", "document_type": "passport",
            "document_name": "Valid US Passport",
            "is_required": True, "is_conditional": False,
            "freshness_days": None,
            "requires_apostille": False, "requires_translation": False,
            "can_be_prefilled": True, "can_be_ocr_extracted": True,
            "vault_field_mapping": "identity.passport.number",
            "typical_processing_days": 0,
            "validity_min_days_after_visa_expiry": 90,   # corpus-only, dropped
            "source_url": "https://france-visas.gouv.fr/x", "source_tier": 1,
        }
        row = map_document(doc, fetched_at="2026-06-04")
        # every declared column is present in the mapped row
        self.assertEqual(set(name for name, _ in COLUMNS), set(row.keys()))
        # source_url is lifted to instructions_url; fetched_at to last_verified_date
        self.assertEqual(row["instructions_url"], "https://france-visas.gouv.fr/x")
        self.assertEqual(row["last_verified_date"], "2026-06-04")
        self.assertEqual(row["source"], "corridor_corpus")
        # corpus-only fields are not leaked as columns
        self.assertNotIn("validity_min_days_after_visa_expiry", row)
        self.assertNotIn("source_tier", row)

    def test_defaults_for_sparse_document(self):
        row = map_document(
            {"corridor_from": "IN", "corridor_to": "DE", "visa_type": "blue_card",
             "document_type": "cv", "document_name": "CV"},
            fetched_at=None,
        )
        self.assertEqual(row["employee_type"], "any")
        self.assertTrue(row["is_required"])          # default True
        self.assertFalse(row["is_conditional"])      # default False
        self.assertEqual(row["apostille_countries"], [])
        self.assertEqual(row["translation_languages"], [])
        self.assertEqual(row["success_tips"], [])
        self.assertIsNone(row["last_verified_date"])


class BuildSqlTests(unittest.TestCase):
    def _corpus(self, supersede=False):
        c = {
            "corridor": {"from": "IN", "to": "DE"},
            "fetched_at": "2026-06-04",
            "required_documents": [
                {"corridor_from": "IN", "corridor_to": "DE", "visa_type": "blue_card",
                 "document_type": "passport", "document_name": "P",
                 "success_tips": ["keep it valid"], "source_url": "https://x"},
            ],
        }
        if supersede:
            c["supersedes_db_seed"] = {"note": "stale", "row_count_after_target": 1}
        return c

    def _write(self, corpus):
        p = Path(self.tmp.name) / "c.json"
        p.write_text(json.dumps(corpus), encoding="utf-8")
        return str(p)

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_upsert_only_without_supersede(self):
        sql = build_sql([self._write(self._corpus(supersede=True))], supersede=False)
        self.assertNotIn("DELETE FROM", sql)
        self.assertIn("INSERT INTO public.immigration_requirements", sql)
        self.assertIn("ON CONFLICT (" + ", ".join(CONFLICT_KEY) + ") DO UPDATE", sql)

    def test_no_txn_wrapper_by_default_but_optin_works(self):
        files = [self._write(self._corpus())]
        self.assertNotIn("BEGIN;", build_sql(files, supersede=False))           # migration default
        wrapped = build_sql(files, supersede=False, wrap_transaction=True)
        self.assertIn("BEGIN;", wrapped)
        self.assertIn("COMMIT;", wrapped)

    def test_supersede_emits_scoped_delete_before_insert(self):
        sql = build_sql([self._write(self._corpus(supersede=True))], supersede=True)
        delete_idx = sql.index("DELETE FROM public.immigration_requirements")
        insert_idx = sql.index("INSERT INTO public.immigration_requirements")
        self.assertLess(delete_idx, insert_idx)               # delete precedes insert
        self.assertIn("corridor_from = 'IN'", sql)
        self.assertIn("visa_type = 'blue_card'", sql)

    def test_jsonb_and_quote_escaping(self):
        corpus = self._corpus()
        corpus["required_documents"][0]["success_tips"] = ["it's fine"]
        sql = build_sql([self._write(corpus)], supersede=False)
        self.assertIn("::jsonb", sql)
        self.assertIn("it''s fine", sql)                      # single-quote escaped


class RealCorpusCountTests(unittest.TestCase):
    """Pin the row counts the task's validation SQL asserts (US→FR=12, IN→DE=11)."""

    @unittest.skipUnless((_CORPUS_DIR / "us_fr_corridor.json").exists(),
                         "us_fr corpus not present")
    def test_us_fr_yields_12_rows(self):
        corpus = json.load(open(_CORPUS_DIR / "us_fr_corridor.json", encoding="utf-8"))
        rows = map_corpus(corpus)
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(r["corridor_from"] == "US" and r["corridor_to"] == "FR" for r in rows))

    @unittest.skipUnless((_CORPUS_DIR / "in_de_corridor.json").exists(),
                         "in_de corpus not present")
    def test_in_de_yields_11_blue_card_rows(self):
        corpus = json.load(open(_CORPUS_DIR / "in_de_corridor.json", encoding="utf-8"))
        rows = map_corpus(corpus)
        self.assertEqual(len(rows), 11)
        self.assertTrue(all(r["visa_type"] == "blue_card" for r in rows))


if __name__ == "__main__":
    unittest.main()
