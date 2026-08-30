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
    best_source_text,
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


class TestRecomposedQuotes:
    """[AIQ-2126] A quotation assembled from the page with an ellipsis or a flattened list is
    still a quotation.

    The extractor legitimately recomposes: it joins a lead-in to its bullet ("You can receive a
    D number if you: ... provide a certified copy"), or elides an aside with "...". Every word
    still comes from the page, in page order — but a plain substring test says "unsupported",
    which is then written as `evidence_verified = FALSE`, and PR #1851 excludes FALSE from
    serving. So a correctly-quoted fact gets DELETED from what a user sees.

    Measured 2026-08-23 over the 120 approved SG + IE facts that carry a quote: 81 fail the
    substring test, and 8 of those are ordered spans of the page. This class pins those 8.

    The rule is deliberately narrow and provable: EVERY segment must appear verbatim, in
    increasing order, the first segment must be a substantial anchor, and the matched
    characters must cover most of the quote. That is strictly stronger than "the words appear
    somewhere" — see TestRecomposedRuleCannotLaunderErrors, which is the half that matters.
    """

    def test_an_ellipsis_quotation_is_verified(self):
        quote = "You cannot apply for a D number... it needs you to have a Norwegian identification number."
        r = check_evidence(quote, SOURCE)
        assert r.status == VERIFIED
        assert r.verified is True

    def test_a_flattened_list_is_verified(self):
        """The lead-in and its bullet, joined — the shape that broke Singapore."""
        quote = "You can receive a D number if you: - provide a certified copy of your proof of identity when requested"
        r = check_evidence(quote, SOURCE)
        assert r.status == VERIFIED

    def test_a_recomposed_match_reports_an_offset_and_context(self):
        """A reviewer must still be able to see where it came from."""
        quote = "You cannot apply for a D number... it needs you to have a Norwegian identification number."
        r = check_evidence(quote, SOURCE)
        assert r.offset is not None and r.offset >= 0
        assert "D number" in r.context

    def test_segments_must_appear_in_page_order(self):
        """Reversing the halves is not a quotation of this page — it asserts a sequence the
        source does not make."""
        reversed_quote = (
            "it needs you to have a Norwegian identification number"
            "... There are two types of identification numbers in Norway"
        )
        assert check_evidence(reversed_quote, SOURCE).status == UNVERIFIED


class TestRecomposedRuleCannotLaunderErrors:
    """THE POINT, again. Every planted error must stay caught once recomposition is allowed.

    A looser rule is only worth having if it still fails. `You can apply for a D number
    yourself` shares nearly every content word with the source and inverts its meaning — which
    is exactly why this check is span-based and ordered rather than bag-of-words. A
    content-overlap rule would have let that negation through as supported.
    """

    @pytest.mark.parametrize("quote", TestPlantedErrors.PLANTED)
    def test_planted_errors_survive_the_recomposition_rule(self, quote):
        r = check_evidence(quote, SOURCE)
        assert r.status == UNVERIFIED, f"recomposition laundered an unsupported claim: {quote!r}"
        assert r.verified is False

    @pytest.mark.parametrize("quote", TestPlantedErrors.PLANTED)
    def test_planted_errors_stay_caught_when_spliced_onto_a_true_anchor(self, quote):
        """The attack the rule invites: prepend a real sentence, splice on a false one."""
        anchor = "A Norwegian D number is an identification number that may be relevant"
        r = check_evidence(f"{anchor}... {quote}", SOURCE)
        assert r.status == UNVERIFIED, f"a true anchor laundered a false tail: {quote!r}"

    def test_a_negation_flip_is_not_rescued_by_segmenting(self):
        """The source says 'You cannot apply'. Splitting the inversion into segments must not
        turn it into a quotation."""
        r = check_evidence("You can apply for a D number... yourself", SOURCE)
        assert r.status == UNVERIFIED

    def test_the_recomposed_rule_still_discriminates(self):
        supported = check_evidence(
            "You can receive a D number if you: - attend an ID check when an enterprise asks you to",
            SOURCE,
        )
        unsupported = check_evidence(
            "You can receive a D number if you: - pay a fee of NOK 5,400 at the police station",
            SOURCE,
        )
        assert supported.status == VERIFIED
        assert unsupported.status == UNVERIFIED


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


# ---------------------------------------------------------------------------
# best_source_text — `knowledge_docs` has two source-text columns and neither
# is reliably the fuller one.
# ---------------------------------------------------------------------------


def test_best_source_text_takes_the_longer_column():
    assert best_source_text("short", "a much longer body of text") == "a much longer body of text"
    assert best_source_text("a much longer excerpt of text", "tiny") == "a much longer excerpt of text"


def test_best_source_text_handles_the_enterprise_gov_ie_shape():
    """The case that motivated it: the excerpt captured the consent notice and stopped, while
    text_content holds the permit page. Preferring the excerpt loses 9 served Irish facts."""
    cookie_banner = "Our website uses cookies to enhance your browsing experience " * 5
    real_page = "Because the skills are identified as being in short supply, " * 60
    assert best_source_text(cookie_banner, real_page) == real_page


def test_best_source_text_missing_columns_do_not_raise():
    assert best_source_text(None, None) == ""
    assert best_source_text(None, "body") == "body"
    assert best_source_text("excerpt", None) == "excerpt"


def test_best_source_text_a_tie_keeps_the_excerpt():
    """Equal length is no reason to switch column; the excerpt is the maintained one."""
    assert best_source_text("abcd", "wxyz") == "abcd"


def test_a_quote_only_in_text_content_still_verifies_through_the_resolver():
    """End to end: the resolver is what makes check_evidence see the Irish CSEP quotes."""
    quote = "a Labour Market Needs Test is not required"
    excerpt = "Our website uses cookies to enhance your browsing experience."
    body = ("The Critical Skills Employment Permit is designed to attract highly skilled people. "
            "Because the skills are identified as being in short supply, "
            + quote + ". Eligible occupations are listed separately. ") * 3
    assert check_evidence(quote, excerpt).status != VERIFIED
    assert check_evidence(quote, best_source_text(excerpt, body)).status == VERIFIED


# ---------------------------------------------------------------------------
# normalise() is the ONLY quote normaliser. Each fold below cost a real false
# negative before it existed; each non-fold protects a word or a guard.
# ---------------------------------------------------------------------------


def test_normalise_folds_a_list_bullet():
    assert normalise("prove: • you are resident or • your visa permits") == \
           "prove: you are resident or your visa permits"


def test_normalise_folds_the_service_public_template_token():
    """service-public.fr prints a literal `titleContent` inside its own sentences."""
    assert normalise("un salarié étranger (UE + EEE + Suisse) : titleContent en France") == \
           "un salarié étranger (UE + EEE + Suisse): en France"


def test_normalise_closes_a_space_before_punctuation():
    """What stripping an <a> or <li> around the mark leaves behind."""
    assert normalise("note : if you are") == "note: if you are"
    assert normalise("the Department (DSP) .") == "the Department (DSP)."


def test_normalise_closes_french_elision_split_across_a_tag():
    """CLEISS renders "L' article" for "l'article"; this alone had a genuine, verbatim CLEISS
    sentence recorded as fabricated."""
    assert normalise("L' article 11 du règlement") == "L'article 11 du règlement"


def test_normalise_does_not_touch_a_hyphen_inside_a_word():
    """Folding every dash would merge "e-mail" into "e mail" — a word, not markup."""
    assert "e-mail" in normalise("send an e-mail today")


def test_normalise_keeps_a_whitespace_delimited_dash():
    """Deliberate. It is markup by the same argument, but `_SEGMENT_SPLIT` keys on it, and
    folding it stops the recomposed-quote rule discriminating (see the planted-error suite)."""
    assert " - " in normalise("if you: - attend an ID check")


def test_normalise_keeps_a_slash():
    """The batch copy folded "/" to a space, which destroys "and/or"."""
    assert "and/or" in normalise("the spouse and/or partner")


def test_normalise_bullet_fold_runs_before_the_whitespace_collapse():
    """Order matters: collapse first and removing a bullet leaves a double space, so a true
    quote reads as missing."""
    assert "  " not in normalise("prove: • you and • your dependants")


def test_the_batch_checker_delegates_to_this_normaliser():
    """There is one definition. `verify_batch_quotes.norm` may only add the case-fold."""
    import importlib.util
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("vbq", root / "scripts" / "verify_batch_quotes.py")
    vbq = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vbq)
    for sample in ("L' article 11 (CE) n° 883/2004",
                   "prove: • you and • your dependants",
                   "note : if you are",
                   "send an e-mail today"):
        assert vbq.norm(sample) == normalise(sample).lower(), sample
