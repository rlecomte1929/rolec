/**
 * A corridor step's "easy to miss" trap must render on the roadmap the mover opens.
 *
 * The backend now carries `non_obvious` + `non_obvious_note` onto each corridor step
 * (feat/andrea-roadmap-traps). This is the consumer: without it the note reaches the wire
 * and no component reads it — the same shape as the advisories that #1953 rescued.
 *
 * BUG-260909-73EA: the Tasks list also has to say what is expected, where the
 * requirement comes from, and when to complete it — not just a title.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
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

function renderCard(step: RoadmapV2Step, caseId?: string) {
  return render(
    <MemoryRouter>
      <RoadmapStepCard step={step} caseId={caseId} />
    </MemoryRouter>,
  );
}

describe('RoadmapStepCard — non-obvious trap', () => {
  it('renders the trap note when the step is flagged', () => {
    renderCard({
      ...base,
      non_obvious: true,
      non_obvious_note:
        'If the job is not registered with Revenue before your first pay run, you are put on emergency tax, then all income at the higher 40% rate from week five.',
    });
    const trap = screen.getByTestId('roadmap-step-trap');
    expect(trap).toHaveTextContent('Easy to miss');
    expect(trap).toHaveTextContent(/40% rate from week five/);
  });

  it('renders nothing extra for a routine step', () => {
    renderCard({ ...base, id: 'corridor-ppsn', non_obvious: false });
    expect(screen.queryByTestId('roadmap-step-trap')).not.toBeInTheDocument();
  });

  it('does not render an empty amber box when flagged but note is missing', () => {
    renderCard({ ...base, non_obvious: true, non_obvious_note: null });
    expect(screen.queryByTestId('roadmap-step-trap')).not.toBeInTheDocument();
  });
});

describe('RoadmapStepCard — expected / source / timeline', () => {
  it('shows the description as what is expected and cites the official host', () => {
    renderCard({
      ...base,
      source_url: 'https://www.revenue.ie/en/starting-a-business/registering-a-new-business',
      source_excerpt: 'Employers must register the employment before the first pay run.',
      due_date: '2026-10-01',
      due_date_is_suggested: true,
      estimated_effort: '~15 min',
    });
    expect(screen.getByTestId('task-whats-expected')).toHaveTextContent(/Typically 7 days/);
    const source = screen.getByTestId('task-source');
    expect(source).toHaveTextContent('revenue.ie');
    expect(source).toHaveTextContent(/Employers must register/);
    const timeline = screen.getByTestId('task-timeline');
    expect(timeline).toHaveTextContent(/not a legal deadline/);
    expect(timeline).toHaveTextContent(/~15 min/);
  });

  it('points at the dossier when there is no source URL', () => {
    renderCard({ ...base, source_url: null }, 'case-1');
    const source = screen.getByTestId('task-source');
    expect(source).toHaveTextContent(/destination requirements/i);
    expect(screen.getByRole('link', { name: /Open your destination requirements/i })).toHaveAttribute(
      'href',
      '/employee/case/case-1/dossier',
    );
  });
});
