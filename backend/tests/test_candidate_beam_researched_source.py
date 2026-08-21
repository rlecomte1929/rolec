"""A human-researched source rescues a candidate the beam could not cite.

Around a quarter of a run arrives with no source — 10 of 35 in the validated FR→NO run —
and `FactRow` requires a URL, so those candidates are unimportable no matter how real the
obligation is. These tests pin what happens when a person supplies the missing citation, and
more importantly what does NOT happen: the model's claim is never overwritten, and research
never buys a better accuracy tier.
"""
from __future__ import annotations

import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.imports.candidate_beam import importer  # noqa: E402
from backend.imports.otto import parsers  # noqa: E402

OFFICIAL = "https://www.udi.no/en/want-to-apply/registration-eu-eea/"
BLOG = "https://some-relocation-blog.example.com/moving-to-norway"


def candidate(**over):
    """An UNSOURCED candidate — the case this whole feature exists for."""
    base = {
        "candidate_uid": "c1",
        "title": "Child School Registration in Norway",
        "official_guidance": "Register the child with the municipality.",
        "actual_reality": "Places are allocated by catchment.",
        "action_required": "Contact the kommune on arrival.",
        "source": None,
        "researched_source_url": None,
        "researched_evidence_quote": None,
        "category": "registration",
        "status": "approved",
        "flagged": True,
        "pass_frequency": 2,
        "confidence_band": "moderate",
    }
    base.update(over)
    return base


def _row(cand, pillar="RESIDENCE"):
    return importer.to_fact_row(cand, country="NORWAY", batch_id="b1", pillar=pillar)


# ─── the rescue ─────────────────────────────────────────────────────────────

def test_an_unsourced_candidate_is_skipped_until_someone_researches_it():
    plan = importer.plan_import([candidate()], country="NORWAY", batch_id="b1")
    assert plan.importable == 0
    assert "no source" in plan.skipped[0].reason


def test_a_researched_source_makes_the_same_candidate_importable():
    plan = importer.plan_import(
        [candidate(researched_source_url=OFFICIAL)], country="NORWAY", batch_id="b1"
    )
    assert plan.importable == 1
    assert plan.skipped == []


def test_the_researched_url_is_what_gets_staged():
    row = _row(candidate(researched_source_url=OFFICIAL))
    assert row.source_url == OFFICIAL


def test_a_researched_source_may_carry_the_quote_the_beam_never_had():
    row = _row(
        candidate(
            researched_source_url=OFFICIAL,
            researched_evidence_quote="EU/EEA nationals must register within three months.",
        )
    )
    assert row.evidence_quote == "EU/EEA nationals must register within three months."


# ─── what research must NOT buy ─────────────────────────────────────────────

def test_research_does_not_lift_the_accuracy_tier():
    """The load-bearing assertion.

    An official government URL found by a person is better provenance than a model claim and
    is still not a checked citation. If this ever fails, beam output has quietly gained a
    route to auto-accepted, which is the failure this feature was designed not to create.
    """
    row = _row(candidate(researched_source_url=OFFICIAL))
    assert row.accuracy_tier == parsers.TIER_REVIEW


def test_the_staged_row_says_which_provenance_it_used():
    researched = _row(candidate(researched_source_url=OFFICIAL))
    claimed = _row(candidate(source=OFFICIAL))

    assert any("human-researched" in d for d in researched.downgrades)
    assert not any("human-researched" in d for d in claimed.downgrades)
    assert any("model's unverified claim" in d for d in claimed.downgrades)


def test_the_models_claim_wins_when_both_exist_and_is_not_silently_replaced():
    """The model's claim is what the row was generated from, so it stays the source of record;
    the research is kept beside it in the beam table rather than overwriting history."""
    row = _row(candidate(source=OFFICIAL, researched_source_url=BLOG))
    assert row.source_url == OFFICIAL
    assert any("model's unverified claim" in d for d in row.downgrades)


def test_no_quote_is_synthesised_for_a_model_claimed_source():
    row = _row(candidate(source=OFFICIAL, researched_evidence_quote="not mine to use"))
    assert row.evidence_quote is None


# ─── an unofficial researched source is recorded, not refused ───────────────

def test_an_unofficial_researched_source_still_imports_but_is_downgraded():
    """A reviewer may genuinely have nothing better than a blog. Refusing it strands a real
    obligation; accepting it silently launders a weak citation. So it imports, and says so."""
    row = _row(candidate(researched_source_url=BLOG))
    assert row.source_class == "unofficial"
    assert any("unofficial" in d for d in row.downgrades)
    assert row.accuracy_tier == parsers.TIER_REVIEW


def test_a_blank_researched_url_is_not_a_source():
    with pytest.raises(ValueError, match="no source"):
        _row(candidate(researched_source_url="   "))
