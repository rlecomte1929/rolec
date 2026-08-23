/**
 * [AIQ-2057] Who may tick a step, and what the optimistic overlay does to the numbers.
 *
 * Pure-function half of the completion control. The rules are product rules, not styling:
 * an HR-owned milestone is somebody else's to close, and a plan HR still holds for review
 * is one the server will refuse (`assert_roadmap_released` 409s), so offering the control
 * there would only manufacture an error.
 */
import { describe, expect, it } from 'vitest';
import { applyStatusOverrides, canEmployeeToggle } from './RoadmapTemplate';
import type {
  RelocationPlanPhaseTaskDTO,
  RelocationPlanViewResponseDTO,
} from '../../../types/relocationPlanView';

const task = (over: Partial<RelocationPlanPhaseTaskDTO> = {}): RelocationPlanPhaseTaskDTO =>
  ({
    task_id: 't1',
    task_code: 'code',
    title: 'Register with the local authority',
    status: 'not_started',
    owner: 'employee',
    priority: 'standard',
    is_overdue: false,
    is_due_soon: false,
    blocked_by: [],
    depends_on: [],
    instructions: [],
    required_inputs: [],
    auto_completion_source: 'none',
    notes_enabled: false,
    ...over,
  }) as RelocationPlanPhaseTaskDTO;

describe('canEmployeeToggle', () => {
  it('lets the employee tick their own step', () => {
    expect(canEmployeeToggle(task({ owner: 'employee' }), false)).toBe(true);
  });

  it('lets the employee tick a joint step', () => {
    expect(canEmployeeToggle(task({ owner: 'joint' }), false)).toBe(true);
  });

  it.each(['hr', 'provider'] as const)('does not let the employee close a %s-owned step', (owner) => {
    expect(canEmployeeToggle(task({ owner }), false)).toBe(false);
  });

  it('withholds the control while HR still holds the plan for review', () => {
    // The server 409s here. A control that always errors is worse than no control.
    expect(canEmployeeToggle(task({ owner: 'employee' }), true)).toBe(false);
  });
});

const view = (tasks: RelocationPlanPhaseTaskDTO[]): RelocationPlanViewResponseDTO =>
  ({
    case_id: 'c1',
    role: 'employee',
    summary: {
      total_tasks: tasks.length,
      completed_tasks: tasks.filter((t) => t.status === 'completed').length,
      in_progress_tasks: 0,
      blocked_tasks: 0,
      overdue_tasks: 0,
      due_soon_tasks: 0,
      completion_ratio: 0,
    },
    phases: [
      {
        phase_key: 'before',
        title: 'Before you go',
        status: 'active',
        completion_ratio: 0,
        task_counts: { total: tasks.length, completed: 0, in_progress: 0, blocked: 0 },
        tasks,
      },
    ],
  }) as RelocationPlanViewResponseDTO;

describe('applyStatusOverrides', () => {
  it('returns the very same object when there is nothing to override', () => {
    const v = view([task()]);
    expect(applyStatusOverrides(v, undefined)).toBe(v);
    expect(applyStatusOverrides(v, {})).toBe(v);
  });

  it('returns the same object when the override matches what is already there', () => {
    const v = view([task({ status: 'completed' })]);
    expect(applyStatusOverrides(v, { t1: 'completed' })).toBe(v);
  });

  it('flips the task status', () => {
    const out = applyStatusOverrides(view([task()]), { t1: 'completed' });
    expect(out.phases[0].tasks[0].status).toBe('completed');
  });

  it('moves the phase counter with the tick', () => {
    const out = applyStatusOverrides(
      view([task({ task_id: 't1' }), task({ task_id: 't2' })]),
      { t1: 'completed' },
    );
    expect(out.phases[0].task_counts.completed).toBe(1);
    expect(out.phases[0].completion_ratio).toBe(0.5);
  });

  it('keeps the hero count and the hero percentage in agreement', () => {
    // deriveCanonicalProgress reads completion_ratio for the % and completed_tasks for the
    // "x of y done" text. Updating one and not the other shows two different truths at once.
    const out = applyStatusOverrides(
      view([task({ task_id: 't1' }), task({ task_id: 't2' }), task({ task_id: 't3' }), task({ task_id: 't4' })]),
      { t1: 'completed', t2: 'completed' },
    );
    expect(out.summary.completed_tasks).toBe(2);
    expect(out.summary.completion_ratio).toBe(0.5);
  });

  it('does not mutate the plan it was given', () => {
    const v = view([task()]);
    applyStatusOverrides(v, { t1: 'completed' });
    expect(v.phases[0].tasks[0].status).toBe('not_started');
    expect(v.summary.completed_tasks).toBe(0);
  });

  it('ignores an override for a task that is not in this plan', () => {
    const v = view([task()]);
    expect(applyStatusOverrides(v, { 'not-here': 'completed' })).toBe(v);
  });
});
