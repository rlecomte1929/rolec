"""Importing approved beam candidates into the existing otto_staging flow.

The tests that matter here are the refusals. Staging a row is easy; the value of this
layer is that it will not launder unverified model text into the fact pipeline, and every
assertion below pins one way it could.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.imports.candidate_beam import importer  # noqa: E402
from backend.imports.otto import parsers  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def candidate(**over):
    base = {
        "candidate_uid": "c1",
        "title": "Tax Exit from France",
        "official_guidance": "File form 2042.",
        "actual_reality": "The office often asks for proof of departure.",
        "action_required": "File the exit declaration before leaving.",
        "source": "https://www.impots.gouv.fr/particulier/depart",
        "category": "tax",
        "status": "approved",
        "flagged": False,
        "pass_frequency": 4,
        "confidence_band": "strong",
    }
    base.update(over)
    return base


# ─── the pillar selector ────────────────────────────────────────────────────


def test_the_seven_canonical_pillars_are_the_production_vocabulary():
    """Measured from requirement_items on 2026-08-19, not invented."""
    assert set(importer.CANONICAL_PILLARS) == {
        "RESIDENCE", "IDENTITY", "EMPLOYMENT", "HOUSING",
        "SOCIAL_SECURITY", "TIMELINE", "HEALTHCARE",
    }


@pytest.mark.parametrize(
    "category,pillar",
    [
        ("tax", "EMPLOYMENT"),          # "Tax deduction card (skattekort) before first salary"
        ("payroll", "EMPLOYMENT"),
        ("health", "HEALTHCARE"),       # "French health cover (CPAM affiliation)"
        ("housing", "HOUSING"),         # "Long-term housing contract"
        ("registration", "RESIDENCE"),  # "Residence registration (folkeregister)"
        ("immigration", "RESIDENCE"),
        ("social_security", "SOCIAL_SECURITY"),  # "National Insurance registration"
    ],
)
def test_grounded_categories_map_to_their_production_pillar(category, pillar):
    assert importer.suggest_pillar(category) == pillar


@pytest.mark.parametrize("category", ["customs", "pets", "driving", "banking", "family", "other"])
def test_ungrounded_categories_return_none_rather_than_a_guess(category):
    """None is the answer. Bucketing customs paperwork under RESIDENCE would hide the
    decision inside an import and nobody would see it happen."""
    assert importer.suggest_pillar(category) is None


def test_all_thirteen_beam_categories_are_accounted_for():
    """Every category the validated run actually produced either maps or is explicitly
    left to a human — none falls through unnoticed."""
    payload = json.loads((FIXTURES / "candidate_beam_fr_no_eea_pass_outputs.json").read_text())
    seen = {i["category"] for p in payload["passOutputs"] for i in p["items"] if i.get("category")}
    assert len(seen) == 13
    grounded = {c for c in seen if importer.suggest_pillar(c)}
    assert grounded == {"tax", "payroll", "health", "housing", "registration",
                        "immigration", "social_security"}


# ─── the refusals ───────────────────────────────────────────────────────────


def test_unapproved_candidates_are_never_staged():
    """The beam review queue IS the human gate; importing around it defeats the point."""
    plan = importer.plan_import(
        [candidate(status="pending_review"), candidate(candidate_uid="c2", status="rejected")],
        country="FRANCE", batch_id="B1",
    )
    assert plan.importable == 0
    assert all("not approved" in s.reason for s in plan.skipped)


def test_an_unsourced_candidate_is_skipped_not_invented():
    """~10 of the validated run's 35 have no source. They are the research worklist —
    fabricating one would be the defect that survives review by looking already done."""
    plan = importer.plan_import([candidate(source=None)], country="FRANCE", batch_id="B1")
    assert plan.importable == 0
    assert "no source" in plan.skipped[0].reason


def test_an_ungrounded_category_is_skipped_until_a_human_selects():
    plan = importer.plan_import([candidate(category="pets")], country="NORWAY", batch_id="B1")
    assert plan.importable == 0
    assert "pillar unresolved" in plan.skipped[0].reason


def test_a_human_override_unblocks_an_ungrounded_category():
    plan = importer.plan_import(
        [candidate(category="pets")], country="NORWAY", batch_id="B1",
        pillar_overrides={"c1": "TIMELINE"},
    )
    assert plan.importable == 1
    assert plan.pillar_by_uid["c1"] == "TIMELINE"


def test_an_override_outside_the_canonical_vocabulary_is_refused():
    plan = importer.plan_import(
        [candidate(category="pets")], country="NORWAY", batch_id="B1",
        pillar_overrides={"c1": "PETS"},
    )
    assert plan.importable == 0
    assert "pillar invalid" in plan.skipped[0].reason


# ─── the tier control ───────────────────────────────────────────────────────


def test_beam_rows_can_never_reach_auto_accepted():
    """THE control. grade() awards auto_accepted on an official host + a quotable line.
    A beam source is the model's claim; an official-LOOKING host must not score like a
    checked citation."""
    row = importer.to_fact_row(
        candidate(source="https://www.skatteetaten.no/en/person/"),
        country="NORWAY", batch_id="B1", pillar="EMPLOYMENT",
    )
    assert row.source_class == parsers.OFFICIAL   # the host really is official…
    assert row.accuracy_tier == parsers.TIER_REVIEW  # …and it still cannot auto-accept
    assert any("unverified claim" in d for d in row.downgrades)


def test_regrading_a_beam_row_still_cannot_auto_accept_it():
    """Belt and braces: even if someone later runs grade() over these rows, the absent
    evidence_quote keeps them in needs_review."""
    row = importer.to_fact_row(
        candidate(source="https://www.skatteetaten.no/en/person/"),
        country="NORWAY", batch_id="B1", pillar="EMPLOYMENT",
    )
    regraded = parsers.grade(row)
    assert regraded.accuracy_tier == parsers.TIER_REVIEW


def test_no_evidence_quote_is_synthesised_from_the_model_prose():
    row = importer.to_fact_row(candidate(), country="FRANCE", batch_id="B1", pillar="EMPLOYMENT")
    assert not (row.evidence_quote or "")


def test_a_flagged_candidate_records_that_it_was_flagged():
    row = importer.to_fact_row(
        candidate(flagged=True), country="FRANCE", batch_id="B1", pillar="EMPLOYMENT",
    )
    assert any("flagged in beam review" in d for d in row.downgrades)


# ─── what the staged row carries ────────────────────────────────────────────


def test_the_raw_beam_category_is_kept_beside_the_canonical_pillar():
    """'pillar canonical + raw category kept' — the pillar is what the platform selects
    on; the category is the only record of what the model actually said."""
    row = importer.to_fact_row(candidate(), country="FRANCE", batch_id="B1", pillar="EMPLOYMENT")
    assert row.applies_to["pillar"] == "EMPLOYMENT"
    assert row.applies_to["beam_category"] == "tax"
    assert row.applies_to["beam_candidate_uid"] == "c1"


def test_the_fact_text_carries_all_three_body_fields():
    row = importer.to_fact_row(candidate(), country="FRANCE", batch_id="B1", pillar="EMPLOYMENT")
    for fragment in ("File form 2042.", "proof of departure", "exit declaration"):
        assert fragment in row.fact_text


def test_topic_key_is_derived_from_the_title_not_the_run_scoped_uid():
    """candidate_uid is per-run; keying on it would fragment one obligation across
    re-runs into separate staging entities."""
    a = importer.to_fact_row(candidate(candidate_uid="run1"), country="FRANCE", batch_id="B1", pillar="EMPLOYMENT")
    b = importer.to_fact_row(candidate(candidate_uid="run2"), country="FRANCE", batch_id="B2", pillar="EMPLOYMENT")
    assert a.entity_topic_key == b.entity_topic_key == "tax_exit_from_france"


def test_dedupe_key_matches_the_production_convention():
    row = importer.to_fact_row(candidate(), country="FRANCE", batch_id="B1", pillar="EMPLOYMENT")
    assert row.dedupe_key == "FRANCE|tax_exit_from_france|employment"


def test_topic_key_survives_punctuation_and_accents():
    assert importer.topic_key_for("Employer's Obligation — Register (workplace)") == (
        "employer_s_obligation_register_workplace"
    )


# ─── the audit stamp ────────────────────────────────────────────────────────


def test_audit_stamp_supplies_every_column_the_check_constraint_demands():
    """candidate_beam_items refuses status='imported' unless all four are present, so the
    stamp is assembled as one unit rather than risking a mid-batch rejection."""
    stamp = importer.audit_stamp(
        country="FRANCE", pillar="EMPLOYMENT", batch_id="B1", imported_by="romain",
    )
    assert stamp["status"] == "imported"
    for column in ("import_country", "import_requirement_type", "imported_ref", "imported_at"):
        assert stamp[column] is not None


# ─── the plan as a whole ────────────────────────────────────────────────────


def test_a_mixed_batch_reports_every_skip_with_a_reason():
    """A partial import that looks complete is the failure this repo's importers exist to
    stop — so nothing is dropped silently."""
    plan = importer.plan_import(
        [
            candidate(candidate_uid="ok"),
            candidate(candidate_uid="nosource", source=""),
            candidate(candidate_uid="pets", category="pets"),
            candidate(candidate_uid="draft", status="pending_review"),
        ],
        country="FRANCE", batch_id="B1",
    )
    assert plan.importable == 1
    assert len(plan.skipped) == 3
    assert set(plan.skips_by_reason()) == {"no source", "pillar unresolved", "not approved"}


def test_plan_import_writes_nothing():
    """It is a plan. The caller shows it, then stages inside its own transaction."""
    plan = importer.plan_import([candidate()], country="FRANCE", batch_id="B1")
    assert isinstance(plan.rows[0], parsers.FactRow)
    assert plan.importable == 1
