/**
 * ProgressStrip — visual pipeline flowchart for a single feedback item's
 * `dispatch_status`. Pure presentational: no API imports (must stay jsdom-safe
 * for the Vitest suite — never import api/supabase here).
 *
 * AIQ-1478: this used to render the pipeline as a text breadcrumb plus manual
 * "advance" buttons (Triage / Draft spec / Mark in progress / …). Those manual
 * transitions are superseded by the AI actions ("Draft task with AI", "Trigger
 * fix") + the Notion→Feedback sync, so the strip is now a passive visual stepper:
 * completed steps are green (✓), the current step pulses blue, upcoming steps are
 * grey. The 8-step order mirrors the backend `ALLOWED_TRANSITIONS`
 * (`backend/app/services/feedback_state_machine.py`).
 */
import { Badge } from '../antigravity/Badge';

const ORDER = ['new', 'triaged', 'spec_drafted', 'dispatched', 'in_progress', 'in_review', 'deployed', 'done'];

const STEP_LABEL: Record<string, string> = {
  new: 'New',
  triaged: 'Triaged',
  spec_drafted: 'Spec drafted',
  dispatched: 'Dispatched',
  in_progress: 'In progress',
  in_review: 'In review',
  deployed: 'Deployed',
  done: 'Done',
};

const TIER_VARIANT: Record<string, 'success' | 'warning' | 'error'> = {
  green: 'success',
  yellow: 'warning',
  red: 'error',
};

// Terminal / notable states get a prominent badge so a completed item reads green
// ("Done ✓") at a glance — set by the Notion→Feedback sync when the task ships.
const TERMINAL: Record<string, { label: string; variant: 'success' | 'neutral' | 'error' }> = {
  done: { label: 'Done ✓', variant: 'success' },
  deployed: { label: 'Deployed', variant: 'success' },
  verify_failed: { label: 'Needs attention', variant: 'error' },
  dismissed: { label: 'Dismissed', variant: 'neutral' },
  wont_fix: { label: "Won't fix", variant: 'neutral' },
};

type StepState = 'completed' | 'active' | 'pending' | 'failed';

function circleClasses(state: StepState): string {
  const base = 'flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ';
  switch (state) {
    case 'completed':
      return base + 'bg-emerald-500 text-white';
    case 'active':
      return base + 'bg-blue-600 text-white ring-4 ring-blue-200 animate-pulse';
    case 'failed':
      return base + 'bg-red-500 text-white';
    default:
      return base + 'bg-gray-200 text-gray-500';
  }
}

export function ProgressStrip({ status, tier }: {
  status: string;
  tier?: string | null;
}) {
  const idx = ORDER.indexOf(status);
  const terminal = TERMINAL[status];
  // verify_failed isn't on the happy path — flag the current step red; the badge
  // conveys dismissed / wont_fix side-states.
  const failed = status === 'verify_failed';

  return (
    <div className="space-y-2">
      {(terminal || tier) && (
        <div className="flex items-center gap-2 flex-wrap">
          {terminal && <Badge variant={terminal.variant} size="sm">{terminal.label}</Badge>}
          {tier && <Badge variant={TIER_VARIANT[tier] ?? 'neutral'} size="sm">{tier}</Badge>}
        </div>
      )}
      <ol
        aria-label="Pipeline progress"
        className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-0"
      >
        {ORDER.map((s, i) => {
          const state: StepState =
            failed && i === idx ? 'failed'
              : i < idx ? 'completed'
                : i === idx ? 'active'
                  : 'pending';
          return (
            <li
              key={s}
              className="flex items-center sm:flex-1"
              aria-label={`Step ${i + 1}: ${STEP_LABEL[s]} — ${state}`}
            >
              <div className="flex items-center gap-1.5">
                <span className={circleClasses(state)} aria-hidden="true">
                  {state === 'completed' ? '✓' : i + 1}
                </span>
                <span
                  className={`text-[11px] ${
                    state === 'pending' ? 'text-gray-400' : 'font-medium text-gray-700'
                  }`}
                >
                  {STEP_LABEL[s]}
                </span>
              </div>
              {i < ORDER.length - 1 && (
                <span
                  aria-hidden="true"
                  className={`mx-1.5 hidden h-px flex-1 sm:block ${
                    i < idx ? 'bg-emerald-400' : 'bg-gray-200'
                  }`}
                />
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
