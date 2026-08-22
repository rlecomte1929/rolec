from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from ...database import db
from ...app.db import SessionLocal
from ...app import crud
from .destination_normalizer import normalize_destination_country
from .guidance_pack_service import build_profile_snapshot

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


def _apply_applies_to(applies_to: Dict[str, Any], snapshot: Dict[str, Any]) -> bool:
    if not applies_to:
        return True
    for key, value in applies_to.items():
        if snapshot.get(key) != value:
            return False
    return True


def _citation_status(evidence_verified: Any) -> str:
    """[AIQ-2132] Is this fact's citation one we checked, or one we have never opened?

    `list_approved_requirement_facts` deliberately serves two evidence states side by side —
    PR #1851 excludes only `evidence_verified = FALSE`, because NULL means "never checked", not
    "wrong". Measured on production 2026-08-22: of the 205 served facts, **121 are TRUE and 84
    are NULL**, and the dossier rendered both with the same "Source:" anchor. Provenance is the
    product; presenting an unchecked citation as a checked one spends the trust it is built on.

    Truthiness, not `is True`: Postgres returns a real bool, SQLite (what CI runs against)
    returns 1/0. Anything that is not affirmatively verified — NULL, FALSE, or a row that
    predates the column — reads as `unverified`. Absent evidence is not evidence, so the
    default is always the weaker claim.
    """
    return "verified" if bool(evidence_verified) else "unverified"


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
        if not _apply_applies_to(fact.get("applies_to") or {}, snapshot):
            continue
        required_fields.extend(fact.get("required_fields") or [])
        supporting_requirements.append({
            "fact_id": fact.get("id"),
            "fact_text": fact.get("fact_text"),
            "source_url": fact.get("source_url"),
            # [AIQ-2132] Whether we verified that source verbatim, so the dossier can render a
            # checked citation differently from a never-checked one instead of identically.
            "citation_status": _citation_status(fact.get("evidence_verified")),
            "required_fields": fact.get("required_fields") or [],
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
