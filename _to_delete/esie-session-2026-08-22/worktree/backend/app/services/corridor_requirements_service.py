"""Read the verified corridor ``requirement_items`` for an internal (authenticated) caller.

Feeds the DOC-1 fallback (see ``corridor_requirements_fallback.py``). Reuses the SAME
deterministic seams the public endpoint uses — ``resolve_catalog_country`` +
``crud.list_requirements`` + ``rules_engine.apply_rules`` — so the HR case immigration
view and the public ``/api/public/corridor-requirements`` surface stay consistent.
``public_corridor.py`` is deliberately left untouched.

No PII, no case data, no LLM. Content is only ever what a human seeded into
``requirement_items``. An empty list means nothing is seeded for the destination.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .. import crud
from ..db import SessionLocal
from .nationality_class import classify  # noqa: F401  (kept for parity / future nationality gating)
from .requirements_country_key import resolve_catalog_country
from .rules_engine import apply_rules

_VALID_EMPLOYEE_TYPES = {"STA", "LTA", "PERMANENT"}
_DEFAULT_EMPLOYEE_TYPE = "PERMANENT"
_VALID_PURPOSES = {"employment", "other", "study", "family"}


def _norm_employee_type(employee_type: Optional[str]) -> str:
    et = (employee_type or "").strip().upper()
    return et if et in _VALID_EMPLOYEE_TYPES else _DEFAULT_EMPLOYEE_TYPE


def _urls(citations: Any) -> List[str]:
    out: List[str] = []
    seen = set()
    for c in citations or []:
        if isinstance(c, dict):
            u = str(c.get("url") or "").strip()
        elif isinstance(c, str):
            u = c.strip()
        else:
            continue
        if not u.lower().startswith(("http://", "https://")) or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def _base_items(rows: List[Any]) -> List[Dict[str, Any]]:
    """Project ORM RequirementItem rows into the dict shape ``apply_rules`` expects.
    Mirrors ``public_corridor._base_items`` (kept in sync deliberately; that file explains
    why ``appliesToNationalityClasses`` must be carried)."""
    return [
        {
            "id": item.id,
            "pillar": item.pillar,
            "title": item.title,
            "description": item.description,
            "severity": item.severity,
            "owner": item.owner,
            "requiredFields": json.loads(item.required_fields_json or "[]"),
            "citations": json.loads(item.citations_json or "[]"),
            "appliesToAssignmentTypes": (
                json.loads(item.applies_to_assignment_types_json)
                if getattr(item, "applies_to_assignment_types_json", None) else None
            ),
            "appliesToNationalityClasses": (
                json.loads(item.applies_to_nationality_classes_json)
                if getattr(item, "applies_to_nationality_classes_json", None) else None
            ),
            "verificationStatus": getattr(item, "verification_status", None),
            "attestationStatus": getattr(item, "attestation_status", None),
            "non_obvious": bool(getattr(item, "non_obvious", False)),
            "timing": getattr(item, "timing", None),
        }
        for item in rows
    ]


def list_corridor_requirement_items(
    to: str,
    employee_type: Optional[str] = None,
    purpose: str = "employment",
    nationality: Optional[str] = None,
    db_session_factory=SessionLocal,
) -> List[Dict[str, Any]]:
    """Verified corridor requirement_items for a destination, filtered by the deterministic
    rules engine. ``nationality=None`` filters as THIRD_COUNTRY (most demanding; can only
    over-show), which is the right default for an HR panel that wants the full picture.
    Empty list => nothing seeded for the destination."""
    purp = (purpose or "employment").strip().lower()
    if purp not in _VALID_PURPOSES:
        purp = "employment"
    etype = _norm_employee_type(employee_type)
    dest_catalog = resolve_catalog_country(to)
    if not dest_catalog:
        return []
    draft = {
        "relocationBasics": {"purpose": purp, "destCountry": to},
        "assignmentContext": {"assignmentType": etype},
        "employeeProfile": ({"nationality": nationality} if nationality else {}),
    }
    with db_session_factory() as db:
        base_items = _base_items(crud.list_requirements(db, dest_catalog, purp))
    _required, expanded, _flags = apply_rules(draft, base_items)
    out: List[Dict[str, Any]] = []
    for item in expanded:
        out.append({
            "title": item.get("title"),
            "description": item.get("description"),
            "category": item.get("pillar"),
            "non_obvious": bool(item.get("non_obvious")),
            "timing": item.get("timing"),
            "sources": _urls(item.get("citations")),
            "verification_status": item.get("verificationStatus"),
            "attestation_status": item.get("attestationStatus"),
        })
    return out
