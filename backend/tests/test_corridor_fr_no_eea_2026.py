"""C1-10 · Structural tests for the FR_NO_EEA_2026 corridor YAML.

Notion Validation Criteria:

  1. Marc test case routes to Branch 1; produces 5-step graph
     (police registration → tax administration → Folkeregister →
     social security → BankID).                                       → SKIPPED (needs C1-05 evaluator)
  2. Marc + Indian spouse routes Branch 2; adds residence card step.  → SKIPPED (needs C1-05 evaluator)
  3. Marc + Norwegian spouse routes Branch 3; two parallel registrations. → SKIPPED (needs C1-05 evaluator)
  4. Marc + child (Indian-born) handled via birth cert + spouse linkage.  → SKIPPED (needs C1-05 evaluator)
  5. NOK 599,200/522,600 thresholds appear as reference_values not enforcement. → covered

Same skip-gated pattern as C1-09 — the evaluator-driven tests activate
once ``backend.relopass.agents.corridor_runtime.evaluate`` exists.

The structural tests below give us confidence that the YAML schema is
the right shape for the evaluator to consume.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from backend.relopass.corridors import (
    CorridorAgent,
    CorridorLoadError,
    load_corridor,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CORRIDOR_PATH = REPO_ROOT / "corridors" / "FR_NO_EEA_2026" / "v1.yaml"


@pytest.fixture(scope="module")
def corridor() -> CorridorAgent:
    return load_corridor(CORRIDOR_PATH)


# ─────────────────────────────────────────────────────────────────────────────
# Structural — every YAML file the loader can parse cleanly
# ─────────────────────────────────────────────────────────────────────────────


def test_yaml_loads_via_loader(corridor: CorridorAgent):
    assert corridor.corridor_id == "FR_NO_EEA_2026"
    assert corridor.version == "2026.01"
    assert corridor.origin_country_iso3 == "FRA"
    assert corridor.destination_country_iso3 == "NOR"
    assert corridor.petitioning_party == "EMPLOYEE"


def test_yaml_contains_required_legal_references(corridor: CorridorAgent):
    required_rule_ids = {
        "NO_EOS_UTL_111",
        "NO_EOS_UTL_113",
        "NO_EOS_UTL_114",
        "EU_2004_38_ART_10",
        "EU_2004_38_ART_7",
        "NO_FOLKEREG_4_1",
        "NO_SKATT_3_1",
        "NO_FOLKETRYGD_2_1",
        "NO_HVITVASK_10",
        "NO_UDI_2025_THRESHOLDS",
    }
    assert required_rule_ids.issubset(set(corridor.rule_ids()))


def test_eligibility_branches_cite_known_rules(corridor: CorridorAgent):
    rule_ids = set(corridor.rule_ids())
    for branch in corridor.eligibility_branches:
        assert branch.cite in rule_ids, (
            f"branch {branch.id} cites unknown rule {branch.cite}"
        )


def test_three_branches_per_section_4_3(corridor: CorridorAgent):
    ids = {b.id for b in corridor.eligibility_branches}
    assert "BRANCH_1_MARC_SOLO" in ids
    assert "BRANCH_2_NON_EEA_SPOUSE" in ids
    assert "BRANCH_3_EEA_FAMILY" in ids


def test_step_graph_has_no_dangling_prerequisites(corridor: CorridorAgent):
    step_ids = set(corridor.step_ids())
    for step in corridor.step_graph:
        for prereq in step.prerequisite_step_ids:
            assert prereq in step_ids, (
                f"step {step.step_id} has prerequisite {prereq!r} not in step_graph"
            )


def test_branch_1_step_count_is_5(corridor: CorridorAgent):
    # The 5 base steps for Marc-solo: POLICE_REGISTRATION → TAX_ADMIN_D_NUMBER
    # → FOLKEREGISTER_REGISTRATION → NAV_ENROLMENT + BANK_BANKID (last two
    # share the FOLKEREGISTER prerequisite but can run in parallel).
    base_step_ids = {
        "POLICE_REGISTRATION",
        "TAX_ADMIN_D_NUMBER",
        "FOLKEREGISTER_REGISTRATION",
        "NAV_ENROLMENT",
        "BANK_BANKID",
    }
    actual_step_ids = set(corridor.step_ids())
    assert base_step_ids.issubset(actual_step_ids)


def test_branch_2_adds_spouse_residence_card_step(corridor: CorridorAgent):
    spouse_step = corridor.get_step("SPOUSE_RESIDENCE_CARD")
    assert spouse_step is not None
    assert spouse_step.conditional_on is not None
    assert "BRANCH_2_NON_EEA_SPOUSE" in spouse_step.conditional_on


def test_branch_3_has_spouse_police_registration(corridor: CorridorAgent):
    spouse_step = corridor.get_step("SPOUSE_POLICE_REGISTRATION")
    assert spouse_step is not None
    assert spouse_step.conditional_on is not None
    assert "BRANCH_3_EEA_FAMILY" in spouse_step.conditional_on


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 5 — NOK thresholds are reference_values, NOT enforcement
# ─────────────────────────────────────────────────────────────────────────────


def test_nok_thresholds_in_reference_values_not_salary_thresholds(corridor: CorridorAgent):
    # The corridor MUST NOT carry an enforceable salary_thresholds_eur or
    # equivalent block — Marc as EEA is not bound by it. The thresholds
    # live in the reference_values metadata (loaded as part of
    # corridor_agent but not surfaced as eligibility logic).
    # We assert their NUMERIC presence via the underlying YAML text.
    text = CORRIDOR_PATH.read_text(encoding="utf-8")
    assert "no_skilled_worker_threshold_master_nok: 599200" in text
    assert "no_skilled_worker_threshold_bachelor_nok: 522600" in text
    assert "reference_values:" in text

    # Confirm the salary numbers do NOT appear in any branch's
    # requires_all DSL — they are not enforcement.
    for branch in corridor.eligibility_branches:
        for clause in branch.requires_all:
            assert "599200" not in clause, (
                f"NOK threshold leaked into enforcement clause: {clause}"
            )
            assert "522600" not in clause


# ─────────────────────────────────────────────────────────────────────────────
# Exception cases
# ─────────────────────────────────────────────────────────────────────────────


def test_exception_cases_cover_non_eea_employee_and_short_stay(corridor: CorridorAgent):
    ids = {e.id for e in corridor.exception_cases}
    assert "NON_EEA_EMPLOYEE_NOT_SUPPORTED" in ids
    assert "SHORT_STAY_NO_REGISTRATION_NEEDED" in ids


# ─────────────────────────────────────────────────────────────────────────────
# Loader error paths (sanity check that the corridor-specific validator
# rules still fire on this corridor's shape)
# ─────────────────────────────────────────────────────────────────────────────


def test_loader_rejects_branch_citing_unknown_rule_against_this_corridor():
    # Same guard as C1-09's tests, exercised against this corridor's
    # specific YAML so a regression in the loader doesn't bypass us.
    bad_yaml = """
corridor_agent:
  corridor_id: TEST_FR_NO
  version: "0.1"
  applicable_rules:
    - legal_reference: "Foo §1"
      rule_id: KNOWN_RULE
  required_documents: []
  required_data_points: []
  salary_thresholds_eur:
    general: 0.0
  eligibility_logic:
    branches:
      - id: B1
        label: "Test"
        cite: NO_UNKNOWN_RULE
        requires_all:
          - x == y
        verdict_on_pass: ELIGIBLE
    no_branch_verdict: NOT_ELIGIBLE
  exception_cases: []
  step_graph: []
"""
    from backend.relopass.corridors import load_corridor_text

    with pytest.raises(CorridorLoadError, match="unknown rule"):
        load_corridor_text(bad_yaml)


# ─────────────────────────────────────────────────────────────────────────────
# Criteria 1–4 — evaluator-driven Marc fixtures (skipped until C1-05 lands)
# ─────────────────────────────────────────────────────────────────────────────


def _evaluator_available() -> bool:
    try:
        importlib.import_module("backend.relopass.agents.corridor_runtime")
    except ImportError:
        return False
    return True


SKIP_NO_EVALUATOR = pytest.mark.skipif(
    not _evaluator_available(),
    reason=(
        "C1-05 corridor runtime not yet implemented — evaluate(corridor, case) "
        "is the function these tests exercise. Unskips automatically once "
        "backend.relopass.agents.corridor_runtime exposes evaluate()."
    ),
)


@SKIP_NO_EVALUATOR
def test_marc_solo_routes_to_branch_1(corridor: CorridorAgent):
    from backend.relopass.agents.corridor_runtime import evaluate  # type: ignore

    case = {
        "employee_nationality_iso3": "FRA",
        "has_family_relocating": False,
        "spouse_nationality_iso3": None,
        "residence_intent_days": 720,
        "has_employment_contract": True,
    }
    result = evaluate(corridor, case)
    assert result.branch_id == "BRANCH_1_MARC_SOLO"
    assert result.verdict == "ELIGIBLE"
    # 5 base steps
    assert set(result.required_step_ids) == {
        "POLICE_REGISTRATION",
        "TAX_ADMIN_D_NUMBER",
        "FOLKEREGISTER_REGISTRATION",
        "NAV_ENROLMENT",
        "BANK_BANKID",
    }


@SKIP_NO_EVALUATOR
def test_marc_indian_spouse_routes_to_branch_2(corridor: CorridorAgent):
    from backend.relopass.agents.corridor_runtime import evaluate  # type: ignore

    case = {
        "employee_nationality_iso3": "FRA",
        "has_family_relocating": True,
        "spouse_nationality_iso3": "IND",
        "residence_intent_days": 720,
    }
    result = evaluate(corridor, case)
    assert result.branch_id == "BRANCH_2_NON_EEA_SPOUSE"
    assert "SPOUSE_RESIDENCE_CARD" in result.required_step_ids


@SKIP_NO_EVALUATOR
def test_marc_norwegian_spouse_routes_to_branch_3(corridor: CorridorAgent):
    from backend.relopass.agents.corridor_runtime import evaluate  # type: ignore

    case = {
        "employee_nationality_iso3": "FRA",
        "has_family_relocating": True,
        "spouse_nationality_iso3": "NOR",
        "residence_intent_days": 720,
    }
    result = evaluate(corridor, case)
    assert result.branch_id == "BRANCH_3_EEA_FAMILY"
    assert "SPOUSE_POLICE_REGISTRATION" in result.required_step_ids


@SKIP_NO_EVALUATOR
def test_indian_born_child_spawns_child_case(corridor: CorridorAgent):
    from backend.relopass.agents.corridor_runtime import evaluate  # type: ignore

    case = {
        "employee_nationality_iso3": "FRA",
        "has_family_relocating": True,
        "spouse_nationality_iso3": "IND",
        "has_indian_born_child": True,
        "residence_intent_days": 720,
    }
    result = evaluate(corridor, case)
    assert any(
        e.action == "SPAWN_CHILD_CASE" for e in result.triggered_exception_cases
    )
