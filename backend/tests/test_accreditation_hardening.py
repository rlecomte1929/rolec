"""[AIQ-1826] The rules that decide when an accreditation may be called `verified`.

Every test here exists to stop a specific way of granting that word dishonestly. The
interesting ones are the negatives: a reachable register, a registered company, and a
plausible-looking name are each NOT a confirmation, and each has bitten a real row.
"""
from __future__ import annotations

import unittest

from backend.app.services.accreditation_hardening import (
    ACTION_KEEP_CLAIMED,
    ACTION_NAME_MISMATCH,
    ACTION_SKIP_OUT_OF_SCOPE,
    ACTION_VERIFY,
    VALID_METHODS,
    VALID_STATUSES,
    AccreditationRow,
    BODY_POLICIES,
    Capability,
    NOTE_MARKER,
    LookupResult,
    decide,
    merge_note,
    entity_key,
    in_scope,
    page_confirms_entity,
    policy_for_body,
    render_report,
)

_NO_LEGAL = Capability(service_category="legal_admin", country_code="NO")
_NO_HOUSING = Capability(service_category="housing_agencies", country_code="NO")
_DE_MOVERS = Capability(service_category="movers", country_code="DE")
_DE_BANKS = Capability(service_category="banks", country_code="DE")


def _row(**kw) -> AccreditationRow:
    base = dict(
        accreditation_id="acc-1",
        supplier_id="sup-1",
        supplier_name="Deloitte AS",
        body="Finanstilsynet (Norwegian FSA)",
        status="claimed",
        membership_number="99004",
        evidence_url="https://www.finanstilsynet.no/virksomhetsregisteret/detalj/?id=99004",
        capabilities=(Capability(service_category="tax_finance", country_code="NO"),),
    )
    base.update(kw)
    return AccreditationRow(**base)


class ScopeTests(unittest.TestCase):
    def test_a_norwegian_row_in_an_in_scope_category_is_in_scope(self) -> None:
        self.assertTrue(in_scope(_row(capabilities=(_NO_LEGAL,))))

    def test_a_german_only_row_is_out_of_scope(self) -> None:
        """12 of the 27 prod rows are FR-DE. The brief says both 'harden the 27' and
        'FR-NO ONLY'; the guardrail wins and the skip is reported, not silent."""
        self.assertFalse(in_scope(_row(capabilities=(_DE_MOVERS,))))

    def test_banks_never_qualify_even_in_an_in_scope_country(self) -> None:
        """ING-DiBa is the live example. 'banks OUT' is a category rule, not a country one."""
        norwegian_bank = Capability(service_category="banks", country_code="NO")
        self.assertFalse(in_scope(_row(capabilities=(norwegian_bank,))))
        self.assertFalse(in_scope(_row(capabilities=(_DE_BANKS,))))

    def test_a_supplier_serving_both_corridors_is_in_scope(self) -> None:
        """AGS France and Grospiron each carry movers/DE AND movers/NO."""
        both = (_DE_MOVERS, Capability(service_category="movers", country_code="NO"))
        self.assertTrue(in_scope(_row(capabilities=both)))

    def test_a_supplier_with_no_capabilities_is_out_of_scope(self) -> None:
        self.assertFalse(in_scope(_row(capabilities=())))

    def test_out_of_scope_rows_are_reported_not_dropped(self) -> None:
        d = decide(_row(capabilities=(_DE_MOVERS,)), None)
        self.assertEqual(d.action, ACTION_SKIP_OUT_OF_SCOPE)
        self.assertIn("movers", d.reason)
        self.assertFalse(d.writes)


class NameMatchTests(unittest.TestCase):
    def test_case_and_diacritics_fold(self) -> None:
        page = "<title>ADVOKATFIRMAET TVETER OG KLØVFJELL AS - Brreg</title>"
        self.assertTrue(page_confirms_entity(page, "Advokatfirmaet Tveter og Kløvfjell AS"))

    def test_a_trailing_person_qualifier_is_dropped(self) -> None:
        self.assertEqual(entity_key("Humlen Advokater AS — Félix Olivier Helle"),
                         "humlen advokater")

    def test_a_parenthetical_trading_name_is_dropped(self) -> None:
        self.assertEqual(
            entity_key("AGS France (SOFDI – Société Française de Déménagement International)"),
            "ags france",
        )

    def test_a_short_brand_confirms_via_its_full_name(self) -> None:
        """Regression, caught on the first live dry run. 'Deloitte AS' strips to the single
        token 'deloitte', which the two-token floor rejects — so Deloitte, KPMG and PwC were
        all reported not_found against Finanstilsynet pages that name them exactly. Matching
        the full name (legal form kept) restores the second token."""
        page = "<title>DELOITTE AS - Finanstilsynet.no</title>"
        self.assertTrue(page_confirms_entity(page, "Deloitte AS"))
        self.assertTrue(page_confirms_entity("<h1>KPMG AS</h1>", "KPMG AS"))

    def test_the_registered_name_confirms_where_the_trading_name_cannot(self) -> None:
        """Live case: the supplier is stored as `Expat Relocation Norway`, but its EuRA
        register page is titled `Expat Relocation AS` — and `legal_name` already held that
        exact string. Matching only the display name reported a false mismatch."""
        page = "<title>Expat Relocation AS | EuRA</title>"
        self.assertFalse(page_confirms_entity(page, "Expat Relocation Norway"))
        self.assertTrue(
            page_confirms_entity(page, "Expat Relocation Norway",
                                 legal_name="Expat Relocation AS")
        )

    def test_a_wrong_legal_name_does_not_rescue_a_mismatch(self) -> None:
        """The extra candidate must widen the match, not weaken it."""
        self.assertFalse(
            page_confirms_entity("<h1>Ingen treff</h1>", "Expat Relocation Norway",
                                 legal_name="Expat Relocation AS")
        )

    def test_a_bare_single_token_still_never_confirms(self) -> None:
        """The floor still holds where there is genuinely only one token to match on."""
        self.assertFalse(page_confirms_entity("Deloitte", "Deloitte"))

    def test_an_unrelated_page_does_not_confirm(self) -> None:
        self.assertFalse(
            page_confirms_entity("<h1>Ingen treff / no results</h1>", "Deloitte Norge AS")
        )


class VerificationHonestyTests(unittest.TestCase):
    def test_a_confirmed_page_verifies(self) -> None:
        d = decide(_row(supplier_name="Deloitte Norge AS"),
                   LookupResult(ok=True, http_status=200, text="DELOITTE NORGE AS — register"))
        self.assertEqual(d.action, ACTION_VERIFY)
        self.assertEqual(d.status, "verified")
        self.assertEqual(d.verification_method, "public_registry")

    def test_http_200_alone_does_not_verify(self) -> None:
        """A register's 'no results' page is also 200. Only a name match confirms."""
        d = decide(_row(), LookupResult(ok=True, http_status=200, text="Ingen treff"))
        self.assertEqual(d.action, ACTION_NAME_MISMATCH)
        self.assertNotEqual(d.status, "verified")

    def test_a_name_mismatch_is_never_written_as_not_found(self) -> None:
        """Live case: `Expat Relocation Norway` did not match its EuRA page — but the page
        exists and is titled "Expat Relocation AS". A per-entity URL cannot prove absence,
        so the row stays claimed and nothing is asserted about the register's contents."""
        d = decide(_row(), LookupResult(ok=True, http_status=200, text="Expat Relocation AS"))
        self.assertEqual(d.status, "claimed")
        self.assertNotEqual(d.status, "not_found")
        self.assertFalse(d.writes, "a mismatch must not change any status")
        self.assertIn("cannot prove absence", d.reason)

    def test_an_unreachable_register_keeps_the_row_claimed(self) -> None:
        """Our failure to check is not a finding about the supplier — it must not be
        recorded as not_found, which is a positive claim."""
        d = decide(_row(), LookupResult(ok=False, http_status=403, error="HTTP 403"))
        self.assertEqual(d.action, ACTION_KEEP_CLAIMED)
        self.assertEqual(d.status, "claimed")
        self.assertIn("unreachable", d.reason)

    def test_no_lookup_means_claimed_not_verified(self) -> None:
        d = decide(_row(), None)
        self.assertEqual(d.action, ACTION_KEEP_CLAIMED)

    def test_a_row_without_evidence_url_can_never_verify(self) -> None:
        d = decide(_row(evidence_url=None),
                   LookupResult(ok=True, text="Deloitte Norge AS"))
        self.assertEqual(d.action, ACTION_KEEP_CLAIMED)
        self.assertIn("no evidence_url", d.reason)

    def test_an_unmodelled_body_is_never_verified(self) -> None:
        d = decide(_row(body="Some Association Nobody Modelled"),
                   LookupResult(ok=True, text="Deloitte Norge AS"))
        self.assertEqual(d.action, ACTION_KEEP_CLAIMED)
        self.assertIn("no confirmation rule", d.reason)

    def test_an_already_verified_row_is_left_alone(self) -> None:
        d = decide(_row(status="verified"), None)
        self.assertEqual(d.action, ACTION_KEEP_CLAIMED)
        self.assertFalse(d.writes)


class AdvokatforeningenIsBlockedTests(unittest.TestCase):
    """The four prod rows whose `body` names a bar but whose evidence is a company register.

    This is the specific fabrication this task was most likely to commit: brreg confirms
    'ADVOKATFIRMAET TVETER OG KLØVFJELL AS' exists, which looks exactly like a confirmation
    and is not one — company registration is not bar membership.
    """

    def _advokat_row(self, **kw) -> AccreditationRow:
        return _row(
            supplier_name="Advokatfirmaet Tveter og Kløvfjell AS",
            body="Den Norske Advokatforening",
            membership_number="917 334 110",
            evidence_url="https://virksomhet.brreg.no/nb/oppslag/enheter/917334110",
            capabilities=(_NO_LEGAL,),
            **kw,
        )

    def test_a_perfect_brreg_name_match_still_does_not_verify(self) -> None:
        d = decide(
            self._advokat_row(),
            LookupResult(ok=True, http_status=200,
                         text="ADVOKATFIRMAET TVETER OG KLØVFJELL AS"),
        )
        self.assertEqual(d.action, ACTION_KEEP_CLAIMED)
        self.assertEqual(d.status, "claimed")
        self.assertFalse(d.writes)

    def test_the_reason_names_the_actual_defect(self) -> None:
        d = decide(self._advokat_row(), None)
        self.assertIn("Brønnøysund", d.reason)
        self.assertIn("bar membership", d.reason)

    def test_the_policy_is_declared_blocked_not_merely_absent(self) -> None:
        pol = policy_for_body("Den Norske Advokatforening")
        self.assertIsNotNone(pol)
        self.assertFalse(pol.auto_verifiable)
        self.assertTrue(pol.blocked_reason)


class MembershipNumberTests(unittest.TestCase):
    def test_fidi_verifies_but_is_flagged_as_number_less(self) -> None:
        """FIDI publishes an affiliate page per member but no public membership number.
        That is a property of the register, not a gap in the row — but the preview says so
        rather than letting 'verified' imply a number was checked."""
        d = decide(
            _row(supplier_name="Alfa Mobility Norway A/S",
                 body="FIDI Global Alliance / FAIM (auditor: EY)",
                 membership_number=None,
                 evidence_url="https://www.fidi.org/find-fidi-affiliate/alfa-mobility-5",
                 capabilities=(Capability(service_category="movers", country_code="NO"),)),
            LookupResult(ok=True, text="Alfa Mobility Norway A/S — FAIM certified"),
        )
        self.assertEqual(d.action, ACTION_VERIFY)
        self.assertFalse(d.membership_number_missing,
                         "FIDI publishes no number, so a null one is not a gap")

    def test_a_number_publishing_register_flags_a_missing_number(self) -> None:
        d = decide(_row(supplier_name="Deloitte Norge AS", membership_number=None),
                   LookupResult(ok=True, text="DELOITTE NORGE AS"))
        self.assertEqual(d.action, ACTION_VERIFY)
        self.assertTrue(d.membership_number_missing)


class SchemaContractTests(unittest.TestCase):
    """Mirrors of the live DB CHECKs. The brief specified a value these reject."""

    def test_registry_lookup_is_not_a_legal_verification_method(self) -> None:
        """The task brief said verification_method='registry_lookup'. The CHECK permits only
        public_registry | supplier_document | manual_email | directory_listing, so that
        write would have failed at the constraint."""
        self.assertNotIn("registry_lookup", VALID_METHODS)

    def test_every_policy_method_satisfies_the_check(self) -> None:
        for pol in BODY_POLICIES:
            if pol.auto_verifiable:
                self.assertIn(pol.method, VALID_METHODS, pol.match)

    def test_every_emitted_status_satisfies_the_check(self) -> None:
        cases = [
            decide(_row(supplier_name="Deloitte Norge AS"),
                   LookupResult(ok=True, text="DELOITTE NORGE AS")),
            decide(_row(), LookupResult(ok=True, text="ingen treff")),
            decide(_row(), LookupResult(ok=False, error="boom")),
            decide(_row(capabilities=(_DE_MOVERS,)), None),
        ]
        for d in cases:
            self.assertIn(d.status, VALID_STATUSES, d.reason)


class NoteMergeTests(unittest.TestCase):
    """`notes` is occupied. All 27 prod rows carry harvest provenance in it."""

    HARVEST = ("expiry coerced from bare year 2026 to 1 Jan (earliest consistent date; "
               "the register publishes only the year)")

    def test_existing_provenance_survives(self) -> None:
        out = merge_note(self.HARVEST, "confirmed on finanstilsynet register page")
        self.assertIn("expiry coerced from bare year 2026", out)
        self.assertIn("confirmed on finanstilsynet", out)

    def test_a_second_run_replaces_its_own_line_rather_than_stacking(self) -> None:
        once = merge_note(self.HARVEST, "confirmed")
        twice = merge_note(once, "confirmed")
        self.assertEqual(once, twice, "re-running must be idempotent")
        self.assertEqual(twice.count(NOTE_MARKER), 1)

    def test_a_changed_reason_replaces_the_previous_one(self) -> None:
        first = merge_note(self.HARVEST, "register unreachable (HTTP 403)")
        second = merge_note(first, "confirmed on finanstilsynet register page")
        self.assertNotIn("HTTP 403", second)
        self.assertIn("confirmed on finanstilsynet", second)
        self.assertIn("expiry coerced", second, "the harvest note still survives")

    def test_an_empty_note_column_is_handled(self) -> None:
        self.assertEqual(merge_note(None, "x"), f"{NOTE_MARKER} x")
        self.assertEqual(merge_note("", "x"), f"{NOTE_MARKER} x")

    def test_the_decision_carries_the_existing_notes_for_the_writer(self) -> None:
        d = decide(_row(notes=self.HARVEST), None)
        self.assertEqual(d.existing_notes, self.HARVEST)


class ReportTests(unittest.TestCase):
    def test_the_report_separates_writes_from_skips(self) -> None:
        decisions = [
            decide(_row(supplier_name="Deloitte Norge AS"),
                   LookupResult(ok=True, text="DELOITTE NORGE AS")),
            decide(_row(capabilities=(_DE_MOVERS,)), None),
        ]
        out = render_report(decisions, dry_run=True)
        self.assertIn("DRY RUN", out)
        self.assertIn("VERIFY: 1", out)
        self.assertIn("SKIP (out of FR-NO scope): 1", out)
        self.assertIn("writes: 1", out)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
