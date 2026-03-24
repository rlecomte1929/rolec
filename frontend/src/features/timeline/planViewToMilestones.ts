import type { TimelineMilestone, TimelineTaskSummary } from '../../api/client';
import type {
  RelocationPlanPhaseDTO,
  RelocationPlanPhaseTaskDTO,
  RelocationPlanSummaryDTO,
} from '../../types/relocationPlanView';
import { milestoneTypeForTaskCode } from './milestoneTypeByTaskCode';

/** Map API plan status to raw milestone status used by the tracker / PATCH vocabulary. */
export function planStatusToMilestoneStatus(status: string): string {
  switch (status) {
    case 'not_started':
      return 'pending';
    case 'in_progress':
      return 'in_progress';
    case 'completed':
      return 'done';
    case 'blocked':
      return 'blocked';
    case 'not_applicable':
      return 'skipped';
    default:
      return 'pending';
  }
}

function buildDescription(task: RelocationPlanPhaseTaskDTO): string | undefined {
  const parts: string[] = [];
  if (task.why_this_matters) parts.push(task.why_this_matters);
  if (task.instructions?.length) parts.push(task.instructions.map((s) => `• ${s}`).join('\n'));
  return parts.length ? parts.join('\n\n') : undefined;
}

/**
 * Flatten phased plan into the legacy `TimelineMilestone[]` shape for the existing tracker UI.
 */
export function planPhasesToMilestones(phases: RelocationPlanPhaseDTO[], caseId: string): TimelineMilestone[] {
  let sortOrder = 0;
  const out: TimelineMilestone[] = [];
  for (const ph of phases) {
    for (const t of ph.tasks) {
      out.push({
        id: t.task_id,
        case_id: caseId,
        milestone_type: milestoneTypeForTaskCode(t.task_code),
        title: t.title,
        description: buildDescription(t),
        target_date: t.due_date ?? undefined,
        status: planStatusToMilestoneStatus(t.status),
        sort_order: sortOrder++,
        owner: t.owner,
        criticality: t.priority === 'critical' ? 'critical' : 'normal',
        notes: null,
      });
    }
  }
  return out;
}

export function planSummaryToTimelineSummary(s: RelocationPlanSummaryDTO): TimelineTaskSummary {
  return {
    total: s.total_tasks,
    completed: s.completed_tasks,
    overdue: s.overdue_tasks,
    due_this_week: s.due_soon_tasks,
    blocked: s.blocked_tasks,
    in_progress: s.in_progress_tasks,
  };
}
