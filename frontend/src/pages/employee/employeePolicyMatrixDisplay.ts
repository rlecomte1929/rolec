import type { PolicyConfigBenefitRow } from '../../features/policy-config/types';

/** Shown under each visible benefit (requirement: explicit about what numbers mean). */
export const EMPLOYEE_POLICY_PER_BENEFIT_EXPLANATION =
  'These values represent the maximum budget or support approved by your company for this assignment.';

export function humanizeUnitFrequency(uf: string | undefined | null): string {
  if (!uf) return '';
  return String(uf).replace(/_/g, ' ');
}

function capSummary(b: PolicyConfigBenefitRow): string | null {
  const cap = b.allowance_cap;
  if (!cap || typeof cap !== 'object') return null;
  const o = cap as Record<string, unknown>;
  const amount = o.amount;
  const currency = (o.currency as string) || (o.cap_currency as string) || '';
  if (typeof amount === 'number') {
    return currency ? `Allowance up to ${amount} ${currency}` : `Allowance up to ${amount}`;
  }
  if (o.cap_amount != null) {
    const cur = (o.cap_currency as string) || currency || '';
    return cur ? `Cap ${o.cap_amount} ${cur}` : `Cap ${o.cap_amount}`;
  }
  return null;
}

/** Primary “maximum budget / cap” line for employees (no internal keys). */
export function formatBenefitBudgetSummary(b: PolicyConfigBenefitRow): string | null {
  const vt = (b.value_type || 'none').toLowerCase();
  if (vt === 'currency' && b.amount_value != null) {
    const cur = (b.currency_code || '').trim();
    const amt = b.amount_value;
    return cur ? `Up to ${amt} ${cur}` : `Up to ${amt}`;
  }
  if (vt === 'percentage' && b.percentage_value != null) {
    return `${b.percentage_value}%`;
  }
  const capLine = capSummary(b);
  if (capLine) return capLine;
  if (b.maximum_budget_explanation && String(b.maximum_budget_explanation).trim()) {
    return String(b.maximum_budget_explanation).trim();
  }
  if (vt === 'text') {
    return 'See notes and conditions below';
  }
  if (vt === 'none' && b.covered) {
    return 'Covered — details in notes below';
  }
  return null;
}

export function mergeNotesAndConditions(b: PolicyConfigBenefitRow): string | null {
  const parts: string[] = [];
  if (b.notes && String(b.notes).trim()) parts.push(String(b.notes).trim());
  const cj = b.conditions_json;
  if (cj && typeof cj === 'object') {
    const en = cj.eligibility_notes;
    const at = cj.additional_terms;
    if (typeof en === 'string' && en.trim()) parts.push(en.trim());
    if (typeof at === 'string' && at.trim()) parts.push(at.trim());
  }
  if (!parts.length) return null;
  return parts.join('\n\n');
}
