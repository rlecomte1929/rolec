/**
 * RelocationTimeline Storybook stories — AIQ-3-C
 *
 * NOTE: Storybook is not currently installed in this project.
 * These stories are written in CSF 3 format and are ready to use
 * once `@storybook/react` + `@storybook/vite` are added.
 *
 * To install: npm install --save-dev @storybook/react @storybook/vite
 */

// @ts-expect-error — storybook not yet installed; see note above
import type { StoryObj } from '@storybook/react';
import { RelocationTimeline } from './RelocationTimeline';
import type { RelocationPlanViewResponseDTO } from '../../types/relocationPlanView';

// ─── Mock data factories ──────────────────────────────────────────────────────

const today = new Date().toISOString().slice(0, 10);
const pastDate = '2026-04-10';
const futureDate = '2026-06-15';
const soonDate = new Date(Date.now() + 4 * 86400_000).toISOString().slice(0, 10);

import type { RelocationPlanPhaseTaskDTO } from '../../types/relocationPlanView';

function makeTask(
  overrides: Partial<RelocationPlanPhaseTaskDTO> & { task_id: string; title: string }
): RelocationPlanPhaseTaskDTO {
  const { task_id, title, ...rest } = overrides;
  return {
    task_id,
    task_code: `task_${task_id}`,
    title,
    status: 'not_started',
    owner: 'employee',
    priority: 'standard',
    due_date: futureDate,
    is_overdue: false,
    is_due_soon: false,
    blocked_by: [],
    depends_on: [],
    instructions: [],
    required_inputs: [],
    auto_completion_source: 'manual',
    notes_enabled: true,
    why_this_matters: undefined,
    cta: null,
    short_label: null,
    ...rest,
  };
}

const MIXED_PHASES: RelocationPlanViewResponseDTO['phases'] = [
  {
    phase_key: 'case_opened',
    title: 'Case opened',
    status: 'completed',
    completion_ratio: 1,
    task_counts: { total: 2, completed: 2, in_progress: 0, blocked: 0 },
    tasks: [
      makeTask({ task_id: 't1', title: 'Complete relocation profile', status: 'completed' }),
      makeTask({ task_id: 't2', title: 'Upload passport', status: 'completed', owner: 'employee' }),
    ],
  },
  {
    phase_key: 'visa_prep',
    title: 'Visa preparation',
    status: 'active',
    completion_ratio: 0.25,
    task_counts: { total: 4, completed: 1, in_progress: 1, blocked: 1 },
    tasks: [
      makeTask({
        task_id: 't3',
        title: 'Prepare visa documents',
        status: 'not_started',
        is_overdue: true,
        due_date: pastDate,
        owner: 'employee',
        priority: 'critical',
        why_this_matters: 'Visa processing takes 6–8 weeks — delays here cascade to move date.',
      }),
      makeTask({
        task_id: 't4',
        title: 'Submit visa application',
        status: 'in_progress',
        due_date: soonDate,
        is_due_soon: true,
        owner: 'employee',
      }),
      makeTask({
        task_id: 't5',
        title: 'Immigration review',
        status: 'blocked',
        due_date: soonDate,
        owner: 'hr',
        instructions: ['Awaiting documents from employee before review can begin.'],
      }),
      makeTask({ task_id: 't6', title: 'Biometrics appointment', status: 'not_started', owner: 'employee' }),
    ],
  },
  {
    phase_key: 'arrival',
    title: 'Arrival',
    status: 'upcoming',
    completion_ratio: 0,
    task_counts: { total: 3, completed: 0, in_progress: 0, blocked: 0 },
    tasks: [
      makeTask({ task_id: 't7', title: 'Arrange temporary housing', status: 'not_started', owner: 'employee' }),
      makeTask({ task_id: 't8', title: 'Confirm travel plan', status: 'not_started', due_date: futureDate }),
      makeTask({ task_id: 't9', title: 'Register on arrival', status: 'not_started', owner: 'joint', due_date: futureDate }),
    ],
  },
];

function mockView(
  phases: RelocationPlanViewResponseDTO['phases'],
  overrides?: Partial<RelocationPlanViewResponseDTO>
): RelocationPlanViewResponseDTO {
  const allTasks = phases.flatMap((p) => p.tasks);
  const completed = allTasks.filter((t) => t.status === 'completed').length;
  const overdue = allTasks.filter((t) => t.is_overdue).length;
  const blocked = allTasks.filter((t) => t.status === 'blocked').length;
  const inProgress = allTasks.filter((t) => t.status === 'in_progress').length;
  return {
    case_id: 'case-mock-001',
    assignment_id: 'assign-mock-001',
    role: 'employee',
    phases,
    summary: {
      total_tasks: allTasks.length,
      completed_tasks: completed,
      in_progress_tasks: inProgress,
      blocked_tasks: blocked,
      overdue_tasks: overdue,
      due_soon_tasks: 0,
      completion_ratio: allTasks.length ? completed / allTasks.length : 0,
    },
    next_action: overdue > 0
      ? {
          task_id: allTasks.find((t) => t.is_overdue)?.task_id ?? '',
          title: allTasks.find((t) => t.is_overdue)?.title ?? '',
          owner: 'employee',
          status: 'not_started',
          priority: 'critical',
          due_date: pastDate,
          reason: 'Overdue',
          cta: null,
          blocking: true,
        }
      : null,
    last_evaluated_at: today,
    ...overrides,
  };
}

// ─── Mock API shim ────────────────────────────────────────────────────────────

/**
 * Stories use a parameter `mockView` (RelocationPlanViewResponseDTO) that a
 * Storybook decorator intercepts to stub `fetchRelocationPlanView`.
 * Install `msw-storybook-addon` for full network mocking, or use the decorator
 * pattern below.
 */

// ─── Meta ─────────────────────────────────────────────────────────────────────

const meta = {
  title: 'Features/Timeline/RelocationTimeline',
  component: RelocationTimeline,
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component:
          'Vertical timeline replacing the accordion-list task tracker on the employee dashboard. Desktop: 2-column (list + sticky detail panel). Mobile: single-column with bottom sheet (AIQ-3-D).',
      },
    },
  },
  args: {
    assignmentId: 'assign-mock-001',
    role: 'employee',
  },
};

export default meta;
type Story = StoryObj<typeof meta>;

// ─── Stories ──────────────────────────────────────────────────────────────────

/** Default: 3 phases, mix of all 5 statuses. */
export const Default: Story = {
  parameters: {
    mockView: mockView(MIXED_PHASES),
  },
};

/** All tasks overdue — worst-case visual test. */
export const AllOverdue: Story = {
  parameters: {
    mockView: mockView([
      {
        phase_key: 'visa_prep',
        title: 'Visa preparation',
        status: 'active',
        completion_ratio: 0,
        task_counts: { total: 3, completed: 0, in_progress: 0, blocked: 0 },
        tasks: [
          makeTask({ task_id: 'o1', title: 'Prepare visa documents', status: 'not_started', is_overdue: true, due_date: pastDate }),
          makeTask({ task_id: 'o2', title: 'Submit visa application', status: 'in_progress', is_overdue: true, due_date: pastDate }),
          makeTask({ task_id: 'o3', title: 'Biometrics appointment', status: 'not_started', is_overdue: true, due_date: pastDate }),
        ],
      },
    ]),
  },
};

/** All tasks done — success state. */
export const AllDone: Story = {
  parameters: {
    mockView: mockView([
      {
        phase_key: 'case_opened',
        title: 'Case opened',
        status: 'completed',
        completion_ratio: 1,
        task_counts: { total: 3, completed: 3, in_progress: 0, blocked: 0 },
        tasks: [
          makeTask({ task_id: 'd1', title: 'Complete relocation profile', status: 'completed' }),
          makeTask({ task_id: 'd2', title: 'Upload passport', status: 'completed' }),
          makeTask({ task_id: 'd3', title: 'Confirm move date', status: 'completed' }),
        ],
      },
    ]),
  },
};

/** No milestones — empty state. */
export const Empty: Story = {
  parameters: {
    mockView: mockView([]),
  },
};

/** Skeleton loading state. */
export const Loading: Story = {
  args: { assignmentId: '__loading__' },
};

/** API error state. */
export const Error: Story = {
  args: { assignmentId: '__error__' },
};

/** Single phase, 2 tasks. */
export const SinglePhase: Story = {
  parameters: {
    mockView: mockView([
      {
        phase_key: 'arrival',
        title: 'Arrival',
        status: 'active',
        completion_ratio: 0.5,
        task_counts: { total: 2, completed: 1, in_progress: 0, blocked: 0 },
        tasks: [
          makeTask({ task_id: 's1', title: 'Arrange temporary housing', status: 'completed' }),
          makeTask({ task_id: 's2', title: 'Register on arrival', status: 'not_started', due_date: soonDate, is_due_soon: true }),
        ],
      },
    ]),
  },
};

/** role="employee" — HR edit controls hidden; HR-owned tasks view-only. */
export const EmployeeRole: Story = {
  args: { role: 'employee' },
  parameters: { mockView: mockView(MIXED_PHASES) },
};

/** role="hr" — all controls visible including target_date, owner, skip. */
export const HrRole: Story = {
  args: { role: 'hr' },
  parameters: { mockView: mockView(MIXED_PHASES) },
};

/** Simulated 375px mobile viewport (bottom sheet handled in AIQ-3-D). */
export const MobileViewport: Story = {
  parameters: {
    viewport: { defaultViewport: 'mobile1' },
    mockView: mockView(MIXED_PHASES),
  },
};

/** All tasks in "blocked" state — tests the amber visual path. */
export const AllBlocked: Story = {
  parameters: {
    mockView: mockView([
      {
        phase_key: 'visa_prep',
        title: 'Visa preparation',
        status: 'blocked',
        completion_ratio: 0,
        task_counts: { total: 2, completed: 0, in_progress: 0, blocked: 2 },
        tasks: [
          makeTask({ task_id: 'b1', title: 'Prepare visa documents', status: 'blocked', owner: 'employee' }),
          makeTask({ task_id: 'b2', title: 'Immigration review', status: 'blocked', owner: 'hr' }),
        ],
      },
    ]),
  },
};
