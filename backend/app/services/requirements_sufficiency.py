from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from ...database import db
from ...app.db import SessionLocal
from ...app import crud
from .destination_normalizer import normalize_destination_country
from .guidance_pack_service import build_profile_snapshot
# Phase 5: scope-aware applies_to matching lives in its own dependency-free module so it can
# be unit-tested without this DB-backed service. It replaces the old strict-equality matcher,
# which dropped any fact whose applies_to carried a key the profile snapshot lacked (all of
# Otto's scope-annotated facts) and hid audience_scope rules from EEA movers.
from .applies_to_matcher import apply_applies_to as _apply_applies_to

log = logging.getLogger(__name__)


def _safe_parse_case_draft(raw: Optional[str]) -> Dict[str, Any]:
    """Never raise: invalid draft_json must not 500 sufficiency."""
    if not raw or not str(raw).strip():
        return {}
    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        log.warning("requirements_sufficiency: invalid draft_json, using empty dict")
        return {}


def _resolve_destination(raw: Optional[str]) -> Optional[str]:
    """Normalise a case's destination to ISO-2, falling back to the raw value.

    [AIQ-1821] Cases do not consistently store ISO-2. Measured on prod 2026-08-12:
    **426 of 1389 wizard_cases store a country NAME** ("Germany", "Norway", "France")
    rather than "DE"/"NO"/"FR". Both consumers below match exactly —
    `list_dossier_questions` on `destination_country = :dest`, and
    `list_approved_requirement_facts` on `e.destination_country = :dest` — so an
    un-normalised "Norway" silently returned zero questions AND zero facts, and the
    endpoint reported "ok" with empty results. That reads as "nothing is required of
    you", which is the opposite of the truth.

    The sibling endpoint GET /api/dossier/questions already normalises; this path did not.
    Both now share `destination_normalizer`, so they cannot drift apart.

    Falls back to the raw value when the country isn't in the normaliser's table, so an
    unmapped destination behaves exactly as it does today rather than becoming None —
    "no facts for Atlantis" must not turn into "no destination set".
    """
    if not raw:
        return None
    return normalize_destination_country(raw) or raw


def compute_requirements_sufficiency(case_id: str, user_id: str) -> Dict[str, Any]:
    with SessionLocal() as session:
        case = crud.get_case(session, case_id)
        if not case:
            raise ValueError("Case not found")
        draft = _safe_parse_case_draft(getattr(case, "draft_json", None))
        raw_dest = case.dest_country or (draft.get("relocationBasics") or {}).get("destCountry")
        dest = _resolve_destination(raw_dest)

    dossier_answers = {}
    if dest:
        questions = db.list_dossier_questions(dest)
        q_by_id = {q["id"]: q for q in questions}
        for ans in db.list_dossier_answers(case_id, user_id):
            q = q_by_id.get(ans["question_id"])
            if q and q.get("question_key"):
                dossier_answers[q["question_key"]] = ans["answer"]

    snapshot = build_profile_snapshot(draft, dossier_answers, dest)
    facts = db.list_approved_requirement_facts(dest or "")
    required_fields: List[str] = []
    supporting_requirements = []
    for fact in facts:
        applies_to = fact.get("applies_to") or {}
        if not _apply_applies_to(applies_to, snapshot):
            continue
        required_fields.extend(fact.get("required_fields") or [])
        supporting_requirements.append({
            "fact_id": fact.get("id"),
            "fact_text": fact.get("fact_text"),
            "source_url": fact.get("source_url"),
            "required_fields": fact.get("required_fields") or [],
            # Phase 5: carry scope/rendering signals so the serving/UI layer can present a
            # conditional fact conditionally and flag "easy to miss" traps, rather than
            # stating every fact as an unconditional requirement.
            "assertion_mode": applies_to.get("assertion_mode"),
            "conditional_on": applies_to.get("conditional_on"),
            "non_obvious": bool(applies_to.get("non_obvious", False)),
        })
    required_fields = list(dict.fromkeys([f for f in required_fields if f]))
    missing_fields = []
    for field in required_fields:
        value = snapshot.get(field)
        if value in (None, "", [], {}):
            missing_fields.append(field)
    return {
        "destination_country": dest,
        "missing_fields": missing_fields,
        "supporting_requirements": supporting_requirements,
    }
