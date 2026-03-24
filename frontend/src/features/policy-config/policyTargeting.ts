/**
 * Canonical targeting values for Compensation & Allowance (aligned with backend enums).
 */

export const POLICY_ASSIGNMENT_TYPE_VALUES = ['short_term', 'long_term', 'permanent', 'international'] as const;
export type PolicyAssignmentTypeValue = (typeof POLICY_ASSIGNMENT_TYPE_VALUES)[number];

export const POLICY_FAMILY_STATUS_VALUES = ['single', 'spouse_partner', 'dependents'] as const;
export type PolicyFamilyStatusValue = (typeof POLICY_FAMILY_STATUS_VALUES)[number];

export const POLICY_ASSIGNMENT_TYPE_OPTIONS: { value: PolicyAssignmentTypeValue; label: string }[] = [
  { value: 'short_term', label: 'Short-term assignment' },
  { value: 'long_term', label: 'Long-term assignment' },
  { value: 'permanent', label: 'Permanent transfer' },
  { value: 'international', label: 'International / host-based assignment' },
];

export const POLICY_FAMILY_STATUS_OPTIONS: { value: PolicyFamilyStatusValue; label: string }[] = [
  { value: 'single', label: 'Employee only (no spouse or dependents)' },
  { value: 'spouse_partner', label: 'Employee with spouse or partner' },
  { value: 'dependents', label: 'Employee with dependents' },
];

const AT_ALIASES: Record<string, PolicyAssignmentTypeValue> = {
  short_term: 'short_term',
  shortterm: 'short_term',
  sta: 'short_term',
  long_term: 'long_term',
  longterm: 'long_term',
  lta: 'long_term',
  permanent: 'permanent',
  international: 'international',
  intl: 'international',
  global: 'international',
  local_plus: 'international',
  commuter: 'short_term',
};

const FS_ALIASES: Record<string, PolicyFamilyStatusValue> = {
  single: 'single',
  spouse_partner: 'spouse_partner',
  spouse: 'spouse_partner',
  partner: 'spouse_partner',
  couple: 'spouse_partner',
  dependents: 'dependents',
  dependent: 'dependents',
  with_dependents: 'dependents',
  family: 'dependents',
  children: 'dependents',
};

function slug(s: string): string {
  return s.trim().toLowerCase().replace(/-/g, '_').replace(/\s+/g, '_');
}

export function normalizeAssignmentType(raw: string | null | undefined): PolicyAssignmentTypeValue | null {
  if (raw == null || !String(raw).trim()) return null;
  const key = slug(String(raw));
  if ((POLICY_ASSIGNMENT_TYPE_VALUES as readonly string[]).includes(key)) return key as PolicyAssignmentTypeValue;
  return AT_ALIASES[key] ?? null;
}

export function normalizeFamilyStatus(raw: string | null | undefined): PolicyFamilyStatusValue | null {
  if (raw == null || !String(raw).trim()) return null;
  const key = slug(String(raw));
  if ((POLICY_FAMILY_STATUS_VALUES as readonly string[]).includes(key)) return key as PolicyFamilyStatusValue;
  return FS_ALIASES[key] ?? null;
}

/** Normalize a list of stored row values to canonical (drops unknown tokens). */
export function normalizeAssignmentTypeList(raw: string[] | undefined): PolicyAssignmentTypeValue[] {
  const out = new Set<PolicyAssignmentTypeValue>();
  for (const x of raw ?? []) {
    const n = normalizeAssignmentType(x);
    if (n) out.add(n);
  }
  return Array.from(out).sort();
}

export function normalizeFamilyStatusList(raw: string[] | undefined): PolicyFamilyStatusValue[] {
  const out = new Set<PolicyFamilyStatusValue>();
  for (const x of raw ?? []) {
    const n = normalizeFamilyStatus(x);
    if (n) out.add(n);
  }
  return Array.from(out).sort();
}

export function humanizeAssignmentTypeLabel(canonical: string | null | undefined): string {
  if (!canonical) return '—';
  const o = POLICY_ASSIGNMENT_TYPE_OPTIONS.find((x) => x.value === canonical);
  return o?.label ?? canonical.replace(/_/g, ' ');
}

export function humanizeFamilyStatusLabel(canonical: string | null | undefined): string {
  if (!canonical) return '—';
  const o = POLICY_FAMILY_STATUS_OPTIONS.find((x) => x.value === canonical);
  return o?.label ?? canonical.replace(/_/g, ' ');
}

export function formatPolicyPreviewBanner(
  assignmentType: string | null | undefined,
  familyStatus: string | null | undefined
): string {
  const at = normalizeAssignmentType(assignmentType);
  const fs = normalizeFamilyStatus(familyStatus);
  const atLabel = at ? POLICY_ASSIGNMENT_TYPE_OPTIONS.find((o) => o.value === at)?.label ?? at : 'All assignment types';
  const fsLabel = fs ? POLICY_FAMILY_STATUS_OPTIONS.find((o) => o.value === fs)?.label ?? fs : 'All family situations';
  return `Viewing policy for: ${atLabel} · ${fsLabel}`;
}

export function rowMatchesTargetingPreview(
  assignmentTypes: string[] | undefined,
  familyStatuses: string[] | undefined,
  filterAssignment: string | null,
  filterFamily: string | null
): boolean {
  const at = normalizeAssignmentTypeList(assignmentTypes);
  const fs = normalizeFamilyStatusList(familyStatuses);
  const fa = normalizeAssignmentType(filterAssignment);
  const ff = normalizeFamilyStatus(filterFamily);

  if (fa) {
    if (at.length > 0 && !at.includes(fa)) return false;
  }
  if (ff) {
    if (fs.length > 0 && !fs.includes(ff)) return false;
  }
  return true;
}
