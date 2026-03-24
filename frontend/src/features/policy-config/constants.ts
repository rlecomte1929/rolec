/** Category order and labels (must match backend category_key values). */
export const POLICY_CONFIG_CATEGORIES: { key: string; label: string }[] = [
  { key: 'pre_assignment_support', label: 'Pre-Assignment Support' },
  { key: 'relocation_assistance', label: 'Relocation Assistance' },
  { key: 'compensation_allowances', label: 'Compensation & Allowances' },
  { key: 'family_support_education', label: 'Family Support & Education' },
  { key: 'leave_repatriation', label: 'Leave & Repatriation' },
  { key: 'tax_payroll', label: 'Tax & Payroll' },
];

/** @deprecated Use POLICY_ASSIGNMENT_TYPE_OPTIONS / POLICY_FAMILY_STATUS_OPTIONS from policyTargeting.ts */
export const ASSIGNMENT_TYPE_SUGGESTIONS = ['short_term', 'long_term', 'permanent', 'international'];

/** @deprecated Use policyTargeting.ts */
export const FAMILY_STATUS_SUGGESTIONS = ['single', 'spouse_partner', 'dependents'];
