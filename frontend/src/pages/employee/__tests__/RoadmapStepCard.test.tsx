/**
 * A corridor step's "easy to miss" trap must render on the roadmap the mover opens.
 *
 * The backend now carries `non_obvious` + `non_obvious_note` onto each corridor step
 * (feat/andrea-roadmap-traps). This is the consumer: without it the note reaches the wire
 * and no component reads it — the same shape as the advisories that #1953 rescued.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RoadmapStepCard } from '../EmployeeTaskPage';
import type { RoadmapV2Step } from '../../../api/roadmapV2';

const base: RoadmapV2Step = {
  id: 'corridor-revenue_registration',
  title: 'Register the employment with Revenue (myAccount / RPN) to avoid emergency tax',
  description: 'Typically 7 days.',
  status: 'pending',
  owner: 'employee',
  due_date: null,
  sort_order: 500,
  ai_suggestion: null,
  dependency_ids: [],
  vendor_id: null,
  doc_count: 0,
  worst_doc_status: null,
};

describe('RoadmapStepCard — non-obvious trap', () => {
  it('renders the trap note when the step is flagged', () => {
    render(
      <RoadmapStepCard
        step={{
          ...base,
          non_obvious: true,
          non_obvious_note:
            'If the job is not registered with Revenue before your first pay run, you are put on emergency tax, then all income at the higher 40% rate from week five.',
        }}
      />,
    );
    const trap = screen.getByTestId('roadmap-step-trap');
    expect(trap).toHaveTextContent('Easy to miss');
    expect(trap).toHaveTextContent(/40% rate from week five/);
  });

  it('renders nothing extra for a routine step', () => {
    render(<RoadmapStepCard step={{ ...base, id: 'corridor-ppsn', non_obvious: false }} />);
    expect(screen.queryByTestId('roadmap-step-trap')).not.toBeInTheDocument();
  });

  it('does not render an empty amber box when flagged but note is missing', () => {
    render(<RoadmapStepCard step={{ ...base, non_obvious: true, non_obvious_note: null }} />);
    expect(screen.queryByTestId('roadmap-step-trap')).not.toBeInTheDocument();
  });
});
