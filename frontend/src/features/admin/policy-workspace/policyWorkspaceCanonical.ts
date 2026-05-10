/**
 * Operational copy and minimum canonical benefit keys per theme for Policy Workspace baseline UI.
 */
import { POLICY_CONFIG_CATEGORIES } from '../../policy-config/constants';

/** Short operational line shown on each theme accordion header. */
export const POLICY_WORKSPACE_THEME_DESCRIPTIONS: Record<string, string> = {
  pre_assignment_support: 'Visa, pre-move preparation, training, and early travel support',
  relocation_assistance: 'Move execution, shipment, temporary living, and settling-in support',
  compensation_allowances: 'Assignment-linked premiums and financial support in host location',
  family_support_education:
    'Spouse/partner and child education support (dual career is grouped under Compensation in the matrix)',
  leave_repatriation: 'Home leave, extra leave, and return support at assignment end',
  tax_payroll: 'Tax handling, payroll model, and banking support',
};

export type CanonicalBenefitDef = { key: string; label: string };

/** Minimum baseline topics per theme (keys align with backend matrix benefit_key where possible). */
export const POLICY_WORKSPACE_CANONICAL_ROWS: Record<string, CanonicalBenefitDef[]> = {
  pre_assignment_support: [
    { key: 'visa_work_permit_assistance', label: 'Visa / work permit assistance' },
    { key: 'medical_exam_reimbursement', label: 'Medical exam reimbursement' },
    { key: 'pre_assignment_visit', label: 'Pre-assignment visit' },
    { key: 'cultural_training', label: 'Cultural training' },
    { key: 'language_training', label: 'Language training' },
  ],
  relocation_assistance: [
    { key: 'relocation_allowance_assignee_partner', label: 'Relocation allowance (assignee/partner)' },
    { key: 'relocation_allowance_dependent', label: 'Relocation allowance (dependent)' },
    { key: 'removal_expenses', label: 'Removal expenses' },
    { key: 'shipment_of_goods', label: 'Shipment of goods' },
    { key: 'storage', label: 'Storage' },
    { key: 'temporary_living', label: 'Temporary living' },
    { key: 'settling_in_services', label: 'Settling-in services' },
  ],
  compensation_allowances: [
    { key: 'mobility_premium', label: 'Mobility premium' },
    { key: 'location_allowance', label: 'Location allowance' },
    { key: 'living_allowance', label: 'Living allowance' },
    { key: 'cola', label: 'COLA' },
    { key: 'dual_career_support', label: 'Dual career support' },
    { key: 'host_housing_cap', label: 'Host housing cap' },
    { key: 'host_transportation', label: 'Host transportation' },
    { key: 'driving_test_reimbursement', label: 'Driving test reimbursement' },
  ],
  family_support_education: [
    { key: 'spouse_partner_assistance', label: 'Spouse / partner assistance' },
    { key: 'child_education_support', label: 'Child education support' },
  ],
  leave_repatriation: [
    { key: 'home_leave_trips', label: 'Home leave trips' },
    { key: 'extra_holiday_days', label: 'Extra holiday days' },
    { key: 'repatriation_allowance_assignee_partner', label: 'Repatriation allowance (assignee/partner)' },
    { key: 'repatriation_allowance_dependent', label: 'Repatriation allowance (dependent)' },
    { key: 'return_shipment_travel', label: 'Return shipment / travel' },
  ],
  tax_payroll: [
    { key: 'tax_equalisation', label: 'Tax equalisation' },
    { key: 'payroll_structure', label: 'Payroll structure' },
    { key: 'banking_assistance', label: 'Banking assistance' },
    { key: 'tax_return_preparation', label: 'Tax return preparation' },
  ],
};

/** Ensure descriptions exist for every ordered category (fallback to label only). */
export function themeDescriptionForCategoryKey(categoryKey: string): string {
  return (
    POLICY_WORKSPACE_THEME_DESCRIPTIONS[categoryKey] ??
    POLICY_CONFIG_CATEGORIES.find((c) => c.key === categoryKey)?.label ??
    ''
  );
}
