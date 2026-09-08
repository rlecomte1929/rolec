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
  const k = (typeof raw === 'string' ? raw : typeof raw === 'number' ? String(raw) : '')
    .trim()
    .toLowerCase()
    .replace(/-/g, '_');
  if (!k) return 'Publish status: —';
  return PUBLISH_STATUS[k] ?? `Publish: ${titleCaseFromKey(k)}`;
}

export function formatComparisonReadinessBadge(raw: unknown): string {
  const k = (typeof raw === 'string' ? raw : typeof raw === 'number' ? String(raw) : '')
    .trim()
    .toLowerCase()
    .replace(/-/g, '_');
  if (!k) return 'Cost comparison: —';
  return COMPARISON_STATUS[k] ?? `Cost comparison: ${titleCaseFromKey(k)}`;
}

/**
 * Phase-aware "If you publish right now: …" sentence shown in the
 * workspace card (slice 3c of the IA simplification). Tells HR the
 * single thing they came to this card for: publish-now consequences.
 *
 * Numbers come from the count of unresolved highlight issues — a
 * lightweight proxy for "what would block / what would change". A
 * richer per-jurisdiction breakdown ("12 caps for relocation, no
 * impact for DE/FR") needs a backend signal that doesn't exist yet
 * and is queued as a follow-up.
 */
type PhaseSignal = {
  phase:
    | 'no_policy'
    | 'draft_not_publishable'
    | 'ready_to_publish'
    | 'published';
  hasUnpublishedDraftAhead?: boolean;
  highlightIssues?: Array<unknown>;
};

type LifecycleSignal = {
  draftReplacement?: { title?: string } | null;
};

export function publishImpactSentence(
  resolved: PhaseSignal,
  _lifecycle: LifecycleSignal
): string {
  const issueCount = resolved.highlightIssues?.length ?? 0;
  switch (resolved.phase) {
    case 'no_policy':
      return 'nothing changes for employees yet — there is no policy to publish. Pick a template or upload a file below to get started.';
    case 'draft_not_publishable':
      return issueCount > 0
        ? `you can't publish yet — there ${issueCount === 1 ? 'is 1 blocker' : `are ${issueCount} blockers`} to resolve in “What to fix before going live” below.`
        : 'your draft still needs review before employees can see it. See “What to fix before going live” below.';
    case 'ready_to_publish':
      return 'employees on this assignment will start seeing the new policy values immediately after you click Publish.';
    case 'published':
      if (resolved.hasUnpublishedDraftAhead) {
        return 'employees keep seeing the live version. Your replacement draft is HR-only until you publish it.';
      }
      return 'no immediate change — the live policy is already what employees see. Edit values below to start a new draft.';
    default:
      return 'review the draft below and use Publish when ready.';
  }
}
