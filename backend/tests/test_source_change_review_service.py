"""P2-02d · Admin material-change review service (AIQ-692).

The service backs the human-in-the-loop gate: an admin lists pending material
source changes, then approves (→ notify every active case citing the changed
rule) or rejects (→ logged, no user notification). These are pure functions over
an injected DB executor and an injected active-case finder, so the approve/reject
logic is fully unit-testable without a live database.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.source_change_review_service import (
    approve_review,
    list_pending_reviews,
    reject_review,
)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeConn:
    """Records every execute() call; returns canned rows for SELECTs."""

    def __init__(self, select_rows=None):
        self.select_rows = select_rows if select_rows is not None else []
        self.calls = []  # list of (sql_lower, params)

    def execute(self, sql, params=None):
        s = str(sql).strip().lower()
        self.calls.append((s, params or {}))
        if s.lstrip().startswith("select"):
            return _FakeResult(self.select_rows)
        return _FakeResult([])

    # convenience accessors for assertions
    def calls_matching(self, needle):
        return [(s, p) for (s, p) in self.calls if needle in s]


def _fake_finder(_rule_version_id):
    return ["case-A", "case-B"]


class ApproveTests(unittest.TestCase):
    def test_approve_notifies_each_active_case_and_marks_approved(self) -> None:
        conn = _FakeConn(select_rows=[{"rule_version_id": "rv-1", "status": "pending"}])
        result = approve_review(conn, "rev-1", reviewed_by="admin-1", finder=_fake_finder)

        # One notification insert per active case citing the rule.
        inserts = conn.calls_matching("insert into public.case_rule_update_notifications")
        self.assertEqual(len(inserts), 2)
        self.assertEqual(
            sorted(p["case_id"] for _, p in inserts), ["case-A", "case-B"]
        )

        # The review row is marked approved with the notified set recorded.
        updates = conn.calls_matching("update public.source_change_reviews")
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0][1]["status"], "approved")
        self.assertEqual(json.loads(updates[0][1]["notified_case_ids"]), ["case-A", "case-B"])

        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["notified_case_ids"], ["case-A", "case-B"])

    def test_approve_missing_review_raises_and_writes_nothing(self) -> None:
        conn = _FakeConn(select_rows=[])
        with self.assertRaises(ValueError):
            approve_review(conn, "nope", reviewed_by="admin-1", finder=_fake_finder)
        self.assertEqual(conn.calls_matching("insert into"), [])
        self.assertEqual(conn.calls_matching("update public.source_change_reviews"), [])

    def test_approve_non_pending_review_raises(self) -> None:
        conn = _FakeConn(select_rows=[{"rule_version_id": "rv-1", "status": "approved"}])
        with self.assertRaises(ValueError):
            approve_review(conn, "rev-1", reviewed_by="admin-1", finder=_fake_finder)
        self.assertEqual(conn.calls_matching("insert into"), [])

    def test_approve_with_no_affected_cases_still_marks_approved(self) -> None:
        conn = _FakeConn(select_rows=[{"rule_version_id": "rv-1", "status": "pending"}])
        result = approve_review(conn, "rev-1", reviewed_by="a", finder=lambda _r: [])
        self.assertEqual(conn.calls_matching("insert into public.case_rule_update_notifications"), [])
        self.assertEqual(result["status"], "approved")
        self.assertEqual(result["notified_case_ids"], [])


class RejectTests(unittest.TestCase):
    def test_reject_marks_rejected_and_creates_no_notifications(self) -> None:
        conn = _FakeConn(select_rows=[{"rule_version_id": "rv-1", "status": "pending"}])
        result = reject_review(conn, "rev-1", reviewed_by="admin-1", note="false positive")

        self.assertEqual(conn.calls_matching("insert into public.case_rule_update_notifications"), [])
        updates = conn.calls_matching("update public.source_change_reviews")
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0][1]["status"], "rejected")
        self.assertEqual(updates[0][1]["review_note"], "false positive")
        self.assertEqual(result["status"], "rejected")

    def test_reject_missing_review_raises(self) -> None:
        conn = _FakeConn(select_rows=[])
        with self.assertRaises(ValueError):
            reject_review(conn, "nope", reviewed_by="admin-1")


class ListPendingTests(unittest.TestCase):
    def test_list_pending_returns_rows(self) -> None:
        rows = [
            {"id": "r1", "rule_version_id": "rv-1", "status": "pending"},
            {"id": "r2", "rule_version_id": "rv-2", "status": "pending"},
        ]
        conn = _FakeConn(select_rows=rows)
        result = list_pending_reviews(conn)
        self.assertEqual([r["id"] for r in result], ["r1", "r2"])
        # Filters on pending status.
        sel = conn.calls_matching("select")
        self.assertTrue(sel)
        self.assertEqual(sel[0][1].get("status"), "pending")


if __name__ == "__main__":
    unittest.main()
