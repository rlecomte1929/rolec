"""
Canonical long-term assignment (LTA) HR policy template — stable target for mapping uploads.

Uploads map into this structure; HR reviews gaps rather than inferring a new ontology per file.
See docs/policy/canonical-lta-policy-template.md for the 90% framework rationale.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Dict, FrozenSet, Iterator, List, Optional, Tuple


class PolicyTemplateValueType(str, Enum):
    """Primary expected shape of the policy field for UI and comparison hints."""

    AMOUNT = "amount"
    DURATION = "duration"
    QUANTITY = "quantity"
    PERCENTAGE = "percentage"
    NARRATIVE = "narrative"
    EXTERNAL_REFERENCE = "external_reference"


class PolicyApplicabilityDimension(str, Enum):
    """Typical applicability axes for template rows (multi-select on a field)."""

    EMPLOYEE = "employee"
    SPOUSE_PARTNER = "spouse_partner"
    CHILDREN = "children"
    FAMILY = "family"
    ASSIGNMENT_TYPE = "assignment_type"


# Ordered top-level domains (id, HR-facing title)
LTA_POLICY_DOMAIN_ORDER: Tuple[Tuple[str, str], ...] = (
    ("eligibility_and_scope", "Eligibility and scope"),
    ("pre_departure_support", "Pre-departure support"),
    ("move_logistics", "Move logistics"),
    ("compensation_and_payroll", "Compensation and payroll"),
    ("assignment_allowances_and_premiums", "Assignment allowances and premiums"),
    ("family_support", "Family support"),
    ("leave_and_travel_during_assignment", "Leave and travel during assignment"),
    ("repatriation", "Repatriation"),
    ("governance_approvals_external", "Governance, approvals, and external dependencies"),
)

LTA_DOMAIN_IDS: FrozenSet[str] = frozenset(d[0] for d in LTA_POLICY_DOMAIN_ORDER)


@dataclass(frozen=True)
class CanonicalLtaTemplateField:
    """
    One row in the LTA canonical template.

    maps_to_benefit_taxonomy_key: optional link to ``policy_taxonomy.BENEFIT_TAXONOMY`` for the
    normalization mapper; None when the template key is finer-grained or not yet in taxonomy.
    """

    key: str
    domain_id: str
    value_type: PolicyTemplateValueType
    applicability: FrozenSet[PolicyApplicabilityDimension]
    drives_comparison: bool
    employee_visible_label: str
    maps_to_benefit_taxonomy_key: Optional[str] = None
    hr_review_note: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "key": self.key,
            "domain_id": self.domain_id,
            "value_type": self.value_type.value,
            "applicability": sorted(a.value for a in self.applicability),
            "drives_comparison": self.drives_comparison,
            "employee_visible_label": self.employee_visible_label,
            "maps_to_benefit_taxonomy_key": self.maps_to_benefit_taxonomy_key,
            "hr_review_note": self.hr_review_note,
        }


def _ap(*dims: PolicyApplicabilityDimension) -> FrozenSet[PolicyApplicabilityDimension]:
    return frozenset(dims)


# Full template: ~90% LTA coverage; order within domain is UX-stable
CANONICAL_LTA_TEMPLATE_FIELDS: Tuple[CanonicalLtaTemplateField, ...] = (
    # --- 1. Eligibility and scope ---
    CanonicalLtaTemplateField(
        key="eligibility_and_assignment_scope",
        domain_id="eligibility_and_scope",
        value_type=PolicyTemplateValueType.NARRATIVE,
        applicability=_ap(
            PolicyApplicabilityDimension.EMPLOYEE,
            PolicyApplicabilityDimension.ASSIGNMENT_TYPE,
        ),
        drives_comparison=True,
        employee_visible_label="Who is eligible for relocation support",
        maps_to_benefit_taxonomy_key=None,
        hr_review_note="Defines LTA vs STA, grades, host countries, start rules.",
    ),
    CanonicalLtaTemplateField(
        key="policy_definitions_and_exceptions",
        domain_id="eligibility_and_scope",
        value_type=PolicyTemplateValueType.NARRATIVE,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.FAMILY),
        drives_comparison=True,
        employee_visible_label="What this policy covers",
        maps_to_benefit_taxonomy_key=None,
    ),
    # --- 2. Pre-departure support ---
    CanonicalLtaTemplateField(
        key="work_permits_and_visas",
        domain_id="pre_departure_support",
        value_type=PolicyTemplateValueType.NARRATIVE,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.SPOUSE_PARTNER),
        drives_comparison=True,
        employee_visible_label="Work permits and visas",
        maps_to_benefit_taxonomy_key="immigration",
    ),
    CanonicalLtaTemplateField(
        key="medical_exam_support",
        domain_id="pre_departure_support",
        value_type=PolicyTemplateValueType.AMOUNT,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.FAMILY),
        drives_comparison=True,
        employee_visible_label="Medical exams for assignment",
        maps_to_benefit_taxonomy_key="medical",
    ),
    CanonicalLtaTemplateField(
        key="pre_assignment_visit",
        domain_id="pre_departure_support",
        value_type=PolicyTemplateValueType.DURATION,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.SPOUSE_PARTNER),
        drives_comparison=True,
        employee_visible_label="Pre-assignment / look-see visit",
        maps_to_benefit_taxonomy_key="scouting_trip",
    ),
    CanonicalLtaTemplateField(
        key="policy_briefing",
        domain_id="pre_departure_support",
        value_type=PolicyTemplateValueType.NARRATIVE,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.FAMILY),
        drives_comparison=False,
        employee_visible_label="Policy and relocation briefing",
        maps_to_benefit_taxonomy_key=None,
    ),
    CanonicalLtaTemplateField(
        key="cultural_training",
        domain_id="pre_departure_support",
        value_type=PolicyTemplateValueType.NARRATIVE,
        applicability=_ap(
            PolicyApplicabilityDimension.EMPLOYEE,
            PolicyApplicabilityDimension.SPOUSE_PARTNER,
            PolicyApplicabilityDimension.FAMILY,
        ),
        drives_comparison=True,
        employee_visible_label="Cultural training",
        maps_to_benefit_taxonomy_key="language_training",
        hr_review_note="Often bundled with language; split in review if needed.",
    ),
    CanonicalLtaTemplateField(
        key="language_training",
        domain_id="pre_departure_support",
        value_type=PolicyTemplateValueType.NARRATIVE,
        applicability=_ap(
            PolicyApplicabilityDimension.EMPLOYEE,
            PolicyApplicabilityDimension.SPOUSE_PARTNER,
            PolicyApplicabilityDimension.FAMILY,
        ),
        drives_comparison=True,
        employee_visible_label="Language training",
        maps_to_benefit_taxonomy_key="language_training",
    ),
    # --- 3. Move logistics ---
    CanonicalLtaTemplateField(
        key="travel_to_host",
        domain_id="move_logistics",
        value_type=PolicyTemplateValueType.AMOUNT,
        applicability=_ap(
            PolicyApplicabilityDimension.EMPLOYEE,
            PolicyApplicabilityDimension.SPOUSE_PARTNER,
            PolicyApplicabilityDimension.CHILDREN,
        ),
        drives_comparison=True,
        employee_visible_label="Travel to host location",
        maps_to_benefit_taxonomy_key="transport",
    ),
    CanonicalLtaTemplateField(
        key="relocation_allowance",
        domain_id="move_logistics",
        value_type=PolicyTemplateValueType.AMOUNT,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.FAMILY),
        drives_comparison=True,
        employee_visible_label="Relocation allowance",
        maps_to_benefit_taxonomy_key="settling_in_allowance",
        hr_review_note="One-time cash / allowance distinct from settling-in services.",
    ),
    CanonicalLtaTemplateField(
        key="removal_expenses",
        domain_id="move_logistics",
        value_type=PolicyTemplateValueType.AMOUNT,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.FAMILY),
        drives_comparison=True,
        employee_visible_label="Removal and moving services",
        maps_to_benefit_taxonomy_key="movers",
    ),
    CanonicalLtaTemplateField(
        key="shipment_outbound",
        domain_id="move_logistics",
        value_type=PolicyTemplateValueType.AMOUNT,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.FAMILY),
        drives_comparison=True,
        employee_visible_label="Household goods shipment to host",
        maps_to_benefit_taxonomy_key="shipment",
    ),
    CanonicalLtaTemplateField(
        key="storage",
        domain_id="move_logistics",
        value_type=PolicyTemplateValueType.DURATION,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.FAMILY),
        drives_comparison=True,
        employee_visible_label="Storage at origin or in transit",
        maps_to_benefit_taxonomy_key="storage",
        hr_review_note="Often duration + cap; capture both in review.",
    ),
    CanonicalLtaTemplateField(
        key="temporary_living_outbound",
        domain_id="move_logistics",
        value_type=PolicyTemplateValueType.DURATION,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.FAMILY),
        drives_comparison=True,
        employee_visible_label="Temporary housing on arrival",
        maps_to_benefit_taxonomy_key="temporary_housing",
    ),
    CanonicalLtaTemplateField(
        key="settling_in_support",
        domain_id="move_logistics",
        value_type=PolicyTemplateValueType.NARRATIVE,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.FAMILY),
        drives_comparison=True,
        employee_visible_label="Settling-in support",
        maps_to_benefit_taxonomy_key="settling_in_allowance",
    ),
    # --- 4. Compensation and payroll ---
    CanonicalLtaTemplateField(
        key="host_housing",
        domain_id="compensation_and_payroll",
        value_type=PolicyTemplateValueType.NARRATIVE,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.FAMILY),
        drives_comparison=True,
        employee_visible_label="Host-country housing support",
        maps_to_benefit_taxonomy_key="housing",
    ),
    CanonicalLtaTemplateField(
        key="host_transportation",
        domain_id="compensation_and_payroll",
        value_type=PolicyTemplateValueType.NARRATIVE,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE),
        drives_comparison=False,
        employee_visible_label="Local transportation allowance",
        maps_to_benefit_taxonomy_key="transport",
    ),
    CanonicalLtaTemplateField(
        key="tax_equalization",
        domain_id="compensation_and_payroll",
        value_type=PolicyTemplateValueType.NARRATIVE,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE),
        drives_comparison=True,
        employee_visible_label="Tax equalization or protection",
        maps_to_benefit_taxonomy_key="tax",
    ),
    CanonicalLtaTemplateField(
        key="tax_briefing",
        domain_id="compensation_and_payroll",
        value_type=PolicyTemplateValueType.NARRATIVE,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.SPOUSE_PARTNER),
        drives_comparison=False,
        employee_visible_label="Tax briefing and education",
        maps_to_benefit_taxonomy_key="tax",
    ),
    CanonicalLtaTemplateField(
        key="tax_return_support",
        domain_id="compensation_and_payroll",
        value_type=PolicyTemplateValueType.NARRATIVE,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.SPOUSE_PARTNER),
        drives_comparison=True,
        employee_visible_label="Tax return preparation support",
        maps_to_benefit_taxonomy_key="tax",
    ),
    # --- 5. Assignment allowances and premiums ---
    CanonicalLtaTemplateField(
        key="mobility_premium",
        domain_id="assignment_allowances_and_premiums",
        value_type=PolicyTemplateValueType.PERCENTAGE,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.ASSIGNMENT_TYPE),
        drives_comparison=True,
        employee_visible_label="Mobility / expatriate premium",
        maps_to_benefit_taxonomy_key="mobility_premium",
    ),
    CanonicalLtaTemplateField(
        key="location_premium",
        domain_id="assignment_allowances_and_premiums",
        value_type=PolicyTemplateValueType.AMOUNT,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.ASSIGNMENT_TYPE),
        drives_comparison=True,
        employee_visible_label="Location allowance or premium",
        maps_to_benefit_taxonomy_key="location_allowance",
    ),
    CanonicalLtaTemplateField(
        key="remote_premium",
        domain_id="assignment_allowances_and_premiums",
        value_type=PolicyTemplateValueType.PERCENTAGE,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.ASSIGNMENT_TYPE),
        drives_comparison=True,
        employee_visible_label="Hardship or remote location premium",
        maps_to_benefit_taxonomy_key="remote_premium",
    ),
    CanonicalLtaTemplateField(
        key="cola",
        domain_id="assignment_allowances_and_premiums",
        value_type=PolicyTemplateValueType.PERCENTAGE,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.ASSIGNMENT_TYPE),
        drives_comparison=True,
        employee_visible_label="Cost of living adjustment (COLA)",
        maps_to_benefit_taxonomy_key="cola",
    ),
    # --- 6. Family support ---
    CanonicalLtaTemplateField(
        key="spouse_support",
        domain_id="family_support",
        value_type=PolicyTemplateValueType.AMOUNT,
        applicability=_ap(PolicyApplicabilityDimension.SPOUSE_PARTNER),
        drives_comparison=True,
        employee_visible_label="Spouse or partner support",
        maps_to_benefit_taxonomy_key="spouse_support",
    ),
    CanonicalLtaTemplateField(
        key="child_education",
        domain_id="family_support",
        value_type=PolicyTemplateValueType.NARRATIVE,
        applicability=_ap(PolicyApplicabilityDimension.CHILDREN),
        drives_comparison=True,
        employee_visible_label="Child education and tuition support",
        maps_to_benefit_taxonomy_key="schooling",
    ),
    CanonicalLtaTemplateField(
        key="school_search",
        domain_id="family_support",
        value_type=PolicyTemplateValueType.NARRATIVE,
        applicability=_ap(PolicyApplicabilityDimension.CHILDREN, PolicyApplicabilityDimension.FAMILY),
        drives_comparison=True,
        employee_visible_label="School search assistance",
        maps_to_benefit_taxonomy_key="schooling",
    ),
    # --- 7. Leave and travel during assignment ---
    CanonicalLtaTemplateField(
        key="home_leave",
        domain_id="leave_and_travel_during_assignment",
        value_type=PolicyTemplateValueType.QUANTITY,
        applicability=_ap(
            PolicyApplicabilityDimension.EMPLOYEE,
            PolicyApplicabilityDimension.FAMILY,
            PolicyApplicabilityDimension.ASSIGNMENT_TYPE,
        ),
        drives_comparison=True,
        employee_visible_label="Home leave (trips home during assignment)",
        maps_to_benefit_taxonomy_key="home_leave",
        hr_review_note="Typically trips per year or days; use quantity + narrative.",
    ),
    # --- 8. Repatriation ---
    CanonicalLtaTemplateField(
        key="return_shipment",
        domain_id="repatriation",
        value_type=PolicyTemplateValueType.AMOUNT,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.FAMILY),
        drives_comparison=True,
        employee_visible_label="Household goods shipment home",
        maps_to_benefit_taxonomy_key="shipment",
    ),
    CanonicalLtaTemplateField(
        key="return_travel",
        domain_id="repatriation",
        value_type=PolicyTemplateValueType.AMOUNT,
        applicability=_ap(
            PolicyApplicabilityDimension.EMPLOYEE,
            PolicyApplicabilityDimension.SPOUSE_PARTNER,
            PolicyApplicabilityDimension.CHILDREN,
        ),
        drives_comparison=True,
        employee_visible_label="Travel home at end of assignment",
        maps_to_benefit_taxonomy_key="transport",
    ),
    CanonicalLtaTemplateField(
        key="temporary_living_return",
        domain_id="repatriation",
        value_type=PolicyTemplateValueType.DURATION,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.FAMILY),
        drives_comparison=True,
        employee_visible_label="Temporary housing after return",
        maps_to_benefit_taxonomy_key="temporary_housing",
    ),
    CanonicalLtaTemplateField(
        key="repatriation_allowance",
        domain_id="repatriation",
        value_type=PolicyTemplateValueType.AMOUNT,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.FAMILY),
        drives_comparison=True,
        employee_visible_label="Repatriation allowance",
        maps_to_benefit_taxonomy_key=None,
        hr_review_note="Map to allowance taxonomy when added; often one-time cash.",
    ),
    # --- 9. Governance ---
    CanonicalLtaTemplateField(
        key="approval_authority_matrix",
        domain_id="governance_approvals_external",
        value_type=PolicyTemplateValueType.NARRATIVE,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.ASSIGNMENT_TYPE),
        drives_comparison=True,
        employee_visible_label="Who approves exceptions and spend",
        maps_to_benefit_taxonomy_key=None,
    ),
    CanonicalLtaTemplateField(
        key="mandatory_notifications_and_compliance",
        domain_id="governance_approvals_external",
        value_type=PolicyTemplateValueType.NARRATIVE,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE),
        drives_comparison=False,
        employee_visible_label="Required notifications and compliance steps",
        maps_to_benefit_taxonomy_key=None,
    ),
    CanonicalLtaTemplateField(
        key="external_providers_and_dependencies",
        domain_id="governance_approvals_external",
        value_type=PolicyTemplateValueType.EXTERNAL_REFERENCE,
        applicability=_ap(PolicyApplicabilityDimension.EMPLOYEE, PolicyApplicabilityDimension.FAMILY),
        drives_comparison=False,
        employee_visible_label="Third-party providers (RMC, tax, immigration)",
        maps_to_benefit_taxonomy_key="relocation_services",
    ),
)


@lru_cache(maxsize=1)
def _field_index() -> Dict[str, CanonicalLtaTemplateField]:
    return {f.key: f for f in CANONICAL_LTA_TEMPLATE_FIELDS}


def get_canonical_lta_field(key: str) -> Optional[CanonicalLtaTemplateField]:
    """Lookup one template field by canonical key."""
    return _field_index().get(key)


def list_canonical_lta_template_fields() -> List[CanonicalLtaTemplateField]:
    """All template fields in stable domain order then definition order."""
    return list(CANONICAL_LTA_TEMPLATE_FIELDS)


def iter_canonical_lta_fields_by_domain(domain_id: str) -> Iterator[CanonicalLtaTemplateField]:
    for f in CANONICAL_LTA_TEMPLATE_FIELDS:
        if f.domain_id == domain_id:
            yield f


def canonical_lta_template_as_jsonable() -> Dict[str, object]:
    """Serialize template for API fixtures or admin tools."""
    return {
        "schema": "canonical_lta_template_v1",
        "domains": [{"id": d, "title": t} for d, t in LTA_POLICY_DOMAIN_ORDER],
        "value_types": [e.value for e in PolicyTemplateValueType],
        "applicability_dimensions": [e.value for e in PolicyApplicabilityDimension],
        "fields": [f.to_dict() for f in CANONICAL_LTA_TEMPLATE_FIELDS],
    }


def list_taxonomy_keys_used_by_lta_template() -> FrozenSet[str]:
    """Benefit taxonomy keys referenced by the LTA template (for mapper wiring)."""
    out: set = set()
    for f in CANONICAL_LTA_TEMPLATE_FIELDS:
        if f.maps_to_benefit_taxonomy_key:
            out.add(f.maps_to_benefit_taxonomy_key)
    return frozenset(out)
