import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { StepRail } from './StepRail';

afterEach(cleanup);

const STEPS = [
  { label: 'Your move', status: 'done' as const },
  { label: 'Your household', status: 'current' as const },
  { label: 'Services', status: 'upcoming' as const },
];

describe('StepRail', () => {
  it('renders all step labels and the step counter', () => {
    render(<StepRail steps={STEPS} />);
    expect(screen.getByText('Your move')).toBeInTheDocument();
    expect(screen.getByText('Your household')).toBeInTheDocument();
    expect(screen.getByText(/Step 2 of 3/i)).toBeInTheDocument();
  });
  it('invokes onSelect with the index for a done step', () => {
    const onSelect = vi.fn();
    render(<StepRail steps={STEPS} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('Your move'));
    expect(onSelect).toHaveBeenCalledWith(0);
  });
  it('does not invoke onSelect for an upcoming step', () => {
    const onSelect = vi.fn();
    render(<StepRail steps={STEPS} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('Services'));
    expect(onSelect).not.toHaveBeenCalled();
  });
});
