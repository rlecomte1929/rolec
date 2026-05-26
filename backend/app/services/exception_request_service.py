"""
exception_request_service.py — Deterministic exception flag detector.

Given a relocation profile and an ImmigrationRegimeResult, evaluates whether
the case has conditions that require explicit HR sign-off (an ExceptionRequest).

Pure Python. No DB interaction — detection only. Persistence is handled
separately (future route wiring, same pattern as S5).

Touch policy: NEW FILE. Does not modify any existing module.

Usage:
    from backend.app.services.exception_request_service import ExceptionRequestService
    from backend.app.services.immigration_regime import ImmigrationRegimeRouter

    router = ImmigrationRegimeRouter()
    regime = router.detect_regime(
        nationality="German",
        destination_country="United States",
        contract_type="lta",
    )

    svc = ExceptionRequestService()
    flags = svc.evaluate_case(
        profile={
            "employment_tenure_months": 8,    # < 12 → tenure_insufficient
            "weeks_to_move_date": 10,          # < 16 → timeline_breach
        },
        regime=regime,
    )
    # → [ExceptionFlag(type="tenure_insufficient", severity="blocker", ...),
    #    ExceptionFlag(type="timeline_breach", severity="warning", ...)]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .immigration_regime import ImmigrationRegimeResult


# ─── Output model ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ExceptionFlag:
    """
    A single condition that requires HR review / exception approval.

    severity:
      "blocker" — case cannot proceed without approval (e.g. no US sponsor entity)
      "warning" — case can proceed but HR should be aware (e.g. tight timeline)

    exception_type maps to the CHECK constraint values in exception_requests table:
      tenure_insufficient | no_sponsoring_entity | timeline_breach |
      cost_threshold | role_category_ambiguous | dual_intent_conflict | policy_custom
    """
    exception_type: str
    reason: str
    severity: str = "warning"              # warning | blocker
    recommended_action: str = ""


# ─── Rule constants ───────────────────────────────────────────────────────────

# L1B requires 1 continuous year of employment with the company within
# the last 3 years. Below this threshold, the petition is highly likely to
# be denied without extensive additional evidence.
_L1B_MIN_TENURE_MONTHS = 12

# Minimum weeks before a move date that allows standard USCIS processing.
# Below this, premium processing (I-907, ~$2,805) becomes mandatory.
_L1B_TIMELINE_STANDARD_WEEKS = 24    # 6 months
_L1B_TIMELINE_PREMIUM_WEEKS = 10     # 2.5 months — minimum even with premium

# Japan COE minimum lead time (1 month minimum, 3 months typical).
_JAPAN_COE_MIN_LEAD_WEEKS = 16       # 4 months = COE + visa + buffer

# Generic minimum for any standard work permit.
_STANDARD_PERMIT_MIN_WEEKS = 8

# UK Skilled Worker visa: UKVI target processing time is 3 weeks, but CoS
# request + document gathering + appointment wait pushes the practical minimum
# to 8 weeks from case open.
_UK_SKILLED_WORKER_MIN_WEEKS = 8

# Cost threshold: if estimated package cost exceeds this (USD equivalent),
# flag for HR approval regardless of visa route.
_COST_THRESHOLD_USD = 150_000


# ─── Core service ─────────────────────────────────────────────────────────────

class ExceptionRequestService:
    """
    Evaluates a relocation profile against known exception trigger rules
    for the detected immigration regime.

    All checks are deterministic — no LLM, no DB. Callers decide whether
    to persist the resulting flags as exception_request rows.
    """

    def evaluate_case(
        self,
        profile: Dict[str, Any],
        regime: ImmigrationRegimeResult,
    ) -> List[ExceptionFlag]:
        """
        Evaluate the profile against the regime's exception triggers.

        profile keys (all optional, safe to pass incomplete):
            employment_tenure_months (int | float)
              — months the employee has worked for the company
            weeks_to_move_date (int | float)
              — weeks until target move date (None = unknown)
            us_entity_confirmed (bool)
              — True if a US legal entity is confirmed as petitioner
            specialized_knowledge_documented (bool)
              — True if specialised knowledge evidence is ready
            japan_visa_category (str)
              — e.g. "eshs", "ict", "specified_skilled" — None = ambiguous
            estimated_package_cost_usd (int | float)
              — total estimated relocation package cost
            uk_sponsor_licence_confirmed (bool)
              — True if employer holds an active UK Sponsor Licence
            uk_points_threshold_confirmed (bool)
              — True if employee's 70-point eligibility has been verified

        Returns an empty list if no exceptions detected.
        """
        flags: List[ExceptionFlag] = []

        if regime.regime_id == "us_l1b":
            flags.extend(self._check_l1b(profile))
        elif regime.regime_id == "japan_coe":
            flags.extend(self._check_japan_coe(profile))
        elif regime.regime_id == "uk_skilled_worker":
            flags.extend(self._check_uk_skilled_worker(profile))
        elif regime.regime_id == "standard_work_permit":
            flags.extend(self._check_timeline(
                profile, min_weeks=_STANDARD_PERMIT_MIN_WEEKS,
                regime_label="Standard Work Permit"
            ))

        # Cost threshold applies to all regimes
        flags.extend(self._check_cost_threshold(profile))

        return flags

    # ── L1B checks ────────────────────────────────────────────────────────────

    def _check_l1b(self, profile: Dict[str, Any]) -> List[ExceptionFlag]:
        flags: List[ExceptionFlag] = []

        # 1. Tenure check
        tenure = self._to_float(profile.get("employment_tenure_months"))
        if tenure is not None and tenure < _L1B_MIN_TENURE_MONTHS:
            flags.append(ExceptionFlag(
                exception_type="tenure_insufficient",
                severity="blocker",
                reason=(
                    f"L1B requires at least {_L1B_MIN_TENURE_MONTHS} months of continuous "
                    f"employment with the company within the last 3 years. "
                    f"Employee has {tenure:.0f} month(s). "
                    f"Petition is very likely to be denied without an exception review."
                ),
                recommended_action=(
                    "Delay move date until 12-month threshold is met, OR consult "
                    "immigration counsel about whether prior subsidiary / affiliate "
                    "service can be counted toward the qualifying period."
                ),
            ))

        # 2. US sponsoring entity
        us_entity = profile.get("us_entity_confirmed")
        if us_entity is False or (us_entity is None and profile.get("us_entity_name") is None):
            flags.append(ExceptionFlag(
                exception_type="no_sponsoring_entity",
                severity="blocker",
                reason=(
                    "L1B requires a US legal entity to act as petitioner (employer of record "
                    "in the US). No confirmed US entity has been recorded for this case."
                ),
                recommended_action=(
                    "Confirm the US petitioner entity name, EIN, and authorised signatory "
                    "before proceeding. Without this, no USCIS filing is possible."
                ),
            ))

        # 3. Timeline check
        weeks = self._to_float(profile.get("weeks_to_move_date"))
        if weeks is not None:
            if weeks < _L1B_TIMELINE_PREMIUM_WEEKS:
                flags.append(ExceptionFlag(
                    exception_type="timeline_breach",
                    severity="blocker",
                    reason=(
                        f"Move date is {weeks:.0f} week(s) away. Even with USCIS premium "
                        f"processing (~15 business days + consulate appointment wait), "
                        f"{_L1B_TIMELINE_PREMIUM_WEEKS} weeks is the absolute minimum. "
                        f"The current timeline is not achievable."
                    ),
                    recommended_action=(
                        "Push the move date by at least "
                        f"{int(_L1B_TIMELINE_PREMIUM_WEEKS - weeks + 1)} week(s), OR discuss "
                        "bridge arrangements (e.g. business visitor entry while petition clears)."
                    ),
                ))
            elif weeks < _L1B_TIMELINE_STANDARD_WEEKS:
                flags.append(ExceptionFlag(
                    exception_type="timeline_breach",
                    severity="warning",
                    reason=(
                        f"Move date is {weeks:.0f} week(s) away. Standard USCIS processing "
                        f"takes {_L1B_TIMELINE_STANDARD_WEEKS} weeks. Premium processing "
                        f"(~$2,805 surcharge) will be required to meet this timeline."
                    ),
                    recommended_action=(
                        "File Form I-907 (premium processing) with the I-129 petition. "
                        "Confirm budget approval for the premium processing fee."
                    ),
                ))

        # 4. Specialised knowledge documentation
        sk_documented = profile.get("specialized_knowledge_documented")
        if sk_documented is False:
            flags.append(ExceptionFlag(
                exception_type="role_category_ambiguous",
                severity="warning",
                reason=(
                    "Specialised knowledge evidence has not been documented for this case. "
                    "USCIS scrutinises L1B petitions heavily on this point — undocumented "
                    "cases have a high RFE (Request for Evidence) rate."
                ),
                recommended_action=(
                    "Work with the employee and their manager to compile: patents, "
                    "proprietary process documentation, certifications, evidence of "
                    "unique internal training, or systems knowledge that is not "
                    "readily available in the US labour market."
                ),
            ))

        return flags

    # ── Japan COE checks ──────────────────────────────────────────────────────

    def _check_japan_coe(self, profile: Dict[str, Any]) -> List[ExceptionFlag]:
        flags: List[ExceptionFlag] = []

        # 1. Timeline
        flags.extend(self._check_timeline(
            profile, min_weeks=_JAPAN_COE_MIN_LEAD_WEEKS, regime_label="Japan COE"
        ))

        # 2. Visa category ambiguity
        category = (profile.get("japan_visa_category") or "").strip().lower()
        if not category:
            flags.append(ExceptionFlag(
                exception_type="role_category_ambiguous",
                severity="warning",
                reason=(
                    "Japan visa sub-category has not been confirmed for this case. "
                    "The most common categories are ESHS (Engineer / Specialist in "
                    "Humanities / International Services) and ICT (Intra-company "
                    "Transferee). Choosing incorrectly delays the COE application."
                ),
                recommended_action=(
                    "Japan HR or immigration counsel should confirm the correct "
                    "activity category based on the employee's actual job duties. "
                    "For corporate roles: ESHS covers most engineering, IT, finance, "
                    "and management functions. ICT requires 1+ year at the company."
                ),
            ))

        return flags

    # ── UK Skilled Worker checks ──────────────────────────────────────────────

    def _check_uk_skilled_worker(self, profile: Dict[str, Any]) -> List[ExceptionFlag]:
        """
        Exception checks specific to the UK Skilled Worker visa route.

        Checks:
          1. Sponsor licence — employer must hold an active Sponsor Licence;
             without it, no Certificate of Sponsorship (CoS) can be issued.
          2. Timeline breach — UKVI standard processing 3 weeks, but CoS
             request + document prep + appointment wait means 8 weeks minimum.
          3. Points threshold — employee must score ≥ 70 points under the
             points-based system; HR should confirm before CoS is assigned.
        """
        flags: List[ExceptionFlag] = []

        # 1. Sponsor licence
        sponsor_licence = profile.get("uk_sponsor_licence_confirmed")
        if sponsor_licence is False or sponsor_licence is None:
            flags.append(ExceptionFlag(
                exception_type="no_sponsoring_entity",
                severity="blocker",
                reason=(
                    "UK Skilled Worker visa requires the employer to hold an active "
                    "Sponsor Licence issued by the Home Office. No confirmed sponsor "
                    "licence has been recorded for this case. Without a valid licence, "
                    "no Certificate of Sponsorship (CoS) can be assigned and the visa "
                    "application cannot proceed."
                ),
                recommended_action=(
                    "Confirm whether the employing entity already holds a Sponsor Licence "
                    "(check UKVI's register of licensed sponsors). If not, apply for one "
                    "immediately — new licence applications typically take 8 weeks. "
                    "Consider interim remote-work arrangements while the licence is pending."
                ),
            ))

        # 2. Timeline check
        flags.extend(self._check_timeline(
            profile,
            min_weeks=_UK_SKILLED_WORKER_MIN_WEEKS,
            regime_label="UK Skilled Worker",
        ))

        # 3. Points threshold
        points_confirmed = profile.get("uk_points_threshold_confirmed")
        if points_confirmed is False or points_confirmed is None:
            flags.append(ExceptionFlag(
                exception_type="points_threshold_unconfirmed",
                severity="warning",
                reason=(
                    "UK Skilled Worker visa requires the employee to score at least "
                    "70 points under the points-based system. Key mandatory points: "
                    "job offer from a licensed sponsor (20 pts), role at required skill "
                    "level (20 pts), English language (10 pts). Salary must meet the "
                    "higher of the general threshold or the going rate for the SOC code. "
                    "Points eligibility has not been confirmed for this case."
                ),
                recommended_action=(
                    "HR or immigration counsel should complete a points-eligibility "
                    "assessment, verifying: the SOC code for the role, the salary "
                    "against the going rate, and the employee's English language "
                    "qualification. Resolve any gaps before assigning the CoS."
                ),
            ))

        return flags

    # ── Shared checks ─────────────────────────────────────────────────────────

    def _check_timeline(
        self,
        profile: Dict[str, Any],
        min_weeks: int,
        regime_label: str,
    ) -> List[ExceptionFlag]:
        flags: List[ExceptionFlag] = []
        weeks = self._to_float(profile.get("weeks_to_move_date"))
        if weeks is not None and weeks < min_weeks:
            flags.append(ExceptionFlag(
                exception_type="timeline_breach",
                severity="blocker" if weeks < min_weeks / 2 else "warning",
                reason=(
                    f"Move date is {weeks:.0f} week(s) away. "
                    f"{regime_label} requires at least {min_weeks} weeks of lead time. "
                    f"Current timeline is {int(min_weeks - weeks)} week(s) short."
                ),
                recommended_action=(
                    f"Push the move date by at least {int(min_weeks - weeks)} week(s), "
                    "OR discuss interim arrangements with HR."
                ),
            ))
        return flags

    def _check_cost_threshold(self, profile: Dict[str, Any]) -> List[ExceptionFlag]:
        cost = self._to_float(profile.get("estimated_package_cost_usd"))
        if cost is not None and cost > _COST_THRESHOLD_USD:
            return [ExceptionFlag(
                exception_type="cost_threshold",
                severity="warning",
                reason=(
                    f"Estimated relocation package cost (${cost:,.0f}) exceeds the "
                    f"policy threshold (${_COST_THRESHOLD_USD:,}). "
                    f"Finance and HR sign-off is required before committing."
                ),
                recommended_action=(
                    "Submit a cost exception request to HR leadership with a full "
                    "package breakdown and business justification."
                ),
            )]
        return []

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
