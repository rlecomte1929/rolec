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
  * `key` is not modeled by the engine — it is slugified from the title.
  * `timing`/`non_obvious` ARE now columns on `requirement_items` and are carried
    through verbatim. They stay `null` until a fact populates them, and stay `null`
    for engine-synthesised items, which have no such data. Never fabricate either.

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
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from ...rate_limit import limiter
from .. import crud
from ..db import SessionLocal
from ..services.disclaimers import IMMIGRATION_DISCLAIMER
from ..services.nationality_class import classify_best
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


def _public_sources(citations: Any) -> List[str]:
    """The citation URLs, and nothing else, for an anonymous caller.

    This endpoint is unauthenticated and answers with `Access-Control-Allow-Origin: *`, and it
    used to emit `citations_json` RAW. That field is not a list of URLs — it holds three shapes,
    and two of them carry things an anonymous caller has no business receiving:

    - inline objects from the corridor generators and `otto.mappings._citations_for`, carrying
      `needs_lawyer_review` and, on the IE→ES rows, a `review_reason` naming exactly which claim
      we do not trust and why;
    - bare `source_records` ids, which are internal identifiers and resolve to nothing publicly.

    Both were unreachable only while every object-shaped row sat at `review_status='pending'`.
    That stopped being true on 2026-08-21 12:02 UTC, when the nine VE→IE rows were approved and
    `needs_lawyer_review: true` began appearing in the live public payload.

    ALLOWLIST, not denylist. Stripping the two keys we happen to know about fails open the next
    time a generator adds a third — and `topic_key`/`corridor` were already being published. A
    citation is a URL to the public; anything that is not one is dropped rather than guessed at.

    The wire type stays `List[str]`: approved string-shaped rows have always emitted a list of
    strings, and Audos reads this seam. `http`/`https` only, deduped, order preserved.
    """
    out: List[str] = []
    seen = set()
    for citation in citations or []:
        if isinstance(citation, dict):
            url = str(citation.get("url") or "").strip()
        elif isinstance(citation, str):
            url = citation.strip()
        else:
            continue
        if not url.lower().startswith(("http://", "https://")):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def _base_items(requirements: List[Any]) -> List[Dict[str, Any]]:
    """Project ORM RequirementItem rows → the dict shape apply_rules expects.

    Mirrors requirements_builder's projection (no case/PII fields are read).

    `appliesToNationalityClasses` MUST be carried. `rules_engine._applies_to_nationality_class`
    treats a missing key as "applies to everyone", so omitting it here did not merely skip the
    nationality filter — it published every mutually exclusive track at once. Norway returned
    both `Valid passport (6+ months)` (THIRD_COUNTRY) and `Valid identity card or passport
    (EU/EEA)` to the same anonymous caller, which is the exact failure `nationality_class.py`
    exists to prevent, on the one surface a prospect sees before they trust us.
    """
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
            # None ⇒ applies to all nationality classes.
            "appliesToNationalityClasses": (
                json.loads(item.applies_to_nationality_classes_json)
                if getattr(item, "applies_to_nationality_classes_json", None)
                else None
            ),
            "verificationStatus": getattr(item, "verification_status", None),
            "attestationStatus": getattr(item, "attestation_status", None),
            "attestedBy": getattr(item, "attested_by", None),
            "attestedAt": getattr(item, "attested_at", None),
            # getattr-defaulted, not `item.non_obvious`: the canned SimpleNamespace rows in
            # backend/tests/test_public_corridor.py don't carry these, and a row read before
            # the migration lands must degrade to false/None rather than raise.
            "non_obvious": bool(getattr(item, "non_obvious", False)),
            "timing": getattr(item, "timing", None),
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
    nationality: Optional[str] = Query(
        None, max_length=40,
        description="Traveller nationality (ISO code or name). A country is NOT a nationality — "
                    "`from` is the origin of the move and is deliberately not used for this. "
                    "Omit it and the response is filtered as THIRD_COUNTRY, the most demanding "
                    "track, which can only ever over-show.",
    ),
    second_nationality: Optional[str] = Query(
        None, max_length=40,
        description="A second nationality, if the traveller holds one. Rights are cumulative: "
                    "a Venezuelan/Italian citizen moving to Ireland exercises Italian free "
                    "movement, so the response is filtered on whichever passport gives the "
                    "most favourable class. Omit it for a single-national traveller.",
    ),
) -> JSONResponse:
    """Generic, non-PII requirement set for (destination, employee_type). No auth."""
    etype = (employee_type or "").strip().upper()
    if etype not in _VALID_EMPLOYEE_TYPES:
        raise HTTPException(status_code=422, detail=f"employee_type must be one of {sorted(_VALID_EMPLOYEE_TYPES)}")
    purp = (purpose or "employment").strip().lower()
    if purp not in _VALID_PURPOSES:
        raise HTTPException(status_code=422, detail=f"purpose must be one of {sorted(_VALID_PURPOSES)}")

    dest_catalog = resolve_catalog_country(to)
    # Minimal, PII-free draft. `destCountry` and the nationalities are here so the engine's
    # nationality gate can run: without them `classify_best()` returns None and every response
    # falls back to THIRD_COUNTRY. A nationality alone is not personal data — no name, no
    # document, no case is involved.
    #
    # `second_nationality` is passed under the same key the case-scoped path uses, because
    # `apply_rules` already reads BOTH (rules_engine.py → classify_best). Before this, a dual
    # national could not be represented here at all: the parameter did not exist, so a
    # Venezuelan/Italian was filtered as a third-country national and shown a permit track
    # they must not apply for. The engine was always right; it was never given the second value.
    profile: dict = {}
    if nationality:
        profile["nationality"] = nationality
    if second_nationality:
        profile["second_nationality"] = second_nationality
    draft = {
        "relocationBasics": {"purpose": purp, "destCountry": to},
        "assignmentContext": {"assignmentType": etype},
        "employeeProfile": profile,
    }
    # Echo the class the engine will actually apply. `classify_best` mirrors apply_rules
    # exactly; using `classify(nationality)` here would report a different class from the one
    # that filtered the payload whenever a second nationality is the more favourable one.
    applied_class = (
        classify_best((nationality, second_nationality), to)
        if (nationality or second_nationality)
        else None
    )

    with SessionLocal() as db:
        base_items = _base_items(crud.list_requirements(db, dest_catalog, purp))

    _required, expanded, flags = apply_rules(draft, base_items)

    requirements = [
        {
            "key": _slug(item.get("title") or item.get("id") or ""),
            "label": item.get("title"),
            "description": item.get("description"),
            # Carried from the catalog row. Still `null` for an item the ENGINE synthesised
            # (_requirement / _immigration_confirmation) rather than read from the catalog —
            # those have no such data, and null ("not modeled") is a different claim from
            # false ("modeled, and it is obvious"). Do not collapse them.
            "timing": item.get("timing"),
            "non_obvious": item.get("non_obvious"),
            "category": item.get("pillar"),
            "source": _public_sources(item.get("citations")),
        }
        for item in expanded
    ]

    payload = {
        "corridor": {"from": (from_ or "").strip().upper(), "to": dest_catalog},
        "employee_type": etype,
        "purpose": purp,
        # Which track the caller is looking at. Without a nationality this is null and the
        # list is the THIRD_COUNTRY one — say so rather than let it read as universal.
        "nationality_class": applied_class,
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
