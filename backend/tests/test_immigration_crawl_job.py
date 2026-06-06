"""
N1 / AIQ-840 — unit tests for the immigration crawl orchestrator.

All mocked: a fake fetcher (records fetched URLs) + an isolated in-memory
SQLite engine (StaticPool so it persists across begin() calls). No network,
no prod DB.
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from backend.crawler.jobs import immigration_crawl_job as job
from backend.crawler.parsers import immigration_page_parser

_NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)


def _make_engine():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with eng.begin() as c:
        c.execute(text(
            "CREATE TABLE crawled_immigration_documents ("
            "id TEXT PRIMARY KEY, corridor TEXT, source_url TEXT, trust_tier INTEGER, "
            "raw_html_path TEXT, extracted_text TEXT, content_hash TEXT, fetched_at TEXT, "
            "http_status INTEGER, crawl_error TEXT, is_active INTEGER)"
        ))
    return eng


def _count(eng, where: str = "") -> int:
    with eng.begin() as c:
        return c.execute(
            text(f"SELECT count(*) FROM crawled_immigration_documents {where}")
        ).scalar()


class FakeResult:
    def __init__(self, content="", http_status=200, error=None):
        self.content = content
        self.http_status = http_status
        self.error = error

    @property
    def success(self):
        return self.error is None and 200 <= self.http_status < 400


class FakeFetcher:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def __call__(self, url, **kw):
        self.calls.append(url)
        return self.pages.get(url, FakeResult(error="not found", http_status=404))


def _src(url, allowed_paths, *, max_depth=1, interval=14, tier=1):
    return {"FR_NO": {"corridor": "FR→NO", "sources": [{
        "url": url, "trust_tier": tier, "allowed_paths": allowed_paths,
        "max_depth": max_depth, "crawl_interval_days": interval,
    }]}}


_OK_PAGE = "<html><head><title>T</title></head><body><main><p>Apply for a permit.</p></main></body></html>"


class TestCrawlJob(unittest.TestCase):
    def test_allowed_paths_filters_discovered_links(self):
        seed = "https://ex.test/en/want-to-apply/"
        in_path = "https://ex.test/en/want-to-apply/forms/"
        out_path = "https://ex.test/en/other/"
        seed_html = (
            f'<html><body><main><p>hi</p>'
            f'<a href="{in_path}">in</a><a href="{out_path}">out</a></main></body></html>'
        )
        fetcher = FakeFetcher({
            seed: FakeResult(seed_html),
            in_path: FakeResult(_OK_PAGE),
            out_path: FakeResult(_OK_PAGE),
        })
        eng = _make_engine()
        job.run_crawl("FR_NO", sources=_src(seed, ["/en/want-to-apply/"], max_depth=2),
                      engine=eng, fetcher=fetcher, robots_allowed=lambda u: True, now=_NOW)
        self.assertIn(seed, fetcher.calls)
        self.assertIn(in_path, fetcher.calls)
        self.assertNotIn(out_path, fetcher.calls)  # criterion #4

    def test_unchanged_hash_updates_only(self):
        seed = "https://ex.test/en/want-to-apply/"
        fetcher = FakeFetcher({seed: FakeResult(_OK_PAGE)})
        eng = _make_engine()
        srcs = _src(seed, ["/en/want-to-apply/"], interval=14)
        job.run_crawl("FR_NO", sources=srcs, engine=eng, fetcher=fetcher,
                      robots_allowed=lambda u: True, now=_NOW)
        self.assertEqual(_count(eng), 1)
        # Re-run past the interval (so not stale) with identical content -> dedup, no new row.
        r2 = job.run_crawl("FR_NO", sources=srcs, engine=eng, fetcher=fetcher,
                           robots_allowed=lambda u: True, now=_NOW + timedelta(days=30))
        self.assertEqual(_count(eng), 1)
        self.assertEqual(r2.rows_skipped, 1)
        self.assertEqual(r2.rows_written, 0)

    def test_changed_hash_writes_new_row(self):
        seed = "https://ex.test/en/want-to-apply/"
        srcs = _src(seed, ["/en/want-to-apply/"], interval=14)
        eng = _make_engine()
        job.run_crawl("FR_NO", sources=srcs, engine=eng,
                      fetcher=FakeFetcher({seed: FakeResult(_OK_PAGE)}),
                      robots_allowed=lambda u: True, now=_NOW)
        changed = "<html><body><main><p>New rules effective 2027.</p></main></body></html>"
        r2 = job.run_crawl("FR_NO", sources=srcs, engine=eng,
                           fetcher=FakeFetcher({seed: FakeResult(changed)}),
                           robots_allowed=lambda u: True, now=_NOW + timedelta(days=30))
        self.assertEqual(_count(eng), 2)
        self.assertEqual(r2.rows_written, 1)

    def test_fetch_failure_writes_error_row_and_continues(self):
        seed = "https://ex.test/en/want-to-apply/"
        fetcher = FakeFetcher({seed: FakeResult(error="Timeout", http_status=0)})
        eng = _make_engine()
        res = job.run_crawl("FR_NO", sources=_src(seed, ["/en/want-to-apply/"]),
                            engine=eng, fetcher=fetcher, robots_allowed=lambda u: True, now=_NOW)
        self.assertEqual(res.rows_failed, 1)
        self.assertEqual(_count(eng, "WHERE crawl_error IS NOT NULL"), 1)
        self.assertEqual(_count(eng, "WHERE extracted_text IS NULL AND crawl_error IS NOT NULL"), 1)

    def test_robots_disallow_skips(self):
        seed = "https://ex.test/en/want-to-apply/"
        fetcher = FakeFetcher({seed: FakeResult(_OK_PAGE)})
        eng = _make_engine()
        res = job.run_crawl("FR_NO", sources=_src(seed, ["/en/want-to-apply/"]),
                            engine=eng, fetcher=fetcher, robots_allowed=lambda u: False, now=_NOW)
        self.assertEqual(res.rows_written, 0)
        self.assertEqual(fetcher.calls, [])  # never fetched

    def test_oslo_crawler_still_imports(self):
        # Criterion #6 — do not break the existing Oslo crawler.
        import backend.relopass.jobs.rule_scraper  # noqa: F401


class TestParser(unittest.TestCase):
    def test_structure_and_unicode(self):
        html = (
            "<html><head><title>Opphold</title></head><body><main>"
            "<h1>Søknad</h1><p>Du må betale gebyr.</p>"
            "<ul><li>Pass</li><li>Visum für Deutschland</li></ul>"
            "<table><tr><th>Type</th><th>Tid</th></tr><tr><td>Arbeid</td><td>14</td></tr></table>"
            "</main></body></html>"
        )
        out = immigration_page_parser.parse(html)
        self.assertEqual(out["title"], "Opphold")
        self.assertIn("# Søknad", out["text"])
        self.assertIn("- Pass", out["text"])
        self.assertIn("Visum für Deutschland", out["text"])  # German umlaut preserved
        self.assertIn("Type | Tid", out["text"])  # table as pipes
        self.assertGreater(out["word_count"], 0)

    def test_empty_html(self):
        self.assertEqual(immigration_page_parser.parse(""), {"title": "", "text": "", "word_count": 0})


class TestScoping(unittest.TestCase):
    def test_path_allowed(self):
        self.assertTrue(job._path_allowed("https://x.test/en/visa/abc", ["/en/visa/"]))
        self.assertFalse(job._path_allowed("https://x.test/en/other/", ["/en/visa/"]))
        self.assertTrue(job._path_allowed("https://x.test/anything", []))  # empty = allow all


if __name__ == "__main__":
    unittest.main()
