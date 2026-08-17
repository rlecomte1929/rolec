"""[AIQ-1903] Case finalisation seeds the destination catalog for a REAL company.

Before this, nothing did. Measured against production 2026-08-17: the only automatic seeder was
the test-drive provisioner, so 27 of 32 non-test companies had ZERO rows in
`company_vendor_selections`. `SLB_Denis` had 46 only because someone typed them in by hand —
that manual step is the bug this closes.

The query itself is exercised against real Postgres in
backend/tests/postgres/test_vendor_selection_seed_postgres.py; these tests pin the WIRING and
the POLICY, which is what differs between the two callers.
"""
from __future__ import annotations

import unittest
from unittest import mock

from backend.app.routers import cases_write


class VendorProposalCaseHookTests(unittest.TestCase):
    USER = {"id": "user-1"}

    def _run(self, *, profile=None, hr_company=None, dest="IE"):
        with mock.patch.object(cases_write.main_db, "get_profile_record", return_value=profile), \
             mock.patch.object(cases_write.main_db, "get_hr_company_id", return_value=hr_company), \
             mock.patch.object(cases_write.vendor_proposal, "seed_destination_proposal",
                               return_value=31) as seed:
            cases_write._seed_vendor_proposal_for_case(self.USER, dest, "case-1")
        return seed

    def test_seeds_unselected_for_a_real_company(self) -> None:
        """The authority model: propose everything, approve nothing.

        `hr_catalog.get_curation_view` treats an untouched master as selected=False, and the
        employee filter renders an empty curation as "HR is finalizing providers". Seeding
        approved rows would put vendors in front of employees that no HR user ever ticked.
        """
        seed = self._run(profile={"company_id": "co-A"})
        seed.assert_called_once()
        kwargs = seed.call_args.kwargs
        self.assertEqual(kwargs["company_id"], "co-A")
        self.assertEqual(kwargs["dest_country"], "IE")
        self.assertIs(kwargs["default_selected"], False)

    def test_company_comes_from_the_caller_never_the_request(self) -> None:
        """Tenant scope is resolved server-side. No request field can redirect the write."""
        seed = self._run(profile={"company_id": "co-A"})
        self.assertEqual(seed.call_args.kwargs["company_id"], "co-A")
        # A different caller resolves to a different tenant — never a shared or default one.
        seed_b = self._run(profile={"company_id": "co-B"})
        self.assertEqual(seed_b.call_args.kwargs["company_id"], "co-B")

    def test_falls_back_to_the_hr_users_link(self) -> None:
        """Legacy HR ids have a NULL profiles.company_id but a valid hr_users row."""
        seed = self._run(profile={"company_id": None}, hr_company="co-legacy")
        self.assertEqual(seed.call_args.kwargs["company_id"], "co-legacy")

    def test_no_company_link_seeds_nothing(self) -> None:
        """A self-serve wizard user with no tenant is a real state, not an error."""
        seed = self._run(profile={}, hr_company=None)
        seed.assert_not_called()

    def test_a_seed_failure_never_breaks_case_creation(self) -> None:
        """The case is already committed by the time this runs — it must not raise.

        But it must not be silent either: a swallowed exception on a seeding path caused a P0
        before, so the failure carries a stack.
        """
        with mock.patch.object(cases_write.main_db, "get_profile_record",
                               return_value={"company_id": "co-A"}), \
             mock.patch.object(cases_write.vendor_proposal, "seed_destination_proposal",
                               side_effect=RuntimeError("boom")), \
             self.assertLogs("backend.app.routers.cases_write", level="ERROR") as logs:
            cases_write._seed_vendor_proposal_for_case(self.USER, "IE", "case-1")  # no raise
        self.assertIn("vendor proposal: seed failed", "\n".join(logs.output))

    def test_no_destination_is_skipped_quietly(self) -> None:
        seed = self._run(profile={"company_id": "co-A"}, dest=None)
        # The shared seeder is still the one that decides; it no-ops on a falsy country.
        seed.assert_called_once()
        self.assertIsNone(seed.call_args.kwargs["dest_country"])


class SharedSeederGuardTests(unittest.TestCase):
    def test_seeder_no_ops_without_a_destination(self) -> None:
        from backend.app.services import vendor_proposal
        with mock.patch.object(vendor_proposal.db, "engine") as engine:
            self.assertEqual(
                vendor_proposal.seed_destination_proposal(company_id="co-A", dest_country=None), 0
            )
        engine.begin.assert_not_called()

    def test_selected_binds_a_python_bool(self) -> None:
        """`selected` is a Postgres BOOLEAN; an int bind raises psycopg2 DatatypeMismatch.

        SQLite coerces 1/0 silently, so only an explicit assertion catches it before prod.
        """
        from backend.app.services import vendor_proposal
        captured = {}
        with mock.patch.object(vendor_proposal.db, "engine") as engine:
            conn = engine.begin.return_value.__enter__.return_value
            conn.execute.side_effect = lambda _sql, params: captured.update(params) or mock.MagicMock(rowcount=1)
            vendor_proposal.seed_destination_proposal(
                company_id="co-A", dest_country="IE", default_selected=1  # type: ignore[arg-type]
            )
        self.assertIsInstance(captured["default_selected"], bool)
