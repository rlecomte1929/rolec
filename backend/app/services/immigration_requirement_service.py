"""
IMM-02 · Immigration Requirement Service

Given a corridor (from_country, to_country) and a visa type, returns:
  - The ordered document checklist for that corridor × visa_type
  - Risk flags derived from the employee's profile
  - An estimated total timeline in days

Entry points:
  get_requirements(corridor_from, corridor_to, visa_type, employee_type)
  evaluate_condition(condition_expression, employee_profile_dict)
  evaluate_risks(employee_profile, requirements, move_date)
  get_timeline_days(requirements)
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ...database import db
from .requirements_country_key import normalize_corridor_code

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RequirementResult:
    document_type: str
    document_name: str
    is_required: bool
    is_conditional: bool
    freshness_days: Optional[int]
    requires_apostille: bool
    apostille_countries: List[str]
    requires_translation: bool
    translation_languages: List[str]
    can_be_prefilled: bool
    can_be_ocr_extracted: bool
    typical_processing_days: Optional[int]
    book_early_flag: bool
    book_early_reason: Optional[str]
    success_tips: List[str]
    common_rejection_reasons: List[str]
    form_url: Optional[str]
    form_version: Optional[str]


@dataclass
class RiskFlag:
    flag_type: str
    severity: str          # critical | warning | info
    title: str
    description: str
    recommended_action: str
    deadline: Optional[date] = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_requirements(
    corridor_from: str,
    corridor_to: str,
    visa_type: str,
    employee_type: str = "any",
    employee_profile: Optional[Dict[str, Any]] = None,
) -> List[RequirementResult]:
    """
    Query immigration_requirements for the given corridor × visa_type.
    Evaluates conditional requirements against employee_profile when provided.
    Returns results ordered: required first, then optional, alphabetically within groups.
    """
    rows = _fetch_requirements(corridor_from, corridor_to, visa_type, employee_type)
    results = []
    for row in rows:
        # Evaluate conditional requirements
        if row.get("is_conditional") and row.get("condition_expression") and employee_profile:
            if not evaluate_condition(row["condition_expression"], employee_profile):
                continue  # Skip — condition not met for this employee

        results.append(RequirementResult(
            document_type=row["document_type"],
            document_name=row["document_name"],
            is_required=row.get("is_required", True),
            is_conditional=row.get("is_conditional", False),
            freshness_days=row.get("freshness_days"),
            requires_apostille=row.get("requires_apostille", False),
            apostille_countries=row.get("apostille_countries") or [],
            requires_translation=row.get("requires_translation", False),
            translation_languages=row.get("translation_languages") or [],
            can_be_prefilled=row.get("can_be_prefilled", False),
            can_be_ocr_extracted=row.get("can_be_ocr_extracted", False),
            typical_processing_days=row.get("typical_processing_days"),
            book_early_flag=row.get("book_early_flag", False),
            book_early_reason=row.get("book_early_reason"),
            success_tips=row.get("success_tips") or [],
            common_rejection_reasons=row.get("common_rejection_reasons") or [],
            form_url=row.get("form_url"),
            form_version=row.get("form_version"),
        ))

    # Sort: required first, then by document_name
    results.sort(key=lambda r: (0 if r.is_required else 1, r.document_name))
    return results


def evaluate_condition(condition_expression: str, profile: Dict[str, Any]) -> bool:
    """
    Evaluate a simple condition expression against an employee profile dict.
    Supported forms:
      "has_dependents = true"
      "has_dependents = false"
      "marital_status = married"
      "nationality != DE"
      "degree_anabin_status = not-recognised"
    """
    try:
        parts = condition_expression.strip().split()
        if len(parts) != 3:
            return True  # Unknown format → include by default
        field_name, operator, expected = parts
        actual = profile.get(field_name)
        if actual is None:
            return False

        # Normalise booleans
        if isinstance(actual, bool):
            actual_str = "true" if actual else "false"
        else:
            actual_str = str(actual).lower().strip()
        expected_str = expected.lower().strip()

        if operator == "=":
            return actual_str == expected_str
        elif operator == "!=":
            return actual_str != expected_str
        else:
            return True
    except Exception as exc:
        log.warning("evaluate_condition error for '%s': %s", condition_expression, exc)
        return True  # Default to include


def evaluate_risks(
    employee_profile: Dict[str, Any],
    requirements: List[RequirementResult],
    move_date: Optional[date] = None,
    visa_end_date: Optional[date] = None,
) -> List[RiskFlag]:
    """
    Evaluate the employee profile and requirements for risk conditions.
    Returns flags sorted by severity: critical first, then warning, then info.
    """
    flags: List[RiskFlag] = []
    today = date.today()

    # ── 1. Passport near expiry ──────────────────────────────────────────────
    passport_expiry = _parse_date(employee_profile.get("passport_expiry"))
    if passport_expiry:
        # Rule: must have 6+ months validity beyond visa end date
        reference_date = visa_end_date or move_date or (today + timedelta(days=180))
        required_valid_until = reference_date + timedelta(days=180)

        if passport_expiry < today + timedelta(days=90):
            flags.append(RiskFlag(
                flag_type="PASSPORT_EXPIRY_WITHIN_90_DAYS",
                severity="critical",
                title="Passport expires within 90 days",
                description=(
                    f"Your passport expires on {passport_expiry.isoformat()}. "
                    "Most countries require a minimum of 6 months validity beyond "
                    "the visa end date. You need to renew your passport immediately."
                ),
                recommended_action=(
                    "Apply for passport renewal urgently. Passport renewal typically "
                    "takes 3–6 weeks in standard service. "
                    "Do not submit any visa application until your new passport is in hand."
                ),
                deadline=passport_expiry,
            ))
        elif passport_expiry < required_valid_until:
            flags.append(RiskFlag(
                flag_type="PASSPORT_NEAR_EXPIRY",
                severity="critical",
                title="Passport will not have 6 months validity beyond visa end date",
                description=(
                    f"Your passport expires on {passport_expiry.isoformat()}, but "
                    f"it must be valid until at least {required_valid_until.isoformat()} "
                    "(6 months beyond the planned visa end date). "
                    "Your visa application will be rejected without this."
                ),
                recommended_action="Renew your passport before submitting the visa application.",
                deadline=passport_expiry,
            ))

    # ── 2. Address history gaps ──────────────────────────────────────────────
    address_history = employee_profile.get("address_history") or []
    if address_history:
        gap = _detect_address_gap(address_history, today)
        if gap:
            flags.append(RiskFlag(
                flag_type="ADDRESS_HISTORY_GAP",
                severity="warning",
                title="Gap detected in your 5-year address history",
                description=(
                    f"There is a gap of {gap['days']} days between "
                    f"{gap['from']} and {gap['to']} in your address history. "
                    "Many visa applications (especially Germany, UK, USA) require "
                    "a complete, gapless 5-year address history. Unexplained gaps "
                    "cause delays and requests for additional documentation."
                ),
                recommended_action=(
                    "Add the address where you lived during this period — even "
                    "temporary accommodation (hotels, family address) counts."
                ),
            ))

    # ── 3. Prior visa refusals ───────────────────────────────────────────────
    if employee_profile.get("prior_visa_refusals"):
        flags.append(RiskFlag(
            flag_type="PRIOR_VISA_REFUSAL",
            severity="warning",
            title="Prior visa refusal on record",
            description=(
                "You have indicated a prior visa refusal. Most visa applications "
                "ask you to disclose this. Concealing a prior refusal is grounds "
                "for automatic rejection and potentially permanent ban."
            ),
            recommended_action=(
                "Disclose the prior refusal on the application form. "
                "Prepare a cover letter explaining the circumstances and what has "
                "changed since the refusal. Consider using an immigration lawyer "
                "for this application."
            ),
        ))

    # ── 4. Blue Card degree not recognised ──────────────────────────────────
    anabin_status = employee_profile.get("degree_anabin_status", "")
    if anabin_status == "not-recognised":
        flags.append(RiskFlag(
            flag_type="DEGREE_NOT_RECOGNISED",
            severity="critical",
            title="University degree not recognised in Germany",
            description=(
                "The EU Blue Card requires a university degree recognised by "
                "the German authorities (anabin database). Your degree is currently "
                "flagged as 'not recognised'. Without recognition, the Blue Card "
                "application will be rejected."
            ),
            recommended_action=(
                "Apply to the Central Office for Foreign Education (KMK/ZAB) for "
                "a Statement of Comparability (Vergleichbarkeit). Processing takes "
                "4–8 weeks. Alternatively, apply for the Skilled Worker visa "
                "under §18a AufenthG which has different recognition criteria."
            ),
        ))

    # ── 5. Medical exam needed with insufficient time ────────────────────────
    has_medical_req = any(r.document_type == "medical_exam" for r in requirements)
    if has_medical_req and move_date:
        medical_req = next((r for r in requirements if r.document_type == "medical_exam"), None)
        processing_days = (medical_req.typical_processing_days or 30) if medical_req else 30
        if (move_date - today).days < processing_days + 14:
            flags.append(RiskFlag(
                flag_type="MEDICAL_EXAM_URGENCY",
                severity="critical",
                title="Medical examination must be booked immediately",
                description=(
                    f"Your destination country requires a medical examination, "
                    f"which typically takes {processing_days}+ days to complete and report. "
                    f"With your move date of {move_date.isoformat()}, you must book "
                    f"the medical appointment within the next few days."
                ),
                recommended_action=(
                    "Book your medical appointment today. Use a panel physician "
                    "approved by your destination country's consulate."
                ),
                deadline=today + timedelta(days=3),
            ))

    # ── 6. Book-early items with insufficient lead time ──────────────────────
    for req in requirements:
        if req.book_early_flag and req.typical_processing_days and move_date:
            days_needed = req.typical_processing_days + 14  # 2-week buffer
            if (move_date - today).days < days_needed:
                flags.append(RiskFlag(
                    flag_type=f"BOOK_EARLY_{req.document_type.upper()}",
                    severity="critical" if (move_date - today).days < req.typical_processing_days else "warning",
                    title=f"{req.document_name} — start immediately",
                    description=(
                        f"{req.book_early_reason or req.document_name} typically takes "
                        f"{req.typical_processing_days} days. "
                        f"With your move date of {move_date.isoformat()}, "
                        f"you have insufficient lead time."
                    ),
                    recommended_action=f"Start the {req.document_name} process today without delay.",
                    deadline=today + timedelta(days=2),
                ))

    # ── 7. Dependents: no dependent application started ──────────────────────
    dependents = employee_profile.get("dependents") or []
    if dependents and move_date:
        days_to_move = (move_date - today).days
        if days_to_move < 60:
            flags.append(RiskFlag(
                flag_type="DEPENDENT_TIMING_RISK",
                severity="warning",
                title="Dependent visa applications should be started in parallel",
                description=(
                    f"You have {len(dependents)} dependent(s) listed. "
                    "Dependent visa applications must be submitted separately but "
                    "should be initiated at the same time as the primary application "
                    "to avoid delays in family reunification."
                ),
                recommended_action=(
                    "Begin dependent visa documentation in parallel. "
                    "Each dependent needs: birth certificate (apostilled), "
                    "photos, and reference to the primary applicant's visa."
                ),
            ))

    # Sort: critical first, then warning, then info
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    flags.sort(key=lambda f: severity_order.get(f.severity, 3))
    return flags


def get_timeline_days(requirements: List[RequirementResult]) -> int:
    """
    Estimate total processing time in days as the longest individual item
    (since most documents can be gathered in parallel).
    Adds a 14-day buffer for logistics.
    """
    if not requirements:
        return 30
    max_days = max(
        (r.typical_processing_days or 0) for r in requirements
    )
    return max_days + 14


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_requirements(
    corridor_from: str,
    corridor_to: str,
    visa_type: str,
    employee_type: str,
) -> List[Dict[str, Any]]:
    """Fetch raw rows from immigration_requirements for this corridor × visa_type."""
    with db.engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT
                    document_type, document_name, is_required, is_conditional,
                    condition_expression, freshness_days, requires_apostille,
                    apostille_countries, requires_translation, translation_languages,
                    can_be_prefilled, can_be_ocr_extracted, typical_processing_days,
                    book_early_flag, book_early_reason, success_tips,
                    common_rejection_reasons, form_url, form_version
                FROM public.immigration_requirements
                WHERE corridor_from = :corridor_from
                  AND corridor_to   = :corridor_to
                  AND visa_type     = :visa_type
                  AND employee_type IN (:employee_type, 'any')
                ORDER BY is_required DESC, document_name ASC
            """),
            {
                "corridor_from": normalize_corridor_code(corridor_from),
                "corridor_to": normalize_corridor_code(corridor_to),
                "visa_type": visa_type.lower(),
                "employee_type": employee_type,
            },
        ).mappings().all()
    return [dict(r) for r in rows]


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _detect_address_gap(
    address_history: List[Dict[str, Any]],
    today: date,
    lookback_years: int = 5,
) -> Optional[Dict[str, Any]]:
    """
    Detect the first gap > 7 days in the address history over the last
    lookback_years years. Returns {days, from, to} or None.
    """
    cutoff = today - timedelta(days=lookback_years * 365)

    # Parse and sort entries
    entries = []
    for entry in address_history:
        from_d = _parse_date(entry.get("from_date"))
        to_d = _parse_date(entry.get("to_date")) or today
        if from_d and from_d >= cutoff:
            entries.append((from_d, to_d))

    if not entries:
        return None

    entries.sort(key=lambda e: e[0])

    # Check for gaps between sorted entries
    for i in range(1, len(entries)):
        prev_end = entries[i - 1][1]
        curr_start = entries[i][0]
        gap_days = (curr_start - prev_end).days
        if gap_days > 7:
            return {
                "days": gap_days,
                "from": prev_end.isoformat(),
                "to": curr_start.isoformat(),
            }

    # Check gap between earliest entry and lookback cutoff
    if entries[0][0] > cutoff + timedelta(days=7):
        gap_days = (entries[0][0] - cutoff).days
        return {
            "days": gap_days,
            "from": cutoff.isoformat(),
            "to": entries[0][0].isoformat(),
        }

    return None
