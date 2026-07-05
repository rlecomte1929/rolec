"""
AIQ-1415 — Natural-Language Policy Builder.

HR describes a mobility policy in plain English; we ask Claude (Anthropic tool-use,
schema-forced) to map it onto the canonical config-matrix benefit set, validate the
result against the real ``PolicyConfigBenefitWrite`` schema, and return a *candidate*
put-draft body (all 31 canonical benefits, covered per the description).

This module NEVER writes. Persistence happens only via the existing
``PUT /api/hr/policy-config/draft`` after the HR user explicitly approves the preview —
so "no policy is saved without approval" holds by construction (confirm-before-save).

Safety:
- user free-text is masked via ``pii_masker.mask_pii`` before egress;
- the Anthropic tool schema constrains ``benefit_key`` + every enum axis, so the model can
  only emit valid values; any non-canonical / invalid row is dropped into ``warnings``;
- a global kill-switch (``RELOPASS_POLICY_LLM_DISABLED``) short-circuits before any egress.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ...core.llm_flags import policy_llm_disabled
from ...schemas_compensation_allowance import (
    PolicyConfigBenefitWrite,
    PolicyConfigCategory,
)
from .llm_client import claude_complete_sync
from .pii_masker import mask_pii
from .policy_config_matrix_service import _CANONICAL_KEYS

log = logging.getLogger(__name__)

# Canonical lookups derived from the single source of truth in the matrix service.
_KEY_TO_LABEL: Dict[str, str] = {k: label for (k, label, _cat) in _CANONICAL_KEYS}
_KEY_TO_CATEGORY: Dict[str, PolicyConfigCategory] = {k: cat for (k, _label, cat) in _CANONICAL_KEYS}
_CANONICAL_KEY_LIST: List[str] = [k for (k, _l, _c) in _CANONICAL_KEYS]

_VALUE_TYPES = ["currency", "percentage", "text", "none"]
_UNIT_FREQS = ["one_time", "monthly", "yearly", "per_trip", "per_day", "per_dependent", "custom"]
_ASSIGNMENT_TYPES = ["short_term", "long_term", "permanent", "international"]
_FAMILY_STATUSES = ["single", "spouse_partner", "dependents"]
_EMPLOYEE_LEVELS = ["entry", "manager", "director", "vp", "c_suite"]

# Anthropic tool-use input schema — forces valid benefit_key + enum axes.
_TOOL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "benefits": {
            "type": "array",
            "description": "One entry per benefit the description OFFERS. Omit benefits not mentioned.",
            "items": {
                "type": "object",
                "properties": {
                    "benefit_key": {"type": "string", "enum": _CANONICAL_KEY_LIST},
                    "covered": {"type": "boolean"},
                    "value_type": {"type": "string", "enum": _VALUE_TYPES},
                    "amount_value": {"type": ["number", "null"]},
                    "currency_code": {"type": ["string", "null"], "description": "ISO 4217, e.g. USD, EUR"},
                    "percentage_value": {"type": ["number", "null"]},
                    "unit_frequency": {"type": "string", "enum": _UNIT_FREQS},
                    "notes": {"type": ["string", "null"]},
                    "assignment_types": {"type": "array", "items": {"type": "string", "enum": _ASSIGNMENT_TYPES}},
                    "family_statuses": {"type": "array", "items": {"type": "string", "enum": _FAMILY_STATUSES}},
                    "employee_levels": {"type": "array", "items": {"type": "string", "enum": _EMPLOYEE_LEVELS}},
                },
                "required": ["benefit_key", "covered"],
            },
        }
    },
    "required": ["benefits"],
}

_SYSTEM_PROMPT = (
    "You are a global-mobility policy configuration assistant. Convert an HR admin's plain-English "
    "description of their company relocation/mobility policy into structured benefit rows using ONLY the "
    "benefit_key values in the provided tool schema — never invent keys.\n"
    "Rules:\n"
    "- Emit a row only for benefits the description clearly OFFERS; set covered=true for those.\n"
    "- When the text states an amount, set value_type='currency' + amount_value + currency_code (+ unit_frequency "
    "if a cadence is given); for a percentage use value_type='percentage' + percentage_value; otherwise "
    "value_type='none'.\n"
    "- Only set assignment_types/family_statuses/employee_levels when the description differentiates by them "
    "(e.g. 'domestic' → short_term/long_term, 'international' → international/permanent; 'families' → dependents). "
    "Leave them empty to mean 'applies to everyone'.\n"
    "- Put any nuance you cannot encode in a field into 'notes'.\n"
    "- Do NOT guess amounts or benefits that were not stated. It is correct to return few rows."
)


def _empty_result(message: str, *, generated: bool) -> Dict[str, Any]:
    return {"categories": [], "warnings": [message], "generated": generated, "covered_count": 0}


def _default_row(key: str, label: str, category: PolicyConfigCategory, order: int) -> Dict[str, Any]:
    row = PolicyConfigBenefitWrite(
        benefit_key=key, benefit_label=label, category=category, covered=False, display_order=order
    )
    return row.model_dump(mode="json")


def generate_policy_config_from_text(text: str) -> Dict[str, Any]:
    """Generate a candidate config-matrix ``categories`` body from free text. Never persists.

    Returns ``{categories, warnings, generated, covered_count}``. ``categories`` is a full
    put-draft-ready array (all 31 canonical benefits, grouped by the 6 categories); ``generated``
    is False when the LLM was skipped (disabled / empty input / call failure)."""
    warnings: List[str] = []

    if policy_llm_disabled():
        return _empty_result("Policy AI is currently disabled — no configuration was generated.", generated=False)

    clean = (text or "").strip()
    if not clean:
        return _empty_result("Please describe your policy first.", generated=False)

    masked = mask_pii(clean)  # HARD RULE: mask before any LLM egress (GDPR Art. 28/44)
    try:
        resp = claude_complete_sync(system=_SYSTEM_PROMPT, user=masked, schema=_TOOL_SCHEMA)
    except Exception as exc:  # noqa: BLE001 — never surface raw LLM/provider errors to HR
        log.warning("nl_policy_builder: LLM call failed: %s", type(exc).__name__)
        return _empty_result(
            "Couldn't generate a policy from that description right now. Please try again or rephrase.",
            generated=False,
        )

    raw_benefits = (resp or {}).get("benefits") or []
    by_key: Dict[str, Dict[str, Any]] = {}
    for item in raw_benefits:
        if not isinstance(item, dict):
            continue
        key = item.get("benefit_key")
        if key not in _KEY_TO_LABEL:
            warnings.append(f"Ignored an unrecognized benefit ({key!r}).")
            continue
        candidate = {
            "benefit_key": key,
            "benefit_label": _KEY_TO_LABEL[key],
            "category": _KEY_TO_CATEGORY[key],
            "covered": bool(item.get("covered", False)),
            "value_type": item.get("value_type") or "none",
            "amount_value": item.get("amount_value"),
            "currency_code": item.get("currency_code"),
            "percentage_value": item.get("percentage_value"),
            "unit_frequency": item.get("unit_frequency") or "one_time",
            "notes": item.get("notes"),
            "assignment_types": item.get("assignment_types") or [],
            "family_statuses": item.get("family_statuses") or [],
            "employee_levels": item.get("employee_levels") or [],
        }
        try:
            valid = PolicyConfigBenefitWrite.model_validate(candidate)
        except Exception:  # noqa: BLE001 — a malformed/hallucinated row must never reach save
            warnings.append(f"Dropped {_KEY_TO_LABEL.get(key, key)!r}: the generated values weren't valid.")
            continue
        by_key[key] = valid.model_dump(mode="json")

    # Expand to the FULL canonical set so put_draft receives a complete, valid matrix
    # (benefits not offered in the text land as covered=false rather than being dropped).
    grouped: Dict[str, List[Dict[str, Any]]] = {c.value: [] for c in PolicyConfigCategory}
    for order, (key, label, category) in enumerate(_CANONICAL_KEYS):
        row = by_key.get(key)
        if row is None:
            row = _default_row(key, label, category, order)
        else:
            row["display_order"] = order
        grouped[category.value].append(row)

    categories = [{"category_key": c.value, "benefits": grouped[c.value]} for c in PolicyConfigCategory]
    return {
        "categories": categories,
        "warnings": warnings,
        "generated": True,
        "covered_count": sum(1 for r in by_key.values() if r.get("covered")),
    }
