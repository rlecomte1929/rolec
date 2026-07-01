"""
Tests for the H3 corpus coverage report
(backend/scripts/report_corpus_coverage.py).

Offline-only (no DB, no network): builds a temp corpus dir with one complete
corridor corpus (covered) and a temp corridor registry with a corridor that has
no corpus (uncovered), then asserts the report classifies each correctly and the
aggregate counts add up. Also exercises the DB-mode SQL path against an in-memory
SQLite mirror of immigration_corpus_chunks (same pattern as
test_immigration_retriever.py — HashEmbedder, no key).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.scripts import report_corpus_coverage as rcc  # noqa: E402

# A minimal but valid corridor corpus (schema the indexer's build_chunks reads).
_COVERED_CORPUS = {
    "schema_version": "1.0.0",
    "corridor": {"from": "FR", "to": "NO", "classification": "eea_to_eea"},
    "fetched_at": "2026-06-15",
    "pathways": [
        {"visa_type": "eu_free_movement", "source_url": "https://gov.example/a", "source_tier": 1},
        {"visa_type": "family_reunification", "source_url": "https://gov.example/b", "source_tier": 1},
    ],
    "required_documents": [
        {"id": "d1", "visa_type": "eu_free_movement", "document_type": "passport",
         "source_url": "https://gov.example/d1", "source_tier": 1},
    ],
    "post_arrival_steps": [
        {"id": "s1", "order": 1, "source_url": "https://gov.example/s1", "source_tier": 1},
    ],
}


def _write_corpus_dir(corpus: dict, name: str = "fr_no_corridor.json") -> str:
    d = tempfile.mkdtemp(prefix="h3_corpus_")
    with open(os.path.join(d, name), "w", encoding="utf-8") as f:
        json.dump(corpus, f)
    return d


class OfflineCoverageTests(unittest.TestCase):
    def setUp(self):
        self.corpus_dir = _write_corpus_dir(_COVERED_CORPUS)
        # Registry universe includes one corridor WITH corpus (FR_NO) and one
        # WITHOUT (XX_YY) — so we get a covered and an uncovered classification.
        self.rows = rcc.build_coverage_offline(
            [self.corpus_dir], registry_corridors=["FR_NO", "XX_YY"]
        )
        self.by_id = {r.corridor: r for r in self.rows}

    def test_covered_corridor_classified_covered(self):
        fr_no = self.by_id["FR_NO"]
        self.assertTrue(fr_no.covered)
        self.assertEqual(fr_no.status, rcc.COVERED)
        self.assertGreater(fr_no.chunk_count, 0)
        self.assertIn("eu_free_movement", fr_no.pathway_types)
        self.assertTrue(fr_no.in_registry)
        self.assertTrue(fr_no.has_corpus_source)

    def test_uncovered_corridor_classified_generic_seed(self):
        xx = self.by_id["XX_YY"]
        self.assertFalse(xx.covered)
        self.assertEqual(xx.status, rcc.UNCOVERED)
        self.assertEqual(xx.chunk_count, 0)
        self.assertEqual(xx.pathway_types, [])
        self.assertTrue(xx.in_registry)
        self.assertFalse(xx.has_corpus_source)

    def test_aggregate_counts(self):
        summary = rcc.summarize(self.rows)
        self.assertEqual(summary["total_corridors"], 2)
        self.assertEqual(summary["covered_count"], 1)
        self.assertEqual(summary["uncovered_count"], 1)
        self.assertEqual(summary["covered_corridors"], ["FR_NO"])
        self.assertEqual(summary["uncovered_corridors"], ["XX_YY"])
        # The headline gap list: configured corridors with no content.
        self.assertEqual(summary["registry_corridors_needing_content"], ["XX_YY"])

    def test_corpus_corridor_outside_registry_still_covered(self):
        # A corridor that has corpus content but is NOT in the registry must still
        # appear and be covered (it renders a real roadmap even if not configured).
        rows = rcc.build_coverage_offline([self.corpus_dir], registry_corridors=[])
        by_id = {r.corridor: r for r in rows}
        self.assertIn("FR_NO", by_id)
        self.assertTrue(by_id["FR_NO"].covered)
        self.assertFalse(by_id["FR_NO"].in_registry)

    def test_dedupes_same_corridor_across_dirs(self):
        # The same corridor in two scanned dirs reports a representative (max)
        # single-file count, not the sum (the indexer replaces per corridor).
        other_dir = _write_corpus_dir(_COVERED_CORPUS)
        single = rcc.offline_corpus_index([self.corpus_dir])["FR_NO"]["chunk_count"]
        doubled = rcc.offline_corpus_index([self.corpus_dir, other_dir])["FR_NO"]["chunk_count"]
        self.assertEqual(single, doubled)

    def test_malformed_corpus_file_is_skipped(self):
        d = tempfile.mkdtemp(prefix="h3_corpus_bad_")
        with open(os.path.join(d, "broken_corridor.json"), "w", encoding="utf-8") as f:
            f.write("{ not valid json")
        # Must not raise; just yields no coverage.
        self.assertEqual(rcc.offline_corpus_index([d]), {})

    def test_report_shape_and_disclaimer(self):
        report = rcc.build_report(self.rows, mode="offline")
        self.assertEqual(report["mode"], "offline")
        self.assertIn("No synthetic", report["disclaimer"])
        self.assertEqual(len(report["corridors"]), 2)
        md = rcc.render_markdown(report)
        self.assertIn("generic seed", md)
        self.assertIn("XX_YY", md)


class DbCoverageTests(unittest.TestCase):
    """DB-mode SQL path over an in-memory SQLite mirror of immigration_corpus_chunks."""

    _SCHEMA = (
        "CREATE TABLE immigration_corpus_chunks ("
        "id TEXT PRIMARY KEY, corridor TEXT NOT NULL, source_url TEXT NOT NULL, "
        "chunk_text TEXT NOT NULL, chunk_index INTEGER NOT NULL, "
        "chunk_metadata TEXT DEFAULT '{}', trust_tier INTEGER NOT NULL DEFAULT 2, "
        "fetched_at TEXT NOT NULL, embedding TEXT, content_hash TEXT NOT NULL, "
        "is_active INTEGER DEFAULT 1)"
    )

    def _engine(self):
        eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        with eng.begin() as c:
            c.execute(text(self._SCHEMA))

            def seed(cid, corridor, pathway, active=1):
                c.execute(
                    text(
                        "INSERT INTO immigration_corpus_chunks "
                        "(id, corridor, source_url, chunk_text, chunk_index, chunk_metadata, "
                        " trust_tier, fetched_at, content_hash, is_active) VALUES "
                        "(:id,:cor,:u,:t,0,:m,1,:f,:h,:a)"
                    ),
                    {"id": cid, "cor": corridor, "u": "https://gov.example/x", "t": "rule",
                     "m": json.dumps({"corridor": corridor, "pathway_type": pathway}),
                     "f": "2026-06-06T00:00:00+00:00", "h": cid, "a": active},
                )

            seed("c1", "FR_NO", "eu_free_movement")
            seed("c2", "FR_NO", "family_reunification")
            seed("c3", "IN_DE", "blue_card")
            seed("c4", "ZZ_ZZ", "x", active=0)  # inactive → must not count
        return eng

    def test_db_mode_counts_and_pathways(self):
        rows = rcc.build_coverage_db(self._engine(), registry_corridors=["FR_NO", "XX_YY"])
        by_id = {r.corridor: r for r in rows}
        self.assertEqual(by_id["FR_NO"].chunk_count, 2)
        self.assertTrue(by_id["FR_NO"].covered)
        self.assertEqual(
            sorted(by_id["FR_NO"].pathway_types), ["eu_free_movement", "family_reunification"]
        )
        # IN_DE has DB rows but is not in the registry → still covered + present.
        self.assertTrue(by_id["IN_DE"].covered)
        # XX_YY is configured but has no rows → generic seed.
        self.assertFalse(by_id["XX_YY"].covered)
        # The inactive-only corridor must not surface as covered.
        self.assertNotIn("ZZ_ZZ", by_id)


if __name__ == "__main__":
    unittest.main()
