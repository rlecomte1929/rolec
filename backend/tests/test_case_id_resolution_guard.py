"""AIQ-1704 B3: the anti-instance-#6 guard.

The case-id/assignment-id confusion class produced ≥5 shipped defects because a
case-scoped endpoint keyed its SQL on the RAW path id, so an assignment id matched
no rows → silent-empty. A1/A2 fixed the known offenders; THIS guard stops the next
one from shipping.

It enumerates every function in the case-scoped routers that (a) takes a `case_id`
param and (b) contains an inline `case_id = :` SQL predicate, and asserts each one
either resolves the id through a recognised resolver OR is on the explicit,
reasoned ALLOWLIST below. A new endpoint that keys on the raw case_id without
resolving fails this test — the author must either resolve it or consciously
allowlist it with a justification.

This guard is what found the two sole-key offenders A2 missed (list_case_budget_lines,
list_dossiers) — both now fixed.
"""

from __future__ import annotations

import ast
import os
import re
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite://")

_ROUTERS = [
    "backend/app/routers/cases_read.py",
    "backend/app/routers/hr_coordination.py",
    "backend/app/routers/services_state.py",
    "backend/app/routers/payment.py",
]
_RESOLVERS = ("resolve_case_ids", "_canonical_case_id_or_404", "resolve_case_forms_case_id")

# Matches a case_id SQL predicate in any of the three styles this codebase writes.
#
# [AIQ-1735] The original pattern was `case_id\s*=\s*:`, which only saw the bare form.
# It was blind to `CAST(case_id AS TEXT) = :cid` — the form the codebase actively
# PREFERS, because `::text` is Postgres-only and breaks the sqlite tests (there is an
# explicit note saying so at cases_read.py:2455). So the guard could not see the very
# style it steers authors towards, and `get_case_rfqs` / `dispatch_case_rfq` sat
# unresolved inside an already-scanned router while the guard stayed green.
#
# Anchored on a word boundary so a column merely ENDING in case_id (e.g.
# canonical_case_id) is not matched by accident.
_CASE_SQL = re.compile(
    r"""
    \bcase_id\b            # the column, not a suffix of a longer name
    (?:\s*::\s*\w+)?       # optional  case_id::text
    \s*\)?                 # optional  ) closing a CAST(...)
    \s*(?:AS\s+\w+\s*\))?  # optional  AS TEXT)   -- CAST(case_id AS TEXT)
    \s*=\s*:               # = :bind
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _resolves(seg: str) -> bool:
    """A function resolves the id if it calls a named resolver, OR derives the
    canonical case id from the assignment that require_case_access returned
    (the services_state pattern: authorize a 3-form id, then key on the
    canonical case id it maps to — reusing the fetch rather than re-querying)."""
    if any(r in seg for r in _RESOLVERS):
        return True
    return "require_case_access" in seg and "canonical_case_id" in seg

# Functions with inline case_id SQL that legitimately do NOT resolve, each with the
# reason it is safe. Keep this SMALL and justified — every entry is a place the
# resolver was deliberately not applied.
_ALLOWLIST = {
    # Internal helpers — get_budget_summary resolves the case_id before calling them.
    "_case_service_estimates": "helper; get_budget_summary resolves case_id before calling it",
    "_selected_services_for_case": "helper; get_budget_summary resolves case_id before calling it",
    # NOTE: the 8 forms/dossier reads (list_form_documents/comments/events,
    # get_form_original, get_dossier[_zip/_pdf], _load_form_with_template) were
    # allowlisted here as secondary-filter reads; AIQ-1719 resolved them all via
    # resolve_case_forms_case_id, so they no longer need the allowlist.
}


def _flagged() -> set:
    flagged = set()
    for path in _ROUTERS:
        with open(path) as fh:
            src = fh.read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                a.arg == "case_id" for a in node.args.args
            ):
                seg = ast.get_source_segment(src, node) or ""
                if _CASE_SQL.search(seg) and not _resolves(seg):
                    flagged.add(node.name)
    return flagged


class CaseSqlPatternTests(unittest.TestCase):
    """[AIQ-1735] Pin the predicate styles the guard must see.

    The guard is only as good as this regex. Its original form matched the bare
    `case_id = :cid` and silently missed `CAST(case_id AS TEXT) = :cid` — the style the
    codebase PREFERS, since `::text` is Postgres-only and breaks the sqlite tests. Two
    unresolved handlers (`get_case_rfqs`, `dispatch_case_rfq`) sat inside a scanned
    router while the guard stayed green. If this test is ever weakened, that hole
    reopens.
    """

    def test_matches_every_predicate_style_the_codebase_writes(self):
        for sql in (
            "WHERE case_id = :cid",
            "WHERE CAST(case_id AS TEXT) = :cid",
            "WHERE case_id::text = :cid",
            "WHERE cvs.case_id = :case_id",
        ):
            self.assertTrue(_CASE_SQL.search(sql), f"should flag: {sql}")

    def test_does_not_flag_lookalikes(self):
        # A guard that cries wolf gets deleted. `canonical_case_id` is a DIFFERENT
        # column and is already the resolved value — flagging it would be a false
        # positive on correct code.
        for sql in (
            "WHERE canonical_case_id = :cid",
            "WHERE CAST(id AS TEXT) = :cid",
            "SELECT case_id, name FROM t",
        ):
            self.assertFalse(_CASE_SQL.search(sql), f"should NOT flag: {sql}")


class CaseIdResolutionGuard(unittest.TestCase):
    def test_no_unresolved_case_scoped_endpoint_outside_the_allowlist(self):
        flagged = _flagged()
        new_offenders = flagged - set(_ALLOWLIST)
        self.assertEqual(
            new_offenders, set(),
            "New case-scoped SQL keyed on the RAW case_id without resolving it "
            "(AIQ-1704). Resolve via resolve_case_ids / _canonical_case_id_or_404 / "
            "resolve_case_forms_case_id, or add it to _ALLOWLIST with a justification: "
            f"{sorted(new_offenders)}",
        )

    def test_allowlist_stays_honest(self):
        # If an allowlisted function was fixed (now resolves) it should be REMOVED from
        # the allowlist so the list keeps meaning something.
        flagged = _flagged()
        stale = set(_ALLOWLIST) - flagged
        self.assertEqual(
            stale, set(),
            f"These are allowlisted but no longer flagged — remove them: {sorted(stale)}",
        )


if __name__ == "__main__":
    unittest.main()
