"""C1-09 · Structural tests for the IN_DE_BLUECARD_2026 corridor YAML.

Notion Validation Criteria:

  1. YAML loads via the runtime without errors.                                  → covered
  2. Priya Sharma (Bengaluru SWE → Munich, €68k) routes to ELIGIBLE Branch A.    → SKIPPED (needs C1-05 evaluator)
  3. Same case with €42k routes to NOT_ELIGIBLE citing §18g threshold.           → SKIPPED (needs C1-05 evaluator)
  4. IT specialist without degree routes to Branch B (§18g(2)).                  → SKIPPED (needs C1-05 evaluator)
  5. Over-45 + reduced salary routes to alternate §18b pathway annotation.       → SKIPPED (needs C1-05 evaluator)
  6. Each step cites its rule_version_id from rule_citations.                    → SKIPPED (needs C1-05 evaluator)

Criteria 2–6 require ``evaluate(corridor, case)`` from C1-05's corridor
runtime, which is not yet built. The case fixtures and assertions live
in this file as ``pytest.skip``-guarded tests; lifting the skip is a
one-line change once :mod:`backend.relopass.agents.corridor_runtime`
exposes :func:`evaluate`.

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
    load_corridor_text,
)
from backend.relopass.corridors.loader import _yaml_parse  # noqa: PLC2701 — internal helper under test


REPO_ROOT = Path(__file__).resolve().parents[2]
CORRIDOR_PATH = REPO_ROOT / "corridors" / "IN_DE_BLUECARD_2026" / "v1.yaml"


@pytest.fixture(scope="module")
def corridor() -> CorridorAgent:
    return load_corridor(CORRIDOR_PATH)


# ─────────────────────────────────────────────────────────────────────────────
# Criterion 1 — YAML loads via the runtime without errors.
# ─────────────────────────────────────────────────────────────────────────────


def test_yaml_loads_via_loader(corridor: CorridorAgent):
    assert corridor.corridor_id == "IN_DE_BLUECARD_2026"
    assert corridor.version == "2026.01"
    assert corridor.origin_country_iso3 == "IND"
    assert corridor.destination_country_iso3 == "DEU"
    assert corridor.petitioning_party == "EMPLOYEE"


def test_yaml_contains_required_legal_references(corridor: CorridorAgent):
    required_rule_ids = {
        "DE_AUFENTHG_18G",
        "DE_AUFENTHG_18G_2",
        "DE_BESCHV_6",
        "EU_2021_1883",
        "DE_AUFENTHG_FAMILY",
        "DE_AUFENTHG_82",
        "DE_AUFENTHG_18G_SALARY",
    }
    assert required_rule_ids.issubset(set(corridor.rule_ids()))


def test_salary_thresholds_match_bgbl_2025_i_278(corridor: CorridorAgent):
    # BGBl. 2025 I Nr. 278 — 2026 EU Blue Card salary floors.
    assert corridor.salary_thresholds_eur["general"] == 50700.00
    assert corridor.salary_thresholds_eur["shortage_or_recent_graduate_or_it"] == 45934.20


def test_required_data_points_include_pf1_external_lookup(corridor: CorridorAgent):
    keys = {dp.key for dp in corridor.required_data_points}
    # PF-1 stress test addition — salary threshold must be an EXTERNAL_LOOKUP.
    assert "salary_threshold_eur" in keys
    threshold_dp = next(dp for dp in corridor.required_data_points if dp.key == "salary_threshold_eur")
    assert threshold_dp.source == "EXTERNAL_LOOKUP"
    assert threshold_dp.lookup == "DE_AUFENTHG_18G_SALARY.current"


def test_step_graph_has_14_steps(corridor: CorridorAgent):
    # Architecture Report §4.1 calls for 14 steps from ZAB → Blue Card collection.
    assert len(corridor.step_graph) == 14


def test_step_graph_has_no_dangling_prerequisites(corridor: CorridorAgent):
    step_ids = set(corridor.step_ids())
    for step in corridor.step_graph:
        for prereq in step.prerequisite_step_ids:
            assert prereq in step_ids, (
                f"step {step.step_id} has prerequisite {prereq!r} not in step_graph"
            )


def test_step_graph_has_time_window_pf1_fields(corridor: CorridorAgent):
    # PF-1 addition — at least one step uses time_window_relative_to.
    windowed = [s for s in corridor.step_graph if s.time_window_relative_to is not None]
    assert len(windowed) >= 3
    for step in windowed:
        assert step.time_window_min_days is not None
        assert step.time_window_max_days is not None
        assert step.time_window_min_days <= step.time_window_max_days


def test_eligibility_branches_cite_known_rules(corridor: CorridorAgent):
    rule_ids = set(corridor.rule_ids())
    for branch in corridor.eligibility_branches:
        assert branch.cite in rule_ids, (
            f"branch {branch.id} cites unknown rule {branch.cite}"
        )


def test_eligibility_logic_covers_branches_a_b_and_alt(corridor: CorridorAgent):
    ids = {b.id for b in corridor.eligibility_branches}
    assert "BRANCH_A" in ids
    assert "BRANCH_B" in ids
    assert "ALT_SKILLED_WORKER" in ids


def test_exception_cases_include_over_45_and_family(corridor: CorridorAgent):
    ids = {e.id for e in corridor.exception_cases}
    assert "OVER_45_INCOME_RULE" in ids
    assert "FAMILY_REUNIFICATION" in ids


# ─────────────────────────────────────────────────────────────────────────────
# Loader error paths
# ─────────────────────────────────────────────────────────────────────────────


def test_loader_rejects_missing_corridor_agent_block():
    with pytest.raises(CorridorLoadError):
        load_corridor_text("foo: bar\n")


def test_loader_rejects_branch_citing_unknown_rule():
    bad_yaml = """
corridor_agent:
  corridor_id: TEST
  version: "0.1"
  applicable_rules:
    - legal_reference: "Foo §1"
      rule_id: KNOWN_RULE
  required_documents: []
  required_data_points: []
  salary_thresholds_eur:
    general: 1.0
  eligibility_logic:
    branches:
      - id: B1
        label: "Test"
        cite: UNKNOWN_RULE
        requires_all:
          - x == y
        verdict_on_pass: ELIGIBLE
    no_branch_verdict: NOT_ELIGIBLE
  exception_cases: []
  step_graph: []
"""
    with pytest.raises(CorridorLoadError, match="unknown rule"):
        load_corridor_text(bad_yaml)


def test_loader_rejects_step_with_dangling_prerequisite():
    bad_yaml = """
corridor_agent:
  corridor_id: TEST
  version: "0.1"
  applicable_rules: []
  required_documents: []
  required_data_points: []
  salary_thresholds_eur:
    general: 1.0
  eligibility_logic:
    branches: []
    no_branch_verdict: NOT_ELIGIBLE
  exception_cases: []
  step_graph:
    - step_id: A
      name: "A"
      responsible_party: EMPLOYEE
      expected_duration_days: 1
      prerequisite_step_ids:
        - GHOST
"""
    with pytest.raises(CorridorLoadError, match="prerequisite"):
        load_corridor_text(bad_yaml)


def test_yaml_parser_handles_block_scalar():
    parsed = _yaml_parse(
        "top:\n  blurb: >\n    This is\n    a folded scalar.\n"
    )
    assert isinstance(parsed["top"]["blurb"], str)
    assert "folded scalar" in parsed["top"]["blurb"]


# ─────────────────────────────────────────────────────────────────────────────
# Criteria 2–6 — Priya Sharma fixture (skipped until C1-05 evaluator lands)
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
        "is the function this test exercises. Unskips automatically once "
        "backend.relopass.agents.corridor_runtime exposes evaluate()."
    ),
)


@SKIP_NO_EVALUATOR
def test_priya_eligible_branch_a(corridor: CorridorAgent):
    from backend.relopass.agents.corridor_runtime import evaluate  # type: ignore

    case = {
        "applicant_age_years": 28,
        "qualification_recognized_in_anabin": True,
        "anabin_rating": "H+",
        "contract_duration_months": 24,
        "gross_salary_annual": 68000.00,
        "position_isco_2008": "2511",
        "position_in_shortage_occupation": False,
        "has_family_relocating": False,
    }
    result = evaluate(corridor, case)
    assert result.verdict == "ELIGIBLE"
    assert any("AufenthG §18g" in c.legal_reference for c in result.citations)


@SKIP_NO_EVALUATOR
def test_priya_not_eligible_below_threshold(corridor: CorridorAgent):
    from backend.relopass.agents.corridor_runtime import evaluate  # type: ignore

    case = {
        "applicant_age_years": 28,
        "qualification_recognized_in_anabin": True,
        "contract_duration_months": 24,
        "gross_salary_annual": 42000.00,
        "position_isco_2008": "2511",
        "position_in_shortage_occupation": False,
    }
    result = evaluate(corridor, case)
    assert result.verdict == "NOT_ELIGIBLE"
    assert "salary" in result.blocking_reason.lower()


@SKIP_NO_EVALUATOR
def test_priya_it_specialist_branch_b_without_degree(corridor: CorridorAgent):
    from backend.relopass.agents.corridor_runtime import evaluate  # type: ignore

    case = {
        "applicant_age_years": 31,
        "qualification_recognized_in_anabin": False,
        "contract_duration_months": 18,
        "gross_salary_annual": 55000.00,
        "position_isco_2008": "2512",  # software developer
        "it_experience_years_last_7": 6,
    }
    result = evaluate(corridor, case)
    assert result.verdict == "ELIGIBLE"
    assert any("§18g (2)" in c.legal_reference for c in result.citations)


@SKIP_NO_EVALUATOR
def test_priya_over_45_alternate_pathway(corridor: CorridorAgent):
    from backend.relopass.agents.corridor_runtime import evaluate  # type: ignore

    case = {
        "applicant_age_years": 47,
        "qualification_recognized_in_anabin": True,
        "contract_duration_months": 24,
        "gross_salary_annual": 48000.00,  # below Blue Card general threshold
        "position_isco_2008": "2511",
    }
    result = evaluate(corridor, case)
    assert result.verdict in {"ALTERNATE_PATHWAY", "NOT_ELIGIBLE"}
    assert any("§18 (2) Nr. 5" in c.legal_reference for c in result.citations)


@SKIP_NO_EVALUATOR
def test_step_results_include_rule_version_id(corridor: CorridorAgent):
    from backend.relopass.agents.corridor_runtime import evaluate  # type: ignore

    case = {
        "applicant_age_years": 28,
        "qualification_recognized_in_anabin": True,
        "contract_duration_months": 24,
        "gross_salary_annual": 68000.00,
        "position_isco_2008": "2511",
    }
    result = evaluate(corridor, case)
    assert all(c.rule_version_id is not None for c in result.citations)
