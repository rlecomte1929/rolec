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
    # [AIQ-1717] services_state was the worst instance of the class and was NOT
    # scanned by the original guard: both endpoints authorized a three-form id via
    # require_case_access, then bound the RAW path param — so an assignment id
    # INSERTed a phantom row the read path could never find (one exists in prod).
    # Now resolved via _canonical_services_case_id.
    "backend/app/routers/services_state.py",
    # [AIQ-1717] payment.py currently has NO inline `case_id = :` SQL — it resolves
    # through lookup_entitlement — so this entry flags nothing today. It is here so
    # that a future inline case-keyed query on the payment/entitlement path cannot
    # ship unresolved; the file is too load-bearing to leave outside the net.
    "backend/app/routers/payment.py",
]
_RESOLVERS = (
    "resolve_case_ids",
    "_canonical_case_id_or_404",
    "resolve_case_forms_case_id",
    "_canonical_services_case_id",
)
_CASE_SQL = re.compile(r"case_id\s*=\s*:")

# Functions with inline case_id SQL that legitimately do NOT resolve, each with the
# reason it is safe. Keep this SMALL and justified — every entry is a place the
# resolver was deliberately not applied.
_ALLOWLIST = {
    # Internal helpers — get_budget_summary resolves the case_id before calling them.
    "_case_service_estimates": "helper; get_budget_summary resolves case_id before calling it",
    "_selected_services_for_case": "helper; get_budget_summary resolves case_id before calling it",
    # Forms/dossier reads where case_id is a SECONDARY tenant filter behind the
    # form_id/dossier_id PK (WHERE <pk> = :id AND case_id = :cid) — the PK identifies
    # the row. Lower risk; resolving these is a tracked AIQ-1704 forms/dossier follow-up.
    "_load_form_with_template": "case_id is a secondary filter behind cf.id (form PK)",
    "list_form_documents": "case_id is a secondary filter behind case_form_id",
    "list_form_comments": "case_id is a secondary filter behind case_form_id",
    "list_form_events": "case_id is a secondary filter behind case_form_id",
    "get_form_original": "case_id is a secondary filter behind the form PK",
    "get_dossier_zip": "case_id is a secondary filter behind the dossier id",
    "get_dossier": "case_id is a secondary filter behind the dossier id",
    "get_dossier_pdf": "case_id is a secondary filter behind the dossier id",
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
                if _CASE_SQL.search(seg) and not any(r in seg for r in _RESOLVERS):
                    flagged.add(node.name)
    return flagged


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
