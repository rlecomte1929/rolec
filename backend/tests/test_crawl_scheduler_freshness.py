"""
Tests for crawl scheduler, change detection, and freshness services.
Uses mocks for Supabase; tests logic without DB.
"""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


class TestFreshnessState(unittest.TestCase):
    def test_compute_freshness_fresh(self):
        from backend.services.freshness_service import compute_source_freshness

        now = datetime.now(timezone.utc)
        last = now - timedelta(hours=6)
        state = compute_source_freshness(last, expected_cadence_days=7, recent_failures=0)
        self.assertEqual(state, "fresh")

    def test_compute_freshness_stale(self):
        from backend.services.freshness_service import compute_source_freshness

        now = datetime.now(timezone.utc)
        last = now - timedelta(days=10)
        state = compute_source_freshness(last, expected_cadence_days=7, recent_failures=0)
        self.assertEqual(state, "stale")

    def test_compute_freshness_overdue(self):
        from backend.services.freshness_service import compute_source_freshness

        now = datetime.now(timezone.utc)
        last = now - timedelta(days=14)
        state = compute_source_freshness(last, expected_cadence_days=7, recent_failures=0)
        self.assertEqual(state, "overdue")

    def test_compute_freshness_error_on_failures(self):
        from backend.services.freshness_service import compute_source_freshness

        now = datetime.now(timezone.utc)
        last = now - timedelta(hours=1)
        state = compute_source_freshness(last, expected_cadence_days=7, recent_failures=2)
        self.assertEqual(state, "error")

    def test_compute_freshness_overdue_when_no_last_crawl(self):
        from backend.services.freshness_service import compute_source_freshness

        state = compute_source_freshness(None, expected_cadence_days=7, recent_failures=0)
        self.assertEqual(state, "overdue")


class TestNextRunComputation(unittest.TestCase):
    def test_interval_next_run(self):
        from backend.services.crawl_scheduler_service import _compute_next_run

        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        next_run = _compute_next_run("interval", "24", from_time=now)
        self.assertIsNotNone(next_run)
        self.assertEqual((next_run - now).total_seconds(), 24 * 3600)

    def test_interval_hours_parsed(self):
        from backend.services.crawl_scheduler_service import _compute_next_run

        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        next_run = _compute_next_run("interval", "12", from_time=now)
        self.assertIsNotNone(next_run)
        self.assertAlmostEqual((next_run - now).total_seconds(), 12 * 3600, delta=1)

    def test_cron_next_run(self):
        from backend.services.crawl_scheduler_service import _compute_next_run

        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        next_run = _compute_next_run("cron", "0 14 * * *", from_time=now)
        self.assertIsNotNone(next_run)
        self.assertGreater(next_run, now)
        self.assertEqual(next_run.minute, 0)


class TestChangeDetectionLogic(unittest.TestCase):
    def test_normalized_content_hash(self):
        from backend.services.change_detection_service import _normalized_content_hash

        h1 = _normalized_content_hash("  Hello   World  ")
        h2 = _normalized_content_hash("hello world")
        self.assertEqual(h1, h2)

    def test_normalized_content_hash_different(self):
        from backend.services.change_detection_service import _normalized_content_hash

        h1 = _normalized_content_hash("Hello World")
        h2 = _normalized_content_hash("Goodbye World")
        self.assertNotEqual(h1, h2)




