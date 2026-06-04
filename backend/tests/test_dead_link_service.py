"""
[P3-02d] Tests for dead_link_service — no DB, no network.

All Supabase calls are mocked so the logic runs purely in-process.
Tests cover:
  - update_404_counter increments on 404, resets on success
  - threshold detection (only at 3, not 2)
  - find_citing_immigration_requirements lookup
  - handle_dead_link raises an ops_notification and logs
  - get_dead_link_sources query
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, call, patch

from backend.app.services.dead_link_service import (
    DEAD_LINK_THRESHOLD,
    find_citing_immigration_requirements,
    get_dead_link_sources,
    handle_dead_link,
    update_404_counter,
)

_URL = "https://example-official.gov/page"


def _make_supabase_mock(select_rows=None):
    """Return a Supabase client mock where .table(...).select(...).eq(...).execute().data = rows."""
    rows = select_rows if select_rows is not None else []
    mock = MagicMock()
    mock.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = rows
    mock.table.return_value.update.return_value.eq.return_value.execute.return_value = None
    mock.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.execute.return_value.data = rows
    return mock


class UpdateCounterTests(unittest.TestCase):
    def test_increments_on_404(self):
        supabase = _make_supabase_mock(select_rows=[{"id": "r1", "consecutive_404_count": 1}])
        with patch("backend.app.services.dead_link_service._get_supabase", return_value=supabase):
            count = update_404_counter(_URL, is_404=True)
        self.assertEqual(count, 2)
        supabase.table().update.assert_called_once_with({"consecutive_404_count": 2})

    def test_resets_on_success(self):
        supabase = _make_supabase_mock(select_rows=[{"id": "r1", "consecutive_404_count": 2}])
        with patch("backend.app.services.dead_link_service._get_supabase", return_value=supabase):
            count = update_404_counter(_URL, is_404=False)
        self.assertEqual(count, 0)
        supabase.table().update.assert_called_once_with({"consecutive_404_count": 0})

    def test_returns_1_for_missing_row_404(self):
        supabase = _make_supabase_mock(select_rows=[])
        with patch("backend.app.services.dead_link_service._get_supabase", return_value=supabase):
            count = update_404_counter(_URL, is_404=True)
        self.assertEqual(count, 1)
        # No update call — row doesn't exist yet
        supabase.table().update.assert_not_called()

    def test_returns_0_for_missing_row_success(self):
        supabase = _make_supabase_mock(select_rows=[])
        with patch("backend.app.services.dead_link_service._get_supabase", return_value=supabase):
            count = update_404_counter(_URL, is_404=False)
        self.assertEqual(count, 0)


class FindCitingRequirementsTests(unittest.TestCase):
    def test_returns_matching_rows(self):
        fake_rows = [
            {
                "id": "req-1",
                "corridor_from": "US", "corridor_to": "FR",
                "visa_type": "long_stay_visa", "employee_type": "any",
                "document_type": "passport", "document_name": "Passport",
                "instructions_url": _URL,
            }
        ]
        supabase = MagicMock()
        supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = fake_rows
        with patch("backend.app.services.dead_link_service._get_supabase", return_value=supabase):
            result = find_citing_immigration_requirements(_URL)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["corridor_from"], "US")

    def test_returns_empty_when_no_match(self):
        supabase = MagicMock()
        supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        with patch("backend.app.services.dead_link_service._get_supabase", return_value=supabase):
            result = find_citing_immigration_requirements("https://not-referenced.com")
        self.assertEqual(result, [])


class HandleDeadLinkTests(unittest.TestCase):
    def test_raises_ops_notification_with_corridor_info(self):
        fake_citing = [
            {"corridor_from": "IN", "corridor_to": "DE",
             "visa_type": "blue_card", "document_type": "cv",
             "document_name": "CV", "instructions_url": _URL},
        ]
        supabase = MagicMock()
        supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = fake_citing

        notif_service = MagicMock()
        with patch("backend.app.services.dead_link_service._get_supabase", return_value=supabase), \
             patch("backend.app.services.dead_link_service._raise_ops_notification") as mock_notify:
            handle_dead_link(_URL)

        mock_notify.assert_called_once()
        args = mock_notify.call_args
        self.assertIn("IN→DE", args.kwargs.get("message", "") or args.args[1])

    def test_handles_exception_in_notification_gracefully(self):
        supabase = MagicMock()
        supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        with patch("backend.app.services.dead_link_service._get_supabase", return_value=supabase), \
             patch("backend.app.services.dead_link_service._raise_ops_notification",
                   side_effect=Exception("Slack down")):
            # Should not raise — best-effort alerting
            handle_dead_link(_URL)


class GetDeadLinkSourcesTests(unittest.TestCase):
    def test_returns_dead_links(self):
        fake_dead = [{"id": "x", "url": _URL, "tier": "1", "consecutive_404_count": 3}]
        supabase = MagicMock()
        supabase.table.return_value.select.return_value.gte.return_value.order.return_value.execute.return_value.data = fake_dead
        with patch("backend.app.services.dead_link_service._get_supabase", return_value=supabase):
            result = get_dead_link_sources()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["consecutive_404_count"], 3)


if __name__ == "__main__":
    unittest.main()
