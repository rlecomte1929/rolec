"""AIQ-1749 — resolve a case's corridor feasibility for the HR command center.

App-layer bridge between the corridor registry and the pure
``relopass.corridors.feasibility`` engine, exactly mirroring the role
``sla_corridor.py`` plays for ``sla_rules.compute_sla_status``: the registry lives
in ``app/``, the engine must not import ``app/``, so the join happens here.

Fallback-safe by construction. The HR case overview is a cockpit surface — a
corridor that fails to resolve must degrade to "no opinion" and never 500 the whole
case view. Every failure path returns None rather than raising, and None means
*render nothing*: an absent assessment must never be shown as reassurance.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from ...relopass.corridors import load_corridor
from ...relopass.corridors.feasibility import FeasibilityAssessment, assess_feasibility
from . import corridor_registry


def _coerce_date(value: Any) -> Optional[date]:
    """Best-effort date parse; None on anything unparseable."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def feasibility_for_case(
    origin: Optional[str],
    destination: Optional[str],
    target_start_date: Any,
    *,
    today: Optional[date] = None,
) -> Optional[FeasibilityAssessment]:
    """Assess a case's timeline against its corridor's pre-arrival runway.

    Returns None — meaning "no opinion, render nothing" — when the corridor cannot
    be resolved, declares no pathway, declares no arrival anchor, or the case has no
    target start date. Never raises.

    The corridor is resolved from the case's origin/destination pair rather than its
    ``corridor`` column, matching how ``sla_corridor`` resolves the SLA config, so
    the two never disagree about which corridor a case belongs to.
    """
    try:
        start = _coerce_date(target_start_date)
        if not origin or not destination or start is None:
            return None

        corridor_id = corridor_registry.normalize_corridor_id(f"{origin}_{destination}")
        if not corridor_id:
            return None

        pathways = corridor_registry.get_pathways(corridor_id)
        if not pathways:
            return None

        # A corridor declares its primary pathway first; alternates (e.g. the ES_IE
        # General Employment Permit) live inside that file as ALTERNATE_PATHWAY
        # branches, not as sibling entries, so the first one is the case's route.
        path = corridor_registry.get_pathway_file(corridor_id, pathways[0].id)
        if path is None:
            return None

        return assess_feasibility(
            load_corridor(path).step_graph, start, today or date.today()
        )
    except Exception:  # noqa: BLE001 — never break the case overview
        return None
