/**
 * Single source of truth for the employee pipeline-stage state and the canonical
 * task-progress numbers. The dashboard widget (JourneySpine), the roadmap page,
 * and the benefit-comparison page MUST all render their "Intake → Services &
 * policy → Roadmap" stepper from `resolveCaseStage`, and every overall task % MUST
 * come from `deriveCanonicalProgress`, so a case can never show contradictory
 * stages or numbers across pages.
 */
import type { RelocationPlanSummaryDTO } from '../../types/relocationPlanView';

// Statuses at/after submit — intake is complete regardless of a stale intakeStep.
const INTAKE_COMPLETE_STATUSES = new Set(['submitted', 'approved', 'rejected', 'closed']);

/**
 * Source of truth for whether intake is finished: the assignment lifecycle status,
 * NOT intakeStep (which can lag — a submitted case may still read step 1).
 */
export function isIntakeComplete(status?: string | null): boolean {
  return !!status && INTAKE_COMPLETE_STATUSES.has(status.trim().toLowerCase());
}

export type StageState = 'done' | 'active' | 'locked';

export interface CaseStageView {
  intake: StageState;
  services: StageState;
  roadmap: StageState;
}

export interface ResolveCaseStageInput {
  /** Authoritative assignment lifecycle status. */
  status?: string | null;
  /** True once the Services sub-flow (select → preferences → recommendations →
   *  review & budget) is genuinely complete. Drives the Services "Done" state so
   *  it's never marked complete just because intake finished (item B4). */
  servicesComplete?: boolean;
}

/**
 * The one resolver. Intake completion gates Services and Roadmap. Services is only
 * "done" when the Services flow actually completed; Roadmap unlocks at submit.
 */
export function resolveCaseStage({ status, servicesComplete }: ResolveCaseStageInput): CaseStageView {
  const intakeDone = isIntakeComplete(status);
  return {
    intake: intakeDone ? 'done' : 'active',
    services: !intakeDone ? 'locked' : servicesComplete ? 'done' : 'active',
    roadmap: intakeDone ? 'active' : 'locked',
  };
}

export interface CanonicalProgress {
  completed: number;
  total: number;
  /** 0–100, derived from the canonical completion_ratio. */
  pct: number;
  blocked: number;
  /** Actionable now = not done and not blocked. */
  readyNow: number;
}

/**
 * The one overall-progress definition: completed/total tasks from the canonical
 * relocation-plan summary. Reuse everywhere a top-level task % is shown, and always
 * label it ("X% of tasks done") so it can't be confused with the dossier
 * fields-filled % or the intake step %.
 */
export function deriveCanonicalProgress(summary: RelocationPlanSummaryDTO | null | undefined): CanonicalProgress {
  const total = summary?.total_tasks ?? 0;
  const completed = summary?.completed_tasks ?? 0;
  const blocked = summary?.blocked_tasks ?? 0;
  const pct = total > 0 ? Math.min(100, Math.round((summary?.completion_ratio ?? 0) * 100)) : 0;
  return { completed, total, pct, blocked, readyNow: Math.max(0, total - completed - blocked) };
}
