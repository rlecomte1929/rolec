"""Dynamic question generation engine for services flow.

Takes selected services, case context, and saved answers,
and returns an ordered questionnaire with prefill and conditional logic applied.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .question_schema import SERVICE_QUESTION_BANK, ServiceQuestionDef, get_questions_for_services

log = logging.getLogger(__name__)


def _eval_applies_if(applies_if: Optional[Dict[str, Any]], answers: Dict[str, Any]) -> bool:
    """Return True if question should be shown given applies_if and current answers."""
    if not applies_if:
        return True
    for key, expected in applies_if.items():
        if key.startswith("!"):
            # e.g. {"!exists": "some_key"} = show if some_key not in answers
            if key == "!exists" and expected not in answers:
                continue
            return False
        actual = answers.get(key)
        if actual != expected:
            return False
    return True


def _get_prefill_value(source: str, case_context: Dict[str, Any], saved_answers: Dict[str, Any]) -> Optional[Any]:
    """Resolve prefill from case or saved answers. Returns None if not found."""
    if not source:
        return None
    if source.startswith("case."):
        path = source[5:].split(".")
        v = case_context
        for p in path:
            v = (v or {}).get(p) if isinstance(v, dict) else None
        return v
    if source.startswith("answers."):
        key = source[8:]
        return saved_answers.get(key)
    return None


def generate_questions(
    selected_services: List[str],
    case_context: Optional[Dict[str, Any]] = None,
    saved_answers: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Generate dynamic question list for selected services.

    Args:
        selected_services: List of service keys (housing, schools, movers, banks, insurances, electricity)
        case_context: Case draft, destCity, destCountry, originCity, dependents, etc.
        saved_answers: Previously saved questionnaire answers (flat key -> value)

    Returns:
        List of question dicts ready for frontend, with prefill/defaults applied.
    """
    ctx = case_context or {}
    answers = saved_answers or {}
    questions = get_questions_for_services(selected_services)

    # Merge saved answers with case-derived values for conditional evaluation
    effective_answers = dict(answers)
    dest_city = (ctx.get("destCity") or ctx.get("destCountry") or "").strip()
    if dest_city:
        effective_answers["dest_city"] = dest_city
    origin = (ctx.get("originCity") or ctx.get("originCountry") or "Oslo").strip()
    if origin:
        effective_answers["origin_city"] = origin

    out: List[Dict[str, Any]] = []
    for q in questions:
        if not _eval_applies_if(q.applies_if, effective_answers):
            continue
        prefill = _get_prefill_value(q.prefill_source, ctx, answers) if q.prefill_source else None
        default = prefill if prefill is not None else (answers.get(q.question_key) if q.question_key in answers else q.default)
        item = {
            "question_key": q.question_key,
            "label": q.label,
            "type": q.type,
            "service_category": q.service_category,
            "required": q.required,
            "placeholder": q.placeholder,
            "default": default,
            "criteria_key": q.criteria_key or q.question_key,
            "applies_if": q.applies_if,
            "prefill_source": q.prefill_source,
        }
        if q.options:
            item["options"] = [o.model_dump() for o in q.options]
        out.append(item)
    log.info("generate_questions services=%s count=%d", selected_services, len(out))
    return out
