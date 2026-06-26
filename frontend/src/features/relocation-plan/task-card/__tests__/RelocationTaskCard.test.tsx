import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import { RelocationTaskCard } from '../RelocationTaskCard';
import type { RelocationPlanPhaseTaskDTO } from '../../../../types/relocationPlanView';

function task(overrides: Partial<RelocationPlanPhaseTaskDTO> = {}): RelocationPlanPhaseTaskDTO {
  return {
    task_id: 'm1',
    task_code: 'upload_passport_copy',
    title: 'Upload passport copy',
    short_label: null,
    status: 'not_started',
    owner: 'employee',
    priority: 'standard',
    due_date: '2026-04-01',
    is_overdue: false,
    is_due_soon: true,
    blocked_by: [],
    depends_on: [],
    why_this_matters: 'HR needs this to start compliance review.',
    instructions: ['Use a color scan', 'PDF under 10MB'],
    required_inputs: [
      { type: 'document', key: 'passport', label: 'Passport copy', present: false },
    ],
    cta: { type: 'upload_document', label: 'Upload document' },
    auto_completion_source: 'unspecified',
    notes_enabled: false,
    ...overrides,
  };
}

const ctx = { routeCaseId: 'aid-1', resourceCaseId: 'cid-1', role: 'employee' as const };

afterEach(() => {
  cleanup();
});

describe('RelocationTaskCard', () => {
  it('shows compact row with due date and expands for details + single CTA', async () => {
    const user = userEvent.setup();
    const onCta = vi.fn();
    render(<RelocationTaskCard task={task()} ctaContext={ctx} onCta={onCta} />);

    expect(screen.getByText('Upload passport copy')).toBeInTheDocument();
    expect(screen.getByText(/Due soon · 2026-04-01/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Upload passport copy/i }));
    expect(screen.getByText(/Why this matters/i)).toBeInTheDocument();
    expect(screen.getByText(/HR needs this to start compliance review/i)).toBeInTheDocument();
    expect(screen.getByText(/Use a color scan/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Upload document/i })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Upload document/i }));
    expect(onCta).toHaveBeenCalledTimes(1);
  });

  it('shows inline blocker copy when blocked_by is non-empty and hides primary CTA', async () => {
    const user = userEvent.setup();
    render(
      <RelocationTaskCard
        task={task({ status: 'in_progress', blocked_by: ['prior_task'] })}
        ctaContext={ctx}
        onCta={vi.fn()}
      />
    );
    expect(screen.getByText(/Waiting on prior steps: prior_task/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Upload passport copy/i }));
    expect(screen.queryByRole('button', { name: /Upload document/i })).not.toBeInTheDocument();
    expect(screen.getByText(/can't be completed here until the blockers/i)).toBeInTheDocument();
  });

  it('omits primary CTA when task is completed', async () => {
    const user = userEvent.setup();
    render(
      <RelocationTaskCard
        task={task({ status: 'completed' })}
        ctaContext={ctx}
        onCta={vi.fn()}
      />
    );
    await user.click(screen.getByRole('button', { name: /Upload passport copy/i }));
    expect(screen.queryByRole('button', { name: /Upload document/i })).not.toBeInTheDocument();
  });

  it('renders notes textarea when notes_enabled and notes prop provided', async () => {
    const user = userEvent.setup();
    render(
      <RelocationTaskCard
        task={task({ notes_enabled: true })}
        ctaContext={ctx}
        onCta={vi.fn()}
        notes={{ value: 'Hello', onChange: vi.fn() }}
      />
    );
    await user.click(screen.getByRole('button', { name: /Upload passport copy/i }));
    expect(screen.getByPlaceholderText(/Short context/i)).toHaveValue('Hello');
  });
});
