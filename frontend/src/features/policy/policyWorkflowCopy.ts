/**
 * HR-facing labels for readiness status codes from the policy API.
 * Unknown values fall back to a readable title case string—never raw enum keys in badges.
 */

function titleCaseFromKey(s: string): string {
  return s
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ');
}

const PUBLISH_STATUS: Record<string, string> = {
  ready: 'Publish: ready to go live',
  not_ready: 'Publish: needs a few fixes',
  blocked: 'Publish: blocked — see checklist',
  pending: 'Publish: in progress',
  in_progress: 'Publish: in progress',
  partial: 'Publish: partially complete',
  failed: 'Publish: something failed — review errors',
};

const COMPARISON_STATUS: Record<string, string> = {
  ready: 'Cost comparison: ready',
  not_ready: 'Cost comparison: needs clearer limits',
  blocked: 'Cost comparison: blocked',
  pending: 'Cost comparison: in progress',
  in_progress: 'Cost comparison: in progress',
  partial: 'Cost comparison: partial — some services only',
  failed: 'Cost comparison: check policy data',
};

export function formatPublishReadinessBadge(raw: unknown): string {
  const k = String(raw ?? '')
    .trim()
    .toLowerCase()
    .replace(/-/g, '_');
  if (!k) return 'Publish status: —';
  return PUBLISH_STATUS[k] ?? `Publish: ${titleCaseFromKey(k)}`;
}

export function formatComparisonReadinessBadge(raw: unknown): string {
  const k = String(raw ?? '')
    .trim()
    .toLowerCase()
    .replace(/-/g, '_');
  if (!k) return 'Cost comparison: —';
  return COMPARISON_STATUS[k] ?? `Cost comparison: ${titleCaseFromKey(k)}`;
}
