"""[AIQ-1821] The evidence check, and proof that it can fail.

The second half matters more than the first. A verification that returns "verified" for
everything is worse than no verification, because it launders unchecked claims as checked —
the same failure the requirement-extraction eval had, where a URL yielding zero facts scored
precision 1.0. So `test_planted_errors_are_caught` feeds deliberately unsupported claims
through and asserts they are NOT verified.

Pure functions: no DB, no network, no LLM.
"""
from __future__ import annotations

import pytest

from backend.app.services.fact_evidence import (
    NO_SOURCE,
    TRANSLATED,
    UNVERIFIED,
    VERIFIED,
    check_evidence,
    normalise,
)

# A realistic slice of skatteetaten.no's D-number page, as the parser returns it.
SOURCE = (
    "# D number\n"
    "There are two types of identification numbers in Norway: national identity numbers and "
    "D numbers. A Norwegian D number is an identification number that may be relevant for "
    "those who do not meet the requirements for a national identity number.\n"
    "## Who can receive a D number?\n"
    "You cannot apply for a D number. An enterprise or authority can request a D number when "
    "it needs you to have a Norwegian identification number.\n"
    "You can receive a D number if you:\n"
    "- provide a certified copy of your proof of identity when requested\n"
    "- attend an ID check when an enterprise asks you to\n"
    "The certified copy cannot be older than three months and must be sent by post."
)


class TestVerified:
    def test_exact_quote_is_verified_with_an_offset(self):
        r = check_evidence("You cannot apply for a D number.", SOURCE)
        assert r.status == VERIFIED
        assert r.verified is True
        assert r.offset is not None and r.offset > 0

    def test_context_includes_text_either_side(self):
        """The point of the context: the reviewer sees the sentence, not the fragment."""
        r = check_evidence("The certified copy cannot be older than three months", SOURCE)
        assert r.status == VERIFIED
        assert "certified copy cannot be older than three months" in r.context
        # Text from BEFORE the quote must be present, otherwise a condition reads as a duty.
        assert "attend an ID check" in r.context

    def test_whitespace_and_newlines_do_not_break_the_match(self):
        """A quote stored on one line vs a source with newlines is the common case."""
        assert check_evidence(
            "national identity numbers and D numbers", SOURCE
        ).status == VERIFIED

    @pytest.mark.parametrize("quote", [
        "You can’t apply",              # curly apostrophe vs straight — publisher/model disagree
        "You can't apply",
    ])
    def test_typographic_variants_fold(self, quote):
        src = "Note: You can't apply for a D number yourself. " + "x" * 250
        assert check_evidence(quote, src).status == VERIFIED

    def test_nbsp_in_the_source_folds(self):
        """NO/FR government pages are full of U+00A0 and U+202F."""
        src = "Vous devez demander le document portable S1. " + "x" * 250
        assert check_evidence("Vous devez demander le document portable S1", src).status == VERIFIED

    def test_case_differences_do_not_break_the_match(self):
        assert check_evidence("you cannot APPLY for a d number", SOURCE).status == VERIFIED


class TestNoSource:
    """"Never checked" must be distinguishable from "checked and failed"."""

    @pytest.mark.parametrize("src", [None, "", "   ", "too short to be an article"])
    def test_missing_or_stub_source_is_no_source(self, src):
        r = check_evidence("anything at all", src)
        assert r.status == NO_SOURCE
        assert r.verified is None, "None means unchecked — never conflate with False"
        assert r.offset is None and r.context == ""

    def test_a_441_char_average_stub_is_still_checkable(self):
        """The pre-backfill corpus averaged 441 chars; that is above the floor, so those
        facts get a real verdict rather than being silently excused as unchecked."""
        src = "The tax deduction card shows how much tax your employer must deduct. " * 7
        assert len(src) > 200
        assert check_evidence("how much tax your employer must deduct", src).status == VERIFIED


class TestPlantedErrors:
    """THE POINT. If none of these is caught, the check is decorative."""

    PLANTED = [
        # Plausible, on-topic, and simply not on the page.
        "You must pay a fee of NOK 5,400 to receive a D number.",
        "A D number expires after two years.",
        "You must apply for a D number in person at the police station.",
        # Subtly wrong: negates what the source says.
        "You can apply for a D number yourself.",
        # Right topic, invented specifics.
        "The certified copy cannot be older than six weeks.",
        # Wholly unrelated.
        "Norwegian citizens must register with the local fire authority.",
    ]

    @pytest.mark.parametrize("quote", PLANTED)
    def test_planted_errors_are_caught(self, quote):
        r = check_evidence(quote, SOURCE)
        assert r.status == UNVERIFIED, f"unsupported claim slipped through as verified: {quote!r}"
        assert r.verified is False
        assert r.offset is None

    def test_the_check_discriminates(self):
        """Supported and unsupported claims must land on OPPOSITE verdicts against the SAME
        source. A checker that says 'verified' for both, or 'unverified' for both, tells a
        reviewer nothing."""
        supported = check_evidence("You cannot apply for a D number.", SOURCE)
        unsupported = check_evidence("You can apply for a D number yourself.", SOURCE)
        assert supported.status == VERIFIED
        assert unsupported.status == UNVERIFIED
        assert supported.status != unsupported.status

    def test_a_fact_with_no_quote_is_unverified_not_unchecked(self):
        """We have the source; the fact cites nothing. That is a human's problem, not a gap
        in our archive — so it must not hide in the 'never checked' bucket."""
        r = check_evidence(None, SOURCE)
        assert r.status == UNVERIFIED
        assert r.verified is False


class TestTranslated:
    """A verbatim check cannot apply across languages — and must not pretend to.

    Measured on prod 2026-08-12: all 97 of France's pending facts are English renderings of
    French service-public.gouv.fr pages. Reporting those as "unverified" would put 97 sound
    facts in the suspect pile and bury the ~390 that genuinely need reading.
    """

    FRENCH_SOURCE = (
        "Vous devez demander le document portable S1 auprès de votre caisse d'assurance "
        "maladie. Le formulaire est valable pour la durée du détachement. Les membres de la "
        "famille qui vous accompagnent sont également couverts par ce dispositif. "
        "Pour bénéficier de la prise en charge des soins, vous devez vous inscrire."
    )

    def test_english_quote_against_a_french_source_is_translated_not_unverified(self):
        r = check_evidence(
            "You must request the portable document S1 from your health insurance fund.",
            self.FRENCH_SOURCE,
        )
        assert r.status == TRANSLATED
        assert r.verified is None, "the check did not apply — that is not the same as failing"

    def test_a_french_quote_against_the_french_source_still_verifies(self):
        assert check_evidence(
            "vous devez demander le document portable S1", self.FRENCH_SOURCE
        ).status == VERIFIED

    def test_same_language_mismatch_is_still_unverified(self):
        """The escape hatch must not swallow genuine misses in the SAME language."""
        r = check_evidence("Vous devez payer 5000 euros.", self.FRENCH_SOURCE)
        assert r.status == UNVERIFIED
        assert r.verified is False

    def test_planted_english_errors_are_not_excused_by_the_language_rule(self):
        """Against an ENGLISH source, an unsupported English claim stays UNVERIFIED."""
        r = check_evidence("A D number costs NOK 5,400.", SOURCE)
        assert r.status == UNVERIFIED


class TestNormalise:
    def test_collapses_whitespace_and_keeps_case(self):
        assert normalise("  You   MUST\n\npay  ") == "You MUST pay"

    def test_empty_input_is_safe(self):
        assert normalise("") == "" and normalise(None) == ""
