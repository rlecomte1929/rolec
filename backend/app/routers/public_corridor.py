"""Public, read-only corridor requirements — Audos integration seam.

    GET /api/public/corridor-requirements?from=FR&to=NO&employee_type=LTA

Returns the generic statutory / immigration / relocation requirements for a
DESTINATION country + employee (assignment) type. **No auth, no case/user data,
no PII.** Intended for an Audos-hosted demo/landing to render generic corridor
requirements with no login.

Why a new endpoint: every existing requirement endpoint is case/assignment-scoped,
authenticated, and PII-bound (`GET /api/cases/{id}/requirements` →
`compute_case_requirements(case_id)`, which needs a persisted `wizard_cases` row +
`get_current_user`). None can be reused for an anonymous generic query.

Design — thin, case-less adapter over the EXISTING deterministic engine (no refactor):
reuse the two genuinely reusable seams —
  * `crud.list_requirements(db, CATALOG_COUNTRY, purpose)`  → catalog fetch
  * `rules_engine.apply_rules(minimal_draft, base_items)`   → pure filter/expand
— and build a minimal PII-free draft from (to, employee_type, purpose). We do NOT
touch `compute_case_requirements` (the case-scoped path).

Honesty / scope (what this exposes = exactly what the engine produces):
  * The engine is **destination-only** — it has no corridor (origin×destination)
    concept, so `from` is accepted for API shape + echoed back but does not affect
    the result today.
  * Requirement data lives in the `requirement_items` Postgres table (seeded from
    `backend/seeds/requirements/*.yaml` via `backend/scripts/seed_requirements.py`).
    Coverage is only as good as what has been seeded. For destination NORWAY the
    engine currently has 3 items, **all gated to LTA/PERMANENT** — an STA query
    returns an empty list (surfaced via `coverage_note` + `waived_for_assignment_type`,
    not a silent `[]`). Known non-obvious NO items (tax card/skattekort, police
    registration, EEA registration) are NOT yet modeled in this engine — that's a
    separate Phase-1 accuracy task, not this endpoint's job.
  * `key`/`timing`/`non_obvious` are not modeled by the engine: `key` is slugified
    from the title; `timing` and `non_obvious` are `null` (do not fabricate).

CORS: must be callable cross-origin from the Audos surface. The global
CORSMiddleware uses an allowlist with `allow_credentials=True` that won't include
audos.com (and `/api/probe` only echoes allowlisted origins). This endpoint is
public and credential-free, so we set an explicit `Access-Control-Allow-Origin: *`
on the response — `*` is safe here precisely because no cookies/auth are involved.

Dual-registered in backend/main.py AND backend/app/main.py (CLAUDE.md 405 rule).
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from ...rate_limit import limiter
from .. import crud
from ..db import SessionLocal
from ..services.disclaimers import IMMIGRATION_DISCLAIMER
from ..services.rules_engine import apply_rules
# AIQ-1473b: single source of truth for ISO → catalog-name mapping. Imported
# (not duplicated) so this endpoint stays in sync if the catalog naming changes.
from ..services.requirements_country_key import resolve_catalog_country

router = APIRouter(prefix="/api/public", tags=["public"])

_VALID_EMPLOYEE_TYPES = {"STA", "LTA", "PERMANENT"}
_VALID_PURPOSES = {"employment", "other", "study", "family"}


def _slug(text: str) -> str:
    """Stable human-readable key from a requirement title (the engine drops the YAML key)."""
    return re.sub(r"[^a-z0-9]+", "_", (text or "").strip().lower()).strip("_") or "requirement"


def _base_items(requirements: List[Any]) -> List[Dict[str, Any]]:
    """Project ORM RequirementItem rows → the dict shape apply_rules expects.

    Mirrors requirements_builder's projection (no case/PII fields are read)."""
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
                if getattr(item, "applies_to_assignment_types_json", None)
                else None
            ),
            "verificationStatus": getattr(item, "verification_status", None),
        }
        for item in requirements
    ]


@router.get("/corridor-requirements")
@limiter.limit("60/hour;600/day")
def corridor_requirements(
    request: Request,
    from_: str = Query(
        ..., alias="from", min_length=2, max_length=40,
        description="Origin country (ISO or name). Accepted for shape; the engine is destination-only.",
    ),
    to: str = Query(..., min_length=2, max_length=40, description="Destination country (ISO code or name)."),
    employee_type: str = Query(..., description="Assignment type: STA | LTA | PERMANENT."),
    purpose: str = Query("employment", description="Relocation purpose: employment | other | study | family."),
) -> JSONResponse:
    """Generic, non-PII requirement set for (destination, employee_type). No auth."""
    etype = (employee_type or "").strip().upper()
    if etype not in _VALID_EMPLOYEE_TYPES:
        raise HTTPException(status_code=422, detail=f"employee_type must be one of {sorted(_VALID_EMPLOYEE_TYPES)}")
    purp = (purpose or "employment").strip().lower()
    if purp not in _VALID_PURPOSES:
        raise HTTPException(status_code=422, detail=f"purpose must be one of {sorted(_VALID_PURPOSES)}")

    dest_catalog = resolve_catalog_country(to)
    # Minimal, PII-free draft: only assignment type + purpose drive deterministic filtering.
    draft = {"relocationBasics": {"purpose": purp}, "assignmentContext": {"assignmentType": etype}}

    with SessionLocal() as db:
        base_items = _base_items(crud.list_requirements(db, dest_catalog, purp))

    _required, expanded, flags = apply_rules(draft, base_items)

    requirements = [
        {
            "key": _slug(item.get("title") or item.get("id") or ""),
            "label": item.get("title"),
            "description": item.get("description"),
            "timing": None,       # not modeled in the engine (Phase-1 gap; do not fabricate)
            "non_obvious": None,  # not modeled in the engine (Phase-1 gap; do not fabricate)
            "category": item.get("pillar"),
            "source": item.get("citations") or [],
        }
        for item in expanded
    ]

    payload = {
        "corridor": {"from": (from_ or "").strip().upper(), "to": dest_catalog},
        "employee_type": etype,
        "purpose": purp,
        "requirements": requirements,
        # Titles dropped because they don't apply to this assignment type — lets the
        # caller explain a short/empty list instead of it looking like missing data.
        "waived_for_assignment_type": sorted({t for t in (flags.get("staWaived") or []) if t}),
        "coverage_note": (
            None if requirements
            else f"No generic requirements are configured for destination {dest_catalog} + {etype} in the engine yet."
        ),
        "disclaimer": IMMIGRATION_DISCLAIMER,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
    # Public, credential-free → explicit wildcard CORS so the Audos origin can read it.
    return JSONResponse(
        content=payload,
        headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, OPTIONS"},
    )
