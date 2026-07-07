import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ProgressStrip } from './ProgressStrip';

describe('ProgressStrip (visual flowchart — AIQ-1478)', () => {
  it('renders all 8 pipeline steps as a passive stepper with no advance buttons', () => {
    render(<ProgressStrip status="dispatched" tier="yellow" />);
    // labels for every step
    for (const label of ['New', 'Triaged', 'Spec drafted', 'Dispatched', 'In progress', 'In review', 'Deployed', 'Done']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    // passive: the manual "Mark in progress" advance button is gone
    expect(screen.queryByRole('button', { name: /in progress/i })).toBeNull();
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('marks completed / active / pending steps via aria-labels', () => {
    render(<ProgressStrip status="dispatched" />);
    // dispatched is index 3 → New/Triaged/Spec drafted completed, Dispatched active, rest pending
    expect(screen.getByLabelText(/Step 1: New — completed/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Step 4: Dispatched — active/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Step 8: Done — pending/)).toBeInTheDocument();
  });

  it('shows a "Done ✓" badge when done', () => {
    render(<ProgressStrip status="done" />);
    expect(screen.getByText(/done ✓/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Step 8: Done — active/)).toBeInTheDocument();
  });

  it('flags verify_failed as needs-attention', () => {
    render(<ProgressStrip status="verify_failed" />);
    expect(screen.getByText(/needs attention/i)).toBeInTheDocument();
  });
});
