"""
immigration_regime.py — Deterministic immigration regime router.

Given (nationality, destination_country, origin_country, contract_type),
returns the applicable immigration regime and the task codes that must be
injected into the relocation plan.

All decisions are lookup-table / decision-tree — no LLM. Immigration rules
for a given route are deterministic; this module is the policy expert for
route-specific visa pathways.

Touch policy: NEW FILE. Does not modify any existing module.

Usage:
    from backend.app.services.immigration_regime import ImmigrationRegimeRouter

    router = ImmigrationRegimeRouter()
    result = router.detect_regime(
        nationality="German",
        destination_country="United States",
        origin_country="Germany",
        contract_type="lta",
    )
    # result.regime_id == "us_l1b"
    # result.task_codes == ["l1b_support_letter", "l1b_petition_preparation", ...]
    # result.exception_triggers == ["tenure_insufficient", "no_sponsoring_entity", ...]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple


# ─── Country / nationality sets ───────────────────────────────────────────────

_EU_EEA_COUNTRIES: FrozenSet[str] = frozenset({
    "austria", "at", "belgium", "be", "bulgaria", "bg", "croatia", "hr",
    "cyprus", "cy", "czechia", "czech republic", "cz", "denmark", "dk",
    "estonia", "ee", "finland", "fi", "france", "fr", "germany", "de",
    "greece", "gr", "hungary", "hu", "ireland", "ie", "italy", "it",
    "latvia", "lv", "lithuania", "lt", "luxembourg", "lu", "malta", "mt",
    "netherlands", "nl", "poland", "pl", "portugal", "pt", "romania", "ro",
    "slovakia", "sk", "slovenia", "si", "spain", "es", "sweden", "se",
    # EEA
    "iceland", "is", "liechtenstein", "li", "norway", "no",
    # Switzerland
    "switzerland", "ch",
})

_US_DESTINATIONS: FrozenSet[str] = frozenset({
    "united states", "united states of america", "usa", "us",
})

_JAPAN_DESTINATIONS: FrozenSet[str] = frozenset({
    "japan", "jp",
})

_UK_DESTINATIONS: FrozenSet[str] = frozenset({
    "united kingdom", "uk", "great britain", "gb", "england", "scotland",
    "wales", "northern ireland",
})

# Contract types that represent ongoing work assignments (as opposed to
# short visits) — relevant for regime determination.
_LONG_TERM_CONTRACT_TYPES: FrozenSet[str] = frozenset({
    "lta", "permanent_transfer", "remote_worker",
})

_SHORT_TERM_CONTRACT_TYPES: FrozenSet[str] = frozenset({
    "short_term_project", "student", "self_employed",
})


def _n(s: Optional[str]) -> str:
    """Normalise: strip + lowercase."""
    return (s or "").strip().lower()


def _is_eu_national(nationality: Optional[str]) -> bool:
    return _n(nationality) in _EU_EEA_COUNTRIES


def _is_eu_destination(destination: Optional[str]) -> bool:
    return _n(destination) in _EU_EEA_COUNTRIES


def _is_us_destination(destination: Optional[str]) -> bool:
    return _n(destination) in _US_DESTINATIONS


def _is_japan_destination(destination: Optional[str]) -> bool:
    return _n(destination) in _JAPAN_DESTINATIONS


def _is_uk_destination(destination: Optional[str]) -> bool:
    return _n(destination) in _UK_DESTINATIONS


# ─── Output model ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ImmigrationRegimeResult:
    """
    The detected immigration regime for a given employee route.

    regime_id maps to a well-known pathway:
      "us_l1b"              — US intracompany transfer, L1B specialised knowledge
      "us_h1b"              — US employer-sponsored specialty occupation (future)
      "japan_coe"           — Japan Certificate of Eligibility route
      "uk_skilled_worker"   — UK Skilled Worker visa (post-Brexit) (future)
      "eu_free_movement"    — EU/EEA national → EU/EEA destination (registration only)
      "standard_work_permit"— Generic work permit (catches all non-specific routes)
      "domestic"            — Same-country move, no immigration required
      "unknown"             — Cannot determine regime from available data
    """
    regime_id: str
    task_codes: Tuple[str, ...] = ()
    priority: str = "standard"                   # standard | critical
    typical_lead_time_weeks: int = 0
    exception_triggers: Tuple[str, ...] = ()     # ExceptionFlag types to evaluate
    notes: str = ""
    requires_employer_petition: bool = False     # True when employer must file on employee's behalf


# ─── Task-code sequences per regime ──────────────────────────────────────────
# Ordered: pre_departure first, then immigration, arrival, post_arrival.
# These map 1:1 to task_codes in relocation_plan_task_library.py.

_REGIME_TASK_CODES: Dict[str, Tuple[str, ...]] = {
    "us_l1b": (
        "l1b_support_letter",
        "l1b_petition_preparation",
        "l1b_petition_filing",
        "l1b_visa_interview",
        "l1b_port_of_entry",
        "l1b_ssn_application",
    ),
    "japan_coe": (
        "japan_coe_preparation",
        "japan_coe_visa_application",
        "japan_residence_card",
        "japan_municipal_registration",
    ),
    "eu_free_movement": (
        "eu_registration",
    ),
    # uk_skilled_worker — P5 sprint
    "uk_skilled_worker": (
        "uk_cos_request",
        "uk_visa_application",
        "uk_biometric_appointment",
        "uk_brp_collection",
        "uk_right_to_work_check",
    ),
    "standard_work_permit": (),
    "domestic": (),
    "unknown": (),
}

_REGIME_EXCEPTION_TRIGGERS: Dict[str, Tuple[str, ...]] = {
    "us_l1b": (
        "tenure_insufficient",       # < 1 year with company
        "no_sponsoring_entity",      # no US legal entity confirmed
        "timeline_breach",           # move date < 16 weeks out
        "role_category_ambiguous",   # specialised knowledge not documented
    ),
    "japan_coe": (
        "timeline_breach",           # COE takes 1–3 months; total ~4 months
        "role_category_ambiguous",   # visa sub-category (ESHS vs ICT) unclear
    ),
    "eu_free_movement": (),
    "uk_skilled_worker": (
        "timeline_breach",
        "no_sponsoring_entity",
    ),
    "standard_work_permit": (
        "timeline_breach",
    ),
    "domestic": (),
    "unknown": (),
}

_REGIME_LEAD_TIME_WEEKS: Dict[str, int] = {
    "us_l1b": 20,          # 5 months: USCIS standard (premium = 6 weeks)
    "japan_coe": 16,       # COE 1–3 months + visa 2 weeks
    "eu_free_movement": 0, # No immigration lead time
    "uk_skilled_worker": 8,
    "standard_work_permit": 8,
    "domestic": 0,
    "unknown": 0,
}


# ─── Core router ──────────────────────────────────────────────────────────────

class ImmigrationRegimeRouter:
    """
    Deterministic immigration regime router.

    Detection priority (first match wins):
      1. Domestic move    — origin == destination country
      2. US destination   — → us_l1b (long-term) or standard (short-term)
      3. Japan destination— → japan_coe
      4. EU/EEA dest + EU/EEA nationality → eu_free_movement
      5. UK destination   → uk_skilled_worker (stub)
      6. Catch-all        → standard_work_permit
    """

    def detect_regime(
        self,
        nationality: Optional[str] = None,
        destination_country: Optional[str] = None,
        origin_country: Optional[str] = None,
        contract_type: Optional[str] = None,
    ) -> ImmigrationRegimeResult:
        """
        Return the best-matching ImmigrationRegimeResult for this route.

        All parameters are optional — passing an incomplete profile returns
        "unknown" rather than raising. Callers should treat "unknown" as
        "no regime-specific tasks injected" (fail-open).
        """
        dest = _n(destination_country)
        orig = _n(origin_country)
        ct = _n(contract_type)

        # ── 1. Domestic: same country ─────────────────────────────────────────
        if dest and orig and dest == orig:
            return self._make(regime_id="domestic")

        # ── 2. US destination ─────────────────────────────────────────────────
        if _is_us_destination(destination_country):
            if ct in _LONG_TERM_CONTRACT_TYPES or not ct:
                return self._make(
                    regime_id="us_l1b",
                    priority="critical",
                    requires_employer_petition=True,
                    notes=(
                        "L1B intracompany transfer: US employer must file I-129 petition "
                        "with USCIS. Standard processing 3–6 months; premium 15 business days. "
                        "Requires at least 1 year of qualifying employment."
                    ),
                )
            # Short-term / student to US → standard for now
            return self._make(
                regime_id="standard_work_permit",
                notes="Short-term US assignments: B-1 business visitor or J-1 depending on activity.",
            )

        # ── 3. Japan destination ──────────────────────────────────────────────
        if _is_japan_destination(destination_country):
            return self._make(
                regime_id="japan_coe",
                priority="critical",
                requires_employer_petition=True,
                notes=(
                    "Japan COE (在留資格認定証明書): Japan-side employer files with Immigration "
                    "Services Agency. Processing 1–3 months. No expedited option. "
                    "Employee then applies for visa at Japanese consulate using original COE."
                ),
            )

        # ── 4. EU/EEA destination + EU/EEA national → free movement ──────────
        if _is_eu_destination(destination_country) and _is_eu_national(nationality):
            return self._make(
                regime_id="eu_free_movement",
                notes=(
                    "EU/EEA free movement: no work permit required. "
                    "Registration with local authorities within 3 months of arrival."
                ),
            )

        # ── 5. UK destination ─────────────────────────────────────────────────
        if _is_uk_destination(destination_country):
            return self._make(
                regime_id="uk_skilled_worker",
                priority="critical",
                requires_employer_petition=True,
                notes=(
                    "UK Skilled Worker visa: employer must hold a sponsor licence. "
                    "Detailed implementation in a future sprint."
                ),
            )

        # ── 6. Catch-all ──────────────────────────────────────────────────────
        if dest:
            return self._make(
                regime_id="standard_work_permit",
                notes=(
                    f"Standard work permit route for {destination_country}. "
                    "Check destination-country specific requirements."
                ),
            )

        # No destination provided
        return self._make(regime_id="unknown")

    # ── Private builder ───────────────────────────────────────────────────────

    def _make(
        self,
        regime_id: str,
        priority: str = "standard",
        requires_employer_petition: bool = False,
        notes: str = "",
    ) -> ImmigrationRegimeResult:
        return ImmigrationRegimeResult(
            regime_id=regime_id,
            task_codes=_REGIME_TASK_CODES.get(regime_id, ()),
            priority=priority,
            typical_lead_time_weeks=_REGIME_LEAD_TIME_WEEKS.get(regime_id, 0),
            exception_triggers=_REGIME_EXCEPTION_TRIGGERS.get(regime_id, ()),
            notes=notes,
            requires_employer_petition=requires_employer_petition,
        )
