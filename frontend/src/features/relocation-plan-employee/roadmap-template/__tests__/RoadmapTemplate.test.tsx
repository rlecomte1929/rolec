import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RoadmapTemplate } from '../RoadmapTemplate';
import type { RelocationPlanViewResponseDTO } from '../../../../types/relocationPlanView';

vi.mock('../../../platform-v2/roadmap/RoadmapActions', () => ({
  RoadmapActions: () => null,
}));

const data: RelocationPlanViewResponseDTO = {
  case_id: 'case-1',
  role: 'employee',
  summary: {
    total_tasks: 1,
    completed_tasks: 1,
    in_progress_tasks: 0,
    blocked_tasks: 0,
    overdue_tasks: 0,
    due_soon_tasks: 0,
    completion_ratio: 1,
  },
  phases: [
    {
      phase_key: 'prepare',
      title: 'Prepare',
      status: 'completed',
      completion_ratio: 1,
      task_counts: { total: 1, completed: 1, in_progress: 0, blocked: 0 },
      tasks: [],
    },
  ],
};

describe('RoadmapTemplate', () => {
  it('shows roadmap validation status in the hero', () => {
    render(
      <RoadmapTemplate
        data={data}
        header={{ originCity: 'Dubai', destCity: 'Toronto', destCountry: 'CA' }}
        caseId="case-1"
        onCta={() => {}}
        validated
        validatedAt="2026-06-26T00:00:00.000Z"
        validating={false}
        onValidate={() => {}}
      />,
    );

    expect(screen.getByText(/Roadmap validated/)).toBeInTheDocument();
    expect(screen.queryByText(/Your tasks are unlocked/)).not.toBeInTheDocument();
  });
});
