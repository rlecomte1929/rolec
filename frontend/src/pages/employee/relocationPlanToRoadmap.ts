/**
 * [AIQ-1005] Adapt the seeded relocation plan (case_milestones via
 * GET /api/relocation-plans/{id}/view) into the RoadmapScreen track/step shape.
 *
 * Pure mapping, no side-effect imports — kept in its own module so it is unit-
 * testable without dragging in the page's Supabase/API client chain.
 * Used as a fallback in EmployeeCaseRoadmapPage when the case_forms-projected V2
 * roadmap is empty, so the employee sees their actual milestones instead of the
 * "being built" placeholder. Each plan phase becomes a track; each task a step.
 */
import type { RoadmapTrack, RoadmapStep } from '../../types/relopass-api-contracts';
import type {
  RelocationPlanViewResponseDTO,
  RelocationPlanTaskStatusWire,
  RelocationPlanTaskOwnerWire,
} from '../../types/relocationPlanView';

const PLAN_STATUS_TO_STEP: Record<RelocationPlanTaskStatusWire, RoadmapStep['status']> = {
  not_started: 'pending',
  in_progress: 'in_progress',
  completed: 'completed',
  blocked: 'blocked',
  not_applicable: 'skipped',
};

const PLAN_OWNER_TO_STEP: Record<RelocationPlanTaskOwnerWire, RoadmapStep['owner']> = {
  employee: 'employee',
  hr: 'hr',
  joint: 'employee',
  provider: 'vendor',
};

export function adaptPlanViewToTracks(
  plan: RelocationPlanViewResponseDTO
): (RoadmapTrack & { steps: RoadmapStep[] })[] {
  return plan.phases.map((phase, phaseIdx) => ({
    id: phase.phase_key,
    case_id: plan.case_id,
    name: phase.title,
    icon: '',
    sort_order: phaseIdx,
    is_mandatory: true,
    progress_pct: Math.round((phase.completion_ratio ?? 0) * 100),
    created_at: '',
    updated_at: '',
    steps: phase.tasks.map((task, taskIdx) => ({
      id: task.task_id,
      track_id: phase.phase_key,
      case_id: plan.case_id,
      title: task.title,
      description:
        task.why_this_matters ?? (task.instructions.length ? task.instructions.join(' ') : null),
      status: PLAN_STATUS_TO_STEP[task.status] ?? 'pending',
      owner: PLAN_OWNER_TO_STEP[task.owner] ?? 'employee',
      vendor_id: null,
      due_date: task.due_date ?? null,
      completed_at: null,
      sort_order: taskIdx,
      dependency_ids: task.depends_on ?? [],
      ai_suggestion: null,
      created_at: '',
      updated_at: '',
    })),
  }));
}
