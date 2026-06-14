import { formatBenefitLabel } from './benefitCategories';

/**
 * Map an internal comparison-readiness blocker CODE to an HR-facing message.
 *
 * The backend (policy_comparison_readiness.py) emits machine-readable codes
 * like "MISSING_COMPARISON_CATEGORY:shipment" /
 * "COVERED_WITHOUT_DECISION_FIELDS:temporary_housing" in
 * comparison_readiness.comparison_blockers. These are for logic, not display —
 * they must NEVER be rendered raw. TASK-004: they leaked onto the live Policy
 * page as "MISSING COMPARISON CATEGORY:shipment" (underscores swapped for
 * spaces), which an HR manager can't interpret or act on.
 *
 * Always returns a clean, actionable sentence; an unrecognised code falls back
 * to a generic message rather than exposing the code.
 */
export function comparisonBlockerMessage(code: string): string {
  const [kind, rawKey = ''] = (code || '').split(':');
  const label = rawKey ? formatBenefitLabel(rawKey) : '';
  switch (kind) {
    case 'MISSING_COMPARISON_CATEGORY':
      return label
        ? `${label} isn't set up for cost comparison yet — add limits for it in the Policy builder.`
        : "A benefit isn't set up for cost comparison yet — add limits in the Policy builder.";
    case 'COVERED_WITHOUT_DECISION_FIELDS':
      return label
        ? `${label} is covered, but has no limits to compare — add limits in the Policy builder.`
        : 'A covered benefit has no limits to compare — add limits in the Policy builder.';
    case 'NO_MATCHING_PUBLISHED_POLICY':
      return 'No published policy matches this case yet.';
    case 'ERROR_LOADING_POLICY':
      return "We couldn't load the cost comparison right now — try again shortly.";
    default:
      // Never surface an unrecognised raw code to the user.
      return "Some benefits aren't ready for cost comparison yet — add limits in the Policy builder.";
  }
}
