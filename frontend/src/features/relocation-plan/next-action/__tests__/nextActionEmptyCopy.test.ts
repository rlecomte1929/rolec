import { describe, expect, it } from 'vitest';
import type { RelocationPlanViewResponseDTO } from '../../../../types/relocationPlanView';
import { nextActionCardEmptyCopy } from '../nextActionEmptyCopy';

function basePlan(overrides: Partial<RelocationPlanViewResponseDTO> = {}): RelocationPlanViewResponseDTO {
  return {
    case_id: 'c1',
    role: 'employee',
    summary: {
      total_tasks: 2,
      completed_tasks: 0,
      in_progress_tasks: 0,
      blocked_tasks: 0,
      overdue_tasks: 0,
      due_soon_tasks: 0,
      completion_ratio: 0,
    },
    phases: [
      {
        phase_key: 'p1',
        title: 'Phase',
        status: 'active',
        completion_ratio: 0,
        task_counts: { total: 2, completed: 0, in_progress: 0, blocked: 0 },
        tasks: [],
      },
    ],
    ...overrides,
  };
}

describe('nextActionCardEmptyCopy', () => {
  it('returns all-complete headline when no incomplete tasks', () => {
    const data = basePlan({
      phases: [
        {
          phase_key: 'p1',
          title: 'P',
          status: 'completed',
          completion_ratio: 1,
          task_counts: { total: 1, completed: 1, in_progress: 0, blocked: 0 },
          tasks: [
            {
              task_id: '1',
              task_code: 'a',
              title: 'A',
              status: 'completed',
              owner: 'employee',
              priority: 'standard',
              is_overdue: false,
              is_due_soon: false,
              blocked_by: [],
              depends_on: [],
              instructions: [],
              required_inputs: [],
              auto_completion_source: 'manual',
              notes_enabled: false,
            },
          ],
        },
      ],
      empty_state_reason: '  Synced just now.  ',
    });
    const out = nextActionCardEmptyCopy(data);
    expect(out.headline).toBe('No action required right now');
    expect(out.detail).toBe('Synced just now.');
  });

  it('detects HR-only pipeline', () => {
    const data = basePlan({
      phases: [
        {
          phase_key: 'p1',
          title: 'P',
          status: 'active',
          completion_ratio: 0,
          task_counts: { total: 1, completed: 0, in_progress: 1, blocked: 0 },
          tasks: [
            {
              task_id: '1',
              task_code: 'hr_review',
              title: 'HR review',
              status: 'in_progress',
              owner: 'hr',
              priority: 'standard',
              is_overdue: false,
              is_due_soon: false,
              blocked_by: [],
              depends_on: [],
              instructions: [],
              required_inputs: [],
              auto_completion_source: 'unspecified',
              notes_enabled: false,
            },
          ],
        },
      ],
    });
    expect(nextActionCardEmptyCopy(data).headline).toBe('Waiting for HR review');
  });

  it('prefers API primary empty_state_reason as headline when server sends it', () => {
    const data = basePlan({
      empty_state_reason: 'Waiting for employee action',
      phases: [
        {
          phase_key: 'p1',
          title: 'P',
          status: 'active',
          completion_ratio: 0,
          task_counts: { total: 1, completed: 0, in_progress: 0, blocked: 0 },
          tasks: [
            {
              task_id: '1',
              task_code: 'x',
              title: 'Employee task',
              status: 'not_started',
              owner: 'employee',
              priority: 'standard',
              is_overdue: false,
              is_due_soon: false,
              blocked_by: [],
              depends_on: [],
              instructions: [],
              required_inputs: [],
              auto_completion_source: 'unspecified',
              notes_enabled: false,
            },
          ],
        },
      ],
    });
    const out = nextActionCardEmptyCopy(data);
    expect(out.headline).toBe('Waiting for employee action');
    expect(out.detail).toBeUndefined();
  });

  it('detects provider-only wait', () => {
    const data = basePlan({
      phases: [
        {
          phase_key: 'p1',
          title: 'P',
          status: 'active',
          completion_ratio: 0,
          task_counts: { total: 1, completed: 0, in_progress: 1, blocked: 0 },
          tasks: [
            {
              task_id: '1',
              task_code: 'prov',
              title: 'Vendor step',
              status: 'not_started',
              owner: 'provider',
              priority: 'standard',
              is_overdue: false,
              is_due_soon: false,
              blocked_by: [],
              depends_on: [],
              instructions: [],
              required_inputs: [],
              auto_completion_source: 'unspecified',
              notes_enabled: false,
            },
          ],
        },
      ],
    });
    expect(nextActionCardEmptyCopy(data).headline).toBe('Waiting for provider update');
  });
});
