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

    # ── S4 SPIKE: Family workstream task codes ────────────────────────────────
    # These task_codes are conditionally included in a plan when the
    # family_propagation service returns the corresponding workstream_id.
    # They are ADDITIVE — no existing task_code is modified.
    # mapping: workstream_id → task_codes to hydrate
    #   "school_enrollment"         → school_enrollment_research + school_enrollment_application
    #   "spouse_work_authorization" → spouse_work_authorization
    #   "partner_family_visa"       → partner_family_visa_application
    #   "partner_mvv"               → partner_mvv_application
    #   "dependent_visa"            → dependent_visa_application

    # School enrollment — research phase (pre-departure)
    TaskLibraryEntry(
        task_code="school_enrollment_research",
        milestone_type="task_school_research",
        phase_key="pre_departure",
        title="Research and shortlist schools",
        short_label="School research",
        default_owner="employee",
        priority="standard",
        depends_on=("confirm_family_details",),
        auto_completion_hint="manual",
        why_this_matters="International school applications open months before the academic "
                         "year and popular schools fill quickly. Start early.",
        instructions=(
            "Identify schools matching the curriculum preference and location.",
            "Check application deadlines — many open 6–12 months before term start.",
            "Request prospectus and open-day invitations.",
        ),
        required_inputs=(
            RequiredInputDef("profile_field", "child_ages", "Child age(s)"),
            RequiredInputDef("profile_field", "school_curriculum_preference", "Curriculum preference"),
        ),
        sequence_in_phase=25,
    ),

    # School enrollment — application (immigration phase, after visa confirmed)
    TaskLibraryEntry(
        task_code="school_enrollment_application",
        milestone_type="task_school_application",
        phase_key="immigration",
        title="Submit school applications",
        short_label="School application",
        default_owner="employee",
        priority="standard",
        depends_on=("school_enrollment_research", "prepare_visa_pack"),
        auto_completion_hint="manual",
        why_this_matters="Many schools require proof of address or visa before confirming "
                         "a place. Submit as soon as documentation is available.",
        instructions=(
            "Submit applications to shortlisted schools.",
            "Attach passport copies, previous school reports, and proof of address.",
            "Follow up within two weeks of submission.",
        ),
        required_inputs=(
            RequiredInputDef("document", "previous_school_reports", "Previous school reports"),
        ),
        sequence_in_phase=35,
    ),

    # Spouse / partner work authorisation (immigration phase)
    TaskLibraryEntry(
        task_code="spouse_work_authorization",
        milestone_type="task_spouse_work_permit",
        phase_key="immigration",
        title="Obtain spouse / partner work authorisation",
        short_label="Spouse work permit",
        default_owner="joint",
        priority="standard",
        depends_on=("hr_review_case_data",),
        auto_completion_hint="manual",
        why_this_matters="Work authorisation for a partner is separate from the employee "
                         "visa. In many countries the partner cannot begin employment "
                         "until their own permit is granted.",
        instructions=(
            "Check if the employee's visa category confers automatic work rights on the partner.",
            "If not, apply for the appropriate dependent work permit.",
            "Timeline is typically 4–12 weeks depending on the route.",
        ),
        required_inputs=(
            RequiredInputDef("document", "spouse_passport_copy", "Spouse passport copy"),
            RequiredInputDef("profile_field", "spouse_nationality", "Spouse nationality"),
        ),
        sequence_in_phase=25,
    ),

    # Partner family reunification visa (generic EU route, non-NL)
    TaskLibraryEntry(
        task_code="partner_family_visa_application",
        milestone_type="task_partner_family_visa",
        phase_key="immigration",
        title="Apply for partner / family reunification visa",
        short_label="Partner family visa",
        default_owner="joint",
        priority="critical",
        depends_on=("hr_review_case_data",),
        auto_completion_hint="manual",
        why_this_matters="A non-EU partner cannot legally reside in most EU countries "
                         "without a family reunification permit. This must run in "
                         "parallel with the employee visa process.",
        instructions=(
            "Confirm the correct family visa category for the destination country.",
            "Gather: proof of relationship, income proof, partner passport, accommodation proof.",
            "Submit at the destination country's consulate in the origin country.",
            "Processing typically takes 8–16 weeks.",
        ),
        required_inputs=(
            RequiredInputDef("document", "marriage_or_partnership_cert", "Marriage / partnership certificate"),
            RequiredInputDef("document", "spouse_passport_copy", "Spouse passport copy"),
        ),
        sequence_in_phase=20,
    ),

    # Dutch MVV (Machtiging tot Voorlopig Verblijf) — NL-specific family visa
    TaskLibraryEntry(
        task_code="partner_mvv_application",
        milestone_type="task_partner_mvv",
        phase_key="immigration",
        title="Apply for Dutch MVV (partner family entry visa)",
        short_label="Partner MVV",
        default_owner="joint",
        priority="critical",
        depends_on=("hr_review_case_data",),
        auto_completion_hint="manual",
        why_this_matters="Non-EU partners cannot enter the Netherlands to reside without "
                         "an MVV. The IND (Dutch immigration) processes this and it must "
                         "be applied for before the partner travels.",
        instructions=(
            "The employee (as sponsor) submits the MVV application to the IND online.",
            "Required documents: both passports, proof of income, proof of relationship, "
            "proof of accommodation in NL.",
            "After IND approval (~3 months), the partner collects the MVV sticker at "
            "the Dutch consulate in their home country.",
            "Do NOT wait for this — start on day one of the case.",
        ),
        required_inputs=(
            RequiredInputDef("document", "income_proof", "Proof of income (sponsor)"),
            RequiredInputDef("document", "marriage_or_partnership_cert", "Marriage / partnership certificate"),
            RequiredInputDef("document", "spouse_passport_copy", "Spouse passport copy"),
            RequiredInputDef("document", "accommodation_proof_nl", "Proof of accommodation in NL"),
        ),
        sequence_in_phase=15,
    ),

    # Dependent visa (non-EU destinations: SG, US, UK etc.)
    TaskLibraryEntry(
        task_code="dependent_visa_application",
        milestone_type="task_dependent_visa",
        phase_key="immigration",
        title="Apply for dependent / spouse visa",
        short_label="Dependent visa",
        default_owner="joint",
        priority="standard",
        depends_on=("submit_visa_application",),
        auto_completion_hint="manual",
        why_this_matters="The dependent visa application can only be submitted after the "
                         "employee work permit is granted or in progress.",
        instructions=(
            "Apply for the dependent visa after the employee's work permit is confirmed.",
            "Required documents: employee's permit, marriage certificate, spouse passport.",
        ),
        required_inputs=(
            RequiredInputDef("document", "spouse_passport_copy", "Spouse passport copy"),
            RequiredInputDef("document", "marriage_or_partnership_cert", "Marriage / partnership certificate"),
        ),
        sequence_in_phase=45,
    ),
    # ─────────────────────────────────────────────────────────────────────────

    # ── P2 SPIKE: US L1B intracompany transfer task codes ─────────────────────
    # Triggered by immigration_regime.py when regime_id == "us_l1b".
    # All are ADDITIVE — no existing task_code is modified.
    # Flow: support letter → I-129 petition → USCIS approval → DS-160 →
    #       consulate interview → visa stamp → CBP entry → SSN
    # ─────────────────────────────────────────────────────────────────────────

    # US entity prepares internal support / authorisation letter for USCIS filing
    TaskLibraryEntry(
        task_code="l1b_support_letter",
        milestone_type="task_l1b_support_letter",
        phase_key="pre_departure",
        title="Prepare US entity L1B support letter",
        short_label="L1B support letter",
        default_owner="hr",
        priority="critical",
        depends_on=("hr_review_case_data",),
        auto_completion_hint="document_presence",
        why_this_matters=(
            "The L1B petition requires a detailed support letter from the US petitioner "
            "establishing the employee's specialised knowledge and the intracompany "
            "relationship. USCIS scrutinises this heavily."
        ),
        instructions=(
            "US HR or legal counsel drafts the support letter on company letterhead.",
            "Letter must describe: (1) specialised knowledge held by the employee, "
            "(2) duties in the US role, (3) qualifying relationship between entities.",
            "Get sign-off from US entity's authorised signatory.",
        ),
        required_inputs=(
            RequiredInputDef("profile_field", "us_entity_name", "US petitioner entity name"),
            RequiredInputDef("profile_field", "employee_specialized_knowledge", "Specialised knowledge description"),
            RequiredInputDef("profile_field", "employment_start_date", "Date employment began"),
        ),
        sequence_in_phase=6,
    ),

    # Compile the full I-129 petition package (forms + exhibits)
    TaskLibraryEntry(
        task_code="l1b_petition_preparation",
        milestone_type="task_l1b_petition_prep",
        phase_key="pre_departure",
        title="Prepare I-129 L1B petition package",
        short_label="I-129 petition prep",
        default_owner="hr",
        priority="critical",
        depends_on=("l1b_support_letter",),
        auto_completion_hint="manual",
        why_this_matters=(
            "The I-129 is the core USCIS filing. An incomplete package triggers a "
            "Request for Evidence (RFE), adding 2–4 months to the timeline."
        ),
        instructions=(
            "Complete USCIS Form I-129 and L Classification Supplement.",
            "Assemble exhibits: organisational charts, financial statements, "
            "employee's CV, evidence of specialised knowledge (patents, certifications, "
            "internal documentation).",
            "Prepare filing fee payment (~$1,385 base + $600 ACWIA training fee for "
            "25+ employee companies; ~$4,190 for premium processing).",
            "Consider premium processing (I-907) if move date is within 6 months.",
        ),
        required_inputs=(
            RequiredInputDef("document", "i129_form", "USCIS Form I-129 (completed)"),
            RequiredInputDef("document", "l_supplement", "L Classification Supplement"),
            RequiredInputDef("document", "specialised_knowledge_evidence", "Specialised knowledge evidence"),
        ),
        sequence_in_phase=7,
    ),

    # File I-129 with USCIS (immigration phase — filing happens before move)
    TaskLibraryEntry(
        task_code="l1b_petition_filing",
        milestone_type="task_l1b_petition_filing",
        phase_key="immigration",
        title="File I-129 L1B petition with USCIS",
        short_label="USCIS I-129 filing",
        default_owner="hr",
        priority="critical",
        depends_on=("l1b_petition_preparation",),
        auto_completion_hint="manual",
        why_this_matters=(
            "USCIS processing is the long pole in the tent: 3–6 months standard, "
            "15 business days with premium processing. File as early as possible."
        ),
        instructions=(
            "Submit I-129 package to the correct USCIS service centre (varies by "
            "US work location — check USCIS direct-filing instructions).",
            "Retain the USCIS receipt notice (Form I-797) immediately on receipt — "
            "this is proof of pending status.",
            "Track case status at egov.uscis.gov using the receipt number.",
            "If an RFE is issued, respond within the stated deadline (typically 87 days).",
        ),
        required_inputs=(
            RequiredInputDef("document", "i129_petition_package", "Completed I-129 package"),
            RequiredInputDef("document", "filing_fee_receipt", "USCIS filing fee payment receipt"),
        ),
        sequence_in_phase=5,
    ),

    # Employee completes DS-160 and schedules consulate visa interview
    TaskLibraryEntry(
        task_code="l1b_visa_interview",
        milestone_type="task_l1b_visa_interview",
        phase_key="immigration",
        title="Complete DS-160 and attend US consulate visa interview",
        short_label="US visa interview",
        default_owner="employee",
        priority="critical",
        depends_on=("l1b_petition_filing",),
        auto_completion_hint="manual",
        why_this_matters=(
            "After USCIS approves the I-129, the employee must obtain an L1B visa "
            "stamp at a US consulate or embassy. This is a separate step from USCIS approval."
        ),
        instructions=(
            "Complete the DS-160 online nonimmigrant visa application at ceac.state.gov.",
            "Pay the MRV visa application fee (~$205).",
            "Schedule a visa interview at the nearest US embassy or consulate.",
            "Bring: passport, DS-160 confirmation, I-797 approval notice, support "
            "letter, employment evidence, and financial documents.",
            "Visa interview wait times vary by location — check current wait times "
            "at travel.state.gov before scheduling.",
        ),
        required_inputs=(
            RequiredInputDef("document", "i797_approval_notice", "USCIS I-797 approval notice"),
            RequiredInputDef("document", "ds160_confirmation", "DS-160 confirmation barcode"),
            RequiredInputDef("document", "mrv_fee_receipt", "MRV fee payment receipt"),
        ),
        sequence_in_phase=20,
    ),

    # CBP inspection at US port of entry + I-94 verification
    TaskLibraryEntry(
        task_code="l1b_port_of_entry",
        milestone_type="task_l1b_port_of_entry",
        phase_key="arrival",
        title="US port of entry — CBP inspection and I-94 record",
        short_label="US port of entry",
        default_owner="employee",
        priority="critical",
        depends_on=("l1b_visa_interview",),
        auto_completion_hint="manual",
        why_this_matters=(
            "CBP admission at the port of entry establishes the I-94 record, which "
            "is the legal record of authorised stay. The I-94 end date controls "
            "how long the employee may remain and work in the US."
        ),
        instructions=(
            "Present passport with L1B visa stamp, I-797 approval notice, and "
            "support letter to CBP officer.",
            "After admission, retrieve the electronic I-94 record at cbp.dhs.gov/i94 "
            "and verify the class of admission (L-1B) and authorised until date.",
            "Keep a printed copy of the I-94 in a safe place — required for SSN, "
            "driving licence, and bank account applications.",
        ),
        required_inputs=(
            RequiredInputDef("document", "i94_record", "Electronic I-94 record (printed)"),
        ),
        sequence_in_phase=2,
    ),

    # Social Security Number application
    TaskLibraryEntry(
        task_code="l1b_ssn_application",
        milestone_type="task_l1b_ssn",
        phase_key="post_arrival",
        title="Apply for US Social Security Number",
        short_label="US SSN application",
        default_owner="employee",
        priority="standard",
        depends_on=("l1b_port_of_entry",),
        auto_completion_hint="manual",
        why_this_matters=(
            "A Social Security Number is required for payroll, tax filing, banking, "
            "and many everyday services in the US. Applications can be submitted "
            "10 days after arriving in the US."
        ),
        instructions=(
            "Wait at least 10 days after US entry before applying (SSA system update lag).",
            "Complete Form SS-5 at ssa.gov or collect from your local SSA office.",
            "Bring: passport, I-94, I-797, and employment offer letter.",
            "SSN cards typically arrive by post within 2–4 weeks.",
        ),
        required_inputs=(
            RequiredInputDef("document", "i94_record", "I-94 record"),
            RequiredInputDef("document", "i797_approval_notice", "I-797 approval notice"),
        ),
        sequence_in_phase=6,
    ),

    # ── P2 SPIKE: Japan Certificate of Eligibility (COE) task codes ───────────
    # Triggered when regime_id == "japan_coe".
    # A COE (在留資格認定証明書) must be issued by Japan's Immigration Services
    # Agency BEFORE the employee applies for a visa at the Japanese consulate
    # in their home country. It is the first step, not an optional one.
    # ─────────────────────────────────────────────────────────────────────────

    # HR prepares the COE application package
    TaskLibraryEntry(
        task_code="japan_coe_preparation",
        milestone_type="task_japan_coe_prep",
        phase_key="pre_departure",
        title="Prepare Certificate of Eligibility (COE) application",
        short_label="Japan COE prep",
        default_owner="hr",
        priority="critical",
        depends_on=("hr_review_case_data",),
        auto_completion_hint="manual",
        why_this_matters=(
            "Japan's COE is the first step in the work visa process and is filed "
            "by the Japan-side employer with the Immigration Services Agency (ISA). "
            "Without it, the employee cannot apply for a work visa."
        ),
        instructions=(
            "Identify the correct visa category: Engineer / Specialist in Humanities "
            "/ International Services (ESHS) covers most corporate roles; "
            "Intra-company Transferee (ICT) for intracompany transfers.",
            "Japan HR prepares: application form (ISA), passport copy, diploma/degree "
            "certificates, employment contract, company documents (registration, "
            "financial statements).",
            "Submit to the regional ISA office covering the employee's workplace.",
            "Processing takes 1–3 months. No expedited option exists.",
        ),
        required_inputs=(
            RequiredInputDef("profile_field", "japan_visa_category", "Japan visa category (ESHS / ICT / other)"),
            RequiredInputDef("document", "degree_certificate", "Academic degree certificate + translation"),
            RequiredInputDef("document", "employment_contract_jp", "Japan employment contract"),
        ),
        sequence_in_phase=6,
    ),

    # COE issued → employee applies for visa at Japanese consulate
    TaskLibraryEntry(
        task_code="japan_coe_visa_application",
        milestone_type="task_japan_coe_visa",
        phase_key="immigration",
        title="Apply for Japan work visa using COE",
        short_label="Japan visa application",
        default_owner="employee",
        priority="critical",
        depends_on=("japan_coe_preparation",),
        auto_completion_hint="manual",
        why_this_matters=(
            "Once the COE is issued, the employee uses it to apply for the actual "
            "visa sticker at the Japanese consulate in their home country. "
            "Visa processing takes 5–10 business days once the COE is in hand."
        ),
        instructions=(
            "Receive the original COE certificate from Japan HR by post or courier "
            "(originals required — copies are not accepted).",
            "Submit visa application at the Japanese embassy or consulate: "
            "application form, passport, photo, COE original.",
            "Visa is typically issued within 5–10 business days.",
            "Check passport validity: must be valid for the full intended stay.",
        ),
        required_inputs=(
            RequiredInputDef("document", "coe_original", "Original COE certificate"),
            RequiredInputDef("document", "visa_application_form_jp", "Japan visa application form"),
        ),
        sequence_in_phase=6,
    ),

    # Collect Residence Card at port of entry (issued to stays > 3 months)
    TaskLibraryEntry(
        task_code="japan_residence_card",
        milestone_type="task_japan_residence_card",
        phase_key="arrival",
        title="Collect Residence Card at Japan port of entry",
        short_label="Japan Residence Card",
        default_owner="employee",
        priority="critical",
        depends_on=("japan_coe_visa_application",),
        auto_completion_hint="manual",
        why_this_matters=(
            "The Residence Card (在留カード) is issued at major international airports "
            "on arrival. It is the primary ID for foreign residents and required for "
            "municipal registration, bank accounts, and mobile contracts."
        ),
        instructions=(
            "At immigration control, declare you are arriving for a mid-to-long-term "
            "stay — the Residence Card is issued automatically at Narita, Haneda, "
            "Kansai, Chubu, and a few other major airports.",
            "At smaller entry points, a provisional stamp is issued and the card "
            "is sent by post to the registered address.",
            "Keep the Residence Card on your person at all times — legally required.",
        ),
        required_inputs=(
            RequiredInputDef("document", "residence_card_jp", "Japan Residence Card (front + back photo)"),
        ),
        sequence_in_phase=3,
    ),

    # Municipal registration + My Number
    TaskLibraryEntry(
        task_code="japan_municipal_registration",
        milestone_type="task_japan_municipal_reg",
        phase_key="post_arrival",
        title="Register at municipal office and obtain My Number",
        short_label="Japan municipal registration",
        default_owner="employee",
        priority="critical",
        depends_on=("japan_residence_card",),
        auto_completion_hint="manual",
        why_this_matters=(
            "Residents must register at the local municipal office within 14 days "
            "of arrival. This triggers issuance of the My Number (個人番号) card, "
            "which is required for payroll, tax, and social insurance enrollment."
        ),
        instructions=(
            "Visit the local ward / city office with Residence Card and passport.",
            "Complete the move-in notification (転入届).",
            "My Number notification letter arrives by post within ~2 weeks.",
            "Apply for the My Number Card (optional physical card; recommended for "
            "banking and remote ID verification).",
            "Register for National Health Insurance (国民健康保険) if not covered "
            "by employer's social insurance from day one.",
        ),
        required_inputs=(
            RequiredInputDef("document", "residence_card_jp", "Residence Card"),
            RequiredInputDef("profile_field", "japan_address", "Japan home address"),
        ),
        sequence_in_phase=3,
    ),

    # ── P2 SPIKE: EU free movement registration task code ─────────────────────
    # Triggered when regime_id == "eu_free_movement" (EU/EEA national → EU/EEA).
    # No work permit needed, but registration is required in most destinations.
    # ─────────────────────────────────────────────────────────────────────────

    TaskLibraryEntry(
        task_code="eu_registration",
        milestone_type="task_eu_registration",
        phase_key="post_arrival",
        title="Register as EU/EEA resident at local authority",
        short_label="EU resident registration",
        default_owner="employee",
        priority="standard",
        depends_on=(),
        auto_completion_hint="manual",
        why_this_matters=(
            "EU/EEA nationals exercising free movement rights must register with "
            "local authorities within 3 months of arrival in most EU countries. "
            "Registration confirms right-to-reside and is required for bank accounts, "
            "tax registration, and social insurance enrollment."
        ),
        instructions=(
            "Check the destination country's registration authority "
            "(e.g. Empadronamiento in Spain, Anmeldung in Germany, BSN in Netherlands).",
            "Bring: passport or national ID, employment contract, and proof of address.",
            "Timeline: within 3 months of arrival for most EU countries.",
        ),
        required_inputs=(
            RequiredInputDef("document", "employment_contract", "Employment contract"),
            RequiredInputDef("document", "proof_of_address", "Proof of address at destination"),
        ),
        sequence_in_phase=4,
    ),
    # ─────────────────────────────────────────────────────────────────────────

    # ── P5 SPRINT: UK Skilled Worker visa task codes ──────────────────────────
    # Triggered when regime_id == "uk_skilled_worker".
    # Post-Brexit: all overseas nationals (incl. EU citizens) need a Skilled
    # Worker visa. The employer must hold a sponsor licence and assign a
    # Certificate of Sponsorship (CoS) before the visa application can begin.
    # ─────────────────────────────────────────────────────────────────────────

    TaskLibraryEntry(
        task_code="uk_cos_request",
        milestone_type="task_uk_cos_request",
        phase_key="immigration",
        title="Request Certificate of Sponsorship (CoS) from UK employer",
        short_label="CoS request",
        default_owner="hr",
        priority="critical",
        depends_on=(),
        auto_completion_hint="manual",
        why_this_matters=(
            "A valid CoS is mandatory before the employee can apply for a UK "
            "Skilled Worker visa. The employer's HR or sponsor licence holder "
            "assigns it via the Sponsor Management System (SMS). Processing "
            "takes 1–5 business days once requested."
        ),
        instructions=(
            "Confirm the employee's role SOC code appears on the UK eligible "
            "occupations list and meets the minimum salary threshold.",
            "Log into the Sponsor Management System (SMS) and assign a defined "
            "or undefined CoS to the employee.",
            "Share the CoS reference number with the employee for their visa application.",
        ),
        required_inputs=(
            RequiredInputDef("profile_field", "uk_sponsor_licence_confirmed",
                             "Sponsor licence confirmed"),
            RequiredInputDef("profile_field", "uk_soc_code", "SOC occupation code"),
        ),
        sequence_in_phase=1,
    ),

    TaskLibraryEntry(
        task_code="uk_visa_application",
        milestone_type="task_uk_visa_application",
        phase_key="immigration",
        title="Apply for UK Skilled Worker visa online",
        short_label="UK visa application",
        default_owner="employee",
        priority="critical",
        depends_on=("uk_cos_request",),
        auto_completion_hint="manual",
        why_this_matters=(
            "The Skilled Worker visa application is submitted online via gov.uk. "
            "Standard processing takes up to 3 weeks from outside the UK. "
            "A priority service (additional fee) can reduce this to 5 business days."
        ),
        instructions=(
            "Complete the online application at gov.uk/skilled-worker-visa.",
            "Upload: CoS reference number, valid passport, English language evidence, "
            "tuberculosis test results (if required for your country of residence), "
            "and proof of maintenance funds if applicable.",
            "Pay the visa application fee and Immigration Health Surcharge (IHS).",
            "Book the biometric appointment at a UKVCAS centre.",
        ),
        required_inputs=(
            RequiredInputDef("document", "cos_reference", "CoS reference number"),
            RequiredInputDef("document", "passport_uk", "Valid passport"),
        ),
        sequence_in_phase=2,
    ),

    TaskLibraryEntry(
        task_code="uk_biometric_appointment",
        milestone_type="task_uk_biometric_appointment",
        phase_key="immigration",
        title="Attend UKVCAS biometric enrolment appointment",
        short_label="Biometric appointment",
        default_owner="employee",
        priority="critical",
        depends_on=("uk_visa_application",),
        auto_completion_hint="manual",
        why_this_matters=(
            "UK Visas and Citizenship Application Services (UKVCAS) collects "
            "fingerprints and a photograph. The visa decision is usually made "
            "within 3 weeks of the biometric appointment for standard service."
        ),
        instructions=(
            "Book your appointment at a UKVCAS service point — choose a centre "
            "convenient to your current location.",
            "Bring: your passport and any supporting documents uploaded during "
            "the online application.",
            "Enhanced service points offer same-day or next-day appointments "
            "for an additional fee.",
        ),
        required_inputs=(
            RequiredInputDef("document", "passport_uk", "Valid passport"),
        ),
        sequence_in_phase=3,
    ),

    TaskLibraryEntry(
        task_code="uk_brp_collection",
        milestone_type="task_uk_brp_collection",
        phase_key="arrival",
        title="Collect Biometric Residence Permit (BRP) on arrival in the UK",
        short_label="BRP collection",
        default_owner="employee",
        priority="critical",
        depends_on=("uk_biometric_appointment",),
        auto_completion_hint="manual",
        why_this_matters=(
            "The BRP is your physical proof of right to work and live in the UK. "
            "It must be collected from the Post Office branch specified in your "
            "visa decision letter within 10 days of arrival (or by the BRP "
            "collection deadline printed on the sticker in your passport)."
        ),
        instructions=(
            "Locate the Post Office branch shown in your visa decision letter.",
            "Bring your passport and visa decision letter to collect the BRP.",
            "Check the BRP details immediately and report any errors to the "
            "Home Office within 5 days.",
        ),
        required_inputs=(
            RequiredInputDef("document", "visa_decision_letter", "Visa decision letter"),
        ),
        sequence_in_phase=1,
    ),

    TaskLibraryEntry(
        task_code="uk_right_to_work_check",
        milestone_type="task_uk_right_to_work_check",
        phase_key="post_arrival",
        title="Employer conducts statutory Right to Work check",
        short_label="Right to Work check",
        default_owner="hr",
        priority="critical",
        depends_on=("uk_brp_collection",),
        auto_completion_hint="manual",
        why_this_matters=(
            "UK employers have a legal duty to check that every employee has the "
            "right to work in the UK before employment begins. Failure to conduct "
            "the check correctly can result in a civil penalty of up to £60,000 "
            "per illegal worker."
        ),
        instructions=(
            "Conduct the check using the Home Office online service "
            "(right-to-work-in-great-britain-check) — requires the employee's "
            "share code generated from their UKVI account.",
            "Record the check date and retain a copy of the confirmation for the "
            "duration of employment plus 2 years.",
            "Alternatively, check the BRP or eVisa digitally via the Employer "
            "Checking Service.",
        ),
        required_inputs=(
            RequiredInputDef("document", "brp_or_eVisa", "BRP or eVisa confirmation"),
        ),
        sequence_in_phase=1,
    ),
    # ─────────────────────────────────────────────────────────────────────────
)

TASK_BY_CODE: Dict[str, TaskLibraryEntry] = {t.task_code: t for t in _TASK_LIBRARY_SEQ}
TASK_BY_MILESTONE_TYPE: Dict[str, TaskLibraryEntry] = {t.milestone_type: t for t in _TASK_LIBRARY_SEQ}

# Representative per-task-type effort estimate (the "~10 min" shown on the roadmap).
# Library-level approximations (always rendered with a "~"), not per-case data.
_ESTIMATED_EFFORT: Final[Mapping[str, str]] = {
    # Pre-departure
    "confirm_employee_core_profile": "~5 min",
    "confirm_family_details": "~10 min",
    "upload_passport_copy": "~5 min",
    "upload_assignment_letter": "~5 min",
    "verify_destination_route": "~10 min",
    # Immigration (generic)
    "hr_review_case_data": "~1 day",
    "schedule_immigration_review": "~15 min",
    "prepare_visa_pack": "~2 days",
    "submit_visa_application": "~1 day",
    "book_biometrics": "~20 min",
    # Logistics
    "arrange_temporary_housing": "~30 min",
    "arrange_movers": "~45 min",
    "coordinate_relocation_providers": "~30 min",
    "plan_travel": "~30 min",
    # Arrival / post-arrival
    "complete_arrival_registration": "~20 min",
    "tax_local_registration": "~1 hour",
    "settle_in": "",
    # Family / schooling
    "school_enrollment_research": "~1 hour",
    "school_enrollment_application": "~45 min",
    "spouse_work_authorization": "~30 min",
    "partner_family_visa_application": "~1 hour",
    "partner_mvv_application": "~1 hour",
    "dependent_visa_application": "~1 hour",
    # US L-1B corridor
    "l1b_support_letter": "~1 day",
    "l1b_petition_preparation": "~3 days",
    "l1b_petition_filing": "~1 day",
    "l1b_visa_interview": "~1 hour",
    "l1b_port_of_entry": "~30 min",
    "l1b_ssn_application": "~20 min",
    # Japan corridor
    "japan_coe_preparation": "~2 days",
    "japan_coe_visa_application": "~1 day",
    "japan_residence_card": "~30 min",
    "japan_municipal_registration": "~1 hour",
    # EU / UK corridor
    "eu_registration": "~30 min",
    "uk_cos_request": "~1 day",
    "uk_visa_application": "~1 hour",
    "uk_biometric_appointment": "~20 min",
    "uk_brp_collection": "~20 min",
    "uk_right_to_work_check": "~15 min",
}


def estimated_effort_for(task_code: str) -> Optional[str]:
    """Representative effort label for a task code, e.g. "~10 min". None when the
    task has no meaningful estimate (open-ended) or the code is unknown."""
    val = _ESTIMATED_EFFORT.get((task_code or "").strip())
    return val or None


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
