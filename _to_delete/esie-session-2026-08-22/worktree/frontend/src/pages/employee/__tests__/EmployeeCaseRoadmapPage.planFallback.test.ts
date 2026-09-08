/**
 * [AIQ-1005] EmployeeCaseRoadmapPage — relocation-plan fallback adapter.
 *
 * When the case_forms-projected V2 roadmap is empty, the page falls back to the
 * seeded relocation plan (case_milestones via /api/relocation-plans/{id}/view).
 * `adaptPlanViewToTracks` maps that response into the RoadmapScreen track/step
 * shape so the employee sees their milestones instead of the "being built"
 * placeholder. These tests pin the mapping (phase→track, task→step, status/owner).
 */
import { describe, it, expect } from 'vitest';
import { adaptPlanViewToTracks } from '../relocationPlanToRoadmap';
import type { RelocationPlanViewResponseDTO } from '../../../types/relocationPlanView';

function makePlan(): RelocationPlanViewResponseDTO {
  return {
    case_id: 'case-1',
    assignment_id: 'asg-1',
    role: 'employee',
    summary: {
      total_tasks: 3,
      completed_tasks: 1,
      in_progress_tasks: 1,
      blocked_tasks: 0,
      overdue_tasks: 0,
      due_soon_tasks: 0,
      completion_ratio: 0.33,
    },
    next_action: null,
    phases: [
      {
        phase_key: 'pre_move',
        title: 'Before you move',
        status: 'active',
        completion_ratio: 0.5,
        task_counts: { total: 2, completed: 1, in_progress: 1, blocked: 0 },
        tasks: [
          {
            task_id: 't1',
            task_code: 'ANMELDUNG',
            title: 'Register address (Anmeldung)',
            short_label: null,
            status: 'completed',
            owner: 'employee',
            priority: 'standard',
            due_date: '2026-09-15',
            is_overdue: false,
            is_due_soon: false,
            blocked_by: [],
            depends_on: [],
            why_this_matters: 'Required within 14 days of arrival.',
            instructions: ['Book a Bürgeramt appointment'],
            required_inputs: [],
            cta: null,
            auto_completion_source: 'manual',
            notes_enabled: true,
          },
          {
            task_id: 't2',
            task_code: 'TAXID',
            title: 'Get your Steuer-ID',
            short_label: null,
            status: 'in_progress',
            owner: 'joint',
            priority: 'standard',
            due_date: null,
            is_overdue: false,
            is_due_soon: false,
            blocked_by: [],
            depends_on: ['t1'],
            why_this_matters: null,
            instructions: [],
            required_inputs: [],
            cta: null,
            auto_completion_source: 'system_rule',
            notes_enabled: true,
          },
        ],
      },
      {
        phase_key: 'at_arrival',
        title: 'When you arrive',
        status: 'upcoming',
        completion_ratio: 0,
        task_counts: { total: 1, completed: 0, in_progress: 0, blocked: 1 },
        tasks: [
          {
            task_id: 't3',
            task_code: 'BANK',
            title: 'Open a German bank account',
            short_label: null,
            status: 'blocked',
            owner: 'provider',
            priority: 'standard',
            due_date: null,
            is_overdue: false,
            is_due_soon: false,
            blocked_by: ['t1'],
            depends_on: [],
            why_this_matters: null,
            instructions: ['Bring your Anmeldung certificate', 'and passport'],
            required_inputs: [],
            cta: null,
            auto_completion_source: 'unspecified',
            notes_enabled: true,
          },
        ],
      },
    ],
    last_evaluated_at: null,
    data_freshness: null,
    empty_state_reason: null,
    debug: null,
  };
}

describe('adaptPlanViewToTracks', () => {
  it('maps each phase to a track and each task to a step', () => {
    const tracks = adaptPlanViewToTracks(makePlan());
    expect(tracks).toHaveLength(2);
    expect(tracks[0].name).toBe('Before you move');
    expect(tracks[0].id).toBe('pre_move');
    expect(tracks[0].progress_pct).toBe(50);
    expect(tracks[0].steps).toHaveLength(2);
    expect(tracks[1].steps).toHaveLength(1);
    // Titles carry through — corridor-specific content reaches the UI.
    expect(tracks[0].steps[0].title).toBe('Register address (Anmeldung)');
    expect(tracks[1].steps[0].title).toBe('Open a German bank account');
  });

  it('maps task status and owner to the RoadmapStep vocabulary', () => {
    const [pre, arrival] = adaptPlanViewToTracks(makePlan());
    expect(pre.steps[0].status).toBe('completed');
    expect(pre.steps[0].owner).toBe('employee');
    expect(pre.steps[1].status).toBe('in_progress');
    expect(pre.steps[1].owner).toBe('employee'); // joint → employee
    expect(arrival.steps[0].status).toBe('blocked');
    expect(arrival.steps[0].owner).toBe('vendor'); // provider → vendor
  });

  it('derives description from why_this_matters, then instructions', () => {
    const [pre, arrival] = adaptPlanViewToTracks(makePlan());
    expect(pre.steps[0].description).toBe('Required within 14 days of arrival.');
    expect(pre.steps[1].description).toBeNull(); // no why + no instructions
    expect(arrival.steps[0].description).toBe('Bring your Anmeldung certificate and passport');
    expect(pre.steps[1].dependency_ids).toEqual(['t1']);
  });

  it('returns no tracks for an empty plan (placeholder stays)', () => {
    const empty = { ...makePlan(), phases: [] };
    expect(adaptPlanViewToTracks(empty)).toEqual([]);
  });
});
