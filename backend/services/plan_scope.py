"""
plan_scope.py — Phase-gating logic for the relocation plan.

Given a CaseClassification (produced by relocation_classifier.classify_case),
returns the ordered list of plan phases that are active for that case.

This module is the single source of truth for "which phases appear in a plan".
It is a pure function with no side effects and no database access — safe to
call from any context.

Touch policy: this is a NEW FILE. It does not modify any existing module.
Callers (plan generation routes, task library hydration) import from here.

Phase ordering is preserved from PHASE_ORDER in relocation_plan_task_library.py:
  pre_departure → immigration → logistics → arrival → post_arrival

S3 suppression rules:
  domestic_move     → suppress immigration
  short_term_project → suppress logistics + post_arrival
  repatriation      → suppress immigration (replaced by admin_reinstatement)
"""

from __future__ import annotations

from typing import List, Optional


# Canonical phase order — mirrors PHASE_ORDER in relocation_plan_task_library.py.
# Do not reorder; task library hydration depends on this sequence.
ALL_PHASES: List[str] = [
    "pre_departure",
    "immigration",
    "logistics",
    "arrival",
    "post_arrival",
]

# Repatriation gets its own phase instead of immigration.
REPATRIATION_PHASES: List[str] = [
    "pre_departure",
    "admin_reinstatement",   # French/home-country re-registration
    "logistics",
    "arrival",
    "post_arrival",
]

# case_type → set of phases to suppress from ALL_PHASES
_SUPPRESSED: dict = {
    "domestic_move":        {"immigration"},
    "short_term_project":   {"logistics", "post_arrival"},
}


def active_phases_for_case_type(case_type: str) -> List[str]:
    """
    Return the ordered list of plan phases active for the given case_type.

    Examples:
        >>> active_phases_for_case_type("domestic_move")
        ['pre_departure', 'logistics', 'arrival', 'post_arrival']

        >>> active_phases_for_case_type("short_term_project")
        ['pre_departure', 'immigration', 'arrival']

        >>> active_phases_for_case_type("repatriation")
        ['pre_departure', 'admin_reinstatement', 'logistics', 'arrival', 'post_arrival']

        >>> active_phases_for_case_type("lta")
        ['pre_departure', 'immigration', 'logistics', 'arrival', 'post_arrival']
    """
    if case_type == "repatriation":
        return list(REPATRIATION_PHASES)

    suppressed = _SUPPRESSED.get(case_type, set())
    return [p for p in ALL_PHASES if p not in suppressed]


def active_phases_for_classification(classification) -> List[str]:
    """
    Convenience wrapper: accepts a CaseClassification object (or any object
    with a .case_type attribute) and returns the active phases.

    If classification.active_phases is already populated (set by classify_case),
    returns that directly to avoid recomputing.
    """
    # Prefer pre-computed value if available
    if hasattr(classification, "active_phases") and classification.active_phases:
        return list(classification.active_phases)

    return active_phases_for_case_type(classification.case_type)


def immigration_required(case_type: str) -> bool:
    """
    Quick predicate: does this case type require an immigration workstream?

    Used by task library hydration to gate immigration task_codes.
    """
    return "immigration" in active_phases_for_case_type(case_type)


def plan_scope_summary(case_type: str) -> dict:
    """
    Returns a human-readable summary of what is and is not included in the plan.
    Useful for the UI "here's what your plan covers" banner.
    """
    phases = active_phases_for_case_type(case_type)
    suppressed = set(ALL_PHASES) - set(phases)

    return {
        "case_type": case_type,
        "active_phases": phases,
        "suppressed_phases": sorted(suppressed),
        "immigration_required": "immigration" in phases,
        "logistics_included": "logistics" in phases,
        "post_arrival_included": "post_arrival" in phases,
    }
