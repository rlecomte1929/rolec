"""
Canonical task definitions for the phased relocation plan (MVP).

Each task has a stable ``task_code`` (API / UI) and a ``milestone_type`` that matches
``case_milestones.milestone_type`` / ``OPERATIONAL_TASK_DEFAULTS`` in ``timeline_service``.
Adapter layer uses ``milestone_type`` to hydrate rows from the DB without migrations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Final, List, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class RequiredInputDef:
    """Declarative input gate for progressive disclosure (not evaluated here)."""

    input_type: str  # document | profile_field | assignment_field | approval | other
    key: str
    label: str


@dataclass(frozen=True)
class TaskLibraryEntry:
    """
    Single row in the MVP task catalog.
    ``auto_completion_hint`` is a machine hint for a future reconciler (document_presence, etc.).
    """

    task_code: str
    milestone_type: str
    phase_key: str
    title: str
    short_label: str
    default_owner: str  # employee | hr | joint | provider
    priority: str  # standard | critical
    depends_on: Tuple[str, ...] = ()
    auto_completion_hint: str = "manual"
    why_this_matters: str = ""
    instructions: Tuple[str, ...] = ()
    required_inputs: Tuple[RequiredInputDef, ...] = ()
    sequence_in_phase: int = 0


# Global phase ordering (first → last in the journey).
PHASE_ORDER: Final[Tuple[str, ...]] = (
    "pre_departure",
    "immigration",
    "logistics",
    "arrival",
    "post_arrival",
)

# Human titles for phases (API / UI).
PHASE_TITLES: Final[Mapping[str, str]] = {
    "pre_departure": "Pre-departure",
    "immigration": "Immigration",
    "logistics": "Logistics",
    "arrival": "Arrival",
    "post_arrival": "Post-arrival",
}

_PHASE_INDEX: Dict[str, int] = {k: i for i, k in enumerate(PHASE_ORDER)}


def phase_index(phase_key: str) -> int:
    """Sort key for phases; unknown phases sort last."""
    return _PHASE_INDEX.get(phase_key, 999)


# ---------------------------------------------------------------------------
# MVP task library (deterministic; order within phase via sequence_in_phase)
# ---------------------------------------------------------------------------

_TASK_LIBRARY_SEQ: Tuple[TaskLibraryEntry, ...] = (
    TaskLibraryEntry(
        task_code="confirm_employee_core_profile",
        milestone_type="task_profile_core",
        phase_key="pre_departure",
        title="Confirm employee core profile",
        short_label="Core profile",
        default_owner="employee",
        priority="standard",
        depends_on=(),
        auto_completion_hint="profile_fields_present",
        why_this_matters="Legal name, contact, and job basics must be correct before documents and filings.",
        instructions=(
            "Review your name, email, nationality, and role in the case wizard.",
            "Fix any mistakes before uploading identity documents.",
        ),
        required_inputs=(
            RequiredInputDef("profile_field", "full_name", "Full legal name"),
            RequiredInputDef("profile_field", "nationality", "Nationality"),
        ),
        sequence_in_phase=10,
    ),
    TaskLibraryEntry(
        task_code="confirm_family_details",
        milestone_type="task_family_dependents",
        phase_key="pre_departure",
        title="Confirm family / dependent details",
        short_label="Family",
        default_owner="joint",
        priority="standard",
        depends_on=("confirm_employee_core_profile",),
        auto_completion_hint="profile_fields_present",
        why_this_matters="Household composition drives immigration, benefits, and schooling.",
        instructions=(
            "Record spouse and children if they relocate with you.",
            "Mark single / no dependents if applicable.",
        ),
        required_inputs=(),
        sequence_in_phase=20,
    ),
    TaskLibraryEntry(
        task_code="upload_passport_copy",
        milestone_type="task_passport_upload",
        phase_key="pre_departure",
        title="Upload passport copy",
        short_label="Passport",
        default_owner="employee",
        priority="critical",
        depends_on=("confirm_employee_core_profile",),
        auto_completion_hint="document_presence",
        why_this_matters="Passport bio page is required for visa and work authorization.",
        instructions=(
            "Upload a clear, color scan of the passport photo page.",
            "Ensure expiry date is visible.",
        ),
        required_inputs=(RequiredInputDef("document", "passport_copy", "Passport copy"),),
        sequence_in_phase=30,
    ),
    TaskLibraryEntry(
        task_code="upload_assignment_letter",
        milestone_type="task_employment_letter",
        phase_key="pre_departure",
        title="Upload employment / assignment letter",
        short_label="Assignment letter",
        default_owner="employee",
        priority="critical",
        depends_on=("confirm_employee_core_profile",),
        auto_completion_hint="document_presence",
        why_this_matters="Confirms role, compensation, and assignment terms for authorities and HR.",
        instructions=(
            "Upload the signed letter from your employer describing the assignment.",
            "Include start date and host location if stated.",
        ),
        required_inputs=(RequiredInputDef("document", "employment_letter", "Employment / assignment letter"),),
        sequence_in_phase=40,
    ),
    TaskLibraryEntry(
        task_code="verify_destination_route",
        milestone_type="task_route_verify",
        phase_key="pre_departure",
        title="Verify destination route",
        short_label="Route",
        default_owner="hr",
        priority="standard",
        depends_on=("upload_passport_copy", "upload_assignment_letter"),
        auto_completion_hint="manual",
        why_this_matters="HR confirms origin → destination and policy routing before filings.",
        instructions=(
            "HR: confirm origin and destination against policy and assignment record.",
            "Flag exceptions for policy review if the route is unusual.",
        ),
        required_inputs=(),
        sequence_in_phase=50,
    ),
    TaskLibraryEntry(
        task_code="hr_review_case_data",
        milestone_type="task_hr_case_review",
        phase_key="immigration",
        title="HR review of case data",
        short_label="HR review",
        default_owner="hr",
        priority="critical",
        depends_on=("verify_destination_route",),
        auto_completion_hint="manual",
        why_this_matters="Internal gate before external immigration work.",
        instructions=(
            "Review intake, uploaded documents, and policy fit.",
            "Request changes from the employee if data is incomplete.",
        ),
        required_inputs=(),
        sequence_in_phase=10,
    ),
    TaskLibraryEntry(
        task_code="schedule_immigration_review",
        milestone_type="task_immigration_review",
        phase_key="immigration",
        title="Schedule immigration review",
        short_label="Immigration review",
        default_owner="hr",
        priority="standard",
        depends_on=("hr_review_case_data",),
        auto_completion_hint="manual",
        why_this_matters="Counsel or vendor must review the route before pack preparation.",
        instructions=("Book the immigration consultation or vendor review.",),
        required_inputs=(),
        sequence_in_phase=20,
    ),
    TaskLibraryEntry(
        task_code="prepare_visa_pack",
        milestone_type="task_visa_docs_prep",
        phase_key="immigration",
        title="Prepare visa / work permit application pack",
        short_label="Visa pack",
        default_owner="joint",
        priority="critical",
        depends_on=("schedule_immigration_review",),
        auto_completion_hint="manual",
        why_this_matters="Forms and evidence must be complete before submission.",
        instructions=(
            "Compile required forms per destination checklist.",
            "Align dates with passport and assignment letter.",
        ),
        required_inputs=(),
        sequence_in_phase=30,
    ),
    TaskLibraryEntry(
        task_code="submit_visa_application",
        milestone_type="task_visa_submit",
        phase_key="immigration",
        title="Submit visa / work permit application",
        short_label="Submit visa",
        default_owner="joint",
        priority="critical",
        depends_on=("prepare_visa_pack",),
        auto_completion_hint="manual",
        why_this_matters="Official filing starts processing time and reference numbers.",
        instructions=("Submit to authority or sponsor; store receipt and reference IDs.",),
        required_inputs=(),
        sequence_in_phase=40,
    ),
    TaskLibraryEntry(
        task_code="book_biometrics",
        milestone_type="task_biometrics",
        phase_key="immigration",
        title="Book biometrics / appointment (if applicable)",
        short_label="Biometrics",
        default_owner="employee",
        priority="standard",
        depends_on=("submit_visa_application",),
        auto_completion_hint="manual",
        why_this_matters="Many routes require a visa center or embassy appointment.",
        instructions=("Book the earliest practical slot; bring required documents.",),
        required_inputs=(),
        sequence_in_phase=50,
    ),
    TaskLibraryEntry(
        task_code="arrange_temporary_housing",
        milestone_type="task_temp_housing",
        phase_key="logistics",
        title="Arrange temporary housing",
        short_label="Temp housing",
        default_owner="employee",
        priority="standard",
        depends_on=("submit_visa_application",),
        auto_completion_hint="manual",
        why_this_matters="Short-term accommodation before permanent housing is secured.",
        instructions=("Book dates aligned with visa validity and arrival.",),
        required_inputs=(),
        sequence_in_phase=10,
    ),
    TaskLibraryEntry(
        task_code="arrange_movers",
        milestone_type="task_movers_shipment",
        phase_key="logistics",
        title="Arrange movers / shipment",
        short_label="Movers",
        default_owner="employee",
        priority="standard",
        depends_on=("arrange_temporary_housing",),
        auto_completion_hint="manual",
        why_this_matters="Inventory, insurance, and shipping dates must align with travel.",
        instructions=("Get quotes; confirm pickup and delivery windows.",),
        required_inputs=(),
        sequence_in_phase=20,
    ),
    TaskLibraryEntry(
        task_code="coordinate_relocation_providers",
        milestone_type="task_provider_coordination",
        phase_key="logistics",
        title="Coordinate relocation providers",
        short_label="Providers",
        default_owner="provider",
        priority="standard",
        depends_on=("hr_review_case_data",),
        auto_completion_hint="manual",
        why_this_matters="Approved vendors for housing, schools, or logistics when services are selected.",
        instructions=("Engage vendors per company policy.",),
        required_inputs=(),
        sequence_in_phase=25,
    ),
    TaskLibraryEntry(
        task_code="plan_travel",
        milestone_type="task_travel_plan",
        phase_key="logistics",
        title="Plan travel",
        short_label="Travel",
        default_owner="employee",
        priority="standard",
        depends_on=("submit_visa_application", "book_biometrics"),
        auto_completion_hint="manual",
        why_this_matters="Flights must align with visa validity and start date.",
        instructions=("Book flights; share itinerary with HR if required.",),
        required_inputs=(),
        sequence_in_phase=30,
    ),
    TaskLibraryEntry(
        task_code="complete_arrival_registration",
        milestone_type="task_arrival_registration",
        phase_key="arrival",
        title="Complete arrival registration",
        short_label="Arrival registration",
        default_owner="employee",
        priority="standard",
        depends_on=("plan_travel",),
        auto_completion_hint="manual",
        why_this_matters="Local registration or residency steps are often time-bound after entry.",
        instructions=("Complete host-country registration within the required window.",),
        required_inputs=(),
        sequence_in_phase=10,
    ),
    TaskLibraryEntry(
        task_code="tax_local_registration",
        milestone_type="task_tax_local_registration",
        phase_key="post_arrival",
        title="Tax / local registration",
        short_label="Tax / ID",
        default_owner="employee",
        priority="standard",
        depends_on=("complete_arrival_registration",),
        auto_completion_hint="manual",
        why_this_matters="Tax ID and social identifiers unlock payroll and benefits.",
        instructions=("Register for tax ID or social security equivalents.",),
        required_inputs=(),
        sequence_in_phase=10,
    ),
    TaskLibraryEntry(
        task_code="settle_in",
        milestone_type="task_settling_in",
        phase_key="post_arrival",
        title="Settle in — critical post-arrival steps",
        short_label="Settle in",
        default_owner="joint",
        priority="standard",
        depends_on=("tax_local_registration",),
        auto_completion_hint="manual",
        why_this_matters="Bank, utilities, and healthcare registration complete the move.",
        instructions=("Open bank account, utilities, and local healthcare as required.",),
        required_inputs=(),
        sequence_in_phase=20,
    ),
)

TASK_BY_CODE: Dict[str, TaskLibraryEntry] = {t.task_code: t for t in _TASK_LIBRARY_SEQ}
TASK_BY_MILESTONE_TYPE: Dict[str, TaskLibraryEntry] = {t.milestone_type: t for t in _TASK_LIBRARY_SEQ}


def get_task_library_entry_by_code(task_code: str) -> Optional[TaskLibraryEntry]:
    return TASK_BY_CODE.get(task_code)


def get_task_library_entry_by_milestone_type(milestone_type: str) -> Optional[TaskLibraryEntry]:
    return TASK_BY_MILESTONE_TYPE.get((milestone_type or "").strip())


def iter_task_library() -> Sequence[TaskLibraryEntry]:
    """Stable iteration order: phase order, then sequence_in_phase."""
    return tuple(
        sorted(
            _TASK_LIBRARY_SEQ,
            key=lambda t: (phase_index(t.phase_key), t.sequence_in_phase, t.task_code),
        )
    )
