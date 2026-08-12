"""The four rules that decide whether an Otto fact becomes a requirement a user reads.

`mappings.resolve()` is pure, so every rule below is provable without a database. That is the
point of keeping the decision surface out of the executor — the same reason
`vendor_harvester.plan_pair()` is separate from `suppliers/executor.stage()`.

The rule these tests exist for is the nationality one. `requirement_items`
`applies_to_nationality_classes_json = NULL` means *applies to everyone*, and
`nationality_class.py` was written because serving the non-EEA visa track to an EU free mover
is the bug this codebase keeps re-committing. Otto writes `"any"` on entities like
`schengen_court_sejour` — a short-stay visa an EU citizen does not need at all. So `"any"` is
not a categorisation; it is the absence of one, and it must not promote.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.imports.otto.mappings import (
    DEFAULT_OWNER,
    DEFAULT_SEVERITY,
    IMMIGRATION_PILLAR,
    RequirementDraft,
    Unmapped,
    compose_description,
    resolve,
)

OFFICIAL = "https://www.service-public.gouv.fr/particuliers/vosdroits/F16003"


def _entity(**over):
    base = dict(
        destination_country="FR",
        topic_key="eu_free_movement_worker",
        title="EU/EEA/Swiss citizen – worker right of residence",
        domain_area="immigration",
    )
    base.update(over)
    return SimpleNamespace(**base)


def _fact(**over):
    base = dict(
        id="00000000-0000-0000-0000-000000000001",
        fact_type="fee",
        fact_key="cardFee",
        fact_text="The card is free of charge.",
        applies_to={"role": "primary", "status": "professional", "nationality": "EU"},
        source_url=OFFICIAL,
        evidence_quote="délivrée gratuitement",
        accuracy_tier="auto_accepted",
    )
    base.update(over)
    return SimpleNamespace(**base)


# ── rule 1: categorise the audience, or refuse ───────────────────────────────────────

def test_nationality_any_is_not_a_categorisation_and_does_not_promote():
    """`schengen_court_sejour` carries nationality 'any'. NULL classes would serve a
    short-stay visa requirement to an EU citizen who needs no visa at all."""
    got = resolve(_entity(topic_key="schengen_court_sejour"),
                  [_fact(applies_to={"status": "any", "nationality": "any"})])
    assert isinstance(got, Unmapped)
    assert "applies to everyone" in got.reason


def test_a_missing_nationality_does_not_promote():
    got = resolve(_entity(), [_fact(applies_to={"status": "professional"})])
    assert isinstance(got, Unmapped)


@pytest.mark.parametrize(
    "nationality,want",
    [("EU", ["OWN_NATIONAL", "EU_EEA"]), ("non-EEA", ["THIRD_COUNTRY"])],
)
def test_an_explicit_nationality_maps_to_the_class_set(nationality, want):
    got = resolve(_entity(), [_fact(applies_to={"status": "professional",
                                                "nationality": nationality})])
    assert isinstance(got, RequirementDraft)
    assert got.payload["applies_to_nationality_classes_json"] == str(want).replace("'", '"')


def test_facts_that_disagree_on_audience_are_not_one_requirement():
    got = resolve(_entity(), [
        _fact(applies_to={"status": "professional", "nationality": "EU"}),
        _fact(fact_key="other", applies_to={"status": "professional", "nationality": "non-EEA"}),
    ])
    assert isinstance(got, Unmapped)
    assert "disagree" in got.reason


# ── rule 2: provenance is derived from the weakest fact ──────────────────────────────

def test_one_needs_review_fact_downgrades_the_whole_requirement():
    """The facts are merged into a single description a reader cannot unpick, so the
    requirement can be no stronger than its weakest source."""
    got = resolve(_entity(), [
        _fact(),
        _fact(fact_key="cardDuration", accuracy_tier="needs_review"),
    ])
    assert got.verification_status == "representative"
    assert any("not source-grounded" in d for d in got.derivations)


def test_a_self_assigned_tier_without_a_quote_does_not_earn_corpus_grounded():
    """The 2026-08-12 defect, pinned.

    `accuracy_tier` is a column in `otto_staging`, and the research routine writes rows
    straight into that schema setting `auto_accepted` on its own output — the parser's
    sourcing gate never runs. Two France requirements shipped badged "Source-grounded" while
    all 15 contributing facts had `evidence_quote IS NULL`. A tier the producer assigned to
    itself is a claim; the quote is the evidence, and it is checked independently.
    """
    got = resolve(_entity(), [
        _fact(accuracy_tier="auto_accepted", evidence_quote=None),
        _fact(fact_key="cardDuration", accuracy_tier="auto_accepted", evidence_quote=""),
    ])
    assert got.verification_status == "representative"
    assert any("no evidence_quote" in d for d in got.derivations)


def test_all_auto_accepted_facts_earn_corpus_grounded():
    got = resolve(_entity(), [_fact(), _fact(fact_key="cardDuration")])
    assert got.verification_status == "corpus_grounded"


def test_promotion_never_produces_expert_verified():
    """That status is a human signature. Nothing in this pipeline may write it."""
    got = resolve(_entity(), [_fact()])
    assert got.verification_status != "expert_verified"


# ── rule 3: refuse rather than guess a target column ─────────────────────────────────

def test_a_country_outside_the_requirement_catalog_does_not_promote():
    """`iso_to_catalog_name` is the narrow map — it answers 'do we hold catalog data?'.
    Australia and Canada have staged facts but no catalog coverage."""
    got = resolve(_entity(destination_country="AU", topic_key="189-visa-fee"), [_fact()])
    assert isinstance(got, Unmapped)
    assert "catalog coverage" in got.reason


def test_a_non_immigration_entity_does_not_borrow_the_residence_pillar():
    got = resolve(_entity(domain_area="tax"), [_fact()])
    assert isinstance(got, Unmapped)
    assert "domain_area" in got.reason


def test_an_entity_with_no_facts_is_a_worklist_item_not_a_requirement():
    """17 of the FR entities are enumerated topics Otto never delivered content for."""
    got = resolve(_entity(topic_key="talent_chercheur"), [])
    assert isinstance(got, Unmapped)
    assert "never delivered" in got.reason


def test_an_unbounded_topic_key_still_resolves():
    """Topic keys are invented per country and unbounded (`189-visa-fee`,
    `crs-score-draw-process`). A per-topic mapping table would stall on every new one."""
    got = resolve(_entity(topic_key="some-topic-nobody-predicted"), [_fact()])
    assert isinstance(got, RequirementDraft)


# ── rule 4: the derived columns say what they are ────────────────────────────────────

def test_severity_is_warn_because_otto_cannot_express_blocking_ness():
    """The France set includes `cardOptional` — an optional card. Defaulting to BLOCKER
    would assert the opposite of what the source says."""
    got = resolve(_entity(), [_fact()])
    assert got.payload["severity"] == DEFAULT_SEVERITY == "WARN"
    assert any("not derivable" in d for d in got.derivations)


def test_pillar_is_read_off_domain_area_not_guessed():
    got = resolve(_entity(), [_fact()])
    assert got.payload["pillar"] == IMMIGRATION_PILLAR
    assert got.payload["owner"] == DEFAULT_OWNER


@pytest.mark.parametrize(
    "status,want", [("professional", "employment"), ("student", "study"), ("any", "other")]
)
def test_purpose_comes_from_applies_to_status(status, want):
    got = resolve(_entity(), [_fact(applies_to={"status": status, "nationality": "EU"})])
    assert got.payload["purpose"] == want


def test_citations_carry_every_distinct_source():
    got = resolve(_entity(), [
        _fact(),
        _fact(fact_key="cardDuration", source_url="https://www.legifrance.gouv.fr/x"),
        _fact(fact_key="cardOptional"),          # duplicate URL, must not repeat
    ])
    assert got.payload["citations_json"].count("http") == 2


def test_description_order_is_stable_so_a_rerun_is_a_real_no_op():
    """`create_requirement_item` upserts; unstable text would rewrite the row every run and
    make a no-op look like a change."""
    facts = [_fact(fact_type="fee", fact_key="b"), _fact(fact_type="eligibility", fact_key="a")]
    assert compose_description(facts) == compose_description(list(reversed(facts)))
    assert compose_description(facts).startswith(facts[1].fact_text)
