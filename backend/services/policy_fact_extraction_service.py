"""
PolicyFactExtractionService — deterministic minimal facts for assistant grounding (approved taxonomy only).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

APPROVED_FACT_TYPES = frozenset(
    {
        "benefit",
        "allowance_cap",
        "duration_limit",
        "eligibility_rule",
        "family_rule",
        "assignment_type_rule",
        "destination_rule",
        "approval_requirement",
        "reimbursement_rule",
        "excluded_item",
        "exception_note",
    }
)

_CURRENCY_RE = re.compile(
    r"\b(?:USD|EUR|GBP|CHF|CAD|AUD|JPY|\$|€|£)\s*[0-9][0-9,.\s]*(?:per\s+(?:month|year|day|week))?",
    re.I,
)
_AMOUNT_RE = re.compile(r"\b[0-9][0-9,.\s]*(?:%|percent)\b", re.I)
_DURATION_RE = re.compile(
    r"\b(?:up to\s+)?([0-9]+)\s*(days?|weeks?|months?|years?)\b",
    re.I,
)
_ASSIGNMENT_TERMS = [
    ("long_term", ["long-term assignment", "long term assignment", "lta", "long-term"]),
    ("short_term", ["short-term assignment", "short term assignment", "sta", "short-term"]),
    ("permanent", ["permanent transfer", "permanent relocation"]),
    ("commuter", ["commuter assignment", "commuter"]),
]
_FAMILY_TERMS = [
    "spouse",
    "dependent",
    "dependents",
    "family",
    "accompanying",
    "married",
    "single",
    "children",
]
_SOFT_LANGUAGE_RE = re.compile(
    r"\b(?:may|typically|exceptional|discretionary)\b|subject\s+to\s+approval|"
    r"at\s+the\s+discretion|case[- ]by[- ]case|exceptional\s+cases",
    re.I,
)
_COUNTRY_HINT_RE = re.compile(
    r"\b(?:United States|U\.S\.A?\.|USA|UK|United Kingdom|Germany|France|Japan|Singapore|Australia|Canada|India|China)\b",
    re.I,
)


def _soft_language_ambiguous(low: str) -> bool:
    return bool(_SOFT_LANGUAGE_RE.search(low))


def _extended_applicability_json(low: str) -> Dict[str, Any]:
    """Structured hints aligned with policy assistant applicability hardening (conservative)."""
    o: Dict[str, Any] = {}
    if re.search(r"\b(?:grade|band|career level|job level)\b", low, re.I):
        o["employee_levels"] = ["grade_or_level_mentioned"]
    fam: List[str] = []
    if "married" in low or "spouse" in low or "partner" in low:
        fam.append("married_or_partner")
    if "single" in low and "single" in low.split()[:40]:
        fam.append("single_mentioned")
    if fam:
        o["family_statuses"] = list(dict.fromkeys(fam))
    if "dependent" in low and "child" in low:
        o["dependent_children_required"] = True
    if "no dependent" in low or "without children" in low:
        o["dependent_children_required"] = False
    countries = [c.strip() for c in _COUNTRY_HINT_RE.findall(low)]
    if countries:
        uniq = list(dict.fromkeys(countries))[:16]
        o["destination_countries"] = uniq
        if "home country" in low or "country of origin" in low:
            o["origin_countries"] = uniq
    ct: List[str] = []
    if "local plus" in low or "local-plus" in low:
        ct.append("local_plus")
    if re.search(r"\blocal contract\b|\blocal hire\b", low, re.I):
        ct.append("local")
    if ct:
        o["contract_types"] = list(dict.fromkeys(ct))
    if any(
        x in low
        for x in (
            "approval required",
            "prior approval",
            "pre-approval",
            "pre approval",
            "must be approved",
            "subject to approval",
        )
    ):
        o["approval_required"] = True
    o["mandatory_missing_case_fields"] = []
    return o


_BENEFIT_TERMS = [
    "housing",
    "temporary housing",
    "relocation allowance",
    "home leave",
    "household goods",
    "shipment",
    "school",
    "tuition",
    "immigration",
    "visa",
    "tax equalization",
    "settling",
    "mobility",
]


def _quote_snippet(text: str, max_len: int = 320) -> str:
    t = " ".join(text.split())
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _infer_assignment_applicability(text_lower: str) -> Dict[str, Any]:
    hits: List[str] = []
    for key, pats in _ASSIGNMENT_TERMS:
        if any(p in text_lower for p in pats):
            hits.append(key)
    if not hits:
        return {}
    return {"assignment_types": list(dict.fromkeys(hits))}


def _infer_destination_applicability(text_lower: str) -> Dict[str, Any]:
    # Very light signals — preserve ambiguity rather than invent countries.
    out: Dict[str, Any] = {}
    if "host country" in text_lower or "host location" in text_lower:
        out["scope"] = "host_country_mentioned"
    if "home country" in text_lower:
        out["origin_mentioned"] = True
    return out


def extract_minimal_policy_facts(
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    chunks: rows with at least id, text_content (or text), section_title, chunk_index.
    Returns fact dicts ready for insert_policy_fact (plus source_chunk_id).
    """
    facts: List[Dict[str, Any]] = []
    for ch in chunks:
        cid = str(ch.get("id") or "")
        raw = str(ch.get("text_content") or ch.get("text") or "")
        if not cid or not raw.strip():
            continue
        low = raw.lower()
        sec = ch.get("section_title")
        page = ch.get("page_number")
        chunk_app = {
            **_infer_assignment_applicability(low),
            **_infer_destination_applicability(low),
            **_extended_applicability_json(low),
        }
        soft_lang = _soft_language_ambiguous(low)

        # Benefits (keyword presence in chunk)
        for term in _BENEFIT_TERMS:
            if term in low:
                facts.append(
                    {
                        "fact_type": "benefit",
                        "category": term.replace(" ", "_")[:80],
                        "subcategory": None,
                        "normalized_value_json": {"mention": term, "chunk_index": ch.get("chunk_index")},
                        "applicability_json": dict(chunk_app),
                        "ambiguity_flag": True,
                        "confidence_score": 0.35,
                        "source_chunk_id": cid,
                        "source_page": page,
                        "source_section": sec,
                        "source_quote": _quote_snippet(raw),
                    }
                )
                break

        # Allowance / caps
        for m in _CURRENCY_RE.finditer(raw):
            facts.append(
                {
                    "fact_type": "allowance_cap",
                    "category": "monetary",
                    "subcategory": None,
                    "normalized_value_json": {"raw_span": m.group(0).strip()},
                    "applicability_json": dict(chunk_app),
                    "ambiguity_flag": True or soft_lang,
                    "confidence_score": 0.45,
                    "source_chunk_id": cid,
                    "source_page": page,
                    "source_section": sec,
                    "source_quote": _quote_snippet(raw),
                }
            )
        for m in _AMOUNT_RE.finditer(raw):
            facts.append(
                {
                    "fact_type": "allowance_cap",
                    "category": "percentage",
                    "subcategory": None,
                    "normalized_value_json": {"raw_span": m.group(0).strip()},
                    "applicability_json": dict(chunk_app),
                    "ambiguity_flag": True or soft_lang,
                    "confidence_score": 0.4,
                    "source_chunk_id": cid,
                    "source_page": page,
                    "source_section": sec,
                    "source_quote": _quote_snippet(raw),
                }
            )

        # Duration limits
        for m in _DURATION_RE.finditer(raw):
            facts.append(
                {
                    "fact_type": "duration_limit",
                    "category": "time_bound",
                    "subcategory": None,
                    "normalized_value_json": {"amount": m.group(1), "unit": m.group(2).lower()},
                    "applicability_json": dict(chunk_app),
                    "ambiguity_flag": soft_lang
                    or (not ("up to" in low or "maximum" in low or "not to exceed" in low)),
                    "confidence_score": 0.5,
                    "source_chunk_id": cid,
                    "source_page": page,
                    "source_section": sec,
                    "source_quote": _quote_snippet(raw),
                }
            )

        # Eligibility
        if any(x in low for x in ("eligible", "eligibility", "qualify", "qualifying")):
            facts.append(
                {
                    "fact_type": "eligibility_rule",
                    "category": "general",
                    "subcategory": None,
                    "normalized_value_json": {"signal": "eligibility_language_present"},
                    "applicability_json": dict(chunk_app),
                    "ambiguity_flag": True or soft_lang,
                    "confidence_score": 0.3,
                    "source_chunk_id": cid,
                    "source_page": page,
                    "source_section": sec,
                    "source_quote": _quote_snippet(raw),
                }
            )

        # Family
        if any(ft in low for ft in _FAMILY_TERMS):
            facts.append(
                {
                    "fact_type": "family_rule",
                    "category": "household",
                    "subcategory": None,
                    "normalized_value_json": {"terms_found": [t for t in _FAMILY_TERMS if t in low][:6]},
                    "applicability_json": {**dict(chunk_app), "family_mentioned": True},
                    "ambiguity_flag": True or soft_lang,
                    "confidence_score": 0.35,
                    "source_chunk_id": cid,
                    "source_page": page,
                    "source_section": sec,
                    "source_quote": _quote_snippet(raw),
                }
            )

        # Assignment type (explicit)
        app = _infer_assignment_applicability(low)
        if app.get("assignment_types"):
            facts.append(
                {
                    "fact_type": "assignment_type_rule",
                    "category": "assignment",
                    "subcategory": None,
                    "normalized_value_json": dict(app),
                    "applicability_json": {**dict(chunk_app), **app},
                    "ambiguity_flag": True or soft_lang,
                    "confidence_score": 0.4,
                    "source_chunk_id": cid,
                    "source_page": page,
                    "source_section": sec,
                    "source_quote": _quote_snippet(raw),
                }
            )

        # Destination / origin
        dest = _infer_destination_applicability(low)
        if dest:
            facts.append(
                {
                    "fact_type": "destination_rule",
                    "category": "location",
                    "subcategory": None,
                    "normalized_value_json": dict(dest),
                    "applicability_json": {**dict(chunk_app), **dest},
                    "ambiguity_flag": True or soft_lang,
                    "confidence_score": 0.25,
                    "source_chunk_id": cid,
                    "source_page": page,
                    "source_section": sec,
                    "source_quote": _quote_snippet(raw),
                }
            )

        # Approval
        if any(x in low for x in ("approval required", "prior approval", "pre-approval", "pre approval", "must be approved")):
            facts.append(
                {
                    "fact_type": "approval_requirement",
                    "category": "approval",
                    "subcategory": None,
                    "normalized_value_json": {"signal": "approval_language_present"},
                    "applicability_json": dict(chunk_app),
                    "ambiguity_flag": True or soft_lang,
                    "confidence_score": 0.4,
                    "source_chunk_id": cid,
                    "source_page": page,
                    "source_section": sec,
                    "source_quote": _quote_snippet(raw),
                }
            )

        # Reimbursement
        if "reimburs" in low:
            facts.append(
                {
                    "fact_type": "reimbursement_rule",
                    "category": "reimbursement",
                    "subcategory": None,
                    "normalized_value_json": {"signal": "reimbursement_mentioned"},
                    "applicability_json": dict(chunk_app),
                    "ambiguity_flag": True or soft_lang,
                    "confidence_score": 0.35,
                    "source_chunk_id": cid,
                    "source_page": page,
                    "source_section": sec,
                    "source_quote": _quote_snippet(raw),
                }
            )

        # Exclusions
        if any(x in low for x in ("not covered", "excluded", "exclusion", "ineligible", "outside policy")):
            facts.append(
                {
                    "fact_type": "excluded_item",
                    "category": "exclusion",
                    "subcategory": None,
                    "normalized_value_json": {"signal": "exclusion_language_present"},
                    "applicability_json": dict(chunk_app),
                    "ambiguity_flag": True or soft_lang,
                    "confidence_score": 0.35,
                    "source_chunk_id": cid,
                    "source_page": page,
                    "source_section": sec,
                    "source_quote": _quote_snippet(raw),
                }
            )

        # Exceptions
        if "exception" in low or "waiv" in low:
            facts.append(
                {
                    "fact_type": "exception_note",
                    "category": "exception",
                    "subcategory": None,
                    "normalized_value_json": {"signal": "exception_language_present"},
                    "applicability_json": dict(chunk_app),
                    "ambiguity_flag": True or soft_lang,
                    "confidence_score": 0.3,
                    "source_chunk_id": cid,
                    "source_page": page,
                    "source_section": sec,
                    "source_quote": _quote_snippet(raw),
                }
            )

    # Deduplicate near-identical facts (same type + chunk + category)
    seen: set = set()
    unique: List[Dict[str, Any]] = []
    for f in facts:
        key = (f["fact_type"], f["source_chunk_id"], f["category"], f.get("subcategory"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(f)

    return [f for f in unique if f.get("fact_type") in APPROVED_FACT_TYPES]


class PolicyFactExtractionService:
    def extract_minimal_policy_facts(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return extract_minimal_policy_facts(chunks)
