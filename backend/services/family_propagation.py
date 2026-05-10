"""
family_propagation.py — Deterministic family workstream propagation.

Given a family profile, returns the list of additional workstreams that must
be added to the relocation plan. All logic is a lookup table / decision tree —
no LLM reasoning. Immigration rules are deterministic; this module is the
policy expert for family cases.

Touch policy: NEW FILE. Does not modify any existing module.

Usage:
    from backend.services.family_propagation import FamilyPropagator, WorkstreamRequirement

    propagator = FamilyPropagator()
    requirements = propagator.get_required_workstreams(
        family_profile={
            "hasSpouse": True,
            "partnerVisaStatus": "non_eu_no_permit",
            "spouseEmploymentIntent": "yes",
            "childCount": 2,
        },
        destination_country="Netherlands",
        origin_country="Spain",
    )
    # → [WorkstreamRequirement(workstream_id="partner_mvv", ...),
    #    WorkstreamRequirement(workstream_id="spouse_work_authorization", ...),
    #    WorkstreamRequirement(workstream_id="school_enrollment", ...)]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# ─── EU / EEA countries ───────────────────────────────────────────────────────
# Used to determine if a partner has free movement rights.
# ISO 3166-1 alpha-2 codes + common name variants (lowercase for comparison).
_EU_EEA_COUNTRIES = frozenset({
    # EU member states
    "austria", "at", "belgium", "be", "bulgaria", "bg", "croatia", "hr",
    "cyprus", "cy", "czechia", "czech republic", "cz", "denmark", "dk",
    "estonia", "ee", "finland", "fi", "france", "fr", "germany", "de",
    "greece", "gr", "hungary", "hu", "ireland", "ie", "italy", "it",
    "latvia", "lv", "lithuania", "lt", "luxembourg", "lu", "malta", "mt",
    "netherlands", "nl", "poland", "pl", "portugal", "pt", "romania", "ro",
    "slovakia", "sk", "slovenia", "si", "spain", "es", "sweden", "se",
    # EEA (non-EU but free movement)
    "iceland", "is", "liechtenstein", "li", "norway", "no",
    # Switzerland (bilateral agreements, treated as free movement for most purposes)
    "switzerland", "ch",
})

# Countries that require an MVV (Machtiging tot Voorlopig Verblijf) for
# non-EU family members before entering. Currently: Netherlands.
_MVV_REQUIRED_DESTINATIONS = frozenset({"netherlands", "nl"})

# Countries with a specific family reunification visa track (not generic dependent)
_FAMILY_REUNIFICATION_DESTINATIONS = frozenset({
    "france", "fr", "germany", "de", "netherlands", "nl",
    "belgium", "be", "sweden", "se",
})


def _is_eu_national(nationality: Optional[str]) -> bool:
    if not nationality:
        return False
    return nationality.strip().lower() in _EU_EEA_COUNTRIES


def _is_eu_destination(destination: Optional[str]) -> bool:
    if not destination:
        return False
    return destination.strip().lower() in _EU_EEA_COUNTRIES


def _requires_mvv(destination: Optional[str]) -> bool:
    if not destination:
        return False
    return destination.strip().lower() in _MVV_REQUIRED_DESTINATIONS


# ─── Output model ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class WorkstreamRequirement:
    """
    A single additional workstream that must be added to the relocation plan
    because of the family situation.

    workstream_id maps to task_codes in the task library:
      "school_enrollment"         → school_enrollment_research + school_enrollment_application
      "spouse_work_authorization" → spouse_work_authorization task
      "partner_family_visa"       → partner_family_visa task
      "partner_mvv"               → partner_mvv_application task (NL-specific)
      "dependent_visa"            → dependent_visa_application (SG, UK, US)
    """
    workstream_id: str
    reason: str
    priority: str = "standard"      # standard | critical
    typical_lead_time_weeks: int = 0
    additional_questions_required: List[str] = field(default_factory=list)
    notes: str = ""


# ─── Core propagation logic ───────────────────────────────────────────────────

class FamilyPropagator:
    """
    Deterministic family workstream propagator.

    All decisions are based on explicit lookup rules. The LLM is not involved.
    To add support for a new country pair or scenario, add a new rule block —
    no changes to the core logic needed.
    """

    def get_required_workstreams(
        self,
        family_profile: dict,
        destination_country: Optional[str] = None,
        origin_country: Optional[str] = None,
    ) -> List[WorkstreamRequirement]:
        """
        Return the list of additional workstreams required given this family profile.

        family_profile keys (all optional, safe to pass incomplete):
            hasSpouse (bool)
            spouseNationality (str)
            partnerVisaStatus (str):
                "eu_citizen" | "non_eu_with_permit" | "non_eu_no_permit" |
                "same_as_employee" | "unknown"
            spouseEmploymentIntent (str): "yes" | "no" | "unknown"
            childCount (int or str)

        destination_country: name or ISO code of destination (case-insensitive)
        origin_country: name or ISO code of origin (for context)
        """
        requirements: List[WorkstreamRequirement] = []

        has_spouse = family_profile.get("hasSpouse", False)
        child_count = self._parse_int(family_profile.get("childCount", 0))
        partner_visa_status = (family_profile.get("partnerVisaStatus") or "unknown").lower()
        spouse_nationality = family_profile.get("spouseNationality") or ""
        spouse_employment_intent = (family_profile.get("spouseEmploymentIntent") or "unknown").lower()

        # ── Partner / spouse workstreams ──────────────────────────────────────
        if has_spouse:
            requirements.extend(
                self._spouse_workstreams(
                    partner_visa_status=partner_visa_status,
                    spouse_nationality=spouse_nationality,
                    spouse_employment_intent=spouse_employment_intent,
                    destination_country=destination_country,
                )
            )

        # ── Child / school workstreams ────────────────────────────────────────
        if child_count > 0:
            requirements.extend(
                self._child_workstreams(
                    child_count=child_count,
                    destination_country=destination_country,
                )
            )

        return requirements

    # ── Private: spouse workstream rules ─────────────────────────────────────

    def _spouse_workstreams(
        self,
        partner_visa_status: str,
        spouse_nationality: str,
        spouse_employment_intent: str,
        destination_country: Optional[str],
    ) -> List[WorkstreamRequirement]:
        result: List[WorkstreamRequirement] = []

        # Determine if partner needs immigration steps
        partner_is_eu = (
            partner_visa_status == "eu_citizen"
            or _is_eu_national(spouse_nationality)
        )
        destination_is_eu = _is_eu_destination(destination_country)

        # ── Rule: non-EU partner → MVV (Netherlands) ─────────────────────────
        if (
            not partner_is_eu
            and partner_visa_status in {"non_eu_no_permit", "non_eu_with_permit", "unknown"}
            and _requires_mvv(destination_country)
        ):
            result.append(WorkstreamRequirement(
                workstream_id="partner_mvv",
                reason=(
                    f"Your partner requires a Dutch MVV (Machtiging tot Voorlopig Verblijf) "
                    f"before entering the Netherlands as a non-EU national. "
                    f"The procedure is initiated at the Dutch consulate in the origin country."
                ),
                priority="critical",
                typical_lead_time_weeks=12,
                additional_questions_required=[
                    "partner_passport_expiry",
                    "income_proof_available",
                    "relationship_proof_available",
                ],
                notes="MVV must be approved before the partner can enter NL. "
                      "Start this immediately — do not wait for the employee's visa.",
            ))

        # ── Rule: non-EU partner → family reunification visa (EU, non-NL) ────
        elif (
            not partner_is_eu
            and partner_visa_status in {"non_eu_no_permit", "unknown"}
            and destination_is_eu
            and not _requires_mvv(destination_country)
        ):
            result.append(WorkstreamRequirement(
                workstream_id="partner_family_visa",
                reason=(
                    f"Your partner is a non-EU national relocating to an EU country. "
                    f"They will need a family reunification visa to join you legally. "
                    f"Requirements and timelines vary by destination country."
                ),
                priority="critical",
                typical_lead_time_weeks=8,
                additional_questions_required=[
                    "partner_passport_expiry",
                    "income_proof_available",
                ],
                notes="Check specific requirements for the destination country's family "
                      "reunification route. Some EU countries allow entry on a tourist visa "
                      "while the application is processed; others do not.",
            ))

        # ── Rule: non-EU destination (SG, US, UK) → dependent visa ───────────
        elif (
            not destination_is_eu
            and partner_visa_status in {"non_eu_no_permit", "non_eu_with_permit",
                                         "same_as_employee", "unknown"}
        ):
            result.append(WorkstreamRequirement(
                workstream_id="dependent_visa",
                reason=(
                    f"Your partner will need a dependent visa or pass to legally reside "
                    f"in the destination country with you."
                ),
                priority="standard",
                typical_lead_time_weeks=6,
                additional_questions_required=["partner_passport_expiry"],
                notes="Dependent visa eligibility usually requires the employee's work "
                      "permit to be approved first. Start the dependent application "
                      "immediately after the main permit is granted.",
            ))

        # ── Rule: spouse intends to work → work authorisation needed ─────────
        if spouse_employment_intent == "yes":
            # Only add if we haven't already captured work rights via the
            # partner visa workstream (MVV and family reunification visas
            # typically include work rights in their own task flow).
            partner_visa_workstream_ids = {r.workstream_id for r in result}
            if not partner_visa_workstream_ids.intersection({"partner_mvv", "partner_family_visa"}):
                result.append(WorkstreamRequirement(
                    workstream_id="spouse_work_authorization",
                    reason=(
                        "Your partner intends to work in the destination country. "
                        "They need their own work authorisation, separate from your visa. "
                    ),
                    priority="standard",
                    typical_lead_time_weeks=8,
                    additional_questions_required=[
                        "spouse_occupation",
                        "spouse_qualification_level",
                    ],
                    notes="In EU countries with free movement, an EU-national partner "
                          "can generally work without a separate permit. "
                          "For non-EU destinations check the spouse visa category "
                          "carefully — not all dependent visas include work rights.",
                ))
            else:
                # MVV / family reunification route — note that work rights are bundled
                # Add a lighter note workstream instead
                result.append(WorkstreamRequirement(
                    workstream_id="spouse_work_authorization",
                    reason=(
                        "Your partner intends to work. Confirm that the family visa route "
                        "you are pursuing includes work authorisation for the partner."
                    ),
                    priority="standard",
                    typical_lead_time_weeks=0,
                    notes="Work rights are often included in MVV / family reunification "
                          "permits but must be confirmed with the immigration adviser.",
                ))

        return result

    # ── Private: child workstream rules ──────────────────────────────────────

    def _child_workstreams(
        self,
        child_count: int,
        destination_country: Optional[str],
    ) -> List[WorkstreamRequirement]:
        result: List[WorkstreamRequirement] = []

        result.append(WorkstreamRequirement(
            workstream_id="school_enrollment",
            reason=(
                f"You have {child_count} child{'ren' if child_count > 1 else ''} relocating. "
                f"School enrollment in the destination country requires research, applications, "
                f"and often proof of local address — start this early."
            ),
            priority="standard",
            typical_lead_time_weeks=12,
            additional_questions_required=[
                "child_ages",
                "school_curriculum_preference",
                "school_budget",
            ],
            notes=(
                "International school applications typically open 6–12 months before the "
                "academic year. Local public school enrollment often requires a registered "
                "address in the catchment area. Plan both options in parallel."
            ),
        ))

        return result

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_int(value) -> int:
        """Safely coerce string or numeric child count to int. '4+' → 4."""
        if value is None:
            return 0
        try:
            s = str(value).replace("+", "").strip()
            return int(s) if s.isdigit() else 0
        except (ValueError, TypeError):
            return 0
