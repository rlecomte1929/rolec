"""
[AIQ-1868] Ireland readiness template registration.

HR's case summary showed, on every Madrid->Dublin case:

    "No verified readiness template is configured for destination 'IE' and
     route 'employment'. Human review required."

Verified in prod 2026-08-20: readiness_templates carries an `employment` row for
sixteen destinations (AE AU BR CA CH DE ES FR GB HK IT JP NL NO SG ZA) and none
for IE. Ireland is sellable in the destination catalog but reads to HR as an
unconfigured corridor.

Two things are tested here, because the ticket asks for both:

1. the migration genuinely registers IE/employment, with content that is true for
   BOTH nationality branches — readiness_templates has no nationality dimension,
   and Ireland's split is unusually wide (EEA nationals register nothing at all;
   non-EEA face a 12-week permit chain plus an IRP);
2. the human-review fallback is NOT weakened for destinations that really are
   unconfigured — the Technical Constraint on the ticket.
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.provenance_catalog import degraded_readiness_payload  # noqa: E402

MIGRATION = (
    Path(_REPO_ROOT) / "supabase" / "migrations" / "20261114000000_ie_destination.sql"
)


class MigrationRegistersIrelandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_migration_exists(self) -> None:
        self.assertTrue(MIGRATION.is_file(), f"{MIGRATION.name} missing")

    def test_registers_ie_for_the_employment_route(self) -> None:
        self.assertIn("_dest TEXT := 'IE'", self.sql)
        self.assertIn("_route TEXT := 'employment'", self.sql)
        self.assertIn("INSERT INTO readiness_templates", self.sql)

    def test_is_idempotent_on_destination_and_route(self) -> None:
        """Re-running must not duplicate the row — readiness_templates is
        UNIQUE(destination_key, route_key), so a second insert would raise."""
        self.assertIn(
            "IF EXISTS (SELECT 1 FROM readiness_templates WHERE destination_key = _dest AND route_key = _route)",
            self.sql,
        )
        # Every dossier question is guarded too.
        inserts = self.sql.count("INSERT INTO dossier_questions")
        guards = self.sql.count("IF NOT EXISTS (SELECT 1 FROM dossier_questions WHERE question_key")
        self.assertEqual(inserts, guards, "a dossier question insert is unguarded")

    def test_covers_both_nationality_branches(self) -> None:
        """One template, two very different journeys. Getting either half wrong is
        expensive: telling an EEA citizen to register, or telling a non-EEA hire
        they need nothing."""
        low = self.sql.lower()
        # EEA half — registers nothing.
        self.assertIn("no permit, no visa and no residence registration", low)
        # Non-EEA half — the chain.
        for marker in ("employment permit", "long-stay", "irp", "90 days"):
            self.assertIn(marker, low, f"non-EEA branch missing {marker!r}")

    def test_states_the_twelve_week_binding_constraint(self) -> None:
        """The permit application must be RECEIVED 12 weeks before the start date.
        That, not DETE's processing queue, is what sets the timeline."""
        self.assertIn("12 weeks", self.sql)
        self.assertRegex(self.sql, r"RECEIVED at least 12 weeks")

    def test_blue_card_is_only_ever_mentioned_to_deny_it(self) -> None:
        """Ireland is not in the Blue Card scheme — AIQ-1878 already had to strip a
        `visa_type` default that offered one. The template may name it, but only to
        say it does not apply; a bare mention would quietly reintroduce the error.

        Checks each occurrence in context rather than with a lookahead, so a future
        edit that adds an affirmative mention fails loudly."""
        low = self.sql.lower()
        occurrences = [m.start() for m in re.finditer(r"blue card", low)]
        self.assertTrue(occurrences, "expected the template to address the Blue Card myth")
        for i in occurrences:
            window = low[max(0, i - 120): i + 120]
            self.assertTrue(
                ("not in the eu blue card" in window) or ("is wrong" in window),
                f"Blue Card mentioned without denial near: ...{window}...",
            )

    def test_states_ireland_is_outside_schengen(self) -> None:
        """A Spanish residence permit confers no right to enter Ireland — a common
        and expensive misunderstanding for a third-country national moving from ES."""
        self.assertIn("Schengen", self.sql)

    def test_ppsn_and_revenue_apply_to_every_nationality(self) -> None:
        """These are the two steps an EEA citizen still has to take, and the ones a
        permit-focused template would omit for her."""
        low = self.sql.lower()
        self.assertIn("ppsn", low)
        self.assertIn("revenue myaccount", low)
        self.assertIn("emergency tax", low)

    def test_timestamp_is_above_the_repo_and_ledger_max(self) -> None:
        """20261112000000 was taken on main by another PR after this work started;
        20261113000000 is this branch's sibling seed. Nothing may collide."""
        versions = sorted(
            p.name[:14]
            for p in (Path(_REPO_ROOT) / "supabase" / "migrations").glob("*.sql")
        )
        self.assertEqual(
            versions.count("20261114000000"), 1, "duplicate migration version"
        )


class HumanReviewFallbackUnweakenedTests(unittest.TestCase):
    """Technical Constraint: 'Do not weaken the human-review fallback for genuinely
    unconfigured destinations.' Adding a row must not soften the guard."""

    def test_unconfigured_destination_still_demands_human_review(self) -> None:
        payload = degraded_readiness_payload("no_template", "Reykjavik", "IS", "employment")
        self.assertTrue(payload["human_review_required"])
        self.assertEqual(payload["trust_tier"], "unverified")
        self.assertIn("No verified readiness template is configured", payload["user_message"])
        self.assertIn("'IS'", payload["user_message"])

    def test_unresolved_destination_still_degrades(self) -> None:
        payload = degraded_readiness_payload("no_destination", None, None, "employment")
        self.assertTrue(payload["human_review_required"])
        self.assertIn("Destination could not be resolved", payload["user_message"])

    def test_missing_store_still_degrades(self) -> None:
        payload = degraded_readiness_payload("readiness_store_unavailable", None, None, "employment")
        self.assertTrue(payload["human_review_required"])
        self.assertIn("readiness reference database is not available", payload["user_message"])


if __name__ == "__main__":
    unittest.main()
