"""AIQ-806 · Tests for the corridor-corpus → source_pages tier backfill.

Fixture-free: builds tiny in-memory corpus dicts and asserts the URL/tier
collection, dedup, and the generated SQL shape (idempotent ON CONFLICT). Also
runs the committed corpus/*.json files through the collector to pin that real
corridors yield tiered rows. No DB, no network.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from scripts.backfill_source_pages_from_corpus import (  # noqa: E402
    build_sql,
    collect_all,
    collect_source_pages,
)

_CORPUS_DIR = _BACKEND.parent / "corpus"


class CollectSourcePagesTests(unittest.TestCase):
    def test_collects_required_documents_and_primary_sources(self):
        corpus = {
            "fetched_at": "2026-06-04",
            "primary_sources": [
                {"url": "https://gov.example/primary", "tier": 1, "title": "Primary"},
            ],
            "required_documents": [
                {"source_url": "https://gov.example/doc", "source_tier": 2},
            ],
        }
        got = collect_source_pages(corpus)
        self.assertEqual(got["https://gov.example/primary"], ("1", "2026-06-04"))
        self.assertEqual(got["https://gov.example/doc"], ("2", "2026-06-04"))

    def test_skips_urls_without_a_tier(self):
        # No fabricated default '1' — a URL with no tier is dropped (honest).
        corpus = {
            "fetched_at": "2026-06-04",
            "required_documents": [
                {"source_url": "https://gov.example/no-tier"},
                {"source_url": "https://gov.example/blank-tier", "source_tier": "  "},
                {"source_url": "", "source_tier": 1},
            ],
        }
        self.assertEqual(collect_source_pages(corpus), {})

    def test_first_tier_wins_within_file(self):
        corpus = {
            "fetched_at": "2026-06-04",
            "required_documents": [
                {"source_url": "https://gov.example/dup", "source_tier": 1},
                {"source_url": "https://gov.example/dup", "source_tier": 3},
            ],
        }
        self.assertEqual(collect_source_pages(corpus)["https://gov.example/dup"], ("1", "2026-06-04"))


class BuildSqlTests(unittest.TestCase):
    def _tmp_corpus(self, tmp_path: Path, name: str, payload: dict) -> str:
        import json
        p = tmp_path / name
        p.write_text(json.dumps(payload), encoding="utf-8")
        return str(p)

    def test_sql_is_idempotent_upsert(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = self._tmp_corpus(
                Path(d), "c.json",
                {"fetched_at": "2026-06-04",
                 "required_documents": [{"source_url": "https://gov.example/a", "source_tier": 2}]},
            )
            sql = build_sql([f])
        self.assertIn("INSERT INTO public.source_pages (url, tier, last_fetched_at)", sql)
        self.assertIn("ON CONFLICT (url) DO UPDATE SET", sql)
        # tier overwritten (corpus authoritative); crawler fetch ts preserved.
        self.assertIn("tier = EXCLUDED.tier", sql)
        self.assertIn("last_fetched_at = COALESCE(public.source_pages.last_fetched_at, EXCLUDED.last_fetched_at)", sql)
        self.assertIn("('https://gov.example/a', '2', '2026-06-04'::timestamptz)", sql)

    def test_single_quote_is_escaped(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = self._tmp_corpus(
                Path(d), "c.json",
                {"fetched_at": "2026-06-04",
                 "required_documents": [{"source_url": "https://gov.example/o'brien", "source_tier": 1}]},
            )
            sql = build_sql([f])
        self.assertIn("https://gov.example/o''brien", sql)

    def test_empty_corpus_emits_no_insert(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = self._tmp_corpus(Path(d), "c.json", {"fetched_at": "2026-06-04", "required_documents": []})
            sql = build_sql([f])
        self.assertNotIn("INSERT INTO", sql)
        self.assertIn("nothing to upsert", sql)


class RealCorpusTests(unittest.TestCase):
    def test_committed_corridors_yield_tiered_rows(self):
        files = sorted(str(p) for p in _CORPUS_DIR.glob("*_corridor.json"))
        self.assertTrue(files, "expected corridor corpus files under corpus/")
        rows = collect_all(files)
        self.assertGreater(len(rows), 16, "backfill should exceed the 16-row form_templates seed")
        tiers = {tier for _, tier, _ in rows}
        # Real provenance is not uniform — at least two distinct tiers present.
        self.assertGreaterEqual(len(tiers), 2)
        self.assertTrue(tiers.issubset({"1", "2", "3"}))
        # Dedup invariant: every URL appears once.
        urls = [url for url, _, _ in rows]
        self.assertEqual(len(urls), len(set(urls)))


if __name__ == "__main__":
    unittest.main()
