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
});
