"""
Tests for backend/services/catalog_scraper.py — Phase 2b.

The real implementation calls OpenAI; tests mock that out so we never
hit the network and never need an API key.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import catalog_scraper, service_catalog  # noqa: E402


SCHEMA = """
CREATE TABLE service_catalog_items (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    city TEXT,
    country TEXT,
    name TEXT NOT NULL,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    source TEXT NOT NULL DEFAULT 'manual',
    active INTEGER NOT NULL DEFAULT 1,
    external_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id TEXT,
    UNIQUE (category, external_id)
);
"""


def _fake_client(payload: dict):
    """Build a mock OpenAI client whose chat completion returns json.dumps(payload)."""
    msg = mock.Mock()
    msg.content = json.dumps(payload)
    choice = mock.Mock()
    choice.message = msg
    resp = mock.Mock()
    resp.choices = [choice]
    client = mock.Mock()
    client.chat.completions.create.return_value = resp
    return client


class CatalogScraperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        self.engine_patcher = mock.patch.object(service_catalog.db, "engine", self.engine)
        self.engine_patcher.start()
        self.addCleanup(self.engine_patcher.stop)
        # Default-on for the gate so we don't have to patch it in every test.
        self.env_patcher = mock.patch.dict(
            os.environ, {"CATALOG_SCRAPER_ENABLED": "1", "OPENAI_API_KEY": "sk-test"}
        )
        self.env_patcher.start()
        self.addCleanup(self.env_patcher.stop)

    def _read_rows(self):
        with self.engine.connect() as conn:
            return list(
                conn.execute(
                    text(
                        "SELECT category, city, country, name, source, external_id "
                        "FROM service_catalog_items ORDER BY name"
                    )
                ).mappings()
            )

    # ------------------------------------------------------------------
    # Off-by-default
    # ------------------------------------------------------------------
    def test_no_op_when_disabled(self) -> None:
        with mock.patch.dict(os.environ, {"CATALOG_SCRAPER_ENABLED": "0"}):
            client = _fake_client({"vendors": [{"name": "X"}]})
            result = catalog_scraper.populate_destination_catalog(
                category="movers", destination_city="Tokyo", client=client,
            )
        self.assertEqual(result, [])
        client.chat.completions.create.assert_not_called()

    def test_no_op_when_no_api_key_and_no_client(self) -> None:
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            result = catalog_scraper.populate_destination_catalog(
                category="movers", destination_city="Tokyo",
            )
        self.assertEqual(result, [])

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------
    def test_writes_vendors_with_scraper_source(self) -> None:
        client = _fake_client({
            "vendors": [
                {"name": "Tokyo Movers Inc",  "summary": "Big in TY", "website": "https://t.example",
                 "strengths": ["fast"], "notes": None},
                {"name": "Asahi Relocation",  "summary": "Family-owned", "website": None,
                 "strengths": ["family", "local"], "notes": "Speaks English."},
            ]
        })
        rows = catalog_scraper.populate_destination_catalog(
            category="movers", destination_city="Tokyo", country="Japan", client=client,
        )
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertEqual(r["source"], "scraper")
            self.assertEqual(r["city"], "Tokyo")
            self.assertEqual(r["country"], "Japan")
            self.assertTrue(r["external_id"].startswith("scrape-movers-tokyo-"))

    def test_idempotent_on_rerun(self) -> None:
        payload = {
            "vendors": [
                {"name": "Tokyo Movers Inc", "summary": "X", "website": None,
                 "strengths": [], "notes": None},
            ]
        }
        client = _fake_client(payload)
        catalog_scraper.populate_destination_catalog(
            category="movers", destination_city="Tokyo", client=client,
        )
        catalog_scraper.populate_destination_catalog(
            category="movers", destination_city="Tokyo", client=client,
        )
        rows = self._read_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Tokyo Movers Inc")

    def test_caps_at_max_items(self) -> None:
        many = [
            {"name": f"Vendor {i}", "summary": "x", "website": None, "strengths": [], "notes": None}
            for i in range(20)
        ]
        client = _fake_client({"vendors": many})
        rows = catalog_scraper.populate_destination_catalog(
            category="movers", destination_city="Tokyo", client=client,
        )
        self.assertEqual(len(rows), catalog_scraper.MAX_ITEMS_PER_DESTINATION)

    def test_skips_unnamed_vendors(self) -> None:
        client = _fake_client({"vendors": [
            {"name": "OK Vendor", "summary": "x", "website": None, "strengths": [], "notes": None},
            {"name": "", "summary": "no name", "website": None, "strengths": [], "notes": None},
            {"summary": "missing name field"},
        ]})
        rows = catalog_scraper.populate_destination_catalog(
            category="movers", destination_city="Tokyo", client=client,
        )
        self.assertEqual([r["name"] for r in rows], ["OK Vendor"])

    # ------------------------------------------------------------------
    # Defensive parsing
    # ------------------------------------------------------------------
    def test_invalid_json_returns_empty(self) -> None:
        msg = mock.Mock(); msg.content = "not json"
        choice = mock.Mock(); choice.message = msg
        resp = mock.Mock(); resp.choices = [choice]
        client = mock.Mock(); client.chat.completions.create.return_value = resp
        result = catalog_scraper.populate_destination_catalog(
            category="movers", destination_city="Tokyo", client=client,
        )
        self.assertEqual(result, [])

    def test_missing_vendors_key_returns_empty(self) -> None:
        client = _fake_client({"items": [{"name": "x"}]})
        result = catalog_scraper.populate_destination_catalog(
            category="movers", destination_city="Tokyo", client=client,
        )
        self.assertEqual(result, [])


    # ------------------------------------------------------------------
    # L1 cost short-circuit: skip LLM when slot already populated
    # ------------------------------------------------------------------
    def test_short_circuit_skips_llm_when_already_populated(self) -> None:
        # Pre-populate the master with one row for (movers, Tokyo)
        service_catalog.upsert_item(
            category="movers", name="Pre-existing", attributes={}, source="seed",
            city="Tokyo", external_id="pre-1",
        )
        client = _fake_client({
            "vendors": [{"name": "Should Not Insert", "summary": "x", "website": None,
                         "strengths": [], "notes": None}]
        })
        result = catalog_scraper.populate_destination_catalog(
            category="movers", destination_city="Tokyo", client=client,
        )
        self.assertEqual(result, [])
        # Critical: the LLM client must NOT have been called.
        client.chat.completions.create.assert_not_called()
        # And no scraper-source row was added.
        rows = self._read_rows()
        self.assertEqual([r["source"] for r in rows], ["seed"])

    # ------------------------------------------------------------------
    # Dispatch path: ensure_destination_catalog calls into the scraper
    # ------------------------------------------------------------------
    def test_dispatch_from_ensure_destination_catalog(self) -> None:
        # Use a (category, city) pair where coverage is genuinely zero in
        # the seed JSON dataset: schools is geo-bound, and there are no
        # Tokyo entries — so report_coverage returns have=0 and needed=10,
        # which lets the scraper dispatch fire end-to-end.
        from backend.app.services import catalog_coverage
        client = _fake_client({
            "vendors": [
                {"name": "Tokyo International School", "summary": "Big in TY",
                 "website": None, "strengths": [], "notes": None},
                {"name": "ASIJ", "summary": "American school",
                 "website": None, "strengths": [], "notes": None},
            ]
        })
        with mock.patch.object(catalog_scraper, "_build_client", return_value=client):
            result = catalog_coverage.ensure_destination_catalog(
                category="schools",
                destination_city="Tokyo",
                country="Japan",
            )
        self.assertEqual(result["category"], "schools")
        # Phase 1 telemetry: gap detected.
        self.assertGreater(result["needed"], 0)
        # Phase 2b: scraper fired and reported the count.
        self.assertEqual(result["scraper_inserted"], 2)
        self.assertTrue(result["scraper_dispatched"])

        rows = self._read_rows()
        tokyo_schools = [r for r in rows if r["category"] == "schools" and r["city"] == "Tokyo"]
        self.assertEqual(len(tokyo_schools), 2)
        self.assertTrue(all(r["source"] == "scraper" for r in tokyo_schools))


if __name__ == "__main__":
    unittest.main()
