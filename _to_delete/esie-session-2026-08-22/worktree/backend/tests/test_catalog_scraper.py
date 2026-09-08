"""
Tests for backend/app/services/catalog_scraper.py — Phase 2b.

The real implementation calls the LLM via llm_client.complete_text_sync; tests
patch that seam so we never hit the network and never need an API key (AIQ-401).
"""
from __future__ import annotations

import json
import os
import sys
import unittest
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


def _patch_complete(payload: dict):
    """Patch the llm_client seam so the scraper 'LLM' returns json.dumps(payload)."""
    return mock.patch.object(
        catalog_scraper, "complete_text_sync", return_value=json.dumps(payload)
    )


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
        with mock.patch.dict(os.environ, {"CATALOG_SCRAPER_ENABLED": "0"}), \
                mock.patch.object(catalog_scraper, "complete_text_sync") as m:
            result = catalog_scraper.populate_destination_catalog(
                category="movers", destination_city="Tokyo",
            )
        self.assertEqual(result, [])
        m.assert_not_called()

    def test_no_op_when_no_api_key(self) -> None:
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}), \
                mock.patch.object(catalog_scraper, "complete_text_sync") as m:
            result = catalog_scraper.populate_destination_catalog(
                category="movers", destination_city="Tokyo",
            )
        self.assertEqual(result, [])
        m.assert_not_called()

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------
    def test_writes_vendors_with_scraper_source(self) -> None:
        payload = {
            "vendors": [
                {"name": "Tokyo Movers Inc",  "summary": "Big in TY", "website": "https://t.example",
                 "strengths": ["fast"], "notes": None},
                {"name": "Asahi Relocation",  "summary": "Family-owned", "website": None,
                 "strengths": ["family", "local"], "notes": "Speaks English."},
            ]
        }
        with _patch_complete(payload):
            rows = catalog_scraper.populate_destination_catalog(
                category="movers", destination_city="Tokyo", country="Japan",
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
        with _patch_complete(payload):
            catalog_scraper.populate_destination_catalog(
                category="movers", destination_city="Tokyo",
            )
            catalog_scraper.populate_destination_catalog(
                category="movers", destination_city="Tokyo",
            )
        rows = self._read_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Tokyo Movers Inc")

    def test_caps_at_max_items(self) -> None:
        many = [
            {"name": f"Vendor {i}", "summary": "x", "website": None, "strengths": [], "notes": None}
            for i in range(20)
        ]
        with _patch_complete({"vendors": many}):
            rows = catalog_scraper.populate_destination_catalog(
                category="movers", destination_city="Tokyo",
            )
        self.assertEqual(len(rows), catalog_scraper.MAX_ITEMS_PER_DESTINATION)

    def test_skips_unnamed_vendors(self) -> None:
        payload = {"vendors": [
            {"name": "OK Vendor", "summary": "x", "website": None, "strengths": [], "notes": None},
            {"name": "", "summary": "no name", "website": None, "strengths": [], "notes": None},
            {"summary": "missing name field"},
        ]}
        with _patch_complete(payload):
            rows = catalog_scraper.populate_destination_catalog(
                category="movers", destination_city="Tokyo",
            )
        self.assertEqual([r["name"] for r in rows], ["OK Vendor"])

    # ------------------------------------------------------------------
    # Defensive parsing
    # ------------------------------------------------------------------
    def test_invalid_json_returns_empty(self) -> None:
        with mock.patch.object(catalog_scraper, "complete_text_sync", return_value="not json"):
            result = catalog_scraper.populate_destination_catalog(
                category="movers", destination_city="Tokyo",
            )
        self.assertEqual(result, [])

    def test_missing_vendors_key_returns_empty(self) -> None:
        with _patch_complete({"items": [{"name": "x"}]}):
            result = catalog_scraper.populate_destination_catalog(
                category="movers", destination_city="Tokyo",
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
        with mock.patch.object(catalog_scraper, "complete_text_sync") as m:
            result = catalog_scraper.populate_destination_catalog(
                category="movers", destination_city="Tokyo",
            )
        self.assertEqual(result, [])
        # Critical: the LLM must NOT have been called.
        m.assert_not_called()
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
        payload = {
            "vendors": [
                {"name": "Tokyo International School", "summary": "Big in TY",
                 "website": None, "strengths": [], "notes": None},
                {"name": "ASIJ", "summary": "American school",
                 "website": None, "strengths": [], "notes": None},
            ]
        }
        with _patch_complete(payload):
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

    # ------------------------------------------------------------------
    # Service types — generation + backfill (vendor-filter feature)
    # ------------------------------------------------------------------
    def test_populate_persists_service_types(self) -> None:
        payload = {"vendors": [
            {"name": "Tokyo Movers Inc", "summary": "x", "website": None,
             "strengths": [], "service_types": ["International", "Storage"], "notes": None},
        ]}
        with _patch_complete(payload):
            rows = catalog_scraper.populate_destination_catalog(
                category="movers", destination_city="Tokyo",
            )
        self.assertEqual(rows[0]["attributes_json"]["service_types"], ["International", "Storage"])

    def test_parse_dedupes_service_types_case_insensitively(self) -> None:
        self.assertEqual(
            catalog_scraper._clean_service_types(["International", "international", " Storage ", ""]),
            ["International", "Storage"],
        )

    def test_backfill_tags_only_untagged_rows(self) -> None:
        # Seed two movers (geo-agnostic, no city): one already tagged, one not.
        service_catalog.upsert_item(
            category="movers", name="Tagged Co", attributes={"service_types": ["Local"]},
            source="seed", external_id="m-tagged",
        )
        service_catalog.upsert_item(
            category="movers", name="Untagged Co", attributes={}, source="seed",
            external_id="m-untagged",
        )
        tagging = {"tags": [
            {"name": "Untagged Co", "service_types": ["International", "Vehicle shipping"]},
            {"name": "Tagged Co", "service_types": ["SHOULD-NOT-OVERWRITE"]},
        ]}
        with _patch_complete(tagging):
            result = catalog_scraper.backfill_service_types(category="movers")
        self.assertEqual(result["tagged"], 1)
        rows = {r["name"]: r for r in service_catalog.list_items(category="movers")}
        self.assertEqual(rows["Untagged Co"]["attributes_json"]["service_types"],
                         ["International", "Vehicle shipping"])
        # The already-tagged row is left untouched (not in the candidate set).
        self.assertEqual(rows["Tagged Co"]["attributes_json"]["service_types"], ["Local"])

    def test_backfill_noop_without_llm_when_all_tagged(self) -> None:
        service_catalog.upsert_item(
            category="movers", name="A", attributes={"service_types": ["Local"]},
            source="seed", external_id="m-a",
        )
        with mock.patch.object(catalog_scraper, "complete_text_sync") as m:
            result = catalog_scraper.backfill_service_types(category="movers")
        m.assert_not_called()
        self.assertEqual(result["tagged"], 0)


if __name__ == "__main__":
    unittest.main()
