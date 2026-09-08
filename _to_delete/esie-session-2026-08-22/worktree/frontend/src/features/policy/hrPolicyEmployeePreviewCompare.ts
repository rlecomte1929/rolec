/**
 * Side-by-side "current employee view" vs "if you publish this draft" — pure presentation model.
 */
import {
  COMPARISON_SUMMARY_COPY,
  type HrPolicyComparisonSummary,
  type HrPolicyWorkspaceResolved,
} from './hrPolicyWorkspaceState';

export const COMPARISON_TIER_HEADLINE: Record<HrPolicyComparisonSummary, string> = {
  full: 'Cost comparison available',
  partial: 'Cost comparison limited',
  informational: 'Informational only',
};

export type EmployeeComparePanel = {
  /** Whether a published policy is visible on employee assignments */
  policyVisibleToEmployees: boolean;
  visibilityLine: string;
  tier: HrPolicyComparisonSummary;
  tierHeadline: string;
  tierBody: string;
  summaryLine: string;
  previewRows: Array<Record<string, unknown>>;
};

export type EmployeePreviewCompareModel = {
  showFuturePanel: boolean;
  current: EmployeeComparePanel;
  future?: EmployeeComparePanel;
};

export function buildEmployeePreviewCompare(input: {
  resolved: HrPolicyWorkspaceResolved;
  draftEntitlementPreview: Array<Record<string, unknown>>;
  publishedComparison: HrPolicyComparisonSummary;
  workingComparison: HrPolicyComparisonSummary;
}): EmployeePreviewCompareModel {
  const { resolved, draftEntitlementPreview, publishedComparison, workingComparison } = input;

  const hasPublished =
    resolved.phase === 'published' || resolved.publishedVersionNumber != null;

  const showFuturePanel =
    resolved.phase === 'draft_not_publishable' ||
    resolved.phase === 'ready_to_publish' ||
    resolved.hasUnpublishedDraftAhead;

  const currentRowsSameAsWorking =
    hasPublished && !resolved.hasUnpublishedDraftAhead && draftEntitlementPreview.length > 0;

  const currentRows: Array<Record<string, unknown>> =
    hasPublished && resolved.hasUnpublishedDraftAhead
      ? []
      : currentRowsSameAsWorking
        ? draftEntitlementPreview
        : !hasPublished
          ? []
          : [];

  const currentSummary =
    !hasPublished
      ? 'No published policy yet—employees do not see a company policy in ReloPass for this program.'
      : resolved.hasUnpublishedDraftAhead
        ? `Published version ${
            resolved.publishedVersionNumber ?? '—'
          } is live today. While a replacement draft is open, row samples here stay focused on the draft (right). The live policy is unchanged until you publish.`
        : currentRows.length > 0
          ? `Sample of ${Math.min(12, currentRows.length)} lines for a typical assignment (includes saved HR adjustments).`
          : 'No row samples loaded yet—open Policy draft review or save adjustments, then refresh.';

  const current: EmployeeComparePanel = {
    policyVisibleToEmployees: hasPublished,
    visibilityLine: hasPublished
      ? 'Employees see the published policy on their assignments (by eligibility).'
      : 'Employees do not see a policy until you publish a version.',
    tier: publishedComparison,
    tierHeadline: COMPARISON_TIER_HEADLINE[publishedComparison],
    tierBody: COMPARISON_SUMMARY_COPY[publishedComparison],
    summaryLine: currentSummary,
    previewRows: currentRows.slice(0, 12),
  };

  let future: EmployeeComparePanel | undefined;
  if (showFuturePanel) {
    const dv = resolved.draftVersionNumber;
    future = {
      policyVisibleToEmployees: false,
      visibilityLine:
        'Employees will see this only after you publish this working version (subject to eligibility).',
      tier: workingComparison,
      tierHeadline: COMPARISON_TIER_HEADLINE[workingComparison],
      tierBody: COMPARISON_SUMMARY_COPY[workingComparison],
      summaryLine: `If you publish: working version ${dv ?? '—'} with ${resolved.benefitRuleCount} benefit rules and ${resolved.exclusionCount} exclusions (with HR adjustments where saved).`,
      previewRows: draftEntitlementPreview.slice(0, 12),
    };
  }

  return { showFuturePanel, current, future };
}
