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

[AIQ-1775] SCOPE WIDENED FROM 4 ROUTERS TO ALL OF THEM.
Until 2026-08-04 `_ROUTERS` was a hardcoded list of four files. Applying this guard's
own criterion to the rest of `app/routers/` found **60 more matching functions** — 20
in the unwired `cases.py`, 40 in live routers. So the class that produced ≥5 shipped
defects was guarded in 4 files and unguarded in ~20.

That is the second time this guard was found under-covering (see AIQ-1735 on the regex
below), so the router list is now DERIVED rather than hardcoded: a new router is
covered the day it lands, not the day someone measures again.

The 40 are split into two dicts on purpose:
  _ALLOWLIST        — genuinely safe, each with the reason it is safe.
  _KNOWN_UNRESOLVED — genuinely NOT safe. Recorded, not excused.
Mixing them would let a known gap masquerade as coverage, which is exactly the
failure mode this task existed to correct.
"""

from __future__ import annotations

import ast
import glob
import os
import re
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite://")

_ROUTERS_DIR = "backend/app/routers"

# `cases.py` is NOT wired — backend/main.py:136 records "router itself no longer
# wired (AUDIT-B9-cases-6)". Its 20 matches are dead code; auditing them every run
# would be noise. Delete this exclusion the day the router is re-wired or removed.
_UNWIRED = {"cases.py"}


def _routers() -> list:
    """Every router file, derived — NOT a hardcoded list.

    Hardcoding is what let 20 routers go unguarded for months. Deriving means the
    scope cannot silently fall behind the codebase again.
    """
    return sorted(
        p for p in glob.glob(f"{_ROUTERS_DIR}/*.py")
        if os.path.basename(p) not in _UNWIRED
        and not os.path.basename(p).startswith("__")
    )


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

    # ---- [AIQ-1775] added when the scope widened past the original 4 routers ----

    # Employee-scoped by the WHERE clause itself: the query is keyed on the caller's
    # own user id as well as case_id, so a wrong id form yields nothing rather than
    # another tenant's row. Silent-empty is still possible; cross-tenant read is not.
    "list_consent_employee": "employee-scoped: SQL also keys on current_user id",
    "withdraw_consent_employee": "employee-scoped: SQL also keys on current_user id",
    "upsert_profile_employee": "employee-scoped: SQL also keys on current_user id",
    "get_immigration_case_employee": "employee-scoped: SQL also keys on current_user id",
    "export_my_data": "employee-scoped via _assert_employee_owns_case",
    "_assert_employee_owns_case": "the ownership check itself; keys on caller id",

    # Uses its own access helper, which this guard's _resolves() does not know about.
    "get_outcome_consent": "guards via _resolve_case_employee + _caller_owns_case",

    # Legacy, tombstoned, no live caller. Its own docstring records that it is keyed
    # on the canonical case_id while the HR route param is an assignment id — 0 of 51
    # rows ever matched, and the one frontend caller was removed. Left in place as
    # historical read only; it is an ARTEFACT of this very defect class, not a new
    # instance of it.
    "list_hr_quote_requests": "LEGACY quote_requests read; tombstoned AIQ-1525, no live caller",

    # Internal helpers whose callers resolve before invoking them.
    "_post_form_status_notifications": "helper; caller resolved the id before notifying",
    "_resolve_accessible_case": "the resolution helper itself",
    "_fetch_pet_or_404": "helper; pets endpoints assert access before calling it",
}

# Functions that genuinely do NOT resolve and are NOT safe. Recorded, not excused.
#
# WHY A SEPARATE DICT: putting these in _ALLOWLIST would make the guard green while
# implying they had been reviewed and found safe. They have been reviewed and found
# UNSAFE. This dict is a known-gap register with a ticket, and the test below asserts
# it can only ever shrink.
#
# THE SHARED ROOT CAUSE: `_assert_case_access(user, case_id)` (case_service.py:147)
# accepts EITHER a public.cases UUID OR an assignment_id — its docstring says so — and
# returns None rather than the resolved id. So a caller validates access for either
# form, then runs `WHERE case_id = :raw_value`. Pass an assignment id and the access
# check passes while the SQL matches nothing: silent-empty, the exact F16 failure.
# `require_case_access` (auth_deps.py:245) has the same shape but DOES return the
# assignment row, so its callers can derive the canonical id and simply do not.
#
# Fixing these is deliberately NOT part of AIQ-1775 (measurement first, per its
# Validation Criteria #5) — ~22 endpoints across 9 routers is too large a blast radius
# for one PR. Tracked as a follow-up.
_KNOWN_UNRESOLVED = {
    # _assert_case_access accepts both id forms and returns None (see above).
    "get_form_original_pdf": "AIQ-1775-FU: _assert_case_access accepts both id forms",
    "replace_adhoc_pdf": "AIQ-1775-FU: _assert_case_access accepts both id forms",
    "delete_dossier": "AIQ-1775-FU: _assert_case_access accepts both id forms",
    "create_form_comment": "AIQ-1775-FU: _assert_case_access accepts both id forms",
    "upload_form_document": "AIQ-1775-FU: _assert_case_access accepts both id forms",
    "delete_form_document": "AIQ-1775-FU: _assert_case_access accepts both id forms",
    "patch_form_flag": "AIQ-1775-FU: _assert_case_access accepts both id forms",
    "create_dossier": "AIQ-1775-FU: _assert_case_access accepts both id forms",
    "regenerate_dossier": "AIQ-1775-FU: _assert_case_access accepts both id forms",
    "list_pets": "AIQ-1775-FU: _assert_case_access accepts both id forms",
    "update_pet": "AIQ-1775-FU: _assert_case_access accepts both id forms",
    "delete_pet": "AIQ-1775-FU: _assert_case_access accepts both id forms",
    # require_case_access returns the assignment; these do not use its canonical id.
    "list_exception_requests_for_case": "AIQ-1775-FU: has the assignment, keys on raw id",
    "list_case_notes": "AIQ-1775-FU: has the assignment, keys on raw id",
    "resolve_contradiction": "AIQ-1775-FU: has the assignment, keys on raw id",
    "escalate_contradiction": "AIQ-1775-FU: has the assignment, keys on raw id",
    "list_policy_gaps": "AIQ-1775-FU: has the assignment, keys on raw id",
    # HR/admin-scoped, but still keyed on the raw path id.
    "process_erasure_request": "AIQ-1775-FU: HR-scoped but keys on raw id",
    "update_profile_hr_fields": "AIQ-1775-FU: HR-scoped but keys on raw id",
    "list_milestones": "AIQ-1775-FU: HR-scoped but keys on raw id",
    "update_milestone": "AIQ-1775-FU: HR-scoped but keys on raw id",
    "get_interview_status_hr": "AIQ-1775-FU: HR-scoped but keys on raw id",
    # hr_case_detail's LOCAL _require_case_access pins the id to relocation_cases.id
    # (SELECT * FROM relocation_cases WHERE id = :id) and the rce.* tables key off the
    # same UUID, so these are internally consistent — but the id-space is enforced by
    # convention, not by a resolver, and AIQ-1751 documented a live trap here.
    "get_case_overview": "AIQ-1775-FU: relies on relocation_cases id-space by convention",
    "get_case_documents": "AIQ-1775-FU: relies on relocation_cases id-space by convention",
    "get_case_steps": "AIQ-1775-FU: relies on relocation_cases id-space by convention",
    "get_contradictions_summary": "AIQ-1775-FU: relies on relocation_cases id-space by convention",
    "list_case_contradictions": "AIQ-1775-FU: relies on relocation_cases id-space by convention",
    "get_contradiction_history": "AIQ-1775-FU: relies on relocation_cases id-space by convention",
    "list_immigration_documents": "AIQ-1775-FU: keys on raw id",
}


def _flagged() -> set:
    flagged = set()
    for path in _routers():
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
        new_offenders = flagged - set(_ALLOWLIST) - set(_KNOWN_UNRESOLVED)
        self.assertEqual(
            new_offenders, set(),
            "New case-scoped SQL keyed on the RAW case_id without resolving it "
            "(AIQ-1704). Resolve via resolve_case_ids / _canonical_case_id_or_404 / "
            "resolve_case_forms_case_id, or — only if it is genuinely safe — add it to "
            "_ALLOWLIST with the reason. Do NOT add it to _KNOWN_UNRESOLVED; that "
            f"register is for the AIQ-1775 backlog, not for new work: {sorted(new_offenders)}",
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

    def test_known_unresolved_register_only_shrinks(self):
        """The known-gap register is a debt list. Fixing an entry means DELETING it.

        Without this, a fixed endpoint would linger in the register and the backlog
        would look permanently unchanged — the same 'looks like coverage' failure the
        two-dict split exists to prevent.
        """
        flagged = _flagged()
        stale = set(_KNOWN_UNRESOLVED) - flagged
        self.assertEqual(
            stale, set(),
            "These are in _KNOWN_UNRESOLVED but now resolve — delete them from the "
            f"register, the debt is paid: {sorted(stale)}",
        )

    def test_the_two_registers_are_disjoint(self):
        """A function is either safe or it is not. Being in both would mean the reason
        recorded for it contradicts itself."""
        both = set(_ALLOWLIST) & set(_KNOWN_UNRESOLVED)
        self.assertEqual(both, set(), f"listed as both safe and unsafe: {sorted(both)}")

    def test_scope_is_derived_not_hardcoded(self):
        """The regression AIQ-1775 fixed: a hardcoded 4-router list left ~20 routers
        unguarded. If someone reverts to a literal list, this fails."""
        routers = _routers()
        self.assertGreater(
            len(routers), 20,
            "the guard should scan every router in app/routers/, not a hand-picked few",
        )
        names = {os.path.basename(p) for p in routers}
        # The four it used to scan must still be in scope.
        for original in ("cases_read.py", "hr_coordination.py", "services_state.py", "payment.py"):
            self.assertIn(original, names)
        # And the unwired one must not be.
        self.assertNotIn("cases.py", names)


if __name__ == "__main__":
    unittest.main()
