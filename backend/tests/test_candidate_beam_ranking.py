"""Candidate Beam — the dedupe/ranking port must reproduce the validated run exactly.

Two fixtures, and the distinction between them is the point:

* `candidate_beam_fr_no_eea_pass_outputs.json` — the INPUT. The exact ordered material the
  reference finalizer consumed: raw per-pass parsed items, ascending pass order, array
  order preserved within each pass. Storage shape, snake_case.
* `candidate_beam_fr_no_eea.json` — the EXPECTED OUTPUT. The 35 persisted candidates of
  the reference FR-NO/eea run. Export shape, camelCase presentation keys
  (`passFrequency` is the string `"5/5"`).

Feeding the first through this port must land on the second at every rank — title,
frequency, band, flags and joined source string. Not a count check: counts coincide, a
35-row field-by-field identity does not.

**Why the input fixture is separate.** The published candidate payload groups variants by
candidate in RANK order, which is not the order any pass emitted them, and the clustering
is greedy in arrival order with cluster token sets that grow on join — so order decides
membership, not just presentation. Reconstructing passes by walking that payload gives 26
flagged instead of 25: "Employer Registration in Norway" (pass 4) scores 0.4654 against
the "Employer's Obligation to Register Workplace in Norway" cluster but 0.50 against "Tax
Registration in Norway", so best-fit sends it to the wrong home. Across 200 random
within-pass shuffles, 100 reproduce the reference and 100 do not. That is the algorithm's
order sensitivity, and it is why the true ordering had to be exported rather than inferred.

Best-fit joining is the specified rule and is confirmed here: first-fit also produces
35/25/10 and the same bands, and only the representative-title set separates the two.
Every number in the original spec was blind to that difference.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from backend.imports.candidate_beam.ranking import (
    BAND_LOW,
    BAND_MODERATE,
    BAND_NEAR_CERTAIN,
    BAND_STRONG,
    build_candidates,
    confidence_band,
    normalise_source,
    parse_variant,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
INPUT_FIXTURE = FIXTURES / "candidate_beam_fr_no_eea_pass_outputs.json"
EXPECTED_FIXTURE = FIXTURES / "candidate_beam_fr_no_eea.json"


@pytest.fixture(scope="module")
def pass_outputs() -> list:
    """The canonical ordered input, ascending by pass."""
    payload = json.loads(INPUT_FIXTURE.read_text())
    return sorted(payload["passOutputs"], key=lambda p: p["pass"])


@pytest.fixture(scope="module")
def expected() -> list:
    """The 35 persisted candidates, ascending by rank."""
    payload = json.loads(EXPECTED_FIXTURE.read_text())
    return sorted(payload["candidates"], key=lambda c: c["rank"])


@pytest.fixture(scope="module")
def ported(pass_outputs) -> list:
    return build_candidates(
        [p["items"] for p in pass_outputs],
        [p["framing"] for p in pass_outputs],
    )


# ---------------------------------------------------------------------------
# The golden gate.
# ---------------------------------------------------------------------------


def test_input_fixture_is_the_run_it_claims_to_be(pass_outputs):
    """Guards the fixture itself, so a swapped or truncated export fails loudly here
    rather than as a confusing ranking mismatch twenty assertions later."""
    assert [p["pass"] for p in pass_outputs] == [1, 2, 3, 4, 5]
    assert [len(p["items"]) for p in pass_outputs] == [14, 10, 11, 12, 10]
    assert [p["framing"] for p in pass_outputs] == [
        "zero_shot_official_audit",
        "few_shot_gap_hunter",
        "lived_experience",
        "professional_advisor",
        "red_team_gap_finder",
    ]


def test_reproduces_the_reference_run_field_by_field(ported, expected):
    """THE gate. Every rank, every field the reference persisted."""
    assert len(ported) == len(expected) == 35
    for mine, ref in zip(ported, expected):
        context = f"rank {ref['rank']} — {ref['title']}"
        assert mine["rank"] == ref["rank"], context
        assert mine["title"] == ref["title"], context
        assert f"{mine['pass_frequency']}/{mine['passes_total']}" == ref["passFrequency"], context
        assert mine["confidence_band"] == ref["confidenceBand"], context
        assert bool(mine["flagged"]) is bool(ref["flagged"]), context
        assert bool(mine["source_missing"]) is bool(ref["source_missing"]), context
        assert mine["source"] == ref["source"], context


def test_headline_counts_from_the_spec(ported):
    """The 35 / 25 / 10 the brief names, kept as their own assertion so a regression
    reports the familiar number rather than only a per-rank diff."""
    assert len(ported) == 35
    assert sum(1 for c in ported if c["flagged"]) == 25
    assert sum(1 for c in ported if c["source_missing"]) == 10


def test_rank_one_is_the_digital_identity_item(ported):
    top = ported[0]
    assert top["rank"] == 1
    assert top["title"] == "Preserving Digital Identity"
    assert (top["pass_frequency"], top["passes_total"]) == (5, 5)
    assert top["confidence_band"] == BAND_NEAR_CERTAIN
    assert top["flagged"] is True
    assert top["source_missing"] is True


def test_framings_are_carried_onto_every_variant(ported, pass_outputs):
    """A reviewer auditing divergence needs to know which persona produced a variant;
    losing the framing turns the variants panel into anonymous duplicates."""
    by_pass = {p["pass"]: p["framing"] for p in pass_outputs}
    for candidate in ported:
        for variant in candidate["variants"]:
            assert variant["framing"] == by_pass[variant["pass"]]


# ---------------------------------------------------------------------------
# Order-invariant properties — true under every ordering tried.
# ---------------------------------------------------------------------------


def test_ranks_are_contiguous_and_one_based(ported):
    assert [c["rank"] for c in ported] == list(range(1, len(ported) + 1))


def test_rank_order_is_frequency_then_sourced_then_title(ported):
    keys = [(-c["pass_frequency"], c["source_missing"], c["title"]) for c in ported]
    assert keys == sorted(keys)


def test_no_candidate_is_dropped_for_being_rare(ported):
    """A 1-of-5 candidate is the point of the beam, not noise to be swept up."""
    singletons = [c for c in ported if c["pass_frequency"] == 1]
    assert singletons, "the reference run contains single-pass candidates"
    assert all(c["flagged"] for c in singletons)
    assert all(c["confidence_band"] == BAND_LOW for c in singletons)


def test_every_variant_survives_into_some_cluster(ported, pass_outputs):
    """Clustering regroups; it never discards. The union is persisted."""
    fed = sum(len(p["items"]) for p in pass_outputs)
    kept = sum(len(c["variants"]) for c in ported)
    assert kept == fed


def test_headline_counts_hold_under_a_different_arrival_order(pass_outputs):
    """Clustering is order-sensitive by construction, so the cluster COUNT and the
    unsourced count are asserted to survive reordering while exact membership is not.
    This pins what the algorithm guarantees and refuses to over-claim the rest."""
    reordered = build_candidates([list(reversed(p["items"])) for p in pass_outputs])
    assert len(reordered) == 35
    assert sum(1 for c in reordered if c["source_missing"]) == 10


# ---------------------------------------------------------------------------
# Unit gates.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "frequency,expected_band",
    [(5, BAND_NEAR_CERTAIN), (4, BAND_STRONG), (3, BAND_STRONG), (2, BAND_MODERATE), (1, BAND_LOW)],
)
def test_band_boundaries_at_five_passes(frequency, expected_band):
    assert confidence_band(frequency, 5) == expected_band


@pytest.mark.parametrize("junk", ["n/a", "N/A", "none", "None", "example.com", "  ", "", "tbd", "-"])
def test_junk_sources_become_null(junk):
    assert normalise_source(junk) is None


@pytest.mark.parametrize("real", ["udi.no", "skatteetaten.no", "service-public.fr"])
def test_real_sources_are_stored_verbatim(real):
    """Never URL-ified, never 'cleaned' — the string is the model's CLAIM and a human
    verifies it later. Rewriting it asserts something the model never said."""
    assert normalise_source(f"  {real} ") == real


def test_unusable_items_are_dropped():
    assert parse_variant({"title": "", "action_required": "do it"}, 1) is None
    assert parse_variant({"title": "Something", "action_required": ""}, 1) is None
    assert parse_variant({"title": "Something", "action_required": "do it"}, 1) is not None


def test_a_failed_pass_does_not_inflate_agreement():
    """A run that completed 4 of 5 passes must report x/5, not x/4 — otherwise a
    partially-failed run reads as more unanimous than a complete one."""
    item = {"title": "Register with the folkeregister", "action_required": "Book an appointment"}
    built = build_candidates([[item], [item], [item], [item], []])
    assert built[0]["passes_total"] == 5
    assert built[0]["pass_frequency"] == 4
    assert built[0]["confidence_band"] == BAND_STRONG
