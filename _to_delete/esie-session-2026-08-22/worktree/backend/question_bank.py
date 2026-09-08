from __future__ import annotations

from typing import List, Dict, Any, Optional
from .schemas import Question, QuestionOption


# ─── S3 SPIKE: contract_type + move_type discriminator ───────────────────────
# These two questions are asked first in the intake flow. They gate everything
# downstream: plan scope, phase activation, family propagation, and immigration
# workstream selection. Do not reorder them below the existing questions.
#
# mapsTo paths write into wizard_draft["assignment"]["contractType"] and
# wizard_draft["assignment"]["moveType"] — these are NEW paths that do not
# conflict with any existing question's mapsTo.

CONTRACT_TYPE_OPTIONS = [
    QuestionOption(value="lta",               label="Long-term assignment (12–36 months)"),
    QuestionOption(value="permanent_transfer", label="Permanent transfer — no planned return"),
    QuestionOption(value="short_term_project", label="Short-term project or secondment (< 6 months)"),
    QuestionOption(value="domestic_move",      label="Moving within the same country"),
    QuestionOption(value="repatriation",       label="Returning to my home country"),
    QuestionOption(value="remote_worker",      label="Working remotely — no employer sponsorship"),
    QuestionOption(value="self_employed",      label="Self-employed / contractor / freelancer"),
    QuestionOption(value="student",            label="Student"),
]

MOVE_TYPE_OPTIONS = [
    QuestionOption(value="international", label="Crossing an international border"),
    QuestionOption(value="domestic",      label="Moving within the same country"),
    QuestionOption(value="return",        label="Returning to my home country"),
]

ASSIGNMENT_END_OPTIONS = [
    QuestionOption(value="6",  label="6 months"),
    QuestionOption(value="12", label="1 year"),
    QuestionOption(value="18", label="18 months"),
    QuestionOption(value="24", label="2 years"),
    QuestionOption(value="36", label="3 years"),
    QuestionOption(value="48", label="4+ years"),
    QuestionOption(value="indefinite", label="No fixed end date (permanent)"),
]

# S3 EARLY QUESTIONS — prepended to QUESTION_BANK so they are asked first
S3_QUESTIONS: List[Question] = [
    # S3-1: What kind of move is this?
    # contract_type is the primary discriminator for plan scope.
    # domestic_move → suppress immigration phase entirely.
    # short_term_project → suppress most logistics and post_arrival steps.
    Question(
        id="q_contract_type",
        title="What best describes your relocation situation?",
        whyThisMatters="This determines which steps and permits apply to your move. "
                       "A long-term assignment has different requirements to a permanent transfer.",
        type="single_select",
        required=True,
        mapsTo="assignment.contractType",
        options=CONTRACT_TYPE_OPTIONS,
        allowUnknown=False,
    ),

    # S3-2: Origin and destination countries (if not already captured by the wizard route screen)
    # dependsOn: none — asked unconditionally as a confirmation step.
    # Note: origin_country / dest_country already exist in wizard_cases; this question
    # captures the user-facing confirmation and writes into the draft profile.
    Question(
        id="q_destination_country",
        title="Which country are you moving to?",
        whyThisMatters="Immigration requirements, tax obligations, and housing regulations differ "
                       "significantly by destination country.",
        type="text",
        required=True,
        mapsTo="movePlan.destinationCountry",
        allowUnknown=False,
        dependsOn={"q_contract_type": {"not": "domestic_move"}},
    ),

    # S3-3: Assignment end date — needed for due_date system (S2) and repat triggers (S7).
    # Only shown for time-limited assignments; suppressed for permanent_transfer and domestic_move.
    Question(
        id="q_assignment_end",
        title="How long is your assignment expected to last?",
        whyThisMatters="We use this to schedule reminders, plan your return, and ensure your visa "
                       "covers the full assignment period.",
        type="single_select",
        required=True,
        mapsTo="assignment.expectedDurationMonths",
        options=ASSIGNMENT_END_OPTIONS,
        allowUnknown=True,
        dependsOn={
            "q_contract_type": {
                "in": ["lta", "short_term_project", "student", "remote_worker", "self_employed"]
            }
        },
    ),
]
# ─────────────────────────────────────────────────────────────────────────────


# ─── P4 SPRINT: Immigration-specific questions ────────────────────────────────
# These questions feed ExceptionRequestService with the profile fields it needs
# to fire real exception flags in production (not just in tests).
#
# Gating strategy:
#   • q_destination_region (P4-0) — structured classifier replacing free-text
#     q_destination_country for immigration decisions. Gated on LTA/permanent
#     contract types. Its value gates all downstream P4 questions.
#   • US-specific: q_us_entity_confirmed, q_specialized_knowledge_documented
#     — gated on q_destination_region == "united_states"
#   • Japan-specific: q_japan_visa_category
#     — gated on q_destination_region == "japan"
#   • Cross-regime: q_employment_tenure_months, q_estimated_package_cost
#     — gated on LTA or permanent_transfer contract type
#   • UK-specific: q_uk_sponsor_licence_confirmed, q_uk_points_threshold_confirmed
#     — gated on q_destination_region == "united_kingdom"
#
# mapsTo paths all live under assignment.* (employer/assignment data):
#   assignment.destinationRegion
#   assignment.employmentTenureMonths
#   assignment.usEntityConfirmed
#   assignment.specializedKnowledgeDocumented
#   assignment.japanVisaCategory
#   assignment.estimatedPackageCostBand
#   assignment.ukSponsorLicenceConfirmed
#   assignment.ukPointsThresholdConfirmed

_P4_LTA_TYPES = ["lta", "permanent_transfer"]

P4_QUESTIONS: List[Question] = [
    # P4-0: Destination region classifier
    # Gives the orchestrator a clean enum to gate downstream immigration Qs on.
    # Asked for any long-term / permanent assignment (not domestic, not student).
    Question(
        id="q_destination_region",
        title="Which best describes your destination for immigration purposes?",
        whyThisMatters="Immigration rules, visa categories, and processing times differ "
                       "significantly by destination. This helps us ask the right follow-up "
                       "questions for your specific route.",
        type="single_select",
        required=True,
        mapsTo="assignment.destinationRegion",
        options=[
            QuestionOption(value="united_states", label="United States"),
            QuestionOption(value="japan",         label="Japan"),
            QuestionOption(value="eu_eea",        label="EU / EEA country (incl. Switzerland)"),
            QuestionOption(value="united_kingdom", label="United Kingdom"),
            QuestionOption(value="canada",        label="Canada"),
            QuestionOption(value="australia",     label="Australia / New Zealand"),
            QuestionOption(value="singapore",     label="Singapore"),
            QuestionOption(value="other",         label="Another country"),
        ],
        allowUnknown=False,
        dependsOn={"q_contract_type": {"in": _P4_LTA_TYPES}},
    ),

    # P4-1: Employment tenure — needed for L1B (min 12 months) and Japan COE (ICT).
    # Asked for all LTA/permanent cases regardless of destination.
    Question(
        id="q_employment_tenure_months",
        title="How many months have you worked continuously for your current employer?",
        whyThisMatters="Many work visa categories — including the US L1B and Japan ICT — require "
                       "at least 12 months of continuous employment with the same company. "
                       "Cases below this threshold need HR review before proceeding.",
        type="single_select",
        required=True,
        mapsTo="assignment.employmentTenureMonths",
        options=[
            QuestionOption(value="3",  label="Less than 6 months"),
            QuestionOption(value="6",  label="6 – 11 months"),
            QuestionOption(value="12", label="12 months (1 year) — at the threshold"),
            QuestionOption(value="18", label="18 months"),
            QuestionOption(value="24", label="2 years"),
            QuestionOption(value="36", label="3 years"),
            QuestionOption(value="48", label="4 years or more"),
        ],
        allowUnknown=False,
        dependsOn={"q_contract_type": {"in": _P4_LTA_TYPES}},
    ),

    # P4-2: US petitioner entity — blocker check for L1B.
    # Only asked when destination is the United States.
    Question(
        id="q_us_entity_confirmed",
        title="Has the US legal entity that will sponsor the employee been confirmed?",
        whyThisMatters="An L1B petition requires a named US employer (petitioner) with a valid "
                       "EIN and authorised signatory. Without this, no USCIS filing is possible — "
                       "confirming the entity early avoids a costly delay.",
        type="boolean",
        required=True,
        mapsTo="assignment.usEntityConfirmed",
        allowUnknown=True,
        dependsOn={"q_destination_region": "united_states"},
    ),

    # P4-3: Specialised knowledge documentation — warning check for L1B.
    # USCIS scrutinises L1B petitions heavily on this point.
    Question(
        id="q_specialized_knowledge_documented",
        title="Has the employee's specialised knowledge been documented (patents, certifications, "
              "proprietary process docs)?",
        whyThisMatters="L1B petitions are frequently challenged on specialised knowledge. "
                       "Cases without documented evidence have a significantly higher rate of "
                       "USCIS Requests for Evidence (RFEs), which add 2–4 months to processing.",
        type="boolean",
        required=True,
        mapsTo="assignment.specializedKnowledgeDocumented",
        allowUnknown=True,
        dependsOn={"q_destination_region": "united_states"},
    ),

    # P4-4: Japan visa sub-category — role_category_ambiguous check.
    # Only asked when destination is Japan.
    Question(
        id="q_japan_visa_category",
        title="Which Japan work visa category applies to this role?",
        whyThisMatters="Choosing the wrong category delays the Certificate of Eligibility (COE) "
                       "application. ESHS covers most engineering, IT, finance, and management "
                       "roles; ICT (Intra-company Transferee) requires 1+ year at the company.",
        type="single_select",
        required=True,
        mapsTo="assignment.japanVisaCategory",
        options=[
            QuestionOption(
                value="eshs",
                label="ESHS — Engineer / Specialist in Humanities / International Services",
            ),
            QuestionOption(
                value="ict",
                label="ICT — Intra-company Transferee (requires 1+ year with the company)",
            ),
            QuestionOption(
                value="specified_skilled",
                label="Specified Skilled Worker (SSW) — sector-specific",
            ),
            QuestionOption(
                value="unknown",
                label="Not sure — needs immigration counsel review",
            ),
        ],
        allowUnknown=False,
        dependsOn={"q_destination_region": "japan"},
    ),

    # P4-5: Estimated package cost band — cost_threshold check (all regimes).
    # Band → numeric midpoint mapping is handled in wizard_draft_mapper.py.
    Question(
        id="q_estimated_package_cost",
        title="What is the estimated total relocation package cost (including allowances, "
              "flights, and housing support)?",
        whyThisMatters="Packages over $150,000 require Finance and HR leadership sign-off "
                       "before any supplier commitments are made.",
        type="single_select",
        required=True,
        mapsTo="assignment.estimatedPackageCostBand",
        options=[
            QuestionOption(value="under_50k",   label="Under $50,000"),
            QuestionOption(value="50k_100k",    label="$50,000 – $100,000"),
            QuestionOption(value="100k_150k",   label="$100,000 – $150,000"),
            QuestionOption(value="150k_200k",   label="$150,000 – $200,000 (sign-off required)"),
            QuestionOption(value="over_200k",   label="Over $200,000 (sign-off required)"),
        ],
        allowUnknown=True,
        dependsOn={"q_contract_type": {"in": _P4_LTA_TYPES}},
    ),

    # P5-0: UK Sponsor Licence — no_sponsoring_entity blocker for Skilled Worker.
    # The employer must hold an active Sponsor Licence before a CoS can be assigned.
    Question(
        id="q_uk_sponsor_licence_confirmed",
        title="Has the employer confirmed it holds an active UK Sponsor Licence?",
        whyThisMatters="A UK Skilled Worker visa cannot proceed without a Certificate of "
                       "Sponsorship (CoS), which can only be assigned by an employer with an "
                       "active Home Office Sponsor Licence. Confirming this early prevents "
                       "a costly last-minute delay.",
        type="boolean",
        required=True,
        mapsTo="assignment.ukSponsorLicenceConfirmed",
        allowUnknown=True,
        dependsOn={"q_destination_region": "united_kingdom"},
    ),

    # P5-1: UK points threshold — points_threshold_unconfirmed warning.
    # Employee must score ≥70 points; HR should verify before assigning the CoS.
    Question(
        id="q_uk_points_threshold_confirmed",
        title="Has the employee's eligibility under the UK points-based system been confirmed "
              "(≥70 points: job offer + skill level + English language + salary)?",
        whyThisMatters="UK Skilled Worker visa applicants must score at least 70 points. "
                       "The key checks are: licensed sponsor (20 pts), role at RQF Level 3+ "
                       "(20 pts), English language (10 pts), and salary meeting the higher of "
                       "the general threshold or the going rate for the SOC code. "
                       "Unresolved gaps should be caught before the CoS is assigned.",
        type="boolean",
        required=True,
        mapsTo="assignment.ukPointsThresholdConfirmed",
        allowUnknown=True,
        dependsOn={"q_destination_region": "united_kingdom"},
    ),
]
# ─────────────────────────────────────────────────────────────────────────────


SINGAPORE_AREAS = [
    "Tanglin", "Holland Village", "Bukit Timah", "River Valley", 
    "Novena", "East Coast", "Tiong Bahru"
]

HOUSING_MUST_HAVES = [
    "Furnished", "Near MRT", "Near schools", "Gym/pool", 
    "Playground", "Parking"
]

SCHOOLING_PRIORITIES = [
    "Close to home", "Academic excellence", "Language support", 
    "Extracurriculars", "Class size"
]

SPECIAL_ITEMS = [
    "Piano", "Bicycles", "Artwork", "Antiques", "Sports equipment"
]


QUESTION_BANK: List[Question] = [
    # ── S3 SPIKE: early discriminators (must come first) ──────────────────────
    *S3_QUESTIONS,
    # ─────────────────────────────────────────────────────────────────────────

    # ── S4 SPIKE: family gating questions ─────────────────────────────────────
    # These MUST be asked before the existing detailed spouse/child questions.
    # They act as gates: q_has_spouse gates all spouse questions; q_child_count
    # gates all child questions. Without these, the orchestrator asks about
    # children even for single people.

    # S4-1: Is there a spouse / partner travelling with the employee?
    Question(
        id="q_has_spouse",
        title="Will your partner or spouse be moving with you?",
        whyThisMatters="If your partner is relocating with you, they may need their own visa, "
                       "work authorisation, or residency registration.",
        type="boolean",
        required=True,
        mapsTo="family.hasSpouse",
        allowUnknown=False,
    ),

    # S4-2: How many children are relocating?
    # This is a gate: if 0, all child questions are skipped.
    Question(
        id="q_child_count",
        title="How many children will be relocating with you?",
        whyThisMatters="The number of children affects school enrollment, dependent visas, "
                       "and housing requirements.",
        type="single_select",
        required=True,
        mapsTo="family.childCount",
        options=[
            QuestionOption(value="0", label="None — relocating without children"),
            QuestionOption(value="1", label="1 child"),
            QuestionOption(value="2", label="2 children"),
            QuestionOption(value="3", label="3 children"),
            QuestionOption(value="4+", label="4 or more children"),
        ],
        allowUnknown=False,
    ),

    # S4-3: Does the partner intend to work in the destination country?
    # Only asked if has_spouse = true. Drives the spouse_work_authorization workstream.
    Question(
        id="q_spouse_employment_intent",
        title="Does your partner intend to work in the destination country?",
        whyThisMatters="If your partner wants to work, they will need their own work authorisation "
                       "separate from your visa — the timeline for this can be several months.",
        type="single_select",
        required=True,
        mapsTo="family.spouseEmploymentIntent",
        options=[
            QuestionOption(value="yes",     label="Yes — they plan to work"),
            QuestionOption(value="no",      label="No — they will not work"),
            QuestionOption(value="unknown", label="Not decided yet"),
        ],
        allowUnknown=False,
        dependsOn={"q_has_spouse": True},
    ),

    # S4-4: What is the partner's visa / residence status?
    # Only asked if has_spouse = true. Critical for MVV (Netherlands), family
    # reunification (France, Germany), and dependent visa routes (SG, UK, US).
    Question(
        id="q_partner_visa_status",
        title="What is your partner's nationality or current residence status?",
        whyThisMatters="Non-EU partners moving to an EU country often need a separate family "
                       "visa (e.g. Dutch MVV, French carte de séjour) which can take 3–6 months.",
        type="single_select",
        required=True,
        mapsTo="family.partnerVisaStatus",
        options=[
            QuestionOption(value="eu_citizen",         label="EU / EEA / Swiss citizen"),
            QuestionOption(value="non_eu_with_permit", label="Non-EU with valid residence permit"),
            QuestionOption(value="non_eu_no_permit",   label="Non-EU without a current permit"),
            QuestionOption(value="same_as_employee",   label="Same nationality as me"),
            QuestionOption(value="unknown",            label="Not sure"),
        ],
        allowUnknown=False,
        dependsOn={"q_has_spouse": True},
    ),
    # ─────────────────────────────────────────────────────────────────────────

    # ── P4 SPRINT: immigration-specific intake questions ──────────────────────
    # These gate the ExceptionRequestService with real profile data.
    # Must come after S3/S4 questions (q_contract_type must be answered first).
    *P4_QUESTIONS,
    # ─────────────────────────────────────────────────────────────────────────

    # 1. Target arrival date
    Question(
        id="q_target_arrival_date",
        title="When do you plan to arrive at your destination?",
        whyThisMatters="This helps us plan housing, school enrollment, and your moving timeline.",
        type="date",
        required=True,
        mapsTo="movePlan.targetArrivalDate",
        allowUnknown=True
    ),
    
    # 2. Assignment start date
    Question(
        id="q_assignment_start_date",
        title="When does your assignment start?",
        whyThisMatters="Your work authorization timing depends on this date.",
        type="date",
        required=True,
        mapsTo="primaryApplicant.assignment.startDate",
        allowUnknown=False
    ),
    
    # 3. Assignment duration
    Question(
        id="q_assignment_duration",
        title="How long is your assignment expected to last?",
        whyThisMatters="This affects housing lease terms and school enrollment decisions.",
        type="single_select",
        required=True,
        mapsTo="primaryApplicant.assignment.expectedDurationMonths",
        options=[
            QuestionOption(value="12", label="1 year"),
            QuestionOption(value="24", label="2 years"),
            QuestionOption(value="36", label="3 years"),
            QuestionOption(value="48", label="4+ years"),
        ],
        allowUnknown=True
    ),
    
    # 4. Primary applicant name
    Question(
        id="q_primary_name",
        title="What is your full name (primary applicant)?",
        whyThisMatters="We need this for immigration documents and housing applications.",
        type="text",
        required=True,
        mapsTo="primaryApplicant.fullName",
        allowUnknown=False
    ),
    
    # 5. Primary nationality
    Question(
        id="q_primary_nationality",
        title="What is your nationality?",
        whyThisMatters="Immigration requirements vary by nationality.",
        type="text",
        required=True,
        mapsTo="primaryApplicant.nationality",
        allowUnknown=False
    ),
    
    # 6. Primary DOB
    Question(
        id="q_primary_dob",
        title="What is your date of birth?",
        whyThisMatters="Required for passport and work permit verification.",
        type="date",
        required=True,
        mapsTo="primaryApplicant.dateOfBirth",
        allowUnknown=False
    ),
    
    # 7. Passport expiry
    Question(
        id="q_passport_expiry",
        title="When does your passport expire?",
        whyThisMatters="Your passport must be valid for at least 6 months beyond your arrival date.",
        type="date",
        required=True,
        mapsTo="primaryApplicant.passport.expiryDate",
        allowUnknown=False
    ),
    
    # 8. Role title
    Question(
        id="q_role_title",
        title="What is your role title at your employer?",
        whyThisMatters="This helps determine your work authorization category and housing budget guidance.",
        type="text",
        required=True,
        mapsTo="primaryApplicant.employer.roleTitle",
        allowUnknown=False
    ),
    
    # 9. Salary band
    Question(
        id="q_salary_band",
        title="What is your salary range per year?",
        whyThisMatters="This affects work authorization eligibility and helps us recommend suitable housing.",
        type="single_select",
        required=True,
        mapsTo="primaryApplicant.employer.salaryBand",
        options=[
            QuestionOption(value="60000-100000", label="60k - 100k"),
            QuestionOption(value="100000-150000", label="100k - 150k"),
            QuestionOption(value="150000-200000", label="150k - 200k"),
            QuestionOption(value="200000+", label="200k+"),
        ],
        allowUnknown=True
    ),
    
    # 10. Relocation package
    Question(
        id="q_relocation_package",
        title="Does your employer provide a relocation package?",
        whyThisMatters="This helps us understand what support you already have for moving and housing.",
        type="boolean",
        required=True,
        mapsTo="primaryApplicant.assignment.relocationPackage",
        allowUnknown=True
    ),
    
    # 11. Spouse name — gated: only asked if q_has_spouse = true
    Question(
        id="q_spouse_name",
        title="What is your spouse's full name?",
        whyThisMatters="Required for dependent pass application.",
        type="text",
        required=True,
        mapsTo="spouse.fullName",
        allowUnknown=False,
        dependsOn={"q_has_spouse": True},
    ),

    # 12. Spouse nationality — gated: only asked if q_has_spouse = true
    Question(
        id="q_spouse_nationality",
        title="What is your spouse's nationality?",
        whyThisMatters="Affects dependent pass eligibility and work authorization.",
        type="text",
        required=True,
        mapsTo="spouse.nationality",
        allowUnknown=False,
        dependsOn={"q_has_spouse": True},
    ),

    # 13. Spouse occupation — gated: only asked if q_has_spouse = true
    Question(
        id="q_spouse_occupation",
        title="What is your spouse's current occupation?",
        whyThisMatters="This helps us guide job search and work authorization options.",
        type="text",
        required=False,
        mapsTo="spouse.occupation",
        allowUnknown=True,
        dependsOn={"q_has_spouse": True},
    ),

    # 14-15. Children info — gated: only asked if q_child_count > 0
    Question(
        id="q_child1_name",
        title="What is your first child's name?",
        whyThisMatters="Required for school applications and dependent pass.",
        type="text",
        required=True,
        mapsTo="dependents.0.firstName",
        allowUnknown=False,
        dependsOn={"q_child_count": {"gte": 1}},
    ),

    Question(
        id="q_child1_dob",
        title="What is your first child's date of birth?",
        whyThisMatters="Determines school grade placement and age-appropriate school options.",
        type="date",
        required=True,
        mapsTo="dependents.0.dateOfBirth",
        allowUnknown=False,
        dependsOn={"q_child_count": {"gte": 1}},
    ),

    Question(
        id="q_child2_name",
        title="What is your second child's name?",
        whyThisMatters="Required for school applications and dependent pass.",
        type="text",
        required=True,
        mapsTo="dependents.1.firstName",
        allowUnknown=False,
        dependsOn={"q_child_count": {"gte": 2}},
    ),

    Question(
        id="q_child2_dob",
        title="What is your second child's date of birth?",
        whyThisMatters="Determines school grade placement and age-appropriate school options.",
        type="date",
        required=True,
        mapsTo="dependents.1.dateOfBirth",
        allowUnknown=False,
        dependsOn={"q_child_count": {"gte": 2}},
    ),
    
    # Housing questions
    Question(
        id="q_move_in_date",
        title="When would you like to move into your temporary housing?",
        whyThisMatters="We'll find apartments available from this date.",
        type="date",
        required=True,
        mapsTo="movePlan.housing.desiredMoveInDate",
        allowUnknown=True
    ),
    
    Question(
        id="q_temporary_stay_weeks",
        title="How many weeks do you need temporary housing?",
        whyThisMatters="Most families need 4-8 weeks to find permanent housing.",
        type="single_select",
        required=True,
        mapsTo="movePlan.housing.temporaryStayWeeks",
        options=[
            QuestionOption(value="4", label="4 weeks"),
            QuestionOption(value="6", label="6 weeks"),
            QuestionOption(value="8", label="8 weeks"),
            QuestionOption(value="12", label="12 weeks"),
        ],
        allowUnknown=True
    ),
    
    Question(
        id="q_housing_budget",
        title="What is your monthly housing budget?",
        whyThisMatters="Housing varies widely; this helps us show realistic options.",
        type="single_select",
        required=True,
        mapsTo="movePlan.housing.budgetMonthlySGD",
        options=[
            QuestionOption(value="3000-5000", label="3,000 - 5,000"),
            QuestionOption(value="5000-7000", label="5,000 - 7,000"),
            QuestionOption(value="7000-10000", label="7,000 - 10,000"),
            QuestionOption(value="10000+", label="10,000+"),
        ],
        allowUnknown=True
    ),
    
    Question(
        id="q_bedrooms",
        title="How many bedrooms do you need?",
        whyThisMatters="For a family of four, most choose 3-4 bedrooms.",
        type="single_select",
        required=True,
        mapsTo="movePlan.housing.bedroomsMin",
        options=[
            QuestionOption(value="3", label="3 bedrooms"),
            QuestionOption(value="4", label="4 bedrooms"),
            QuestionOption(value="5", label="5+ bedrooms"),
        ],
        allowUnknown=False
    ),
    
    Question(
        id="q_preferred_areas",
        title="Which neighborhoods interest you? (Select all that apply)",
        whyThisMatters="Different areas suit different lifestyles and school locations.",
        type="multi_select",
        required=False,
        mapsTo="movePlan.housing.preferredAreas",
        options=[QuestionOption(value=area, label=area) for area in SINGAPORE_AREAS],
        allowUnknown=True
    ),
    
    Question(
        id="q_housing_must_haves",
        title="What housing features are must-haves? (Select all that apply)",
        whyThisMatters="We'll prioritize apartments with these features.",
        type="multi_select",
        required=False,
        mapsTo="movePlan.housing.mustHave",
        options=[QuestionOption(value=item, label=item) for item in HOUSING_MUST_HAVES],
        allowUnknown=False
    ),
    
    # School questions
    Question(
        id="q_school_start_date",
        title="When should your children start school?",
        whyThisMatters="School applications can take 2-3 months; early applications are recommended.",
        type="date",
        required=True,
        mapsTo="movePlan.schooling.schoolingStartDate",
        allowUnknown=True
    ),
    
    Question(
        id="q_curriculum_preference",
        title="What curriculum do you prefer for your children?",
        whyThisMatters="Different schools offer different curricula; this narrows your choices.",
        type="single_select",
        required=True,
        mapsTo="movePlan.schooling.curriculumPreference",
        options=[
            QuestionOption(value="IB", label="International Baccalaureate (IB)"),
            QuestionOption(value="UK", label="British (IGCSE/A-Levels)"),
            QuestionOption(value="US", label="American"),
            QuestionOption(value="Local", label="Local curriculum"),
            QuestionOption(value="No preference", label="No preference"),
        ],
        allowUnknown=True
    ),
    
    Question(
        id="q_school_budget",
        title="What is your annual school budget per child?",
        whyThisMatters="International schools range widely by location.",
        type="single_select",
        required=True,
        mapsTo="movePlan.schooling.budgetAnnualSGD",
        options=[
            QuestionOption(value="15000-25000", label="15k - 25k"),
            QuestionOption(value="25000-35000", label="25k - 35k"),
            QuestionOption(value="35000-45000", label="35k - 45k"),
            QuestionOption(value="45000+", label="45k+"),
        ],
        allowUnknown=True
    ),
    
    Question(
        id="q_school_priorities",
        title="What are your top priorities for schools? (Select up to 3)",
        whyThisMatters="We'll rank schools based on your priorities.",
        type="multi_select",
        required=False,
        mapsTo="movePlan.schooling.priorities",
        options=[QuestionOption(value=p, label=p) for p in SCHOOLING_PRIORITIES],
        allowUnknown=True
    ),
    
    # Moving questions
    Question(
        id="q_inventory_size",
        title="How would you describe your household inventory?",
        whyThisMatters="This determines container size and shipping costs.",
        type="single_select",
        required=True,
        mapsTo="movePlan.movers.inventoryRough",
        options=[
            QuestionOption(value="small", label="Small (1-2 bedroom apartment)"),
            QuestionOption(value="medium", label="Medium (3 bedroom house)"),
            QuestionOption(value="large", label="Large (4+ bedroom house)"),
        ],
        allowUnknown=False
    ),
    
    Question(
        id="q_special_items",
        title="Do you have any special items to ship? (Select all that apply)",
        whyThisMatters="Special items need extra care and may affect insurance.",
        type="multi_select",
        required=False,
        mapsTo="movePlan.movers.specialItems",
        options=[QuestionOption(value=item, label=item) for item in SPECIAL_ITEMS],
        allowUnknown=False
    ),
    
    Question(
        id="q_storage_needed",
        title="Will you need storage during the move?",
        whyThisMatters="Some movers offer storage for items that won't fit in temporary housing.",
        type="boolean",
        required=True,
        mapsTo="movePlan.movers.storageNeeded",
        allowUnknown=True
    ),
    
    Question(
        id="q_insurance_needed",
        title="Do you want comprehensive moving insurance?",
        whyThisMatters="Insurance covers damage or loss during international shipping.",
        type="boolean",
        required=True,
        mapsTo="movePlan.movers.insuranceNeeded",
        allowUnknown=True
    ),
    
    # Document questions
    Question(
        id="q_has_passport_scans",
        title="Do you have digital scans of all family passports?",
        whyThisMatters="These are required for all visa and work permit applications.",
        type="boolean",
        required=True,
        mapsTo="complianceDocs.hasPassportScans",
        allowUnknown=False
    ),
    
    Question(
        id="q_has_marriage_cert",
        title="Do you have a copy of your marriage certificate?",
        whyThisMatters="Required for dependent pass applications.",
        type="boolean",
        required=True,
        mapsTo="complianceDocs.hasMarriageCertificate",
        allowUnknown=False
    ),
    
    Question(
        id="q_has_birth_certs",
        title="Do you have birth certificates for both children?",
        whyThisMatters="Required for dependent passes and school enrollment.",
        type="boolean",
        required=True,
        mapsTo="complianceDocs.hasBirthCertificates",
        allowUnknown=False
    ),
    
    Question(
        id="q_has_employment_letter",
        title="Do you have an employment letter from your employer?",
        whyThisMatters="Required for work authorization; should state role, salary, and start date.",
        type="boolean",
        required=True,
        mapsTo="complianceDocs.hasEmploymentLetter",
        allowUnknown=False
    ),
]


def get_question_by_id(question_id: str) -> Question:
    """Get a question by its ID."""
    for q in QUESTION_BANK:
        if q.id == question_id:
            return q
    return None


def get_all_questions(skip_ids: Optional[set] = None) -> List[Question]:
    """Get all questions, optionally skipping IDs for scenario logic."""
    if not skip_ids:
        return QUESTION_BANK
    return [question for question in QUESTION_BANK if question.id not in skip_ids]
