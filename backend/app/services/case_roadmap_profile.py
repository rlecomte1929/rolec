"""P2-01e — map a wizard case to the RAG roadmap pipeline inputs and run it.

Bridges the user-facing case (wizard_cases draft) to the immigration RAG pipeline:
classify the pathway (immigration_regime), normalise countries to ISO-2 so the
corridor matches the ingested rule chunks (e.g. "FR→NO"), build the retriever's
UserProfile + PathClassification, and run rag_pipeline. Returns the pipeline
roadmap (which may be RULE_NOT_FOUND) or None when the case can't be mapped.

The country normaliser and EEA/pathway classification are reused from existing
services so this stays a thin glue layer.

A CURATED CORRIDOR OUTRANKS A GENERATED ONE
-------------------------------------------
``persist_generated_milestones`` calls ``delete_case_milestones(exclude_source="service")``
before writing, so anything that is not a Services-tab step is destroyed — including the
authored corridor pathway ``timeline_service._corridor_milestones`` seeds. On intake submit
``_async_seed_and_generate_roadmap`` (backend/main.py) runs the two in sequence: seed the
deterministic milestones, THEN generate and persist. The generated steps therefore replace
the seeded ones by design, and for a corridor nobody has authored that is the right trade.

For a CURATED corridor it is exactly backwards. The pathway is sequenced, cited and
human-reviewed; the generated steps are none of those things.

Measured in production 2026-08-22 — this is not hypothetical:

  corridor   corpus chunks   cases w/ AI steps   cases w/ corridor steps
  FR_NO           46               265                    0
  IN_DE           19                 6                    0
  ES_IE            8                 0                    8
  US_FR           19                 0                    0

All 272 cases carrying AI steps hold NOTHING but ``source='ai'`` and ``source='service'``
rows — the signature of the delete, since the submit chain always seeds first. FR→NO is
known to have an authored pathway (one case still carries its corridor rows), so those 265
lost theirs. ES→IE had not fired only because its corpus was indexed the same day; the
retriever short-circuits to RULE_NOT_FOUND on an empty corpus, and with 8 active chunks it
no longer does. The next ES→IE intake submit would have deleted the CSEP pathway.

Hence the guard in ``persist_generated_milestones``: if the case already holds curated
corridor milestones, refuse to persist and keep them.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import rag_pipeline
from .country_resources import _country_code_from_name
from .immigration_regime import ImmigrationRegimeRouter, _is_eu_national
from .immigration_retriever import PathClassification, UserProfile, corridor_key
from .wizard_draft_mapper import employee_nationality

log = logging.getLogger(__name__)

_router = ImmigrationRegimeRouter()


def _iso2(value: Optional[str]) -> Optional[str]:
    """Normalise a country name or code to ISO-2 (e.g. 'France'/'fr' → 'FR')."""
    if not value:
        return None
    code = _country_code_from_name(str(value).strip())
    return code or None


def build_case_profile(
    case: Dict[str, Any],
) -> Optional[Tuple[UserProfile, PathClassification]]:
    """Map a case dict (with a `draft`) to (UserProfile, PathClassification), or
    None when origin/destination are missing. Countries are ISO-2 normalised so
    the corridor matches the ingested rule chunks."""
    draft = case.get("draft") or {}
    basics = draft.get("relocationBasics") or {}
    origin_raw = basics.get("originCountry")
    dest_raw = basics.get("destCountry")
    if not origin_raw or not dest_raw:
        return None
    origin = _iso2(origin_raw)
    dest = _iso2(dest_raw)
    if not origin or not dest:
        return None

    # Read nationality from wherever the draft records it — `employee_nationality`
    # is the single source for that, shared with wizard_draft_mapper. This module
    # used to read `relocationBasics.nationality` / `personalInfo.nationality`,
    # neither of which production writes (0 of 1,948 drafts on 2026-08-23), so the
    # origin fallback below fired for every case and 42 movers were classified into
    # the wrong free-movement class — 14 of them third-country nationals on ES->IE
    # told they had free movement into Ireland.
    #
    # The origin fallback is KEPT, and only for a draft that records no nationality
    # at all (514 prod cases). Dropping it would flip those to third-country
    # treatment, which is a decision about live roadmaps rather than a read-path
    # fix; see test_case_profile_nationality_source.ScopeBoundary.
    nationality = employee_nationality(draft) or origin_raw
    regime = _router.detect_regime(
        nationality=nationality,
        destination_country=dest_raw,
        origin_country=origin_raw,
    )
    profile = UserProfile(
        nationality=str(nationality or ""),
        origin_country=origin,
        destination_country=dest,
        is_eea=_is_eu_national(nationality),
    )
    # AIQ-1349: carry the assignment type (STA/LTA/PERMANENT) captured at intake
    # so roadmap generation can tailor a temporary assignment's steps.
    ac = draft.get("assignmentContext") or {}
    assignment_type = str(ac.get("assignmentType") or "").strip().upper() or None
    classification = PathClassification(
        pathway_type=regime.regime_id,
        corridor=corridor_key(origin, dest),
        assignment_type=assignment_type,
    )
    return profile, classification


def generate_ai_roadmap_for_case(case: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build the case profile and run the RAG roadmap pipeline end to end.
    Returns the pipeline roadmap dict (possibly RULE_NOT_FOUND), or None when the
    case can't be mapped to a corridor."""
    mapping = build_case_profile(case)
    if mapping is None:
        return None
    profile, classification = mapping
    return rag_pipeline.generate_roadmap(profile=profile, classification=classification)


def map_generated_steps_to_milestones(
    steps: Sequence[Dict[str, Any]], corridor: Optional[str]
) -> List[Dict[str, Any]]:
    """Map assembled generator steps (emit_case_roadmap shape: order/title/
    description/phase/source_url/confidence/requires_expert_review) to
    case_milestone upsert kwargs. Steps without a title are dropped. Pure — no DB.

    milestone_type is ``{phase}_ai_{NN}`` so relocation_plan_service places each
    step in its real phase block (the synthetic-entry parser reads the prefix);
    an absent/unknown phase falls back to ``pre_departure``."""
    stamp = datetime.now(timezone.utc).date().isoformat()
    rows: List[Dict[str, Any]] = []
    for idx, step in enumerate(steps):
        title = str(step.get("title") or "").strip()
        if not title:
            continue
        order = step.get("order")
        order = order if isinstance(order, int) and order > 0 else idx + 1
        phase = str(step.get("phase") or "").strip() or "pre_departure"
        note = f"AI-generated {stamp} | corridor: {corridor or '?'}"
        src = step.get("source_url")
        if src:
            note += f" | source: {src}"
        rows.append(
            {
                "milestone_type": f"{phase}_ai_{order:02d}",
                "title": title,
                "description": step.get("description") or None,
                "status": "pending",
                "sort_order": order,
                "owner": "employee",
                "criticality": "normal",
                "notes": note,
            }
        )
    return rows


#: Curated corridor milestones are named ``{phase}_corridor_{NN}`` by
#: ``timeline_service._corridor_milestones`` — e.g. ``immigration_corridor_05``,
#: ``post_arrival_corridor_03``.
#:
#: MATCH ON THE NAME, NOT ON ``source``. Every one of the 455 corridor rows in
#: production carries ``source IS NULL``; the only non-null sources in that table are
#: 'service' (3,570), 'ai' (2,065) and 'deterministic_seed' (293). A guard written
#: against ``source='deterministic'`` — the value one would reasonably guess — matches
#: nothing at all and silently protects nothing.
_CORRIDOR_MILESTONE_MARKER = "_corridor_"


def curated_corridor_milestones(
    db: Any, case_id: str, request_id: Optional[str] = None
) -> Optional[List[Dict[str, Any]]]:
    """The case's authored-pathway milestones.

    Returns the matching rows, ``[]`` when the case demonstrably has none, and **None**
    when we could not find out.

    FAILS CLOSED, and the three-state return is the whole point. Collapsing the error
    case into ``[]`` would read as "no curated steps here" and let the caller delete the
    very pathway this guard exists to protect — a transient database blip would destroy
    authored content. `None` forces the caller to treat "unknown" as "do not touch".
    """
    try:
        existing = db.list_case_milestones(case_id, request_id=request_id) or []
    except Exception:  # pragma: no cover - defensive; see docstring
        log.warning(
            "curated_corridor_milestones: could not read milestones for case %s — "
            "treating as UNKNOWN so the caller refuses to overwrite", case_id, exc_info=True,
        )
        return None
    return [
        m for m in existing
        if _CORRIDOR_MILESTONE_MARKER in str(m.get("milestone_type") or "")
    ]


def persist_generated_milestones(
    db: Any,
    case_id: str,
    steps: Sequence[Dict[str, Any]],
    corridor: Optional[str],
    request_id: Optional[str] = None,
) -> int:
    """Replace the case's milestones with the generated AI steps so
    /api/relocation-plans/{id}/view (and the employee roadmap page, AIQ-1005)
    serves corridor-specific content instead of the deterministic seed.

    Returns the number of milestones written. A no-op (returns 0) when there are
    no usable steps — the deterministic seed is left intact in that case.
    Callers must wrap this best-effort so a persist failure never fails the
    generation response.
    """
    rows = map_generated_steps_to_milestones(steps, corridor)
    if not rows:
        return 0
    # A CURATED CORRIDOR OUTRANKS A GENERATED ONE. Refuse to replace an authored
    # pathway with generated steps — see the module note above for the measurements.
    curated = curated_corridor_milestones(db, case_id, request_id=request_id)
    if curated is None:
        log.warning(
            "persist_generated_milestones: REFUSED for case %s (corridor=%s) — could not "
            "determine whether curated corridor milestones exist. Refusing rather than "
            "risking the deletion of an authored pathway.", case_id, corridor,
        )
        return 0
    if curated:
        log.warning(
            "persist_generated_milestones: REFUSED for case %s (corridor=%s) — %d curated "
            "corridor milestones present (%s). The authored pathway is sequenced and cited; "
            "the generated one is not. Keeping the curated steps.",
            case_id, corridor, len(curated),
            ", ".join(sorted(str(m.get("milestone_type") or "?") for m in curated)[:5]),
        )
        return 0
    # Preserve service-derived milestones (source='service') so a regeneration
    # of the AI roadmap doesn't wipe steps the employee added via the Services tab.
    db.delete_case_milestones(case_id, request_id=request_id, exclude_source="service")
    written = 0
    for row in rows:
        db.upsert_case_milestone(case_id=case_id, request_id=request_id, source="ai", **row)
        written += 1
    log.info(
        "persist_generated_milestones: wrote %d AI milestones for case %s (corridor=%s)",
        written, case_id, corridor,
    )
    return written
