"""P2-02e · Case rule-update notification service (AIQ-693).

Backs the in-app "Rule updated — please review" roadmap banner. When an admin
approves a material source change (P2-02d), a row lands in
public.case_rule_update_notifications for each affected case. This service reads
the active ones for a case (banner) and dismisses one (banner X button).

Pure functions over an injected DB executor — unit-testable without a live DB.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.case_rule_update_service import (
    dismiss_rule_update,
    list_active_rule_updates,
)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeConn:
    def __init__(self, select_rows=None):
        self.select_rows = select_rows if select_rows is not None else []
        self.calls = []

    def execute(self, sql, params=None):
        s = str(sql).strip().lower()
        self.calls.append((s, params or {}))
        if s.lstrip().startswith("select"):
            return _FakeResult(self.select_rows)
        return _FakeResult([])

    def calls_matching(self, needle):
        return [(s, p) for (s, p) in self.calls if needle in s]


class ListActiveTests(unittest.TestCase):
    def test_lists_active_updates_for_case(self) -> None:
        rows = [
            {"id": "n1", "source_name": "Cantonal office", "source_url": "https://x"},
            {"id": "n2", "source_name": "Tax authority", "source_url": None},
        ]
        conn = _FakeConn(select_rows=rows)
        result = list_active_rule_updates(conn, "case-1")
        self.assertEqual([r["id"] for r in result], ["n1", "n2"])
        sel = conn.calls_matching("select")[0]
        self.assertEqual(sel[1]["case_id"], "case-1")
        # Only active notifications are surfaced.
        self.assertIn("'active'", sel[0])

    def test_no_updates_returns_empty(self) -> None:
        conn = _FakeConn(select_rows=[])
        self.assertEqual(list_active_rule_updates(conn, "case-1"), [])


class DismissTests(unittest.TestCase):
    def test_dismiss_marks_dismissed(self) -> None:
        conn = _FakeConn(select_rows=[{"id": "n1"}])
        result = dismiss_rule_update(conn, "case-1", "n1")
        updates = conn.calls_matching("update public.case_rule_update_notifications")
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0][1]["status"], "dismissed")
        self.assertEqual(updates[0][1]["id"], "n1")
        self.assertEqual(result["status"], "dismissed")

    def test_dismiss_missing_or_other_case_raises(self) -> None:
        conn = _FakeConn(select_rows=[])  # not found / not this case / already dismissed
        with self.assertRaises(ValueError):
            dismiss_rule_update(conn, "case-1", "nope")
        # No UPDATE statement issued (bare "update" would false-match the table name).
        self.assertEqual(conn.calls_matching("update public.case_rule_update_notifications"), [])


if __name__ == "__main__":
    unittest.main()
