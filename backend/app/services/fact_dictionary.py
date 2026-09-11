"""
fact_dictionary.py — the governed vocabulary for the Document Data Sheet.

One source-of-truth definition per *fact*: its label, its category, whether it is a
regulated determination ReloPass must never fill (``professional_review_required``), and the
canonical ``prefill_source`` path a value is pulled from. Every data-sheet field references a
fact here instead of re-declaring its meaning, so a value captured once fills the same fact
everywhere and "consult a professional" is classified consistently across templates.

This is the **checked-in seed** form the spec (§7) endorses: "may ship first as a checked-in
seed of the key list and be promoted to a small table when query-time filtering is wanted."
Phase 1 is read-only, so a module-level registry is enough; promotion to a table is a later
phase (when write-back + admin authoring need it).

Lookup is keyed **primarily by ``prefill_source``** (portable across templates —
``profile.passport_number`` means the same fact wherever it appears) and **falls back to the
template-local ``field_id``** for facts that carry no source (a free-text field the employee
must supply, or a consult-professional determination that is never pre-filled).

Seeded from the FR→NO ``RP-NO-DATASHEET`` template
(``supabase/migrations/20261015000000_seed_frno_data_sheet.sql``). DE↔FR facts join here as a
fast-follow; the structure is corridor-agnostic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Category vocabulary — the life-domains from the corridor authoring guide.
CATEGORY_IDENTITY = "identity"
CATEGORY_IMMIGRATION = "immigration"
CATEGORY_TAX = "tax"
CATEGORY_SOCIAL_SECURITY = "social_security"
CATEGORY_HEALTHCARE = "healthcare"
CATEGORY_HOUSING = "housing"
CATEGORY_BANKING = "banking"
CATEGORY_EMPLOYMENT = "employment"
CATEGORY_EDUCATION = "education"
CATEGORY_FAMILY = "family"


@dataclass(frozen=True)
class FactEntry:
    """One governed fact. ``professional_review_required`` is the consult-professional
    firewall as a *fact* property — orthogonal to any per-template flag, and the reason a
    value must never be filled for this fact."""

    fact_key: str
    label: str
    category: str
    professional_review_required: bool = False
    #: The canonical dotted context path a value is pulled from (``prefill_engine`` vocabulary).
    #: None for facts with no derivable source (free-text or consult-professional).
    prefill_source: Optional[str] = None
    #: Template-local field ids this fact is known by, used as the fallback join key when a
    #: field carries no ``prefill_source``.
    field_ids: Tuple[str, ...] = ()


# ── The seed registry (FR→NO) ────────────────────────────────────────────────
_FACTS: List[FactEntry] = [
    # Identity
    FactEntry("full_name", "Full legal name", CATEGORY_IDENTITY,
              prefill_source="profile.legal_full_name", field_ids=("full_name",)),
    FactEntry("date_of_birth", "Date of birth", CATEGORY_IDENTITY,
              prefill_source="profile.date_of_birth", field_ids=("date_of_birth",)),
    FactEntry("nationality", "Nationality", CATEGORY_IDENTITY,
              prefill_source="profile.nationality", field_ids=("nationality",)),
    FactEntry("passport_number", "Passport or ID document number", CATEGORY_IDENTITY,
              prefill_source="profile.passport_number", field_ids=("id_document_number",)),
    FactEntry("passport_expiry", "ID document expiry date", CATEGORY_IDENTITY,
              prefill_source="profile.passport_expiry", field_ids=("id_document_expiry",)),
    # Identity — split-name and document fields the DE/FR application forms require. The FR→NO
    # datasheet uses one combined ``full_name`` (above); government application forms split it and
    # ask for extra document facts, so these are governed separately and join by vault column.
    FactEntry("legal_first_name", "Legal given name(s)", CATEGORY_IDENTITY,
              prefill_source="profile.legal_first_name", field_ids=("legal_first_name",)),
    FactEntry("legal_last_name", "Legal surname", CATEGORY_IDENTITY,
              prefill_source="profile.legal_last_name", field_ids=("legal_last_name",)),
    FactEntry("place_of_birth", "Place of birth", CATEGORY_IDENTITY,
              prefill_source="profile.place_of_birth", field_ids=("place_of_birth",)),
    FactEntry("gender", "Gender", CATEGORY_IDENTITY,
              prefill_source="profile.gender", field_ids=("gender",)),
    FactEntry("passport_issue_date", "Passport date of issue", CATEGORY_IDENTITY,
              prefill_source="profile.passport_issue_date", field_ids=("passport_issue_date",)),
    FactEntry("passport_country", "Passport issuing country", CATEGORY_IDENTITY,
              prefill_source="profile.passport_country", field_ids=("passport_country",)),
    # Family
    FactEntry("marital_status", "Marital status", CATEGORY_FAMILY,
              prefill_source="profile.marital_status", field_ids=("marital_status",)),
    # Employment
    FactEntry("employer_name", "Employer", CATEGORY_EMPLOYMENT,
              prefill_source="contract.employer_name", field_ids=("employer_name",)),
    FactEntry("employer_org_number", "Employer organisation number", CATEGORY_EMPLOYMENT,
              prefill_source="contract.employer_org_number", field_ids=("employer_org_number",)),
    FactEntry("job_title", "Job title", CATEGORY_EMPLOYMENT,
              prefill_source="contract.job_title", field_ids=("job_title",)),
    FactEntry("employment_start_date", "Employment start date", CATEGORY_EMPLOYMENT,
              prefill_source="contract.employment_start_date", field_ids=("employment_start_date",)),
    # Canonical vault column is ``salary_amount`` (currency stored separately); the FR→NO
    # datasheet's ``salary_amount_nok`` field id is kept as a fallback join key so that sheet
    # still resolves. See 20261015000000_seed_frno_data_sheet.sql (salary_amount_nok → salary_amount).
    FactEntry("salary_amount", "Gross annual salary", CATEGORY_EMPLOYMENT,
              prefill_source="contract.salary_amount",
              field_ids=("salary_amount", "salary_amount_nok")),
    # Immigration / logistics
    FactEntry("arrival_date", "Date of arrival", CATEGORY_IMMIGRATION,
              prefill_source="case.arrival_date", field_ids=("arrival_date",)),
    FactEntry("intended_stay_months", "Intended length of stay (months)", CATEGORY_IMMIGRATION,
              prefill_source="case.intended_stay_months", field_ids=("intended_stay_months",)),
    # Housing (no derivable source — employee supplies it)
    FactEntry("destination_address", "Address in destination country", CATEGORY_HOUSING,
              prefill_source=None, field_ids=("norwegian_address",)),
    # ── Consult-professional determinations — NEVER filled ────────────────────
    FactEntry("tax_residency_status", "Tax-residency status determination", CATEGORY_TAX,
              professional_review_required=True, field_ids=("tax_residency_status",)),
    FactEntry("shadow_payroll_requirement", "Shadow-payroll requirement", CATEGORY_TAX,
              professional_review_required=True, field_ids=("shadow_payroll_requirement",)),
    FactEntry("pe_risk", "Permanent-establishment (PE) risk", CATEGORY_TAX,
              professional_review_required=True, field_ids=("pe_risk",)),
    FactEntry("a1_determination", "A1 / social-security coordination determination",
              CATEGORY_SOCIAL_SECURITY, professional_review_required=True,
              field_ids=("a1_determination",)),
    FactEntry("contract_classification", "Contract classification (posting vs local hire)",
              CATEGORY_SOCIAL_SECURITY, professional_review_required=True,
              field_ids=("contract_classification",)),
]

# ── Indices (built once) ─────────────────────────────────────────────────────
_BY_PREFILL_SOURCE: Dict[str, FactEntry] = {
    f.prefill_source: f for f in _FACTS if f.prefill_source
}
_BY_FIELD_ID: Dict[str, FactEntry] = {
    fid: f for f in _FACTS for fid in f.field_ids
}


def lookup(prefill_source: Optional[str], field_id: Optional[str] = None) -> Optional[FactEntry]:
    """Resolve a data-sheet field to its governed fact.

    Prefer the portable ``prefill_source`` key; fall back to the template-local ``field_id``.
    Returns None for a field this seed does not yet know (the read-model then degrades to the
    field's own attributes rather than raising).
    """
    if prefill_source and prefill_source in _BY_PREFILL_SOURCE:
        return _BY_PREFILL_SOURCE[prefill_source]
    if field_id and field_id in _BY_FIELD_ID:
        return _BY_FIELD_ID[field_id]
    return None
