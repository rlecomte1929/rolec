"""
Tests for backend/services/scrape_safety.py — Phase 2b-secured.

Locks the cost-control surface that gates the LLM scraper: allowlist,
quota, and the ticket-queue lifecycle.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid
from datetime import date
from unittest import mock

from sqlalchemy import create_engine, text

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import scrape_safety  # noqa: E402


SCHEMA = """
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


class ScrapeSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )
        with self.engine.begin() as conn:
            for stmt in SCHEMA.split(";"):
                s = stmt.strip()
                if s:
                    conn.execute(text(s))
        patcher = mock.patch.object(scrape_safety.db, "engine", self.engine)
        patcher.start()
        self.addCleanup(patcher.stop)

    # ------------------------------------------------------------------
    # Allowlist
    # ------------------------------------------------------------------
    def test_allowlist_add_idempotent(self) -> None:
        admin = str(uuid.uuid4())
        a = scrape_safety.add_allowlist_entry(city="Munich", country="Germany", approved_by_user_id=admin)
        b = scrape_safety.add_allowlist_entry(city="Munich", country="Germany", approved_by_user_id=admin)
        self.assertEqual(a["city"], b["city"])
        self.assertTrue(scrape_safety.is_destination_allowlisted("Munich", "Germany"))

    def test_allowlist_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            scrape_safety.add_allowlist_entry(city="", country="Germany", approved_by_user_id=str(uuid.uuid4()))

    def test_allowlist_check_normalizes_whitespace(self) -> None:
        scrape_safety.add_allowlist_entry(city="Munich", country="Germany", approved_by_user_id=str(uuid.uuid4()))
        self.assertTrue(scrape_safety.is_destination_allowlisted("  Munich ", " Germany "))
        self.assertFalse(scrape_safety.is_destination_allowlisted("Tokyo", "Japan"))
        self.assertFalse(scrape_safety.is_destination_allowlisted("", "Germany"))

    # ------------------------------------------------------------------
    # Quota
    # ------------------------------------------------------------------
    def test_quota_starts_at_zero(self) -> None:
        st = scrape_safety.get_quota_state(str(uuid.uuid4()))
        self.assertEqual(st["used"], 0)
        self.assertEqual(st["remaining"], scrape_safety.DEFAULT_DAILY_QUOTA)

    def test_quota_increments_atomically(self) -> None:
        co = str(uuid.uuid4())
        for i in range(5):
            r = scrape_safety.check_and_increment_quota(co)
            self.assertTrue(r["allowed"])
            self.assertEqual(r["used"], i + 1)
        self.assertEqual(scrape_safety.get_quota_state(co)["used"], 5)

    def test_quota_blocks_at_limit(self) -> None:
        co = str(uuid.uuid4())
        for _ in range(scrape_safety.DEFAULT_DAILY_QUOTA):
            self.assertTrue(scrape_safety.check_and_increment_quota(co)["allowed"])
        # Next call refused.
        blocked = scrape_safety.check_and_increment_quota(co)
        self.assertFalse(blocked["allowed"])
        self.assertEqual(blocked["remaining"], 0)
        # Counter unchanged after refusal.
        self.assertEqual(scrape_safety.get_quota_state(co)["used"], scrape_safety.DEFAULT_DAILY_QUOTA)

    def test_quota_isolated_per_company(self) -> None:
        a, b = str(uuid.uuid4()), str(uuid.uuid4())
        scrape_safety.check_and_increment_quota(a)
        self.assertEqual(scrape_safety.get_quota_state(a)["used"], 1)
        self.assertEqual(scrape_safety.get_quota_state(b)["used"], 0)

    # ------------------------------------------------------------------
    # Ticket queue
    # ------------------------------------------------------------------
    def test_open_request_creates_pending_ticket(self) -> None:
        co = str(uuid.uuid4())
        actor = str(uuid.uuid4())
        ticket = scrape_safety.open_destination_request(
            city="Tokyo", country="Japan", category="schools",
            requested_by_user_id=actor, company_id=co,
        )
        self.assertEqual(ticket["status"], "pending")
        self.assertEqual(ticket["city"], "Tokyo")
        self.assertEqual(ticket["category"], "schools")
        self.assertEqual(ticket["requested_by"], actor)

    def test_open_request_dedups_same_pending(self) -> None:
        co = str(uuid.uuid4())
        actor = str(uuid.uuid4())
        a = scrape_safety.open_destination_request(
            city="Tokyo", country="Japan", category="schools",
            requested_by_user_id=actor, company_id=co,
        )
        b = scrape_safety.open_destination_request(
            city="Tokyo", country="Japan", category="schools",
            requested_by_user_id=actor, company_id=co,
        )
        self.assertEqual(a["id"], b["id"])

    def test_resolve_request_marks_status(self) -> None:
        ticket = scrape_safety.open_destination_request(
            city="Tokyo", country="Japan", category="schools",
            requested_by_user_id=str(uuid.uuid4()), company_id=str(uuid.uuid4()),
        )
        admin = str(uuid.uuid4())
        resolved = scrape_safety.resolve_destination_request(
            request_id=ticket["id"], new_status="approved", actor_user_id=admin,
        )
        self.assertEqual(resolved["status"], "approved")
        self.assertEqual(resolved["resolved_by"], admin)
        self.assertIsNotNone(resolved["resolved_at"])

    def test_resolve_blocks_already_resolved(self) -> None:
        ticket = scrape_safety.open_destination_request(
            city="Tokyo", country="Japan", category="schools",
            requested_by_user_id=str(uuid.uuid4()), company_id=str(uuid.uuid4()),
        )
        scrape_safety.resolve_destination_request(
            request_id=ticket["id"], new_status="approved",
            actor_user_id=str(uuid.uuid4()),
        )
        with self.assertRaises(ValueError):
            scrape_safety.resolve_destination_request(
                request_id=ticket["id"], new_status="rejected",
                actor_user_id=str(uuid.uuid4()),
            )

    def test_resolve_404_when_missing(self) -> None:
        with self.assertRaises(LookupError):
            scrape_safety.resolve_destination_request(
                request_id=str(uuid.uuid4()),
                new_status="approved",
                actor_user_id=str(uuid.uuid4()),
            )

    def test_resolve_rejects_invalid_status(self) -> None:
        ticket = scrape_safety.open_destination_request(
            city="Tokyo", country="Japan", category="schools",
            requested_by_user_id=str(uuid.uuid4()), company_id=str(uuid.uuid4()),
        )
        with self.assertRaises(ValueError):
            scrape_safety.resolve_destination_request(
                request_id=ticket["id"], new_status="bogus",
                actor_user_id=str(uuid.uuid4()),
            )

    def test_list_filtered_by_status_and_company(self) -> None:
        co_a, co_b = str(uuid.uuid4()), str(uuid.uuid4())
        for cat in ("schools", "movers"):
            scrape_safety.open_destination_request(
                city="Tokyo", country="Japan", category=cat,
                requested_by_user_id=str(uuid.uuid4()), company_id=co_a,
            )
        scrape_safety.open_destination_request(
            city="Berlin", country="Germany", category="schools",
            requested_by_user_id=str(uuid.uuid4()), company_id=co_b,
        )
        all_pending = scrape_safety.list_destination_requests(status="pending")
        self.assertEqual(len(all_pending), 3)
        a_only = scrape_safety.list_destination_requests(company_id=co_a)
        self.assertEqual(len(a_only), 2)

    def test_audit_row_written_for_allowlist_add_and_resolve(self) -> None:
        admin = str(uuid.uuid4())
        scrape_safety.add_allowlist_entry(city="Munich", country="Germany", approved_by_user_id=admin)
        ticket = scrape_safety.open_destination_request(
            city="Tokyo", country="Japan", category="schools",
            requested_by_user_id=str(uuid.uuid4()), company_id=str(uuid.uuid4()),
        )
        scrape_safety.resolve_destination_request(
            request_id=ticket["id"], new_status="approved", actor_user_id=admin,
        )
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT entity_type, action_type FROM audit_logs ORDER BY rowid")
            ).mappings().all()
        types = [(r["entity_type"], r["action_type"]) for r in rows]
        self.assertIn(("catalog_destination_allowlist", "insert"), types)
        self.assertIn(("catalog_destination_requests", "insert"), types)
        self.assertIn(("catalog_destination_requests", "update"), types)


class CleanSeedNoteTests(unittest.TestCase):
    """AIQ-1325c — read-time scrub of ReloPass-internal seed tags from allowlist notes."""

    def test_internal_seed_tags_relabelled(self):
        for note in ("AIQ-28-A seed", "B14 seed", "aiq-28-a-backfill original countries"):
            self.assertEqual(scrape_safety._clean_seed_note(note), "ReloPass curated")

    def test_genuine_hr_note_preserved(self):
        note = "HR requested for new Lisbon office"
        self.assertEqual(scrape_safety._clean_seed_note(note), note)

    def test_backfill_word_alone_not_matched(self):
        # Only the 'aiq…' / 'b<digits> seed' shapes are internal tags.
        self.assertEqual(scrape_safety._clean_seed_note("Backfill for Q3"), "Backfill for Q3")

    def test_none_and_empty_passthrough(self):
        self.assertIsNone(scrape_safety._clean_seed_note(None))
        self.assertEqual(scrape_safety._clean_seed_note(""), "")


if __name__ == "__main__":
    unittest.main()
