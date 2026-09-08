import { describe, it, expect } from 'vitest';
import { isIntakeComplete, resolveCaseStage, deriveCanonicalProgress } from './caseStage';
import type { RelocationPlanSummaryDTO } from '../../types/relocationPlanView';

describe('isIntakeComplete', () => {
  it('is true at/after submit (case-insensitive)', () => {
    for (const s of ['submitted', 'approved', 'rejected', 'closed', 'SUBMITTED']) {
      expect(isIntakeComplete(s)).toBe(true);
    }
  });
  it('is false for pre-submit / empty', () => {
    for (const s of ['created', 'assigned', 'awaiting_intake', '', undefined, null]) {
      expect(isIntakeComplete(s as string | undefined)).toBe(false);
    }
  });
});

describe('resolveCaseStage — the one source of truth for every stepper', () => {
  it('submitted case ⇒ intake done, roadmap unlocked, services NOT falsely done', () => {
    // This is exactly what the dashboard, roadmap, and benefit-comparison steppers
    // each render — they all call this function, so they cannot disagree.
    expect(resolveCaseStage({ status: 'submitted' })).toEqual({
      intake: 'done',
      services: 'active', // reachable, but NOT 'done' (item B4)
      roadmap: 'active', // unlocked
    });
  });

  it('services is only done when the Services flow actually completed (B4)', () => {
    expect(resolveCaseStage({ status: 'submitted', servicesComplete: true }).services).toBe('done');
    expect(resolveCaseStage({ status: 'submitted', servicesComplete: false }).services).toBe('active');
  });

  it('pre-intake case ⇒ services + roadmap locked', () => {
    expect(resolveCaseStage({ status: 'awaiting_intake' })).toEqual({
      intake: 'active',
      services: 'locked',
      roadmap: 'locked',
    });
  });
});

describe('deriveCanonicalProgress — the one overall task % definition', () => {
  const summary = (over: Partial<RelocationPlanSummaryDTO>): RelocationPlanSummaryDTO => ({
    total_tasks: 0,
    completed_tasks: 0,
    in_progress_tasks: 0,
    blocked_tasks: 0,
    overdue_tasks: 0,
    due_soon_tasks: 0,
    completion_ratio: 0,
    ...over,
  });

  it('matches the observed case (16 tasks, 1 done, 11 blocked, 6%)', () => {
    const p = deriveCanonicalProgress(
      summary({ total_tasks: 16, completed_tasks: 1, blocked_tasks: 11, completion_ratio: 0.0625 }),
    );
    expect(p).toEqual({ completed: 1, total: 16, pct: 6, blocked: 11, readyNow: 4 });
  });

  it('returns zeros for a null/empty summary (never NaN%)', () => {
    expect(deriveCanonicalProgress(null)).toEqual({
      completed: 0,
      total: 0,
      pct: 0,
      blocked: 0,
      readyNow: 0,
    });
  });
});
