"""
Weighted canonical LTA key resolution for summary rows.

Reduces topic drift (transport→housing, language→schooling, compensation→housing) via
label/section-weighted phrases, explicit boosts, and negative disambiguation.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

# Minimum winning score; below this → no canonical key
MIN_WINNING_SCORE = 5.0
# Second place must be at least this far below the winner (else ambiguous → None)
WIN_MARGIN = 2.0

# Multipliers when phrase matches component label or section context (substring)
LABEL_PHRASE_MULT = 1.85
SECTION_PHRASE_MULT = 1.45
SUMMARY_ONLY_MULT = 1.0

# (canonical_key, phrase, base_weight) — longer / rarer phrases get higher base_weight
_CANONICAL_PHRASES: Tuple[Tuple[str, str, float], ...] = (
    # Move / allowances
    ("relocation_allowance", "relocation allowance", 7.0),
    ("relocation_allowance", "relocation lump sum", 7.0),
    ("relocation_allowance", "mobility allowance", 6.5),
    ("relocation_allowance", "lump sum relocation", 6.5),
    ("relocation_allowance", "relocation payment", 6.0),
    # Temporary living
    ("temporary_living_outbound", "temporary living", 7.0),
    ("temporary_living_outbound", "temporary accommodation", 7.0),
    ("temporary_living_outbound", "temporary housing", 6.5),
    ("temporary_living_outbound", "interim housing", 6.5),
    ("temporary_living_outbound", "interim accommodation", 6.5),
    ("temporary_living_outbound", "initial accommodation", 6.5),
    ("temporary_living_outbound", "serviced apartment", 5.5),
    ("temporary_living_outbound", "hotel", 5.5),
    ("temporary_living_outbound", "temp living", 5.0),
    ("temporary_living_return", "temporary living on return", 8.0),
    ("temporary_living_return", "bridge housing", 6.5),
    ("temporary_living_return", "return accommodation", 7.0),
    ("temporary_living_return", "repatriation housing", 7.5),
    ("temporary_living_return", "end of assignment accommodation", 7.5),
    # Host housing (avoid generic "housing" alone)
    ("host_housing", "host housing", 8.0),
    ("host_housing", "host-provided housing", 8.0),
    ("host_housing", "host country housing", 7.0),
    ("host_housing", "company housing", 6.0),
    ("host_housing", "employer-provided housing", 7.0),
    ("host_housing", "leased accommodation", 5.0),
    ("host_housing", "housing allowance host", 6.5),
    # Transportation (host)
    ("host_transportation", "host transportation", 7.5),
    ("host_transportation", "local transportation", 6.5),
    ("host_transportation", "transportation allowance", 6.0),
    ("host_transportation", "company car", 6.5),
    ("host_transportation", "car allowance", 6.5),
    ("host_transportation", "vehicle allowance", 6.0),
    ("host_transportation", "driving licence", 5.5),
    ("host_transportation", "driving license", 5.5),
    ("host_transportation", "driving test", 5.5),
    ("host_transportation", "parking allowance", 5.5),
    ("host_transportation", "commute support", 5.5),
    ("host_transportation", "driver service", 5.0),
    # Language vs cultural (schooling disambiguation elsewhere)
    ("language_training", "language training", 8.0),
    ("language_training", "language course", 7.5),
    ("language_training", "language lessons", 7.0),
    ("language_training", "language tuition", 6.0),
    ("language_training", "language immersion", 6.5),
    ("language_training", "language school", 6.0),
    ("cultural_training", "cultural training", 8.0),
    ("cultural_training", "cross-cultural training", 7.5),
    ("cultural_training", "intercultural training", 7.5),
    # Child education vs school search
    ("child_education", "child education", 8.0),
    ("child_education", "school fees", 7.5),
    ("child_education", "tuition reimbursement", 7.5),
    ("child_education", "tuition difference", 7.5),
    ("child_education", "education allowance", 6.5),
    ("child_education", "international school", 7.0),
    ("child_education", "dependent schooling", 7.0),
    ("child_education", "schooling costs", 6.5),
    ("school_search", "school search", 8.5),
    ("school_search", "school placement", 7.0),
    ("school_search", "finding a school", 7.0),
    ("school_search", "education search", 6.0),
    # Tax
    ("tax_equalization", "tax equalization", 8.5),
    ("tax_equalization", "tax equalisation", 8.5),
    ("tax_equalization", "hypothetical tax", 8.0),
    ("tax_equalization", "hypo tax", 6.0),
    ("tax_equalization", "tax protection", 6.5),
    ("tax_return_support", "tax return support", 8.0),
    ("tax_return_support", "tax return preparation", 8.0),
    ("tax_return_support", "tax filing support", 7.0),
    ("tax_briefing", "tax briefing", 8.0),
    ("tax_briefing", "tax advice session", 6.5),
    # Spouse
    ("spouse_support", "spouse support", 8.0),
    ("spouse_support", "partner support", 7.0),
    ("spouse_support", "dual career", 7.5),
    ("spouse_support", "partner career", 7.5),
    ("spouse_support", "trailing spouse", 7.0),
    ("spouse_support", "spousal allowance", 6.5),
    # Immigration / leave / policy
    ("work_permits_and_visas", "work permit", 6.0),
    ("work_permits_and_visas", "work permits", 6.0),
    ("work_permits_and_visas", "visa processing", 6.5),
    ("work_permits_and_visas", "visa support", 6.5),
    ("work_permits_and_visas", "visa", 5.2),
    ("work_permits_and_visas", "immigration", 6.0),
    ("work_permits_and_visas", "residence permit", 6.0),
    ("home_leave", "home leave", 7.0),
    ("home_leave", "homeward", 5.5),
    ("home_leave", "rest and recuperation", 6.5),
    ("home_leave", "r&r", 6.0),
    ("home_leave", "split family", 5.5),
    ("home_leave", "dependant in education", 5.5),
    ("home_leave", "dependent in education", 5.5),
    ("work_permits_and_visas", "accompanying family", 6.0),
    ("policy_definitions_and_exceptions", "split payroll", 7.0),
    ("policy_definitions_and_exceptions", "compensation approach", 7.0),
    ("policy_definitions_and_exceptions", "host country payroll", 7.0),
    ("policy_definitions_and_exceptions", "home country payroll", 7.0),
    ("policy_definitions_and_exceptions", "payroll split", 7.0),
    ("policy_definitions_and_exceptions", "remuneration structure", 6.5),
    ("policy_definitions_and_exceptions", "payroll delivery", 6.5),
)


def _apply_phrase_scores(
    scores: Dict[str, float],
    *,
    label: str,
    summary: str,
    section: str,
    combined: str,
) -> None:
    for key, phrase, w in _CANONICAL_PHRASES:
        if phrase not in combined:
            continue
        mult = SUMMARY_ONLY_MULT
        if phrase in label:
            mult = max(mult, LABEL_PHRASE_MULT)
        elif phrase in section:
            mult = max(mult, SECTION_PHRASE_MULT)
        scores[key] = scores.get(key, 0.0) + w * mult


def _disambiguate_temp_living(scores: Dict[str, float], combined: str) -> None:
    ret_hit = any(
        s in combined
        for s in (
            "repatriation",
            "upon return",
            "end of assignment",
            "return accommodation",
            "temporary living on return",
            "bridge housing",
            "repatriation housing",
        )
    )
    out_hit = any(
        s in combined
        for s in (
            "on arrival",
            "assignment start",
            "initial accommodation",
            "outbound",
            "first 30 days",
            "first thirty days",
        )
    )
    t_out = scores.get("temporary_living_outbound", 0.0)
    t_ret = scores.get("temporary_living_return", 0.0)
    if ret_hit and not out_hit:
        scores["temporary_living_return"] = t_ret + 10.0
        scores["temporary_living_outbound"] = max(0.0, t_out - 6.0)
    elif out_hit and not ret_hit and t_out > 0:
        scores["temporary_living_outbound"] = t_out + 4.0
        scores["temporary_living_return"] = max(0.0, t_ret - 4.0)


def _disambiguate_tax_vs_allowance(scores: Dict[str, float], combined: str) -> None:
    tax_strength = max(
        scores.get("tax_equalization", 0.0),
        scores.get("tax_return_support", 0.0),
        scores.get("tax_briefing", 0.0),
    )
    if tax_strength >= 6.0:
        scores["relocation_allowance"] = max(0.0, scores.get("relocation_allowance", 0.0) - 12.0)


def _disambiguate_education_vs_language(scores: Dict[str, float], combined: str) -> None:
    lang_signal = any(
        p in combined
        for p in ("language training", "language course", "language lessons", "language tuition")
    )
    school_child_signal = any(
        p in combined
        for p in (
            "school fees",
            "tuition reimbursement",
            "tuition difference",
            "child education",
            "international school",
            "dependent schooling",
            "schooling costs",
            "education allowance",
        )
    )
    school_search_signal = any(
        p in combined for p in ("school search", "school placement", "finding a school")
    )

    if lang_signal and not school_child_signal and not school_search_signal:
        scores["child_education"] = max(0.0, scores.get("child_education", 0.0) - 18.0)
        scores["school_search"] = max(0.0, scores.get("school_search", 0.0) - 10.0)
        scores["language_training"] = scores.get("language_training", 0.0) + 4.0

    if re.search(r"\blanguage\s+school\b", combined) and not re.search(
        r"\b(school fees|tuition reimbursement|tuition difference)\b", combined
    ):
        scores["child_education"] = max(0.0, scores.get("child_education", 0.0) - 8.0)
        scores["language_training"] = scores.get("language_training", 0.0) + 5.0

    if school_child_signal and lang_signal:
        scores["language_training"] = max(0.0, scores.get("language_training", 0.0) - 6.0)

    if school_search_signal:
        scores["school_search"] = scores.get("school_search", 0.0) + 6.0
        if "language" in combined and not school_child_signal:
            scores["language_training"] = max(0.0, scores.get("language_training", 0.0) - 4.0)


def _disambiguate_housing_vs_transport(
    scores: Dict[str, float],
    *,
    label: str,
    section: str,
    combined: str,
) -> None:
    trans_label = bool(
        re.search(
            r"\b(transport|transportation|car|vehicle|driving|commute|parking)\b",
            label,
            re.I,
        )
    )
    trans_words = any(
        p in combined
        for p in (
            "local transportation",
            "transportation allowance",
            "company car",
            "car allowance",
            "driving licence",
            "driving license",
            "driving test",
            "host transportation",
        )
    )
    housing_words = any(
        p in combined
        for p in (
            "host housing",
            "host-provided housing",
            "temporary living",
            "temporary accommodation",
            "company housing",
        )
    )

    if trans_label and trans_words and not re.search(
        r"\b(host housing|temporary accommodation|temporary living)\b", label, re.I
    ):
        scores["host_transportation"] = scores.get("host_transportation", 0.0) + 10.0
        scores["host_housing"] = max(0.0, scores.get("host_housing", 0.0) - 14.0)
        scores["temporary_living_outbound"] = max(0.0, scores.get("temporary_living_outbound", 0.0) - 8.0)

    if trans_words and not housing_words:
        scores["host_housing"] = max(0.0, scores.get("host_housing", 0.0) - 6.0)

    housing_section = bool(re.search(r"\bhousing\b", section, re.I)) and not re.search(
        r"\btransport\b", section, re.I
    )
    if housing_section and trans_label:
        scores["host_transportation"] = scores.get("host_transportation", 0.0) + 8.0
        scores["host_housing"] = max(0.0, scores.get("host_housing", 0.0) - 10.0)


def _disambiguate_compensation_vs_housing(
    scores: Dict[str, float],
    *,
    label: str,
    section: str,
    combined: str,
) -> None:
    comp_heading = bool(
        re.search(r"\b(compensation|payroll|remuneration|salary package)\b", label, re.I)
    ) or bool(re.search(r"compensation\s+and\s+payroll", section, re.I))
    explicit_housing = bool(
        re.search(
            r"\b(host housing|temporary living|temporary accommodation|company housing)\b",
            combined,
            re.I,
        )
    )
    if comp_heading and not explicit_housing:
        scores["host_housing"] = max(0.0, scores.get("host_housing", 0.0) - 16.0)
        scores["temporary_living_outbound"] = max(0.0, scores.get("temporary_living_outbound", 0.0) - 10.0)
        scores["policy_definitions_and_exceptions"] = scores.get(
            "policy_definitions_and_exceptions", 0.0
        ) + 5.0


def _disambiguate_spouse_vs_housing(scores: Dict[str, float], combined: str) -> None:
    spouse_signal = bool(
        re.search(
            r"\b(spouse support|partner career|dual career|trailing spouse|spousal allowance|partner support)\b",
            combined,
            re.I,
        )
    )
    housing_signal = bool(
        re.search(r"\b(host housing|housing allowance|accommodation|rent|lease)\b", combined, re.I)
    )
    if spouse_signal and not housing_signal:
        scores["spouse_support"] = scores.get("spouse_support", 0.0) + 8.0
        scores["host_housing"] = max(0.0, scores.get("host_housing", 0.0) - 12.0)


def _cross_penalties_host_temp(scores: Dict[str, float], combined: str) -> None:
    """Strong temporary-accommodation language suppresses host housing and vice versa."""
    if re.search(r"\b(temporary living|temporary accommodation|interim housing|hotel)\b", combined):
        scores["host_housing"] = max(0.0, scores.get("host_housing", 0.0) - 5.0)
    if re.search(r"\b(host housing|host-provided housing|company housing)\b", combined):
        scores["temporary_living_outbound"] = max(0.0, scores.get("temporary_living_outbound", 0.0) - 5.0)


def resolve_primary_canonical_lta_key(
    component_label: Optional[str],
    summary_text: str,
    section_context: Optional[str],
) -> Optional[str]:
    """
    Pick at most one canonical LTA template key, or None if weak/ambiguous.
    """
    label = (component_label or "").strip().lower()
    summary = (summary_text or "").strip().lower()
    section = (section_context or "").strip().lower()
    combined = " ".join(x for x in (label, summary, section) if x)

    scores: Dict[str, float] = {}
    _apply_phrase_scores(scores, label=label, summary=summary, section=section, combined=combined)

    _cross_penalties_host_temp(scores, combined)
    _disambiguate_temp_living(scores, combined)
    _disambiguate_tax_vs_allowance(scores, combined)
    _disambiguate_education_vs_language(scores, combined)
    _disambiguate_housing_vs_transport(
        scores, label=label, section=section, combined=combined
    )
    _disambiguate_compensation_vs_housing(
        scores, label=label, section=section, combined=combined
    )
    _disambiguate_spouse_vs_housing(scores, combined)

    if not scores:
        return None
    best_key, best_val = max(scores.items(), key=lambda kv: kv[1])
    if best_val < MIN_WINNING_SCORE:
        return None
    sorted_vals = sorted(scores.values(), reverse=True)
    second = sorted_vals[1] if len(sorted_vals) > 1 else 0.0
    if best_val - second < WIN_MARGIN:
        return None
    return best_key


def score_canonical_lta_keys_for_debug(
    component_label: Optional[str],
    summary_text: str,
    section_context: Optional[str],
) -> Dict[str, float]:
    """Non-exported helper for tests: scores after disambiguation."""
    label = (component_label or "").strip().lower()
    summary = (summary_text or "").strip().lower()
    section = (section_context or "").strip().lower()
    combined = " ".join(x for x in (label, summary, section) if x)
    scores: Dict[str, float] = {}
    _apply_phrase_scores(scores, label=label, summary=summary, section=section, combined=combined)
    _cross_penalties_host_temp(scores, combined)
    _disambiguate_temp_living(scores, combined)
    _disambiguate_tax_vs_allowance(scores, combined)
    _disambiguate_education_vs_language(scores, combined)
    _disambiguate_housing_vs_transport(
        scores, label=label, section=section, combined=combined
    )
    _disambiguate_compensation_vs_housing(
        scores, label=label, section=section, combined=combined
    )
    _disambiguate_spouse_vs_housing(scores, combined)
    return dict(sorted(scores.items(), key=lambda kv: -kv[1]))


