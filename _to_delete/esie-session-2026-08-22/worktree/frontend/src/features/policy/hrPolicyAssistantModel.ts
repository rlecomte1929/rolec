import type { PolicyAssistantAnswer, PolicyAssistantComparisonReadiness, PolicyAssistantPolicyStatus } from '../../types/policyAssistant';

export function policyScopeLine(status: PolicyAssistantPolicyStatus): string {
  const m: Record<PolicyAssistantPolicyStatus, string> = {
    published: 'Uses **published** policy data (what employees see when a version is live).',
    draft: 'Uses **working draft** / HR normalization data for this policy version.',
    draft_and_published: 'References **both** the working draft and **published** data where applicable.',
    no_policy_bound: 'No published policy is bound in ReloPass for this context yet.',
    unknown: 'Policy scope could not be classified from loaded data.',
  };
  return m[status] ?? m.unknown;
}

export function draftVsPublishedHint(answer: PolicyAssistantAnswer): string | null {
  if (answer.answer_type === 'draft_published_summary') {
    return 'Explains **draft vs published** visibility for employees in ReloPass.';
  }
  if (answer.policy_status === 'draft_and_published') {
    return '**Employee view** follows **published** data today; **working draft** may differ until you publish.';
  }
  if (answer.policy_status === 'draft') {
    return 'Uses **working draft** data; **published** employee view may differ until you publish.';
  }
  return null;
}

export function comparisonReadinessExplanation(cr: PolicyAssistantComparisonReadiness): string | null {
  const lines: Record<PolicyAssistantComparisonReadiness, string | null> = {
    comparison_ready:
      'ReloPass treats this topic as **comparison-ready** where numeric caps exist in the loaded data.',
    informational_only:
      'Marked **informational only**—automated dollar comparisons are not asserted for this surface.',
    external_reference_partial:
      '**Partial** readiness: limits may depend on external references or incomplete numeric coverage.',
    review_required: '**Review required** before ReloPass can treat comparisons as reliable.',
    deterministic_non_budget:
      'Covered in policy data, but **not** as a simple budget delta in the comparison UI.',
    not_applicable: null,
  };
  return lines[cr] ?? null;
}
