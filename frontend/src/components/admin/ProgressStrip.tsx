/**
 * ProgressStrip — pipeline stepper + valid next-action button(s) for a single
 * feedback item's `dispatch_status`. Pure presentational: no API imports (must
 * stay jsdom-safe for the Vitest suite — never import api/supabase here).
 *
 * Mirrors the (subset of the) `ALLOWED_TRANSITIONS` state machine used by the
 * backend (`backend/app/services/feedback_state_machine.py`): the primary
 * forward action per state, plus the `deployed → verify_failed` escape and its
 * `verify_failed → in_progress` retry.
 */
import { Button } from '../antigravity/Button';
import { Badge } from '../antigravity/Badge';

const NEXT: Record<string, { target: string; label: string }[]> = {
  new: [{ target: 'triaged', label: 'Triage' }],
  triaged: [{ target: 'spec_drafted', label: 'Draft spec' }],
  spec_drafted: [{ target: 'dispatched', label: 'Create task' }],
  dispatched: [{ target: 'in_progress', label: 'Mark in progress' }],
  in_progress: [{ target: 'in_review', label: 'Mark in review' }],
  in_review: [{ target: 'deployed', label: 'Mark deployed' }],
  deployed: [{ target: 'done', label: 'Done' }, { target: 'verify_failed', label: 'Verify failed' }],
  verify_failed: [{ target: 'in_progress', label: 'Retry' }],
};

const TIER_VARIANT: Record<string, 'success' | 'warning' | 'error'> = {
  green: 'success',
  yellow: 'warning',
  red: 'error',
};

const ORDER = ['new', 'triaged', 'spec_drafted', 'dispatched', 'in_progress', 'in_review', 'deployed', 'done'];

export function ProgressStrip({ status, tier, busy, onAdvance }: {
  status: string;
  tier?: string | null;
  busy: boolean;
  onAdvance: (target: string) => void;
}) {
  const idx = ORDER.indexOf(status);
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {tier && <Badge variant={TIER_VARIANT[tier] ?? 'neutral'} size="sm">{tier}</Badge>}
      <span className="text-xs text-gray-500">
        {ORDER.map((s, i) => (
          <span key={s} className={i <= idx ? 'font-semibold' : 'opacity-40'}>
            {s}{i < ORDER.length - 1 ? ' › ' : ''}
          </span>
        ))}
      </span>
      {(NEXT[status] ?? []).map((a) => (
        <Button key={a.target} size="sm" variant="outline" disabled={busy} onClick={() => onAdvance(a.target)}>
          {a.label}
        </Button>
      ))}
    </div>
  );
}
