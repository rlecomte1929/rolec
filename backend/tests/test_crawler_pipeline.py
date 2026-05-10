"""
Tests for crawler pipeline components.
No Supabase required: mocks staging writes.
"""
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.crawler.config.models import CrawlSource, CONTENT_DOMAIN_TO_CATEGORY
from backend.crawler.config.registry import load_sources, get_sources_for_scope
from backend.crawler.parsers.html_parser import parse_html
from backend.crawler.chunkers.chunker import chunk_document, Chunk
from backend.crawler.extractors.resource_extractor import extract_resource_candidates
from backend.crawler.extractors.event_extractor import extract_event_candidates, _infer_event_type
from backend.crawler.fetchers.http_fetcher import fetch_page, FetchResult


class TestConfig(unittest.TestCase):
    def test_load_sources_fixture(self):
        fixtures = Path(__file__).resolve().parent.parent / "crawler" / "config" / "fixtures" / "sources_oslo_pilot.json"
        if fixtures.exists():
            sources = load_sources(fixtures)
            self.assertGreater(len(sources), 0)
            s = sources[0]
            self.assertEqual(s.country_code, "NO")
            self.assertIn("oslo", s.source_name.lower() or s.base_url.lower())

    def test_get_sources_for_scope(self):
        sources = [
            CrawlSource("a", "https://a.no", "NO", "Norway", "Oslo"),
            CrawlSource("b", "https://b.no", "NO", "Norway", "Bergen"),
        ]
        filtered = get_sources_for_scope(sources, country_code="NO", city_name="Oslo")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].city_name, "Oslo")


class TestHtmlParser(unittest.TestCase):
    def test_parse_html_basic(self):
        html = "<html><head><title>Test Page</title></head><body><h1>Heading</h1><p>Some content here.</p></body></html>"
        doc = parse_html(html)
        self.assertEqual(doc.page_title, "Test Page")
        self.assertIn("Some content", doc.main_text)
        self.assertEqual(len(doc.headings), 1)
        self.assertEqual(doc.headings[0]["text"], "Heading")

    def test_parse_empty(self):
        doc = parse_html("")
        self.assertEqual(doc.page_title, "")
        self.assertTrue(doc.parse_error is not None or not doc.main_text)


class TestChunker(unittest.TestCase):
    def test_chunk_document(self):
        from backend.crawler.parsers.html_parser import ParsedDocument
        doc = ParsedDocument(
            page_title="Test",
            main_text="This is a " + "word " * 100,
            headings=[{"level": 1, "text": "Section", "id": ""}],
        )
        chunks = chunk_document(doc, source_url="https://example.com", page_title="Test", country_code="NO", city_name="Oslo")
        self.assertGreater(len(chunks), 0)
        self.assertIsInstance(chunks[0], Chunk)
        self.assertEqual(chunks[0].country_code, "NO")
        self.assertTrue(chunks[0].chunk_hash)


class TestResourceExtractor(unittest.TestCase):
    def test_extract_candidates(self):
        source = CrawlSource(
            "test", "https://test.no", "NO", "Norway", "Oslo",
            trust_tier="T0", content_domain="admin_essentials",
        )
        chunk = Chunk(
            chunk_index=0,
            heading_path="Registration > Address",
            chunk_text="To register your address in Oslo, visit the citizen service centre. You need to bring your passport and proof of residence. The process takes about 15 minutes.",
            chunk_hash="abc",
        )
        candidates = extract_resource_candidates(
            [chunk],
            source,
            "https://test.no/page",
            "Oslo newcomer guide",
        )
        self.assertGreater(len(candidates), 0)
        c = candidates[0]
        self.assertEqual(c.country_code, "NO")
        self.assertEqual(c.city_name, "Oslo")
        self.assertIn("Address", c.title or "")
        self.assertEqual(c.extraction_method, "rule_based")
        self.assertIn("source_url", c.provenance)


class TestEventExtractor(unittest.TestCase):
    def test_infer_event_type(self):
        self.assertEqual(_infer_event_type("Summer concert", ""), "concert")
        self.assertEqual(_infer_event_type("Film screening", ""), "cinema")
        self.assertEqual(_infer_event_type("Museum exhibition", ""), "museum")


class TestFetchResult(unittest.TestCase):
    def test_fetch_result_success(self):
        r = FetchResult(
            url="https://example.com",
            final_url="https://example.com",
            content="<html><body>Hi</body></html>",
            content_type="text/html",
            http_status=200,
            content_hash="x",
            fetched_at="2024-01-01T00:00:00Z",
        )
        self.assertTrue(r.success)

    def test_fetch_result_failure(self):
        r = FetchResult(
            url="https://example.com",
            final_url="https://example.com",
            content="",
            content_type="text/html",
            http_status=404,
            content_hash="",
            fetched_at="2024-01-01T00:00:00Z",
            error="Not found",
        )
        self.assertFalse(r.success)


if __name__ == "__main__":
    unittest.main()
