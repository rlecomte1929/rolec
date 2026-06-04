/**
 * [P2-07c · AIQ-700] AvailableNowWidget — the "What You Can Do Now" panel.
 *
 * Surfaces only the 2–3 roadmap actions a user can act on today (no unmet
 * dependencies), instead of overwhelming them with the full step list. Pure
 * derivation of its `steps` prop: it re-computes on every render, so once the
 * host refetches after a step is completed the widget reflects the newly
 * unlocked actions automatically (P2-07d · AIQ-701).
 *
 * Visual language mirrors RoadmapScreen's right panel (inline CSS-variable
 * styles + shared Pill) rather than the Tailwind antigravity primitives.
 */

import { Pill, type PillVariant } from '../shared';
import {
  computeAvailableNow,
  computeBlockers,
  CircularDependencyError,
} from '../../../utils/roadmapAvailability';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Minimal step shape the widget renders. Structurally satisfied by both
 * `RoadmapStep` (relopass-api-contracts) and the live `RoadmapV2Step`.
 * `estimated_effort` and `confidence` are optional: the backend does not
 * populate them yet (see "Known gaps"), so they render only when present.
 */
export interface AvailableNowStep {
  id: string;
  title: string;
  description?: string | null;
  status: string;
  owner?: string;
  dependency_ids: string[];
  estimated_effort?: string | null;
  confidence?: 'high' | 'medium' | 'low' | null;
}

export interface AvailableNowWidgetProps {
  /** All roadmap steps across every track. */
  steps: AvailableNowStep[];
  /** Max actions to show before collapsing behind the see-all link. Default 3. */
  maxItems?: number;
  /** Called when the user clicks "See all available steps". */
  onSeeAll?: () => void;
  /** Called when the user clicks an action's title. */
  onStartStep?: (stepId: string) => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Owner / confidence presentation
// ─────────────────────────────────────────────────────────────────────────────

const OWNER_LABEL: Record<string, string> = {
  employee: 'You',
  hr: 'HR',
  vendor: 'Advisor',
  system: 'Automatic',
};

const OWNER_VARIANT: Record<string, PillVariant> = {
  employee: 'info',
  hr: 'warning',
  vendor: 'default',
  system: 'muted',
};

const CONFIDENCE_VARIANT: Record<NonNullable<AvailableNowStep['confidence']>, PillVariant> = {
  high: 'success',
  medium: 'warning',
  low: 'danger',
};

function ownerPill(owner?: string) {
  if (!owner) return null;
  const label = OWNER_LABEL[owner] ?? owner;
  const variant = OWNER_VARIANT[owner] ?? 'default';
  return <Pill variant={variant} size="sm">{label}</Pill>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Widget
// ─────────────────────────────────────────────────────────────────────────────

export function AvailableNowWidget({
  steps,
  maxItems = 3,
  onSeeAll,
  onStartStep,
}: AvailableNowWidgetProps) {
  // Pure derivation. Circular graphs are flagged (never loop) per P2-07b.
  let available: AvailableNowStep[];
  try {
    available = computeAvailableNow(steps);
  } catch (e) {
    if (e instanceof CircularDependencyError) {
      return (
        <WidgetShell>
          <div
            role="alert"
            style={{
              padding: '12px 14px',
              borderRadius: 'var(--radius-sm, 6px)',
              background: 'var(--pill-danger-bg, rgba(229,62,62,0.12))',
              color: 'var(--danger)',
              fontSize: '13px',
              lineHeight: 1.5,
            }}
          >
            We couldn't work out your next actions because your roadmap has a
            circular dependency. Please contact support so we can fix it.
          </div>
        </WidgetShell>
      );
    }
    throw e;
  }

  const shown = available.slice(0, maxItems);
  const hasMore = available.length > maxItems;

  return (
    <WidgetShell>
      {shown.length === 0 ? (
        <EmptyAvailableState steps={steps} />
      ) : (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {shown.map(step => (
            <li
              key={step.id}
              style={{
                padding: '12px 14px',
                borderRadius: 'var(--radius-md, 8px)',
                border: '1px solid var(--border)',
                borderLeft: '3px solid var(--accent)',
                background: 'var(--surface)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <button
                  onClick={() => onStartStep?.(step.id)}
                  disabled={!onStartStep}
                  style={{
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    fontWeight: 600,
                    fontSize: '14px',
                    color: 'var(--text)',
                    cursor: onStartStep ? 'pointer' : 'default',
                    textAlign: 'left',
                  }}
                >
                  {step.title}
                </button>
                {ownerPill(step.owner)}
                {step.estimated_effort && (
                  <Pill variant="muted" size="sm">{step.estimated_effort}</Pill>
                )}
                {/* TODO [P3-04b]: swap for <ConfidenceBadge> once it lands on main. */}
                {step.confidence && (
                  <Pill variant={CONFIDENCE_VARIANT[step.confidence]} size="sm">
                    {step.confidence} confidence
                  </Pill>
                )}
              </div>
              {step.description && (
                <p style={{ margin: '6px 0 0', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {step.description}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}

      {hasMore && (
        <button
          onClick={onSeeAll}
          disabled={!onSeeAll}
          style={{
            marginTop: '10px',
            background: 'none',
            border: 'none',
            padding: 0,
            fontSize: '13px',
            fontWeight: 600,
            color: 'var(--accent, var(--accent-text))',
            cursor: onSeeAll ? 'pointer' : 'default',
          }}
        >
          See all available steps ({available.length})
        </button>
      )}
    </WidgetShell>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Empty state — names the blocker(s) gating progress
// ─────────────────────────────────────────────────────────────────────────────

function EmptyAvailableState({ steps }: { steps: AvailableNowStep[] }) {
  const blockers = computeBlockers(steps);

  let message: string;
  if (blockers.length === 0) {
    message = "You're all caught up — there's nothing waiting on you right now.";
  } else {
    const first = blockers[0].title;
    const extra = blockers.length > 1 ? ` (+${blockers.length - 1} more)` : '';
    message = `No actions available — waiting on "${first}"${extra}.`;
  }

  return (
    <div
      role="status"
      style={{
        padding: '12px 14px',
        borderRadius: 'var(--radius-sm, 6px)',
        background: 'var(--pill-info-bg, rgba(74,154,232,0.12))',
        color: 'var(--text-secondary)',
        fontSize: '13px',
        lineHeight: 1.5,
      }}
    >
      {message}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Shell — header + container, consistent with the roadmap right panel
// ─────────────────────────────────────────────────────────────────────────────

function WidgetShell({ children }: { children: React.ReactNode }) {
  return (
    <section
      aria-label="What you can do now"
      style={{
        padding: '16px',
        borderRadius: 'var(--radius-md, 8px)',
        border: '1px solid var(--border)',
        background: 'var(--surface)',
      }}
    >
      <h2 style={{ margin: '0 0 2px', fontSize: '15px', fontWeight: 700, color: 'var(--text)' }}>
        What you can do now
      </h2>
      <p style={{ margin: '0 0 12px', fontSize: '12px', color: 'var(--text-muted)' }}>
        The actions available to you today — no blockers.
      </p>
      {children}
    </section>
  );
}

export default AvailableNowWidget;
