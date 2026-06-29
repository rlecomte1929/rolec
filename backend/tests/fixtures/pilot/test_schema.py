"""
AIQ-614 — Schema contract tests for the AI-W dossier evaluation harness.

11 pytest cases that validate Pydantic models without any PDF I/O.
All test data is constructed in-memory.
"""
from __future__ import annotations

import json
from datetime import date

import pytest
from pydantic import ValidationError

from backend.eval.schemas.dossier import (
    Bbox,
    CanonicalEntity,
    Dossier,
    EligibilityVerdict,
    ExtractedField,
    GenerationMeta,
    RuleCitation,
    SeededContradiction,
    Step,
    StepGraph,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_BBOX = {"x0": 50, "y0": 100, "x1": 200, "y1": 120}

_VALID_FIELD = {
    "field_key": "surname",
    "value": "Kapoor",
    "bbox": _VALID_BBOX,
    "confidence": 0.99,
}

_GENERATION_META = {
    "dossier_id": "IN_DE_001",
    "seed": 1,
    "generated_at": "2026-06-04T12:00:00Z",
    "schema_version": "1.0",
}

_RULE_CITATION = {
    "rule_version_id": "rv-2026-001",
    "article": "§19a AufenthG",
    "effective_from": "2026-01-01",
    "effective_to": None,
}

_ELIGIBILITY = {
    "outcome_set": ["ELIGIBLE_BLUE_CARD"],
    "citations": [_RULE_CITATION],
}

_STEP = {"step_id": "collect_passport", "description": "Collect passport", "required": True, "order": 1}

_CANONICAL_ENTITY = {
    "entity_type": "PERSON",
    "canonical_value": "Ananya Kapoor",
    "source_field_keys": ["given_name", "surname"],
}

_SEEDED_CONTRADICTION = {
    "contradiction_type": "SURNAME_MISMATCH",
    "field_key": "surname",
    "affected_documents": ["passport.pdf", "diploma.pdf"],
}


def _minimal_dossier(**overrides) -> dict:
    base = {
        "dossier_id": "IN_DE_001",
        "extracted_fields": [_VALID_FIELD],
        "canonical_entities": [_CANONICAL_ENTITY],
        "eligibility_verdict": _ELIGIBILITY,
        "step_graph": {"steps": [_STEP]},
        "seeded_contradictions": [],
        "generation_meta": _GENERATION_META,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Test cases 1–5: Valid Dossier round-trips through JSON
# ---------------------------------------------------------------------------


def test_01_dossier_round_trip_basic() -> None:
    """A minimal valid dossier round-trips through JSON without data loss."""
    d = Dossier(**_minimal_dossier())
    serialised = d.model_dump_json()
    d2 = Dossier.model_validate_json(serialised)
    assert d2.dossier_id == "IN_DE_001"
    assert len(d2.extracted_fields) == 1
    assert d2.extracted_fields[0].field_key == "surname"


def test_02_dossier_round_trip_multiple_fields() -> None:
    """A dossier with multiple extracted fields round-trips cleanly."""
    fields = [
        {"field_key": "surname", "value": "Sharma", "bbox": _VALID_BBOX, "confidence": 0.98},
        {"field_key": "given_name", "value": "Rahul", "bbox": {"x0": 60, "y0": 110, "x1": 180, "y1": 125}, "confidence": 0.97},
        {"field_key": "dob", "value": "1990-03-15", "bbox": {"x0": 70, "y0": 120, "x1": 190, "y1": 135}, "confidence": 0.95},
    ]
    d = Dossier(**_minimal_dossier(extracted_fields=fields))
    assert len(Dossier.model_validate_json(d.model_dump_json()).extracted_fields) == 3


def test_03_dossier_round_trip_with_contradiction() -> None:
    """A dossier containing a seeded contradiction round-trips correctly."""
    d = Dossier(**_minimal_dossier(seeded_contradictions=[_SEEDED_CONTRADICTION]))
    d2 = Dossier.model_validate_json(d.model_dump_json())
    assert d2.seeded_contradictions[0].contradiction_type == "SURNAME_MISMATCH"


def test_04_dossier_round_trip_with_rule_citation() -> None:
    """Eligibility verdict citations survive a round-trip with effective dates."""
    d = Dossier(**_minimal_dossier())
    d2 = Dossier.model_validate_json(d.model_dump_json())
    assert d2.eligibility_verdict.citations[0].article == "§19a AufenthG"


def test_05_dossier_round_trip_multiple_steps() -> None:
    """A step graph with multiple steps round-trips and preserves order."""
    steps = [
        {"step_id": "step_a", "description": "A", "required": True, "order": 1},
        {"step_id": "step_b", "description": "B", "required": False, "order": 2},
        {"step_id": "step_c", "description": "C", "required": True, "order": 3},
    ]
    d = Dossier(**_minimal_dossier(step_graph={"steps": steps}))
    d2 = Dossier.model_validate_json(d.model_dump_json())
    assert [s.order for s in d2.step_graph.steps] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Test case 6: Invalid bbox raises ValidationError (value > 1000)
# ---------------------------------------------------------------------------


def test_06_bbox_out_of_range_raises() -> None:
    """Bbox coordinate > 1000 must raise a ValidationError."""
    with pytest.raises(ValidationError):
        Bbox(x0=0, y0=0, x1=1001, y1=500)


# ---------------------------------------------------------------------------
# Test case 7: Missing required field raises ValidationError
# ---------------------------------------------------------------------------


def test_07_missing_required_field_raises() -> None:
    """Omitting a required ExtractedField attribute must raise ValidationError."""
    with pytest.raises(ValidationError):
        # 'value' is required
        ExtractedField(field_key="surname", bbox=Bbox(**_VALID_BBOX), confidence=0.99)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Test cases 8–9: RuleCitation effective_from / effective_to logic
# ---------------------------------------------------------------------------


def test_08_rule_citation_effective_to_none() -> None:
    """A RuleCitation with effective_to=None (open-ended) is valid."""
    rc = RuleCitation(
        rule_version_id="rv-1",
        article="§19a AufenthG",
        effective_from=date(2026, 1, 1),
        effective_to=None,
    )
    assert rc.effective_to is None


def test_09_rule_citation_with_effective_to() -> None:
    """A RuleCitation with both effective_from and effective_to is valid."""
    rc = RuleCitation(
        rule_version_id="rv-old",
        article="§19a AufenthG (old)",
        effective_from=date(2020, 1, 1),
        effective_to=date(2025, 12, 31),
    )
    assert rc.effective_to == date(2025, 12, 31)
    assert rc.effective_from < rc.effective_to


# ---------------------------------------------------------------------------
# Test case 10: SeededContradiction types are the 5 expected
# ---------------------------------------------------------------------------


def test_10_seeded_contradiction_five_types() -> None:
    """All five documented contradiction_type values are valid and distinct."""
    expected_types = [
        "SURNAME_MISMATCH",
        "DOB_MISMATCH",
        "EMPLOYER_MISMATCH",
        "SALARY_MISMATCH",
        "ADDRESS_MISMATCH",
    ]
    created = [
        SeededContradiction(
            contradiction_type=ct,
            field_key="test_field",
            affected_documents=["a.pdf", "b.pdf"],
        )
        for ct in expected_types
    ]
    assert [c.contradiction_type for c in created] == expected_types


# ---------------------------------------------------------------------------
# Test case 11: GenerationMeta schema_version defaults to "1.0"
# ---------------------------------------------------------------------------


def test_11_generation_meta_schema_version_default() -> None:
    """GenerationMeta.schema_version defaults to '1.0' when not supplied."""
    gm = GenerationMeta(
        dossier_id="IN_DE_001",
        seed=1,
        generated_at="2026-06-04T12:00:00Z",
    )
    assert gm.schema_version == "1.0"


# ---------------------------------------------------------------------------
# AIQ-511 — Pilot corpus materialization tests (cases 12–18)
#
# These exercise the full 20-dossier corpus. The generators / materializer use
# top-level `tests.*` / `eval.*` imports (they are designed to run with backend/
# on sys.path), so we add backend/ to sys.path here before importing them.
# ---------------------------------------------------------------------------

import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

#: Union of all synthetic name pools — used by the no-PII assertion.
_SYNTHETIC_GIVEN: set = set()
_SYNTHETIC_SURNAME: set = set()

_CONTRADICTION_TYPES = {
    "SURNAME_MISMATCH",
    "DOB_MISMATCH",
    "EMPLOYER_MISMATCH",
    "SALARY_MISMATCH",
    "ADDRESS_MISMATCH",
}


def _ensure_backend_on_path() -> None:
    if _BACKEND_DIR not in sys.path:
        sys.path.insert(0, _BACKEND_DIR)


def _materialize(out) -> list:
    """Materialize the corpus into *out*; return list of ground_truth dicts."""
    _ensure_backend_on_path()
    from tests.fixtures.pilot.materialize import materialize  # noqa: E402

    return materialize(str(out))


def _load_pools() -> None:
    _ensure_backend_on_path()
    from tests.fixtures.pilot.generators import base  # noqa: E402

    if not _SYNTHETIC_GIVEN:
        for pool in (base._FIRST_NAMES, base._FR_FIRST_NAMES, base._NO_FIRST_NAMES):
            _SYNTHETIC_GIVEN.update(pool)
        for pool in (base._PRIYA_SURNAMES, base._FR_SURNAMES, base._NO_SURNAMES):
            _SYNTHETIC_SURNAME.update(pool)


@pytest.fixture
def corpus(tmp_path):
    """Materialize the 20-dossier corpus once into tmp_path; return (gts, out_dir)."""
    gts = _materialize(tmp_path)
    return gts, tmp_path


def test_12_corpus_has_exactly_twenty_dossiers(corpus) -> None:
    """Materializing the corpus produces exactly 20 dossier directories."""
    gts, out = corpus
    assert len(gts) == 20
    dossier_dirs = [
        p for p in os.listdir(out)
        if os.path.isdir(os.path.join(out, p))
    ]
    assert len(dossier_dirs) == 20


def test_13_corpus_corridor_split(corpus) -> None:
    """The corpus splits 10 IN→DE + 10 FR→NO by dossier-id prefix."""
    gts, _ = corpus
    in_de = [g for g in gts if g["dossier_id"].startswith("IN_DE")]
    fr_no = [g for g in gts if g["dossier_id"].startswith("FR_NO")]
    assert len(in_de) == 10
    assert len(fr_no) == 10
    assert len(in_de) + len(fr_no) == 20


def test_14_every_ground_truth_validates_as_dossier(corpus) -> None:
    """Every ground_truth.json on disk validates against the Dossier schema."""
    gts, out = corpus
    for g in gts:
        gt_path = os.path.join(out, g["dossier_id"], "ground_truth.json")
        with open(gt_path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        Dossier(**raw)  # raises ValidationError on failure


def test_15_each_contradiction_type_appears_exactly_once(corpus) -> None:
    """The 5 canonical contradiction types each appear exactly once; 15 are clean."""
    gts, _ = corpus
    seeded = [
        c["contradiction_type"]
        for g in gts
        for c in g["seeded_contradictions"]
    ]
    assert sorted(seeded) == sorted(_CONTRADICTION_TYPES)
    assert len(seeded) == 5
    clean = [g for g in gts if not g["seeded_contradictions"]]
    assert len(clean) == 15


def test_16_no_real_pii_names_from_pools(corpus) -> None:
    """Person names come only from the synthetic pools (no real PII)."""
    gts, _ = corpus
    _load_pools()
    for g in gts:
        fields = {f["field_key"]: f["value"] for f in g["extracted_fields"]}
        assert fields["given_name"] in _SYNTHETIC_GIVEN, g["dossier_id"]
        assert fields["surname"] in _SYNTHETIC_SURNAME, g["dossier_id"]


def test_17_eligibility_outcomes_match_corridor(corpus) -> None:
    """Eligibility outcomes are corridor-appropriate (Blue Card vs EU free movement)."""
    gts, _ = corpus
    for g in gts:
        outcomes = g["eligibility_verdict"]["outcome_set"]
        assert outcomes, g["dossier_id"]
        if g["dossier_id"].startswith("FR_NO"):
            assert outcomes == ["ELIGIBLE_EU_FREE_MOVEMENT"], g["dossier_id"]
        elif g["dossier_id"].startswith("IN_DE_NODEG"):
            assert outcomes == ["ELIGIBLE_BLUE_CARD_IT_EXPERIENCE"], g["dossier_id"]
        else:  # IN_DE generic / family
            assert outcomes == ["ELIGIBLE_BLUE_CARD"], g["dossier_id"]


def test_18_corpus_is_deterministic(tmp_path) -> None:
    """Re-materializing yields byte-identical ground_truth EXCEPT generated_at."""
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    _materialize(out_a)
    _materialize(out_b)

    ids_a = sorted(p for p in os.listdir(out_a) if os.path.isdir(out_a / p))
    ids_b = sorted(p for p in os.listdir(out_b) if os.path.isdir(out_b / p))
    assert ids_a == ids_b

    for did in ids_a:
        with open(out_a / did / "ground_truth.json", "r", encoding="utf-8") as fh:
            a = json.load(fh)
        with open(out_b / did / "ground_truth.json", "r", encoding="utf-8") as fh:
            b = json.load(fh)
        # The only permitted non-deterministic field is the generated_at timestamp.
        a["generation_meta"].pop("generated_at", None)
        b["generation_meta"].pop("generated_at", None)
        assert a == b, f"{did} ground_truth differs beyond generated_at"
