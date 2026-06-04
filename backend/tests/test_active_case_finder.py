"""P2-02c · Active-case finder (AIQ-691).

Given a rule_version_id of a source rule that just changed, return the case_ids
of the *active* cases whose provenance audit trail (rce.rule_citations) cites
that rule version — the set of users who must be notified of the change.

The provenance table is rce.rule_citations (AIQ-751): one row per
(case output, rule_version) pair, with a `rule_citations_by_version` index for
exactly this "which cases cite rule_version X" read pattern.
"""
from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.active_case_finder import (
    ACTIVE_CASE_STATUSES,
    find_active_cases_for_rule_version,
    find_cases_citing_rule_version,
)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeConn:
    """Captures the params it was executed with and returns canned rows."""

    def __init__(self, rows):
        self._rows = rows
        self.captured_params = None
        self.captured_sql = None

    def execute(self, sql, params=None):
        self.captured_sql = str(sql)
        self.captured_params = params
        return _FakeResult(self._rows)


class FindCasesCitingRuleVersionTests(unittest.TestCase):
    def test_returns_case_ids_for_rule_version(self) -> None:
        conn = _FakeConn([{"case_id": "case-A"}, {"case_id": "case-B"}])
        result = find_cases_citing_rule_version(conn, "rv-1")
        self.assertEqual(result, ["case-A", "case-B"])
        # The rule_version_id and the active-status filter are bound as params.
        self.assertEqual(conn.captured_params["rule_version_id"], "rv-1")
        self.assertEqual(list(conn.captured_params["statuses"]), list(ACTIVE_CASE_STATUSES))

    def test_dedupes_and_sorts_case_ids(self) -> None:
        conn = _FakeConn([{"case_id": "case-B"}, {"case_id": "case-A"}, {"case_id": "case-B"}])
        self.assertEqual(find_cases_citing_rule_version(conn, "rv-1"), ["case-A", "case-B"])

    def test_custom_statuses_passed_through(self) -> None:
        conn = _FakeConn([])
        find_cases_citing_rule_version(conn, "rv-1", statuses=("ACTIVE",))
        self.assertEqual(list(conn.captured_params["statuses"]), ["ACTIVE"])

    def test_empty_result_returns_empty_list(self) -> None:
        conn = _FakeConn([])
        self.assertEqual(find_cases_citing_rule_version(conn, "rv-1"), [])

    def test_active_statuses_exclude_finished_cases(self) -> None:
        # A rule change should never notify completed or cancelled cases.
        self.assertNotIn("COMPLETED", ACTIVE_CASE_STATUSES)
        self.assertNotIn("CANCELLED", ACTIVE_CASE_STATUSES)
        self.assertIn("ACTIVE", ACTIVE_CASE_STATUSES)


class FindActiveCasesWrapperTests(unittest.TestCase):
    def test_wrapper_returns_rows_from_engine(self) -> None:
        conn = _FakeConn([{"case_id": "case-A"}])

        class _Ctx:
            def __enter__(self_inner):
                return conn

            def __exit__(self_inner, *a):
                return False

        class _FakeEngine:
            def connect(self_inner):
                return _Ctx()

        self.assertEqual(
            find_active_cases_for_rule_version("rv-1", engine=_FakeEngine()), ["case-A"]
        )

    def test_wrapper_degrades_to_empty_when_tables_absent(self) -> None:
        # rce.* not present yet → the wrapper must degrade to [] rather than 500.
        class _BrokenEngine:
            def connect(self_inner):
                raise RuntimeError("relation rce.rule_citations does not exist")

        self.assertEqual(
            find_active_cases_for_rule_version("rv-1", engine=_BrokenEngine()), []
        )


if __name__ == "__main__":
    unittest.main()
