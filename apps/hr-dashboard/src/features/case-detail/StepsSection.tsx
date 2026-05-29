import { Check, Circle, Clock, AlertCircle } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useCaseStepsQuery } from '../../hooks/useCaseDetailQuery';
import { SectionShell } from './SectionShell';
import type { CaseStep } from './types';

interface StepsSectionProps {
  caseId: string;
}

// TODO [C2-07]: Replace this linear list with the real StepGraph DAG
// renderer (dependencies, parallel arms, blocker visualisation). The
// data shape (CaseStep.status / due_date / owner_label) is already
// compatible with the StepGraph node shape — see Architecture Report §12.2.

function statusVisual(status: CaseStep['status']): { icon: typeof Check; className: string; label: string } {
  switch (status) {
    case 'done':
      return { icon: Check, className: 'text-success', label: 'Done' };
    case 'in_progress':
      return { icon: Clock, className: 'text-primary', label: 'In progress' };
    case 'blocked':
      return { icon: AlertCircle, className: 'text-destructive', label: 'Blocked' };
    case 'pending':
    default:
      return { icon: Circle, className: 'text-muted-foreground', label: 'Pending' };
  }
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

export function StepsSection({ caseId }: StepsSectionProps): JSX.Element {
  const query = useCaseStepsQuery(caseId);
  const steps = query.data ?? [];

  return (
    <SectionShell
      title="Steps"
      subtitle="Immigration workflow timeline. Full StepGraph DAG lands with C2-07."
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => void query.refetch()}
      isEmpty={!query.isLoading && steps.length === 0}
      emptyTitle="No steps registered"
      emptyDescription="When the corridor agent runs against this case, the step plan appears here."
    >
      <ol className="flex flex-col gap-2">
        {steps.map((step, index) => {
          const visual = statusVisual(step.status);
          const Icon = visual.icon;
          return (
            <li
              key={step.step_id}
              className="flex items-center justify-between gap-4 rounded-lg border border-border bg-card p-4 shadow-sm"
            >
              <div className="flex items-start gap-3">
                <Icon className={cn('mt-0.5 h-5 w-5', visual.className)} aria-hidden="true" />
                <div className="flex flex-col gap-1">
                  <p className="text-sm font-medium text-foreground">
                    <span className="mr-2 tabular-nums text-muted-foreground">
                      {String(index + 1).padStart(2, '0')}.
                    </span>
                    {step.label}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    <span aria-label={`Status: ${visual.label}`}>{visual.label}</span>
                    {step.owner_label ? ` · Owner ${step.owner_label}` : ''}
                  </p>
                </div>
              </div>
              <span className="text-xs tabular-nums text-muted-foreground">
                Due {formatDate(step.due_date)}
              </span>
            </li>
          );
        })}
      </ol>
    </SectionShell>
  );
}
