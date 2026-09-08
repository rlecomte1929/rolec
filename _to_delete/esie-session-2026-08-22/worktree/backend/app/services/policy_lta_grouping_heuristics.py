"""
Domain-specific grouping heuristics for long-term assignment (LTA) summary rows.

Structures common relocation-policy wording into tiers, variants, applicability,
external governance, governance conditions, and informational compensation lines —
so generic mapping does not scatter them into duplicate sibling concepts.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# --- Allowance pattern (assignee + dependant, one-off, capped reimbursement) ---

_ONE_OFF_RE = re.compile(
    r"\b(?:one[-\s]?off|one[-\s]?time|single\s+payment|lump\s+sum\s+payment|lump\s+sum)\b",
    re.I,
)
_CAPPED_REIMBURSE_RE = re.compile(
    r"\b(?:capped\s+reimbursement|reimbursement\s+capped|maximum\s+reimbursement|"
    r"reimbursed\s+up\s+to|up\s+to\s+(?:a\s+)?(?:maximum|max|cap)|cap\s+of)\b",
    re.I,
)
_ASSIGN_AMOUNT_RE = re.compile(
    r"(?:assignee|employee|principal)\s*[:\s]*(?:USD|EUR|GBP|CHF|CAD|AUD)?\s*(?:[€$£]\s*)?([\d,]+(?:\.\d+)?)\b",
    re.I,
)
_DEP_AMOUNT_RE = re.compile(
    r"(?:each\s+)?depend(?:a|e)nt[s]?\s*[:\s]*(?:USD|EUR|GBP|CHF|CAD|AUD)?\s*(?:[€$£]\s*)?([\d,]+(?:\.\d+)?)\b",
    re.I,
)
_SLASH_LEAD_DEP_RE = re.compile(
    r"^\s*([\d,]+(?:\.\d+)?)\s*/\s*(?:each\s+)?depend",
    re.I,
)


def parse_allowance_value_structure(summary_text: str) -> Dict[str, Any]:
    """
    Group allowance-style value signals into one structure (tiers + flags).
    """
    out: Dict[str, Any] = {}
    tiers: List[Dict[str, Any]] = []
    m_a = _ASSIGN_AMOUNT_RE.search(summary_text)
    m_d = _DEP_AMOUNT_RE.search(summary_text)
    if m_a:
        tiers.append({"role": "assignee", "amount_text": m_a.group(1).replace(",", "")})
    elif m_d and _SLASH_LEAD_DEP_RE.search(summary_text):
        m_lead = _SLASH_LEAD_DEP_RE.match(summary_text.strip())
        if m_lead:
            tiers.append({"role": "assignee", "amount_text": m_lead.group(1).replace(",", "")})
    if m_d:
        tiers.append({"role": "each_dependant", "amount_text": m_d.group(1).replace(",", "")})
    if tiers:
        out["amount_tiers"] = tiers
    if _ONE_OFF_RE.search(summary_text):
        out["allowance_payment_type"] = "one_off"
    if _CAPPED_REIMBURSE_RE.search(summary_text) or re.search(
        r"\bcap(?:ped)?\s+(?:at|to)\b", summary_text, re.I
    ):
        out["reimbursement_cap_mentioned"] = True
    return out


# --- Travel / leave variants (standard, split family, dependant in education, R&R) ---

_VARIANT_SYNONYMS: Tuple[Tuple[str, str], ...] = (
    (r"standard\s+home\s+leave|standard\s+leave", "standard home leave"),
    (r"split\s+family\s+leave|split\s+family", "split family leave"),
    (r"depend(?:a|e)nt\s+in\s+education\s+leave|education\s+leave", "dependant in education leave"),
    (r"\br&r\b|rest\s+and\s+recuperation|r\s+and\s+r", "R&R travel"),
)


def parse_travel_leave_variants(summary_text: str) -> List[str]:
    """
    Extract leave/travel variant labels from slash lists, comma lists, or known phrases.
    """
    text = summary_text.strip()
    if not text:
        return []
    variants: List[str] = []
    seen_lower = set()

    def add_label(label: str) -> None:
        t = label.strip()
        if len(t) < 4:
            return
        k = t.lower()
        if k in seen_lower:
            return
        seen_lower.add(k)
        variants.append(t)

    # Slash-separated (after optional "Home leave" prefix)
    stripped = re.sub(r"^\s*home\s+leave\s*[:\s–\-]*", "", text, flags=re.I)
    if "/" in stripped:
        parts = [p.strip() for p in re.split(r"\s*/\s*", stripped) if p.strip()]
        for p in parts:
            pl = re.sub(r"\s+", " ", p.lower())
            if pl in ("home leave", "homeleave", "leave"):
                continue
            add_label(p)

    # Comma / "and" separated narrative
    if len(variants) < 2:
        chunk = text
        # strip leading "including" / "covers"
        chunk = re.sub(r"^\s*(?:including|covers?|such\s+as)\s+", "", chunk, flags=re.I)
        pieces = re.split(r",|\s+and\s+", chunk)
        for p in pieces:
            p = p.strip().rstrip(".")
            if len(p) < 6 or len(p) > 100:
                continue
            pl = p.lower()
            if " as per " in pl or "policy" in pl:
                continue
            if "home leave" in pl or "leave" in pl or "travel" in pl or "r&r" in pl or "split family" in pl:
                if pl not in ("home leave", "leave"):
                    add_label(p)

    # Regex synonym capture (full text)
    lower = text.lower()
    for pattern, canonical in _VARIANT_SYNONYMS:
        if re.search(pattern, lower, re.I):
            add_label(canonical)

    return variants[:24]


def travel_leave_variants_as_subvalues(summary_text: str) -> Dict[str, Any]:
    v = parse_travel_leave_variants(summary_text)
    if len(v) >= 2:
        return {"leave_variants": v}
    return {}


# --- Family coverage (assignee, spouse, children conditional) ---

def build_family_coverage_structure(text: str) -> Dict[str, Any]:
    lower = text.lower()
    out: Dict[str, Any] = {
        "assignee": bool(
            re.search(r"\bassignee\b|\bemployee\b|\bprincipal\s+assignee\b", lower)
            or ("only" in lower and "assignee" in lower)
        ),
        "spouse_partner": bool(
            re.search(r"\bspouse\b|\bpartner\b|\baccompanying\s+spouse\b", lower)
        ),
        "children": bool(re.search(r"\bchildren\b|\bchild\b|\bdepend(?:a|e)nts?\b", lower)),
        "children_conditional": bool(
            re.search(
                r"\bwhere\s+eligible\b|\bif\s+eligible\b|\bwhen\s+eligible\b|"
                r"\bin\s+full[-\s]?time\s+education\b|\bconditional\w*\s+on\b",
                lower,
            )
        ),
    }
    if re.search(r"\bassignee\s+only\b|\bemployee\s+only\b", lower):
        out["assignee"] = True
        out["spouse_partner"] = out.get("spouse_partner", False)
    notes: List[str] = []
    if out["children"] and out["children_conditional"]:
        notes.append("children_coverage_conditional")
    if notes:
        out["notes"] = notes
    return out


def family_coverage_to_applicability_dims(fc: Dict[str, Any]) -> List[str]:
    dims: List[str] = []
    if fc.get("assignee"):
        dims.append("employee")
    if fc.get("spouse_partner"):
        dims.append("spouse_partner")
    if fc.get("children"):
        dims.append("children")
    return sorted(set(dims))


# --- External reference (other policies, third party) ---

_EXT_POLICY_RE = re.compile(
    r"\b(?:as\s+per|in\s+accordance\s+with|under\s+the|pursuant\s+to|"
    r"in\s+line\s+with|per\s+the)\s+([A-Za-z0-9\s\-]{3,80}?)(?:policy|policies|guidelines|standard|framework)\b",
    re.I,
)
_GLOBAL_TRAVEL_RE = re.compile(
    r"\bglobal\s+travel\s+policy\b|\bcompany\s+travel\s+policy\b", re.I
)


def analyze_external_reference(text: str) -> Dict[str, Any]:
    lower = text.lower()
    phrases: List[str] = []
    m = _EXT_POLICY_RE.search(text)
    if m:
        phrases.append(m.group(0).strip()[:200])
    if _GLOBAL_TRAVEL_RE.search(text):
        phrases.append("Global / company travel policy reference")

    third_party = any(
        x in lower
        for x in (
            "third party",
            "third-party",
            "third party data",
            "determined by",
            "external data",
            "vendor",
            "benchmark",
        )
    )
    if "capped level determined by" in lower or "determined by third party" in lower:
        third_party = True

    is_ext = bool(phrases) or third_party
    if not is_ext:
        return {
            "is_externally_governed": False,
            "reference_phrases": [],
            "coverage_label": None,
            "comparison_readiness": None,
        }

    # Covered but not internally quantified
    coverage_label = "covered"
    if phrases and not third_party:
        comp_ready = "partial"
    elif third_party and "cap" in lower:
        comp_ready = "not_ready"
    elif third_party:
        comp_ready = "partial"
    else:
        comp_ready = "partial"

    if re.search(r"\bsubject\s+to\b|\bat\s+discretion\b|\bmay\s+be\b", lower) and third_party:
        comp_ready = "not_ready"

    return {
        "is_externally_governed": True,
        "reference_phrases": phrases[:6],
        "coverage_label": coverage_label,
        "comparison_readiness": comp_ready,
    }


# --- Governance / approval ---

def extract_governance_conditions(text: str) -> List[Dict[str, Any]]:
    lower = text.lower()
    out: List[Dict[str, Any]] = []
    if re.search(
        r"\b(?:prior|advance|pre[-\s]?)\s+approval\b|\bwith\s+approval\b|\brequires?\s+approval\b",
        lower,
    ):
        out.append({"kind": "prior_approval", "text": "Prior or management approval required"})
    mq = re.search(
        r"\b(two|three|2|3)\s+(?:competitive\s+)?quotes?\s+required\b|\b(?:two|three|2|3)\s+quotes?\b",
        lower,
    )
    if mq:
        n = mq.group(1)
        count = 2 if n in ("two", "2") else 3 if n in ("three", "3") else None
        out.append(
            {
                "kind": "quotes_required",
                "count": count,
                "text": mq.group(0)[:120],
            }
        )
    if re.search(r"\bbusiness\s+line\s+approval\b|\bline\s+manager\s+approval\b", lower):
        out.append({"kind": "business_line_approval", "text": "Business line / management approval"})
    return out


# --- Compensation informational (split payroll, approach — not comparison benefits) ---

_COMP_INFO_RE = re.compile(
    r"\bsplit\s+payroll\b|\bpayroll\s+split\b|\bcompensation\s+approach\b|"
    r"\bhost\s+country\s+payroll\b|\bhome\s+country\s+payroll\b|"
    r"\bpayroll\s+delivery\b|\bremuneration\s+structure\b",
    re.I,
)


def analyze_compensation_informational(text: str, component_label: str = "") -> Dict[str, Any]:
    combined = f"{component_label} {text}".lower()
    if not _COMP_INFO_RE.search(combined):
        return {"is_informational": False, "topics": []}
    topics: List[str] = []
    if re.search(r"split\s+payroll|payroll\s+split", combined):
        topics.append("split_payroll")
    if "compensation approach" in combined:
        topics.append("compensation_approach")
    if "host country payroll" in combined:
        topics.append("host_country_payroll")
    if "home country payroll" in combined:
        topics.append("home_country_payroll")
    return {"is_informational": True, "topics": topics or ["compensation_payroll_narrative"]}


# --- Aggregate analysis (for tests and optional consumers) ---

def analyze_lta_grouping_patterns(
    summary_text: str,
    *,
    component_label: str = "",
    section_context: str = "",
) -> Dict[str, Any]:
    blob = " ".join(
        x.strip()
        for x in (component_label, summary_text, section_context or "")
        if x and str(x).strip()
    )
    return {
        "allowance": parse_allowance_value_structure(summary_text),
        "travel_leave_variants": parse_travel_leave_variants(summary_text),
        "family_coverage": build_family_coverage_structure(blob),
        "external_reference": analyze_external_reference(blob),
        "governance": extract_governance_conditions(blob),
        "compensation_informational": analyze_compensation_informational(blob, component_label),
    }


def merge_lta_pattern_dict(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two ``lta_domain_patterns`` blobs from combined rows."""
    out = dict(a)
    for k, v in b.items():
        if k not in out:
            out[k] = v
            continue
        if k == "travel_leave_variants" and isinstance(out[k], list) and isinstance(v, list):
            out[k] = list(dict.fromkeys(out[k] + v))
        elif k == "governance_conditions" and isinstance(out[k], list) and isinstance(v, list):
            seen = {tuple(sorted(d.items())) for d in out[k] if isinstance(d, dict)}
            for item in v:
                if isinstance(item, dict):
                    t = tuple(sorted(item.items()))
                    if t not in seen:
                        seen.add(t)
                        out[k].append(item)
        elif k == "external_reference" and isinstance(out[k], dict) and isinstance(v, dict):
            merged = {**out[k], **v}
            rp0 = out[k].get("reference_phrases") or []
            rp1 = v.get("reference_phrases") or []
            if isinstance(rp0, list) and isinstance(rp1, list):
                merged["reference_phrases"] = list(dict.fromkeys(rp0 + rp1))
            merged["is_externally_governed"] = bool(
                out[k].get("is_externally_governed") or v.get("is_externally_governed")
            )
            out[k] = merged
        elif k in ("allowance", "family_coverage", "compensation_informational") and isinstance(
            out[k], dict
        ) and isinstance(v, dict):
            out[k] = {**out[k], **v}
        elif isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    return out


def apply_lta_grouping_heuristics_to_mapped_row(
    *,
    primary_canonical_key: Optional[str],
    summary_text: str,
    component_label: Optional[str],
    section_context: Optional[str],
    sub_values: Dict[str, Any],
    applicability: List[str],
    coverage_status: str,
    comparison_readiness_hint: str,
) -> Tuple[Dict[str, Any], List[str], str, str]:
    """
    Enrich an already-keyed mapped row with LTA domain patterns (single grouped item semantics).
    Returns (sub_values, applicability, coverage_status, comparison_readiness_hint).
    """
    sv = dict(sub_values)
    app = list(applicability)
    cov = coverage_status
    comp = comparison_readiness_hint

    comp_label = component_label or ""
    ctx = section_context or ""
    patterns = analyze_lta_grouping_patterns(
        summary_text, component_label=comp_label, section_context=ctx
    )

    domain_blob: Dict[str, Any] = {
        "allowance": patterns["allowance"],
        "travel_leave_variants": patterns["travel_leave_variants"],
        "family_coverage": patterns["family_coverage"],
        "external_reference": patterns["external_reference"],
        "governance_conditions": patterns["governance"],
        "compensation_informational": patterns["compensation_informational"],
    }
    sv["lta_domain_patterns"] = domain_blob

    # 1) Allowance — merge tiers / flags for relocation allowance (or amount-like rows)
    if primary_canonical_key == "relocation_allowance":
        alw = patterns["allowance"]
        if alw.get("amount_tiers"):
            existing = sv.get("amount_tiers") or []
            if isinstance(existing, list):
                seen = {tuple(sorted(d.items())) for d in existing if isinstance(d, dict)}
                for t in alw["amount_tiers"]:
                    if isinstance(t, dict):
                        sig = tuple(sorted(t.items()))
                        if sig not in seen:
                            seen.add(sig)
                            existing.append(t)
                sv["amount_tiers"] = existing
            else:
                sv["amount_tiers"] = alw["amount_tiers"]
        if alw.get("allowance_payment_type"):
            sv["allowance_payment_type"] = alw["allowance_payment_type"]
        if alw.get("reimbursement_cap_mentioned"):
            sv["reimbursement_cap_mentioned"] = True

    # 2) Travel / leave variants (merge with slash-parsed variants)
    if primary_canonical_key == "home_leave":
        tvars = patterns["travel_leave_variants"]
        existing_lv = sv.get("leave_variants") if isinstance(sv.get("leave_variants"), list) else []
        merged_lv = list(dict.fromkeys(list(existing_lv) + tvars))
        if len(merged_lv) >= 2:
            sv["leave_variants"] = merged_lv[:24]
            cov = "specified"
            comp = "ready"

    # 3) Family coverage → applicability structure (prefer heuristic dims when clear)
    fc = patterns["family_coverage"]
    if primary_canonical_key in (
        "work_permits_and_visas",
        "relocation_allowance",
        "home_leave",
        "host_housing",
        "host_transportation",
        "temporary_living_outbound",
        "temporary_living_return",
        "child_education",
        "school_search",
        "spouse_support",
        "language_training",
        "cultural_training",
    ):
        sv["family_coverage"] = fc
        dims = family_coverage_to_applicability_dims(fc)
        if len(dims) >= 1:
            app = sorted(set(app) | set(dims))

    # 4) External reference (covered / externally governed / comparison tier)
    ext = patterns["external_reference"]
    if ext.get("is_externally_governed"):
        sv["external_governance"] = {
            "is_externally_governed": True,
            "reference_phrases": ext.get("reference_phrases") or [],
            "coverage_label": ext.get("coverage_label"),
        }
        erc = ext.get("comparison_readiness")
        if erc == "not_ready":
            comp = "not_ready"
        elif erc == "partial" and comp in ("ready", "partial"):
            comp = "partial"
        if primary_canonical_key == "host_housing":
            cov = "capped_external"
            if comp != "not_ready":
                comp = "external_reference"

    # 5) Governance — attach to row, not separate benefits
    gov = patterns["governance"]
    if gov:
        sv["governance_conditions"] = gov

    # 6) Compensation informational
    ci = patterns["compensation_informational"]
    if ci.get("is_informational") and primary_canonical_key == "policy_definitions_and_exceptions":
        sv["informational_compensation_topics"] = ci.get("topics") or []
        comp = "not_ready"
        cov = "mentioned"

    return sv, app, cov, comp
