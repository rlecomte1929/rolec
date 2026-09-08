import type { LucideIcon } from 'lucide-react';
import { Card } from './Card';
import { Button } from './Button';

export interface EmptyStateAction {
  label: string;
  onClick: () => void;
  /** Defaults to `primary` for the first action, `outline` for the rest. */
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost';
}

interface ConversationalEmptyStateProps {
  /** Optional lucide icon rendered in a teal chip above the heading. */
  icon?: LucideIcon;
  heading: string;
  /** Warm, conversational one/two-liner — the AI-voiced onboarding prompt. */
  body: string;
  /** Quick-action shortcuts. First renders as the primary CTA. */
  actions?: EmptyStateAction[];
  /** Small reassurance line under the actions (e.g. "Takes about 2 minutes"). */
  hint?: string;
  className?: string;
}

/**
 * ConversationalEmptyState — a warm, AI-voiced zero-state surface for the primary
 * persona dashboards (AIQ-1411). Generalises the hand-rolled patterns in
 * `HrDashboard`'s `CasesEmptyState` and `EmployeeNoCaseOnboarding` into one shared
 * primitive: teal icon chip + navy heading + gray body + a row of quick-action
 * buttons + optional hint. Brand tokens only (navy #0b2b43 / teal #1f8e8b per
 * DESIGN.md); lucide icons. This is an EMPTY state, not a loading state — callers
 * must gate it on `!loading` so a cold query never renders it as a false empty.
 */
export function ConversationalEmptyState({
  icon: Icon,
  heading,
  body,
  actions = [],
  hint,
  className = '',
}: ConversationalEmptyStateProps) {
  return (
    <Card padding="lg" className={`text-center ${className}`}>
      <div className="mx-auto flex max-w-md flex-col items-center">
        {Icon && (
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[#f0faf9] text-[#1f8e8b]">
            <Icon className="h-6 w-6" aria-hidden="true" />
          </div>
        )}
        <h3 className="mb-2 text-lg font-semibold text-[#0b2b43]">{heading}</h3>
        <p className="mb-6 text-sm leading-relaxed text-[#4b5563]">{body}</p>
        {actions.length > 0 && (
          <div className="flex flex-wrap items-center justify-center gap-3">
            {actions.map((action, i) => (
              <Button
                key={action.label}
                variant={action.variant ?? (i === 0 ? 'primary' : 'outline')}
                onClick={action.onClick}
              >
                {action.label}
              </Button>
            ))}
          </div>
        )}
        {hint && <p className="mt-3 text-sm text-[#6b7280]">{hint}</p>}
      </div>
    </Card>
  );
}
