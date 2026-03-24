/**
 * Canonical benefit keys and per-row UI extensions (helper fields).
 * Category placement follows the product matrix; API may still store category per row.
 */
export type BenefitHelperKind =
  | 'none'
  | 'pre_visit'
  | 'training_hours'
  | 'shipment_volume'
  | 'storage_duration_volume'
  | 'temp_living_days'
  | 'child_education_tuition'
  | 'home_leave_trips'
  | 'extra_holiday_days'
  | 'payroll_structure'
  | 'banking_monthly_transfer';

export type BenefitRowDefinition = {
  key: string;
  /** Business-facing default title if API label missing */
  title: string;
  helper: BenefitHelperKind;
};

/** Stable key for registry lookup */
const _REGISTRY_ENTRIES: [string, BenefitRowDefinition][] = [
    // Pre-Assignment Support
    ['visa_work_permit_assistance', { key: 'visa_work_permit_assistance', title: 'Visa & work permit support', helper: 'none' }],
    ['medical_exam_reimbursement', { key: 'medical_exam_reimbursement', title: 'Medical exam reimbursement', helper: 'none' }],
    ['pre_assignment_visit', { key: 'pre_assignment_visit', title: 'Pre-assignment visit', helper: 'pre_visit' }],
    ['cultural_training', { key: 'cultural_training', title: 'Cultural training', helper: 'training_hours' }],
    ['language_training', { key: 'language_training', title: 'Language training', helper: 'training_hours' }],
    // Relocation Assistance
    ['relocation_allowance_assignee_partner', { key: 'relocation_allowance_assignee_partner', title: 'Relocation allowance (you & partner)', helper: 'none' }],
    ['relocation_allowance_dependent', { key: 'relocation_allowance_dependent', title: 'Relocation allowance (dependents)', helper: 'none' }],
    ['removal_expenses', { key: 'removal_expenses', title: 'Removal expenses', helper: 'none' }],
    ['shipment_of_goods', { key: 'shipment_of_goods', title: 'Shipment of household goods', helper: 'shipment_volume' }],
    ['storage', { key: 'storage', title: 'Storage', helper: 'storage_duration_volume' }],
    ['temporary_living', { key: 'temporary_living', title: 'Temporary living', helper: 'temp_living_days' }],
    ['settling_in_services', { key: 'settling_in_services', title: 'Settling-in services', helper: 'none' }],
    // Compensation & Allowances
    ['mobility_premium', { key: 'mobility_premium', title: 'Mobility premium', helper: 'none' }],
    ['location_allowance', { key: 'location_allowance', title: 'Location allowance', helper: 'none' }],
    ['living_allowance', { key: 'living_allowance', title: 'Living allowance', helper: 'none' }],
    ['cola', { key: 'cola', title: 'Cost of living adjustment (COLA)', helper: 'none' }],
    ['host_housing_cap', { key: 'host_housing_cap', title: 'Host housing cap', helper: 'none' }],
    ['host_transportation', { key: 'host_transportation', title: 'Host transportation', helper: 'none' }],
    ['driving_test_reimbursement', { key: 'driving_test_reimbursement', title: 'Driving test reimbursement', helper: 'none' }],
    // Family Support & Education
    ['dual_career_support', { key: 'dual_career_support', title: 'Dual career support', helper: 'none' }],
    ['spouse_partner_assistance', { key: 'spouse_partner_assistance', title: 'Spouse or partner assistance', helper: 'none' }],
    ['child_education_support', { key: 'child_education_support', title: 'Child education support', helper: 'child_education_tuition' }],
    // Leave & Repatriation
    ['home_leave_trips', { key: 'home_leave_trips', title: 'Home leave trips', helper: 'home_leave_trips' }],
    ['extra_holiday_days', { key: 'extra_holiday_days', title: 'Extra holiday days', helper: 'extra_holiday_days' }],
    ['repatriation_allowance_assignee_partner', { key: 'repatriation_allowance_assignee_partner', title: 'Repatriation allowance (you & partner)', helper: 'none' }],
    ['repatriation_allowance_dependent', { key: 'repatriation_allowance_dependent', title: 'Repatriation allowance (dependents)', helper: 'none' }],
    ['return_shipment_travel', { key: 'return_shipment_travel', title: 'Return shipment & travel', helper: 'none' }],
    // Tax & Payroll
    ['tax_equalisation', { key: 'tax_equalisation', title: 'Tax equalisation', helper: 'none' }],
    ['payroll_structure', { key: 'payroll_structure', title: 'Payroll structure', helper: 'payroll_structure' }],
    ['banking_assistance', { key: 'banking_assistance', title: 'Banking assistance', helper: 'banking_monthly_transfer' }],
    ['tax_return_preparation', { key: 'tax_return_preparation', title: 'Tax return preparation', helper: 'none' }],
];

export const BENEFIT_REGISTRY: Record<string, BenefitRowDefinition> = Object.fromEntries(_REGISTRY_ENTRIES);

export function getBenefitDefinition(benefitKey: string | undefined): BenefitRowDefinition | null {
  if (!benefitKey) return null;
  return BENEFIT_REGISTRY[benefitKey] ?? null;
}

export function getBenefitTitle(rowKey: string | undefined, apiLabel: string | undefined): string {
  const def = getBenefitDefinition(rowKey);
  return (apiLabel && apiLabel.trim()) || def?.title || rowKey || 'Benefit';
}
