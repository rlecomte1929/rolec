"""
Tests for the destination-scoped HR scraper endpoint
(populate-destination-with-ai) — Phase 2b iteration 2.

Same direct-call pattern as the other Phase 2 router tests; OpenAI is
mocked so no network is needed.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.routers import hr_catalog as hr_catalog_router  # noqa: E402
from backend.app.routers.hr_catalog import (  # noqa: E402
    ALL_CATEGORIES_SENTINEL,
    PopulateDestinationBody,
    populate_destination_with_ai,
)
from backend.app.services import (  # noqa: E402
    catalog_scraper,
    scrape_safety,
    service_catalog,
)


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
CREATE TABLE catalog_destination_allowlist (
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    approved_by TEXT,
    approved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    PRIMARY KEY (city, country)
);
CREATE TABLE catalog_scrape_quota (
    company_id TEXT NOT NULL,
    day TEXT NOT NULL,
    calls_made INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (company_id, day)
);
CREATE TABLE catalog_destination_requests (
    id TEXT PRIMARY KEY,
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    category TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    company_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    resolved_by TEXT,
    resolved_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE audit_logs (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    old_value_json TEXT,
    new_value_json TEXT,
    actor_type TEXT NOT NULL,
    actor_id TEXT,
    created_at TEXT
);
"""


def _user(role: str, company_id: str):
    return {"id": str(uuid.uuid4()), "role": role, "company": company_id, "is_admin": False}


def _patch_llm(payload: dict):
    """Patch the scraper's wrapper seam to return the given parsed JSON
    payload instead of calling OpenAI."""
    return mock.patch.object(catalog_scraper, "_call_llm", return_value=payload)


class PopulateDestinationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        for mod in (service_catalog, scrape_safety, hr_catalog_router):
            patcher = mock.patch.object(mod.db, "engine", self.engine)
            patcher.start()
            self.addCleanup(patcher.stop)
        profile_patcher = mock.patch.object(
            hr_catalog_router.db,
            "get_profile_record",
            side_effect=lambda uid: {"id": uid, "company_id": None},
        )
        profile_patcher.start()
        self.addCleanup(profile_patcher.stop)
        env_patcher = mock.patch.dict(
            os.environ, {"CATALOG_SCRAPER_ENABLED": "1", "OPENAI_API_KEY": "sk-test"}
        )
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

    # ------------------------------------------------------------------
    # Off-allowlist → ONE ticket with sentinel category, no LLM call
    # ------------------------------------------------------------------
    def test_off_allowlist_opens_single_sentinel_ticket(self) -> None:
        emp = _user("HR", str(uuid.uuid4()))
        result = populate_destination_with_ai(
            body=PopulateDestinationBody(destination_city="Tokyo", country="Japan"),
            user=emp,
        )
        self.assertEqual(result["status"], "pending_admin_approval")
        ticket = result["request"]
        self.assertEqual(ticket["category"], ALL_CATEGORIES_SENTINEL)
        self.assertEqual(ticket["city"], "Tokyo")
        self.assertEqual(ticket["status"], "pending")
        # Only ONE ticket, regardless of how many categories the system has.
        with self.engine.connect() as conn:
            n = conn.execute(text("SELECT COUNT(*) FROM catalog_destination_requests")).scalar()
        self.assertEqual(n, 1)

    # ------------------------------------------------------------------
    # On-allowlist → fires across all categories, returns per-category breakdown
    # ------------------------------------------------------------------
    def test_allowlisted_fires_across_categories(self) -> None:
        company = str(uuid.uuid4())
        admin = str(uuid.uuid4())
        scrape_safety.add_allowlist_entry(city="Tokyo", country="Japan", approved_by_user_id=admin)
        payload = {"vendors": [
            {"name": "Vendor A", "summary": "x", "website": None, "strengths": [], "notes": None},
            {"name": "Vendor B", "summary": "x", "website": None, "strengths": [], "notes": None},
        ]}
        with _patch_llm(payload):
            result = populate_destination_with_ai(
                body=PopulateDestinationBody(destination_city="Tokyo", country="Japan"),
                user=_user("HR", company),
            )
        self.assertEqual(result["status"], "completed")
        # 14 categories in the registry today; loose assertion since the count
        # could change as new plugins land — but it must be > 0 and the call
        # must have visited every category.
        self.assertGreater(result["categories_total"], 0)
        self.assertEqual(
            result["categories_total"],
            result["categories_populated"]
            + result["categories_skipped_existing"]
            + result["categories_quota_blocked"]
            + sum(
                1
                for r in result["per_category"]
                if r["status"] in ("scraper_returned_empty", "scraper_disabled")
            ),
        )
        # Some categories must have populated (the mocked LLM returned 2 vendors).
        self.assertGreater(result["categories_populated"], 0)
        self.assertGreater(result["total_inserted"], 0)

    # ------------------------------------------------------------------
    # Already-populated categories short-circuit, never increment quota
    # ------------------------------------------------------------------
    def test_short_circuit_on_existing_does_not_charge_quota(self) -> None:
        company = str(uuid.uuid4())
        admin = str(uuid.uuid4())
        scrape_safety.add_allowlist_entry(city="Munich", country="Germany", approved_by_user_id=admin)
        # Pre-populate every category for Munich → every iteration short-circuits
        from backend.app.recommendations.registry import list_categories
        for cat in list_categories():
            service_catalog.upsert_item(
                category=cat["key"], name="Pre", attributes={}, source="seed",
                city="Munich", external_id=f"pre-{cat['key']}",
            )
        with _patch_llm({"vendors": []}) as m:
            result = populate_destination_with_ai(
                body=PopulateDestinationBody(destination_city="Munich", country="Germany"),
                user=_user("HR", company),
            )
        # All categories skipped → quota counter still zero.
        self.assertEqual(result["categories_skipped_existing"], result["categories_total"])
        self.assertEqual(result["categories_populated"], 0)
        self.assertEqual(result["total_inserted"], 0)
        self.assertEqual(scrape_safety.get_quota_state(company)["used"], 0)
        m.assert_not_called()

    # ------------------------------------------------------------------
    # Quota mid-loop: stops incrementing when limit is hit
    # ------------------------------------------------------------------
    def test_quota_block_mid_loop(self) -> None:
        company = str(uuid.uuid4())
        admin = str(uuid.uuid4())
        scrape_safety.add_allowlist_entry(city="Tokyo", country="Japan", approved_by_user_id=admin)
        # Burn the daily quota up to 1 below the cap so only one LLM call
        # is allowed inside the loop.
        for _ in range(scrape_safety.DEFAULT_DAILY_QUOTA - 1):
            scrape_safety.check_and_increment_quota(company)
        payload = {"vendors": [
            {"name": "X", "summary": "x", "website": None, "strengths": [], "notes": None},
        ]}
        with _patch_llm(payload):
            result = populate_destination_with_ai(
                body=PopulateDestinationBody(destination_city="Tokyo", country="Japan"),
                user=_user("HR", company),
            )
        # At least one category should be reported as quota_blocked.
        self.assertGreater(result["categories_quota_blocked"], 0)
        self.assertLessEqual(result["categories_populated"], 1)


    # ------------------------------------------------------------------
    # Quota is NOT charged when scraper is disabled (config gate)
    # ------------------------------------------------------------------
    def test_disabled_scraper_does_not_charge_quota(self) -> None:
        company = str(uuid.uuid4())
        admin = str(uuid.uuid4())
        scrape_safety.add_allowlist_entry(city="Tokyo", country="Japan", approved_by_user_id=admin)
        # Disable the scraper for this test only.
        with mock.patch.dict(os.environ, {"CATALOG_SCRAPER_ENABLED": "0"}):
            result = populate_destination_with_ai(
                body=PopulateDestinationBody(destination_city="Tokyo", country="Japan"),
                user=_user("HR", company),
            )
        # Every category returns scraper_disabled; nothing populated; quota
        # untouched (so HR doesn't burn their daily allowance for nothing).
        self.assertEqual(result["categories_populated"], 0)
        self.assertEqual(result["total_inserted"], 0)
        self.assertEqual(scrape_safety.get_quota_state(company)["used"], 0)
        statuses = {r["status"] for r in result["per_category"]}
        self.assertIn("scraper_disabled", statuses)


if __name__ == "__main__":
    unittest.main()
