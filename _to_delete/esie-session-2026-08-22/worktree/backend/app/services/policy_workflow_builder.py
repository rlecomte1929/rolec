"""
Post-process LLM-extracted policy benefits into a structured workflow summary.

Transforms the flat benefits list from llm_policy_extractor / policy_extractor
into four demo-ready sections: detected tiers, task list with owners, timeline
estimate, and cost range. No additional LLM call — purely deterministic.

AIQ-1219 PR2.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# ── Mappings ────────────────────────────────────────────────────────────────

BENEFIT_TASKS: Dict[str, Dict[str, str]] = {
    "temporary_housing": {
        "task": "Arrange temporary accommodation",
        "owner": "Relocation Provider",
    },
    "rental_deposit": {
        "task": "Secure rental deposit guarantee",
        "owner": "HR / Finance",
    },
    "shipment": {
        "task": "Coordinate household goods shipment",
        "owner": "Relocation Provider",
    },
    "education_support": {
        "task": "Research and enroll dependents in schools",
        "owner": "Employee + Relocation Provider",
    },
    "visa_support": {
        "task": "Prepare and submit visa/work permit application",
        "owner": "Immigration Provider",
    },
    "travel_host": {
        "task": "Book pre-move scouting / look-see trip",
        "owner": "Relocation Provider",
    },
    "settling_in_allowance": {
        "task": "Disburse settling-in lump sum",
        "owner": "HR / Finance",
    },
    "tax_assistance": {
        "task": "Engage tax advisor for cross-border compliance",
        "owner": "Tax Provider",
    },
    "spousal_support": {
        "task": "Provide spouse/partner career or integration support",
        "owner": "Relocation Provider",
    },
    "language_training": {
        "task": "Arrange language training programme",
        "owner": "Employee + HR",
    },
    "repatriation": {
        "task": "Plan repatriation logistics",
        "owner": "Relocation Provider",
    },
    "scouting_trip": {
        "task": "Organise destination scouting trip",
        "owner": "Relocation Provider",
    },
    "home_sale_purchase": {
        "task": "Coordinate home sale / purchase assistance",
        "owner": "Relocation Provider",
    },
}

CATEGORY_LABELS: Dict[str, str] = {
    "housing": "Housing & Accommodation",
    "movers": "Moving & Shipping",
    "schools": "Education & Schools",
    "immigration": "Immigration & Visas",
    "travel": "Travel & Trips",
    "settling_in": "Settling In",
    "tax": "Tax & Compliance",
    "spouse": "Spouse & Family",
    "integration": "Cultural Integration",
    "repatriation": "Repatriation",
    "home_sale": "Home Sale / Purchase",
}

TIMELINE_PHASES: List[Dict[str, Any]] = [
    {
        "phase": "Pre-departure",
        "duration": "4–8 weeks before move",
        "benefit_keys": ["visa_support", "scouting_trip", "travel_host"],
    },
    {
        "phase": "Moving",
        "duration": "Move week ± 1 week",
        "benefit_keys": ["shipment", "home_sale_purchase"],
    },
    {
        "phase": "First 30 days",
        "duration": "Days 1–30",
        "benefit_keys": ["temporary_housing", "settling_in_allowance", "rental_deposit"],
    },
    {
        "phase": "Settling (30–90 days)",
        "duration": "Months 2–3",
        "benefit_keys": ["education_support", "language_training", "spousal_support"],
    },
    {
        "phase": "Ongoing",
        "duration": "3+ months",
        "benefit_keys": ["tax_assistance", "repatriation"],
    },
]


def build_workflow_summary(
    extraction: Dict[str, Any],
) -> Dict[str, Any]:
    """Transform extraction results into a 4-section workflow summary.

    Accepts the ``merged`` (or ``llm_extracted``) dict from
    ``policy_extractor.extract_policy_with_diff``.
    """
    benefits: List[Dict[str, Any]] = extraction.get("benefits") or []
    policy_meta: Dict[str, Any] = extraction.get("policy_meta") or {}

    tiers = _derive_tiers(benefits)
    tasks = _derive_tasks(benefits)
    timeline = _derive_timeline(benefits)
    cost_summary = _derive_cost_summary(benefits)

    return {
        "policy_title": policy_meta.get("title"),
        "effective_date": policy_meta.get("effective_date"),
        "tiers": tiers,
        "tasks": tasks,
        "timeline": timeline,
        "cost_summary": cost_summary,
        "benefits_count": len(benefits),
    }


def _derive_tiers(benefits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract unique tier / band information from benefit eligibility fields."""
    band_sets: Dict[str, set] = {}
    for b in benefits:
        elig = b.get("eligibility") or {}
        bands = elig.get("bands") or elig.get("employee_levels") or []
        if isinstance(bands, str):
            bands = [bands]
        for band in bands:
            band_str = str(band).strip()
            if band_str:
                band_sets.setdefault(band_str, set()).add(b.get("benefit_key", ""))

    if not band_sets:
        return [{"name": "Standard (all employees)", "bands": [], "benefits_count": len(benefits)}]

    return [
        {
            "name": band,
            "bands": [band],
            "benefits_count": len(keys),
        }
        for band, keys in sorted(band_sets.items())
    ]


def _derive_tasks(benefits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map extracted benefits to actionable tasks with owners."""
    tasks = []
    for b in benefits:
        key = b.get("benefit_key", "")
        mapping = BENEFIT_TASKS.get(key)
        if mapping:
            tasks.append({
                "category": CATEGORY_LABELS.get(b.get("service_category", ""), b.get("service_category", "")),
                "task": mapping["task"],
                "owner": mapping["owner"],
                "benefit_key": key,
                "confidence": b.get("confidence", 0),
            })
        else:
            tasks.append({
                "category": CATEGORY_LABELS.get(b.get("service_category", ""), b.get("service_category", "")),
                "task": b.get("benefit_label", key),
                "owner": "HR / Relocation Provider",
                "benefit_key": key,
                "confidence": b.get("confidence", 0),
            })
    return tasks


def _derive_timeline(benefits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map benefits to timeline phases."""
    present_keys = {b.get("benefit_key") for b in benefits}
    phases = []
    for phase in TIMELINE_PHASES:
        matching = [k for k in phase["benefit_keys"] if k in present_keys]
        if matching:
            phases.append({
                "phase": phase["phase"],
                "duration": phase["duration"],
                "tasks": [
                    BENEFIT_TASKS.get(k, {}).get("task", k) for k in matching
                ],
            })
    return phases


def _extract_cap(limits: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract a monetary cap from a limits dict. Returns {amount, currency} or None."""
    for cap_key in ("cap", "monthly_cap", "lump_sum"):
        val = limits.get(cap_key)
        if isinstance(val, dict):
            for currency, amount in val.items():
                try:
                    return {"amount": float(amount), "currency": str(currency).upper()}
                except (ValueError, TypeError):
                    continue
        elif isinstance(val, (int, float)):
            return {"amount": float(val), "currency": "USD"}
    return None


def _derive_cost_summary(benefits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Derive cost ranges from benefit limits."""
    by_category: Dict[str, List[Dict[str, Any]]] = {}
    total_min = 0.0
    total_max = 0.0
    currency = "USD"

    for b in benefits:
        limits = b.get("limits") or {}
        cap = _extract_cap(limits)
        if not cap:
            continue

        cat = CATEGORY_LABELS.get(b.get("service_category", ""), b.get("service_category", ""))
        currency = cap["currency"]
        amount = cap["amount"]

        by_category.setdefault(cat, []).append(cap)
        total_min += amount * 0.7
        total_max += amount * 1.3

    categories = []
    for cat_name, caps in sorted(by_category.items()):
        cat_total = sum(c["amount"] for c in caps)
        categories.append({
            "category": cat_name,
            "estimated_range": {
                "min": round(cat_total * 0.7),
                "max": round(cat_total * 1.3),
                "currency": currency,
            },
        })

    return {
        "total_range": {
            "min": round(total_min),
            "max": round(total_max),
            "currency": currency,
        } if by_category else None,
        "by_category": categories,
        "note": "Estimates derived from policy caps and allowances. Actual costs depend on assignment specifics.",
    }
