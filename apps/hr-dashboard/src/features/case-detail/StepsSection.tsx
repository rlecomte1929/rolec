import { useMemo } from 'react';
import { Check, Circle, Clock, AlertCircle, CalendarClock, ExternalLink } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useCaseStepsQuery } from '../../hooks/useCaseDetailQuery';
import { SectionShell } from './SectionShell';
import type { CaseStep } from './types';

interface StepsSectionProps {
  caseId: string;
}

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

/**
 * Order steps so every step appears after all of its prerequisites
 * (Kahn's algorithm). Ties keep the server's order; a cycle or dangling
 * prerequisite degrades gracefully by appending the leftovers in order, so
 * the list never disappears on bad data.
 */
function topologicalSort(steps: CaseStep[]): CaseStep[] {
  const byId = new Map(steps.map((s) => [s.step_id, s]));
  const indegree = new Map(steps.map((s) => [s.step_id, 0]));
  for (const s of steps) {
    for (const p of s.prerequisite_step_ids ?? []) {
      if (byId.has(p)) indegree.set(s.step_id, (indegree.get(s.step_id) ?? 0) + 1);
    }
  }
  const ready = steps.filter((s) => (indegree.get(s.step_id) ?? 0) === 0);
  const ordered: CaseStep[] = [];
  const seen = new Set<string>();
  while (ready.length) {
    const s = ready.shift() as CaseStep;
    if (seen.has(s.step_id)) continue;
    seen.add(s.step_id);
    ordered.push(s);
    for (const cand of steps) {
      if (seen.has(cand.step_id)) continue;
      if (!(cand.prerequisite_step_ids ?? []).includes(s.step_id)) continue;
      const left = (indegree.get(cand.step_id) ?? 0) - 1;
      indegree.set(cand.step_id, left);
      if (left <= 0) ready.push(cand);
    }
  }
  if (ordered.length < steps.length) {
    for (const s of steps) if (!seen.has(s.step_id)) ordered.push(s);
  }
  return ordered;
}

export function StepsSection({ caseId }: StepsSectionProps): JSX.Element {
  const query = useCaseStepsQuery(caseId);
  const steps = query.data ?? [];

  const { ordered, labelById } = useMemo(() => {
    const labels = new Map(steps.map((s) => [s.step_id, s.label]));
    return { ordered: topologicalSort(steps), labelById: labels };
  }, [steps]);

  return (
    <SectionShell
      title="Steps"
      subtitle="Rule-anchored StepGraph — ordered by prerequisite, with legally-derived deadlines."
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => void query.refetch()}
      isEmpty={!query.isLoading && steps.length === 0}
      emptyTitle="No steps registered"
      emptyDescription="When the corridor agent runs against this case, the step plan appears here."
    >
      <ol className="flex flex-col gap-2">
        {ordered.map((step, index) => {
          const visual = statusVisual(step.status);
          const Icon = visual.icon;
          const prereqLabels = (step.prerequisite_step_ids ?? [])
            .map((id) => labelById.get(id))
            .filter((l): l is string => Boolean(l));
          const citations = (step.citations ?? []).filter((c) => c.legal_reference);
          const ariaLabel = [
            `Step ${index + 1} of ${ordered.length}: ${step.label}.`,
            step.due_date ? `Due ${formatDate(step.due_date)}.` : null,
            citations.length ? `Legal basis: ${citations.map((c) => c.legal_reference).join(', ')}.` : null,
          ]
            .filter(Boolean)
            .join(' ');

          return (
            <li
              key={step.step_id}
              aria-label={ariaLabel}
              className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4 shadow-sm sm:flex-row sm:items-start sm:justify-between sm:gap-4"
            >
              <div className="flex items-start gap-3">
                <Icon className={cn('mt-0.5 h-5 w-5 shrink-0', visual.className)} aria-hidden="true" />
                <div className="flex flex-col gap-1">
                  <p className="text-sm font-medium text-foreground">
                    <span className="mr-2 tabular-nums text-muted-foreground">
                      {String(index + 1).padStart(2, '0')}.
                    </span>
                    {step.label}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    <span>{visual.label}</span>
                    {step.owner_label ? ` · Owner ${step.owner_label}` : ''}
                    {typeof step.expected_duration_days === 'number'
                      ? ` · ~${step.expected_duration_days}d`
                      : ''}
                  </p>
                  {prereqLabels.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                      After: {prereqLabels.join(' → ')}
                    </p>
                  )}
                  {citations.length > 0 && (
                    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                      {citations.map((c, i) =>
                        c.source_url ? (
                          <a
                            key={i}
                            href={c.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline focus-visible:shadow-focus"
                          >
                            {c.legal_reference}
                            <ExternalLink className="h-3 w-3" aria-hidden="true" />
                          </a>
                        ) : (
                          <span key={i} className="text-muted-foreground">
                            {c.legal_reference}
                          </span>
                        ),
                      )}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex shrink-0 flex-col items-start gap-0.5 sm:items-end">
                <span className="inline-flex items-center gap-1 text-xs tabular-nums text-muted-foreground">
                  {step.due_date && <CalendarClock className="h-3.5 w-3.5" aria-hidden="true" />}
                  Due {formatDate(step.due_date)}
                </span>
                {step.derivation && (
                  <span className="max-w-[16rem] text-right text-[11px] leading-tight text-muted-foreground/80">
                    {step.derivation}
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </SectionShell>
  );
}
