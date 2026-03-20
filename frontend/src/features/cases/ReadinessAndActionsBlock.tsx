import React, { useMemo, useState } from 'react';
import { Badge, Card } from '../../components/antigravity';
import type { AssignmentDetail } from '../../types';
import { scrollToPlanTask } from './CaseOperationalSection';

function statusBadgeVariant(
  status: string
): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (status === 'ready') return 'success';
  if (status === 'missing_information') return 'warning';
  if (status === 'human_review_required') return 'error';
  if (status === 'needs_review') return 'info';
  return 'neutral';
}

function PlanJumpLink({ milestoneType, label }: { milestoneType: string; label: string }) {
  return (
    <button
      type="button"
      onClick={() => scrollToPlanTask(milestoneType)}
      className="ml-2 text-xs font-medium text-[#1d4ed8] hover:underline whitespace-nowrap"
    >
      {label}
    </button>
  );
}

type Props = {
  assignment: AssignmentDetail;
  /** Hide duplicate section label when wrapped by CaseOperationalSection */
  embedInOperationalFlow?: boolean;
};

/**
 * Merged profile completeness + compliance + route checklist — one actionable block.
 * Linked to relocation plan rows via linked_tracker_task_type (same case, no duplicate engine).
 */
export const ReadinessAndActionsBlock: React.FC<Props> = ({
  assignment,
  embedInOperationalFlow = false,
}) => {
  const ui = assignment.caseReadinessUi;
  const [showIntakeDetail, setShowIntakeDetail] = useState(false);

  const intake = assignment.intakeChecklist ?? [];

  const pctExplicit = useMemo(() => {
    if (!ui || ui.intake_total <= 0) return null;
    return Math.round((ui.intake_satisfied / ui.intake_total) * 100);
  }, [ui]);

  if (!ui) {
    return (
      <Card padding="md" className="border border-amber-200 bg-amber-50/50">
        <p className="text-sm text-[#7a5e2a]">
          Readiness summary is not available. Refresh the page or redeploy the API to load the merged readiness
          view.
        </p>
      </Card>
    );
  }

  return (
    <Card padding="lg" className="border border-[#e2e8f0] shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-start sm:justify-between">
        <div>
          {!embedInOperationalFlow && (
            <div className="text-xs font-semibold uppercase tracking-wide text-[#64748b]">
              Readiness &amp; actions
            </div>
          )}
          <div className={`flex flex-wrap items-center gap-2 ${embedInOperationalFlow ? '' : 'mt-1'}`}>
            <span className="text-xl font-semibold text-[#0b2b43]">{ui.overall_label}</span>
            <Badge variant={statusBadgeVariant(ui.overall_status)}>{ui.overall_status.replace(/_/g, ' ')}</Badge>
          </div>
          <p className="text-sm text-[#475569] mt-2 max-w-3xl">{ui.completion_basis}</p>
          <p className="text-xs text-[#64748b] mt-2 max-w-3xl leading-relaxed">
            Intake checkpoints and compliance flags here are tied to <strong>relocation plan</strong> tasks in step 3
            (same case). Use the plan for <strong>who owns</strong> each step and <strong>when it is due</strong> —
            not legal verification unless an official source is cited in Case readiness.
          </p>
          {pctExplicit !== null && (
            <p className="text-xs text-[#64748b] mt-1">
              Intake checkpoints: {pctExplicit}% ({ui.intake_satisfied}/{ui.intake_total}) — explicit fields below, not
              a black-box score. Plan task completion is tracked separately in step 3.
            </p>
          )}
        </div>
        {ui.next_deadline_display && (
          <div className="rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-3 py-2 text-sm shrink-0">
            <div className="text-[11px] font-medium text-[#64748b] uppercase tracking-wide">Next target date</div>
            <div className="font-semibold text-[#0b2b43]">{ui.next_deadline_display}</div>
            <p className="text-[10px] text-[#64748b] mt-1 max-w-[200px]">
              Aligns with profile dates; compare to overdue / due-this-week counts in the plan.
            </p>
          </div>
        )}
      </div>

      <p className="text-xs text-[#64748b] mt-4 border-t border-[#e2e8f0] pt-3 leading-relaxed">{ui.trust_banner}</p>

      <div className="mt-4">
        <button
          type="button"
          onClick={() => setShowIntakeDetail((v) => !v)}
          className="text-sm font-medium text-[#1d4ed8] hover:underline"
        >
          {showIntakeDetail ? 'Hide' : 'Show'} intake checkpoint detail ({intake.filter((i) => i.satisfied).length}/
          {intake.length} satisfied)
        </button>
        {showIntakeDetail && intake.length > 0 && (
          <ul className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
            {intake.map((row) => (
              <li
                key={row.key}
                className={`rounded-lg border px-3 py-2 ${
                  row.satisfied ? 'border-emerald-200 bg-emerald-50/60' : 'border-[#e2e8f0] bg-[#fafbfc]'
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-1">
                  <span className="text-[#0f172a]">{row.label}</span>
                  {!row.satisfied && row.linked_tracker_task_type && (
                    <PlanJumpLink milestoneType={row.linked_tracker_task_type} label="→ Plan step" />
                  )}
                </div>
                <span className={`text-xs font-medium ${row.satisfied ? 'text-emerald-800' : 'text-[#64748b]'}`}>
                  {row.satisfied ? 'Done' : 'Missing / not confirmed'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-5">
        <div className="text-sm font-semibold text-[#0b2b43]">Blocking / review items</div>
        {ui.blocking_items.length === 0 ? (
          <p className="text-sm text-[#64748b] mt-2">
            None flagged from intake, route checklist, or latest compliance run.
          </p>
        ) : (
          <ul className="mt-2 space-y-2">
            {ui.blocking_items.map((b, idx) => (
              <li
                key={`${b.source}-${b.title}-${idx}`}
                className="rounded-lg border border-[#e2e8f0] bg-white px-3 py-2 text-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium text-[#0f172a]">{b.title}</span>
                  <div className="flex flex-wrap items-center gap-1">
                    {b.linked_tracker_task_type && (
                      <PlanJumpLink milestoneType={b.linked_tracker_task_type} label="Open in plan" />
                    )}
                    <Badge variant="neutral" size="sm">
                      {b.source}
                    </Badge>
                    {b.human_review_required && (
                      <Badge variant="warning" size="sm">
                        Human review
                      </Badge>
                    )}
                  </div>
                </div>
                {b.detail && <p className="text-xs text-[#64748b] mt-1">{b.detail}</p>}
                {b.provenance_note && (
                  <p className="text-xs italic text-[#94a3b8] mt-1">{b.provenance_note}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-5">
        <div className="text-sm font-semibold text-[#0b2b43]">Suggested next actions</div>
        {ui.next_actions.length === 0 ? (
          <p className="text-sm text-[#64748b] mt-2">
            No automated suggestions — case may be in good shape for the checks above.
          </p>
        ) : (
          <ol className="mt-2 list-decimal list-inside space-y-2 text-sm text-[#334155]">
            {ui.next_actions.map((a, i) => (
              <li key={i} className="pl-1">
                <span>{a.title}</span>
                <span className="text-xs text-[#94a3b8] ml-1">({a.category})</span>
                {a.linked_tracker_task_type && (
                  <PlanJumpLink milestoneType={a.linked_tracker_task_type} label="Jump to plan task" />
                )}
              </li>
            ))}
          </ol>
        )}
      </div>

      {assignment.readinessSnapshot && !assignment.readinessSnapshot.resolved && (
        <p className="text-xs text-[#64748b] mt-4">
          After the plan, expand <strong>Case readiness</strong> for template pointers when the route is configured.
        </p>
      )}
    </Card>
  );
};
