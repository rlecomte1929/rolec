from __future__ import annotations

import json
from typing import Any, Dict, List

from ...database import db
from ...app.db import SessionLocal
from ...app import crud
from ...services.guidance_pack_service import build_profile_snapshot


def _apply_applies_to(applies_to: Dict[str, Any], snapshot: Dict[str, Any]) -> bool:
    if not applies_to:
        return True
    for key, value in applies_to.items():
        if snapshot.get(key) != value:
            return False
    return True


def compute_requirements_sufficiency(case_id: str, user_id: str) -> Dict[str, Any]:
    with SessionLocal() as session:
        case = crud.get_case(session, case_id)
        if not case:
            raise ValueError("Case not found")
        draft = json.loads(case.draft_json or "{}")
        dest = case.dest_country or (draft.get("relocationBasics") or {}).get("destCountry")

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
