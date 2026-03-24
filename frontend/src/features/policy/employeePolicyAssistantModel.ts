import type { PolicyAssistantAnswer } from '../../types/policyAssistant';

export type EmployeePolicyAssistantSupportStatus =
  | 'included'
  | 'excluded'
  | 'informational'
  | 'clarification'
  | 'refused';

export function deriveSupportStatus(answer: PolicyAssistantAnswer): EmployeePolicyAssistantSupportStatus {
  if (answer.answer_type === 'clarification_needed') {
    return 'clarification';
  }
  if (answer.refusal || answer.answer_type === 'refusal') {
    return 'refused';
  }
  if (answer.answer_type === 'comparison_summary' || answer.answer_type === 'status_summary') {
    return 'informational';
  }
  if (answer.answer_type === 'draft_published_summary') {
    return 'informational';
  }
  if (answer.answer_type === 'entitlement_summary') {
    const t = answer.answer_text.toLowerCase();
    if (t.includes('not included')) {
      return 'excluded';
    }
    const cr = answer.comparison_readiness;
    if (
      cr === 'informational_only' ||
      cr === 'external_reference_partial' ||
      cr === 'review_required' ||
      cr === 'deterministic_non_budget'
    ) {
      return 'informational';
    }
    return 'included';
  }
  return 'informational';
}

const STATUS_LABELS: Record<EmployeePolicyAssistantSupportStatus, string> = {
  included: 'Included (per published policy data)',
  excluded: 'Not included (per published policy data)',
  informational: 'Informational',
  clarification: 'Needs detail',
  refused: 'Not answered',
};

export function supportStatusLabel(status: EmployeePolicyAssistantSupportStatus): string {
  return STATUS_LABELS[status];
}

const STATUS_BADGE_CLASS: Record<EmployeePolicyAssistantSupportStatus, string> = {
  included: 'bg-emerald-50 text-emerald-900 border-emerald-200',
  excluded: 'bg-slate-100 text-slate-800 border-slate-200',
  informational: 'bg-sky-50 text-sky-950 border-sky-200',
  clarification: 'bg-amber-50 text-amber-950 border-amber-200',
  refused: 'bg-rose-50 text-rose-900 border-rose-200',
};

export function supportStatusBadgeClass(status: EmployeePolicyAssistantSupportStatus): string {
  return STATUS_BADGE_CLASS[status];
}
