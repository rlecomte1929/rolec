"""AIQ-1717 — services_state keys on the CANONICAL case id, never the raw route id.

`require_case_access` authorizes any of the three id forms (assignment PK, case_id,
canonical_case_id), but every query in services_state.py bound the RAW path param. So a
request that authorized with an ASSIGNMENT id read nothing and — worse — INSERTed a
phantom `services_state` row keyed on that assignment id, which the read path can never
find again. `services_state.case_id` is UNIQUE, so a case can only ever hold one of the
two keys. One such phantom row exists in production.

The fallback half matters as much as the resolve half: `resolve_case_ids` goes through
`case_assignments`, so it returns None for a case with no assignment row — the HR-wizard
flow `require_case_access` deliberately supports. Ten such rows are live in production,
keyed on a `wizard_cases` id. Resolving those to None and 404ing would break them, so the
raw id is passed through instead. Both halves are pinned below.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "sqlite://")

from backend.app.routers import services_state as router_module  # noqa: E402
from backend.app.routers.services_state import _canonical_services_case_id  # noqa: E402

ASSIGNMENT_ID = "assign-1"
CANONICAL_CASE_ID = "case-1"
WIZARD_ONLY_ID = "wizard-case-no-assignment"


class _Ids:
    """Stand-in for db.CaseIds (a NamedTuple in backend/db/cases.py)."""

    def __init__(self, canonical_case_id: str) -> None:
        self.canonical_case_id = canonical_case_id


class CanonicalServicesCaseId(unittest.TestCase):
    def test_assignment_id_resolves_to_the_canonical_case(self):
        """THE BUG: this id used to be written straight into services_state.case_id."""
        with mock.patch.object(
            router_module.db, "resolve_case_ids", return_value=_Ids(CANONICAL_CASE_ID)
        ) as resolve:
            self.assertEqual(_canonical_services_case_id(ASSIGNMENT_ID), CANONICAL_CASE_ID)
        resolve.assert_called_once_with(ASSIGNMENT_ID)

    def test_canonical_id_passes_through_unchanged(self):
        with mock.patch.object(
            router_module.db, "resolve_case_ids", return_value=_Ids(CANONICAL_CASE_ID)
        ):
            self.assertEqual(_canonical_services_case_id(CANONICAL_CASE_ID), CANONICAL_CASE_ID)

    def test_unresolvable_id_passes_through_rather_than_failing(self):
        """The HR-wizard flow: a real case with NO case_assignments row.

        `resolve_case_ids` returns None for these because it resolves via
        case_assignments. 404ing here would break ten live production rows keyed on a
        wizard_cases id — and for those the raw id IS the canonical key. The dangerous
        case (a raw ASSIGNMENT id) is caught by the resolve above, not by this branch.
        """
        with mock.patch.object(router_module.db, "resolve_case_ids", return_value=None):
            self.assertEqual(_canonical_services_case_id(WIZARD_ONLY_ID), WIZARD_ONLY_ID)


if __name__ == "__main__":
    unittest.main()
