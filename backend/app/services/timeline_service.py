"""Timeline workflow — compute default milestones from case context."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

DEFAULT_MILESTONES = [
    {"milestone_type": "case_created", "title": "Case created", "description": "Relocation case initiated", "sort_order": 0},
    {"milestone_type": "visa_preparation", "title": "Visa preparation", "description": "Gather documents and apply for work permit / visa", "sort_order": 10},
    {"milestone_type": "housing_search", "title": "Housing search", "description": "Find accommodation in destination", "sort_order": 20},
    {"milestone_type": "school_search", "title": "School search", "description": "Research and apply for schools / childcare", "sort_order": 30},
    {"milestone_type": "move_logistics", "title": "Move logistics", "description": "Arrange movers, shipping, flights", "sort_order": 40},
    {"milestone_type": "arrival", "title": "Arrival", "description": "Arrive at destination", "sort_order": 50},
    {"milestone_type": "settling_in", "title": "Settling in", "description": "Register, utilities, bank account", "sort_order": 60},
]

# Service keys that imply certain milestones
SERVICE_TO_MILESTONE: Dict[str, str] = {
    "living_areas": "housing_search",
    "housing": "housing_search",
    "schools": "school_search",
    "childcare": "school_search",
    "movers": "move_logistics",
    "banks": "settling_in",
    "insurance": "visa_preparation",
    "electricity": "settling_in",
}


def compute_default_milestones(
    case_id: str,
    case_draft: Optional[Dict[str, Any]] = None,
    selected_services: Optional[List[str]] = None,
    target_move_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Compute default milestone set from case context.
    Returns list of milestone dicts ready for upsert.
    """
    basics = (case_draft or {}).get("relocationBasics", {})
    target = target_move_date or basics.get("targetMoveDate") or basics.get("target_move_date")
    services = selected_services or []

    # Start with case_created always
    result: List[Dict[str, Any]] = []
    seen_types: set = set()

    # Parse target date for offset calculations
    base_date: Optional[datetime] = None
    if target:
        try:
            if isinstance(target, str) and "T" in target:
                base_date = datetime.fromisoformat(target.replace("Z", "+00:00"))
            elif isinstance(target, str):
                base_date = datetime.strptime(target[:10], "%Y-%m-%d")
            else:
                base_date = None
        except (ValueError, TypeError):
            base_date = None

    def _add_milestone(mt: str, title: str, desc: str, sort_order: int, target_date: Optional[str] = None) -> None:
        if mt in seen_types:
            return
        seen_types.add(mt)
        result.append({
            "milestone_type": mt,
            "title": title,
            "description": desc,
            "sort_order": sort_order,
            "target_date": target_date,
            "status": "pending",
        })

    # Case created — always first
    _add_milestone("case_created", "Case created", "Relocation case initiated", 0)

    # Visa — typically 8–12 weeks before move
    if base_date:
        visa_target = (base_date - timedelta(days=70)).strftime("%Y-%m-%d")
        _add_milestone("visa_preparation", "Visa preparation", "Gather documents and apply for work permit / visa", 10, visa_target)
    else:
        _add_milestone("visa_preparation", "Visa preparation", "Gather documents and apply for work permit / visa", 10)

    # Housing — if housing/living_areas selected
    if any(s in ("living_areas", "housing") for s in services):
        if base_date:
            housing_target = (base_date - timedelta(days=56)).strftime("%Y-%m-%d")
            _add_milestone("housing_search", "Housing search", "Find accommodation in destination", 20, housing_target)
        else:
            _add_milestone("housing_search", "Housing search", "Find accommodation in destination", 20)
    else:
        _add_milestone("housing_search", "Housing search", "Find accommodation in destination", 20)

    # School — if schools/childcare selected
    if any(s in ("schools", "childcare") for s in services):
        if base_date:
            school_target = (base_date - timedelta(days=90)).strftime("%Y-%m-%d")
            _add_milestone("school_search", "School search", "Research and apply for schools / childcare", 30, school_target)
        else:
            _add_milestone("school_search", "School search", "Research and apply for schools / childcare", 30)
    else:
        _add_milestone("school_search", "School search", "Research and apply for schools / childcare", 30)

    # Move logistics — if movers selected or generally relevant
    if "movers" in services or not services:
        if base_date:
            move_target = (base_date - timedelta(days=21)).strftime("%Y-%m-%d")
            _add_milestone("move_logistics", "Move logistics", "Arrange movers, shipping, flights", 40, move_target)
        else:
            _add_milestone("move_logistics", "Move logistics", "Arrange movers, shipping, flights", 40)

    # Arrival
    arrival_date = None
    if target and isinstance(target, str) and len(target) >= 10:
        arrival_date = target[:10]
    elif target and isinstance(target, str):
        arrival_date = target
    _add_milestone("arrival", "Arrival", "Arrive at destination", 50, arrival_date)

    # Settling in — 2 weeks after arrival
    if base_date:
        settling_target = (base_date + timedelta(days=14)).strftime("%Y-%m-%d")
        _add_milestone("settling_in", "Settling in", "Register, utilities, bank account", 60, settling_target)
    else:
        _add_milestone("settling_in", "Settling in", "Register, utilities, bank account", 60)

    return result
