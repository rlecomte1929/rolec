from typing import List, Dict, Any
from schemas import Question, QuestionOption


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
    # 1. Target arrival date
    Question(
        id="q_target_arrival_date",
        title="When do you plan to arrive in Singapore?",
        whyThisMatters="This helps us plan your housing, school enrollment, and moving timeline.",
        type="date",
        required=True,
        mapsTo="movePlan.targetArrivalDate",
        allowUnknown=True
    ),
    
    # 2. Assignment start date
    Question(
        id="q_assignment_start_date",
        title="When does your Singapore assignment start?",
        whyThisMatters="Your work permit application timing depends on this date.",
        type="date",
        required=True,
        mapsTo="primaryApplicant.assignment.startDate",
        allowUnknown=False
    ),
    
    # 3. Assignment duration
    Question(
        id="q_assignment_duration",
        title="How long is your Singapore assignment expected to last?",
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
        title="What is your role title at Norwegian Investment?",
        whyThisMatters="This helps determine your work permit category and housing budget guidance.",
        type="text",
        required=True,
        mapsTo="primaryApplicant.employer.roleTitle",
        allowUnknown=False
    ),
    
    # 9. Salary band
    Question(
        id="q_salary_band",
        title="What is your salary range in SGD per year?",
        whyThisMatters="This affects work permit eligibility and helps us recommend suitable housing.",
        type="single_select",
        required=True,
        mapsTo="primaryApplicant.employer.salaryBand",
        options=[
            QuestionOption(value="60000-100000", label="SGD 60k - 100k"),
            QuestionOption(value="100000-150000", label="SGD 100k - 150k"),
            QuestionOption(value="150000-200000", label="SGD 150k - 200k"),
            QuestionOption(value="200000+", label="SGD 200k+"),
        ],
        allowUnknown=True
    ),
    
    # 10. Relocation package
    Question(
        id="q_relocation_package",
        title="Does Norwegian Investment provide a relocation package?",
        whyThisMatters="This helps us understand what support you already have for moving and housing.",
        type="boolean",
        required=True,
        mapsTo="primaryApplicant.assignment.relocationPackage",
        allowUnknown=True
    ),
    
    # 11. Spouse name
    Question(
        id="q_spouse_name",
        title="What is your wife's full name?",
        whyThisMatters="Required for dependent pass application.",
        type="text",
        required=True,
        mapsTo="spouse.fullName",
        allowUnknown=False
    ),
    
    # 12. Spouse nationality
    Question(
        id="q_spouse_nationality",
        title="What is your wife's nationality?",
        whyThisMatters="Affects dependent pass eligibility and work authorization.",
        type="text",
        required=True,
        mapsTo="spouse.nationality",
        allowUnknown=False
    ),
    
    # 13. Spouse occupation
    Question(
        id="q_spouse_occupation",
        title="What is your wife's current occupation?",
        whyThisMatters="This helps us guide her job search and work permit options in Singapore.",
        type="text",
        required=False,
        mapsTo="spouse.occupation",
        allowUnknown=True
    ),
    
    # 14-15. Children info
    Question(
        id="q_child1_name",
        title="What is your first child's name?",
        whyThisMatters="Required for school applications and dependent pass.",
        type="text",
        required=True,
        mapsTo="dependents.0.firstName",
        allowUnknown=False
    ),
    
    Question(
        id="q_child1_dob",
        title="What is your first child's date of birth?",
        whyThisMatters="Determines school grade placement and age-appropriate school options.",
        type="date",
        required=True,
        mapsTo="dependents.0.dateOfBirth",
        allowUnknown=False
    ),
    
    Question(
        id="q_child2_name",
        title="What is your second child's name?",
        whyThisMatters="Required for school applications and dependent pass.",
        type="text",
        required=True,
        mapsTo="dependents.1.firstName",
        allowUnknown=False
    ),
    
    Question(
        id="q_child2_dob",
        title="What is your second child's date of birth?",
        whyThisMatters="Determines school grade placement and age-appropriate school options.",
        type="date",
        required=True,
        mapsTo="dependents.1.dateOfBirth",
        allowUnknown=False
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
        title="What is your monthly housing budget in SGD?",
        whyThisMatters="Singapore housing varies widely; this helps us show realistic options.",
        type="single_select",
        required=True,
        mapsTo="movePlan.housing.budgetMonthlySGD",
        options=[
            QuestionOption(value="3000-5000", label="SGD 3,000 - 5,000"),
            QuestionOption(value="5000-7000", label="SGD 5,000 - 7,000"),
            QuestionOption(value="7000-10000", label="SGD 7,000 - 10,000"),
            QuestionOption(value="10000+", label="SGD 10,000+"),
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
            QuestionOption(value="Local", label="Singapore Local"),
            QuestionOption(value="No preference", label="No preference"),
        ],
        allowUnknown=True
    ),
    
    Question(
        id="q_school_budget",
        title="What is your annual school budget per child (SGD)?",
        whyThisMatters="International schools range from SGD 20k to 45k+ per year.",
        type="single_select",
        required=True,
        mapsTo="movePlan.schooling.budgetAnnualSGD",
        options=[
            QuestionOption(value="15000-25000", label="SGD 15k - 25k"),
            QuestionOption(value="25000-35000", label="SGD 25k - 35k"),
            QuestionOption(value="35000-45000", label="SGD 35k - 45k"),
            QuestionOption(value="45000+", label="SGD 45k+"),
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
        title="Will you need storage in Singapore?",
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
        title="Do you have an employment letter from Norwegian Investment?",
        whyThisMatters="Required for work permit application; should state role, salary, and start date.",
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


def get_all_questions() -> List[Question]:
    """Get all questions."""
    return QUESTION_BANK
