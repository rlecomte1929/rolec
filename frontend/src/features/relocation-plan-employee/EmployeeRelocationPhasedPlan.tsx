import React, { useEffect, useRef, useState } from 'react';
import { Button, Card } from '../../components/antigravity';
import { useEmployeeRelocationPlanPageData } from './useEmployeeRelocationPlanPageData';
import { useRelocationPlanCtaHandler } from './relocationPlanCtaNavigate';
import { NextActionCard } from '../relocation-plan/next-action';
import { RelocationPlanPageHeader } from './RelocationPlanPageHeader';
import { RelocationPhaseTimeline } from '../relocation-plan/phase-timeline';
import { RelocationPlanSummaryStrip } from './RelocationPlanSummaryStrip';
import { RelocationTaskCard } from '../relocation-plan/task-card';

export interface EmployeeRelocationPhasedPlanProps {
  routeCaseId: string;
}

export const EmployeeRelocationPhasedPlan: React.FC<EmployeeRelocationPhasedPlanProps> = ({
  routeCaseId,
}) => {
  const { data, loading, error, ensureDefaultsAndReload } =
    useEmployeeRelocationPlanPageData(routeCaseId);
  const runCta = useRelocationPlanCtaHandler(routeCaseId, { resourceCaseId: data?.case_id });
  const [expandedPhases, setExpandedPhases] = useState<Record<string, boolean>>({});
  const seededForAssignment = useRef<string | null>(null);

  useEffect(() => {
    seededForAssignment.current = null;
  }, [routeCaseId]);

  useEffect(() => {
    if (!data?.phases?.length) return;
    if (seededForAssignment.current === routeCaseId) return;
    seededForAssignment.current = routeCaseId;
    // Progressive disclosure: only the active phase is open; completed & upcoming stay collapsed.
    setExpandedPhases(
      Object.fromEntries(data.phases.map((p) => [p.phase_key, p.status === 'active']))
    );
  }, [data, routeCaseId]);

  const backToSummaryHref = `/employee/case/${encodeURIComponent(routeCaseId)}/summary`;

  if (loading && !data) {
    return (
      <main aria-label="Relocation plan" className="min-w-0">
        <RelocationPlanPageHeader backToSummaryHref={backToSummaryHref} />
        <div role="status" aria-live="polite" aria-busy="true">
          <Card padding="lg" className="animate-pulse">
            <p className="text-sm text-[#64748b]">Loading your plan…</p>
            <div className="mt-4 h-24 rounded-lg bg-[#f1f5f9]" />
            <div className="mt-3 h-12 rounded-lg bg-[#f1f5f9] w-2/3" />
          </Card>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main aria-label="Relocation plan" className="min-w-0">
        <RelocationPlanPageHeader backToSummaryHref={backToSummaryHref} />
        <Card padding="lg" className="border-slate-200 bg-slate-50/50">
          <div className="flex flex-col items-center py-8 text-center">
            <svg className="h-10 w-10 text-slate-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <p className="text-sm font-medium text-slate-700">Your plan is being prepared</p>
            <p className="mt-1 text-xs text-slate-400 max-w-xs">
              Your relocation plan will appear here once your HR team has set up your roadmap.
            </p>
          </div>
        </Card>
      </main>
    );
  }

  if (!data) {
    return (
      <main aria-label="Relocation plan" className="min-w-0">
        <RelocationPlanPageHeader backToSummaryHref={backToSummaryHref} />
        <p className="text-sm text-[#64748b]">We couldn&apos;t load this plan.</p>
      </main>
    );
  }

  const emptyPlan = data.summary.total_tasks === 0 || !data.phases?.length;

  if (emptyPlan) {
    return (
      <main aria-label="Relocation plan" className="min-w-0">
        <RelocationPlanPageHeader backToSummaryHref={backToSummaryHref} />
        <Card padding="lg">
          <h2 className="text-base font-semibold text-[#0b2b43]">No tasks yet</h2>
          {data.empty_state_reason ? (
            <p className="text-sm text-[#64748b] mt-2">{data.empty_state_reason}</p>
          ) : (
            <p className="text-sm text-[#64748b] mt-2">
              Your checklist will appear here once HR has set up milestones for this assignment.
            </p>
          )}
          <Button variant="outline" size="sm" className="mt-4" onClick={() => void ensureDefaultsAndReload()}>
            Create default plan
          </Button>
        </Card>
      </main>
    );
  }

  return (
    <main aria-label="Relocation plan" className="min-w-0">
      <RelocationPlanPageHeader backToSummaryHref={backToSummaryHref} />

      <NextActionCard
        ctaContext={{ routeCaseId, resourceCaseId: data.case_id, role: 'employee' }}
        nextAction={data.next_action}
        planView={data}
        onCta={runCta}
      />

      <RelocationPlanSummaryStrip summary={data.summary} />

      <RelocationPhaseTimeline
        className="mt-6"
        timelineLabel="Your relocation roadmap by phase"
        phases={data.phases}
        expandedByPhaseKey={expandedPhases}
        onPhaseToggle={(phaseKey) =>
          setExpandedPhases((prev) => ({
            ...prev,
            [phaseKey]: !prev[phaseKey],
          }))
        }
        renderPhaseContent={(phase) =>
          phase.tasks.map((task) => (
            <RelocationTaskCard
              key={task.task_id}
              task={task}
              ctaContext={{ routeCaseId, resourceCaseId: data.case_id }}
              highlightSuggested={data.next_action?.task_id === task.task_id}
              onCta={runCta}
            />
          ))
        }
      />
    </main>
  );
};
