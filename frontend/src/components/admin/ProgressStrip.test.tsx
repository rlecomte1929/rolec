import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ProgressStrip } from './ProgressStrip';

describe('ProgressStrip', () => {
  it('shows the valid next action for the current state', () => {
    render(<ProgressStrip status="dispatched" tier="yellow" busy={false} onAdvance={() => {}} />);
    expect(screen.getByRole('button', { name: /in progress/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^done$/i })).toBeNull();
  });
  it('fires onAdvance with the target state', () => {
    const spy = vi.fn();
    render(<ProgressStrip status="deployed" tier="green" busy={false} onAdvance={spy} />);
    fireEvent.click(screen.getByRole('button', { name: /^done$/i }));
    expect(spy).toHaveBeenCalledWith('done');
  });
  it('shows a "Done ✓" badge and no further actions when done', () => {
    render(<ProgressStrip status="done" busy={false} onAdvance={() => {}} />);
    expect(screen.getByText(/done ✓/i)).toBeInTheDocument();
    // terminal — no forward-action buttons
    expect(screen.queryByRole('button')).toBeNull();
  });
  it('flags verify_failed as needs-attention', () => {
    render(<ProgressStrip status="verify_failed" busy={false} onAdvance={() => {}} />);
    expect(screen.getByText(/needs attention/i)).toBeInTheDocument();
  });
});
