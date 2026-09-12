"""`applies_to.status` must refuse on the same terms its sibling `nationality` does.

`nationality` refuses loudly when it is absent, conflicting or unrecognised — because a NULL
nationality class means "applies to everyone" and would serve a visa track to a free mover.
`status` sat next to it and did the opposite: `PURPOSES.get(status or "", "other")` turned
all three of those into a plausible-looking `purpose='other'` row.

**That default is worse than it looks.** `crud.list_requirements` matches purpose with strict
`==` and no catch-all, and `public_corridor` defaults to `purpose='employment'`. So a row that
lands at 'other' by accident:

  * is counted as loaded by every count check and reconciliation,
  * appears in the reviewer's queue and can be approved,
  * and can never be returned to any reader.

It is invisible in precisely the way that looks like success. The VE→IE batch caught this by
hand at promote time — `docs/imports/ve-ie-entry-family-2026-08-20.md` records that all nine
rows would otherwise have promoted unservable — and the B3 batch's committed JSONL still
carries no `status` key on any of its facts.

`executor._unscoped_topics()` already pre-flights and *reports* exactly this set. These tests
turn that report into a refusal, and pin that the two stay consistent: an explicit `"any"` is
a deliberate choice and still promotes.
"""
from __future__ import annotations

from types import SimpleNamespace

from backend.imports.otto.mappings import PURPOSES, RequirementDraft, Unmapped, resolve

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


# ── the three ways a topic reaches 'other' without anyone choosing it ────────────────

def test_an_absent_status_refuses_instead_of_defaulting_to_other():
    """The B3 shape: every fact carries a nationality and no status at all."""
    got = resolve(_entity(), [_fact(applies_to={"nationality": "EU"})])
    assert isinstance(got, Unmapped), "an absent status must not promote"
    assert "no fact carries applies_to.status" in got.reason
    # The reason must say why it matters, not merely that a key is missing.
    assert "never return" in got.reason


def test_conflicting_statuses_refuse_and_say_so_distinctly():
    """Absence and disagreement are different problems and must not share a message."""
    got = resolve(
        _entity(),
        [
            _fact(applies_to={"status": "professional", "nationality": "EU"}),
            _fact(applies_to={"status": "student", "nationality": "EU"}),
        ],
    )
    assert isinstance(got, Unmapped)
    assert "disagree" in got.reason
    assert "professional" in got.reason and "student" in got.reason


def test_an_unrecognised_status_refuses():
    got = resolve(_entity(), [_fact(applies_to={"status": "tourist", "nationality": "EU"})])
    assert isinstance(got, Unmapped)
    assert "not a recognised purpose" in got.reason


# ── the control: the gate must discriminate, not blanket-refuse ──────────────────────

def test_an_explicit_any_still_promotes_at_other():
    """'other' is a legitimate purpose FRANCE already serves an approved row at.

    Choosing it deliberately is a decision; arriving at it by omission is the bug. Over-
    refusing here would break a real, live promotion path.
    """
    got = resolve(_entity(), [_fact(applies_to={"status": "any", "nationality": "EU"})])
    assert isinstance(got, RequirementDraft), got
    assert got.purpose == "other"


def test_every_recognised_status_still_promotes():
    for status, expected_purpose in PURPOSES.items():
        got = resolve(
            _entity(), [_fact(applies_to={"status": status, "nationality": "EU"})]
        )
        assert isinstance(got, RequirementDraft), f"{status} should promote, got {got}"
        assert got.purpose == expected_purpose


def test_worker_synonyms_map_to_employment():
    """Independent research passes describe the person as 'worker'/'employee'/'salaried' —
    synonyms of the canonical 'professional'. They must promote at purpose='employment', not be
    refused (the first live NO->FR consensus run staged 5 facts that could not promote for this
    reason alone). The gate still discriminates: 'tourist' etc. remain refused.
    """
    for status in ("worker", "employee", "salaried"):
        got = resolve(_entity(), [_fact(applies_to={"status": status, "nationality": "EU"})])
        assert isinstance(got, RequirementDraft), f"{status} should promote, got {got}"
        assert got.purpose == "employment"


def test_agreement_across_several_facts_still_promotes():
    got = resolve(
        _entity(),
        [
            _fact(applies_to={"status": "professional", "nationality": "EU"}),
            _fact(fact_key="other", applies_to={"status": "professional", "nationality": "EU"}),
        ],
    )
    assert isinstance(got, RequirementDraft), got
    assert got.purpose == "employment"


# ── the refusal and the pre-flight report must agree ─────────────────────────────────

def test_the_refusal_matches_what_unscoped_topics_pre_flights():
    """`_unscoped_topics` reports; `resolve` refuses. They must describe the same set.

    If they drift, an operator either sees a clean pre-flight and then a refusal at promote,
    or a warning for something that promotes fine — and learns to ignore whichever cried
    wolf first.
    """
    from backend.imports.otto.executor import _unscoped_topics

    cases = {
        "absent": {"nationality": "EU"},
        "unrecognised": {"status": "tourist", "nationality": "EU"},
        "explicit_any": {"status": "any", "nationality": "EU"},
        "recognised": {"status": "professional", "nationality": "EU"},
    }
    for name, applies_to in cases.items():
        row = SimpleNamespace(
            destination_country="FR", entity_topic_key=f"topic_{name}", applies_to=applies_to
        )
        reported = bool(_unscoped_topics([row]))
        refused = isinstance(resolve(_entity(), [_fact(applies_to=applies_to)]), Unmapped)
        assert reported == refused, (
            f"{name}: pre-flight reported={reported} but resolve refused={refused} — "
            "the report and the refusal have drifted apart"
        )
