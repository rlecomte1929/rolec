import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { PhaseContextBar } from './PhaseContextBar';

afterEach(cleanup);

const PHASES = [
  { key: 'intake', label: 'Intake', status: 'done' as const },
  { key: 'services', label: 'Services & policy', status: 'current' as const },
  { key: 'roadmap', label: 'Roadmap', status: 'upcoming' as const },
];

describe('PhaseContextBar', () => {
  it('renders all phase labels', () => {
    render(<PhaseContextBar phases={PHASES} />);
    expect(screen.getByText('Intake')).toBeInTheDocument();
    expect(screen.getByText('Services & policy')).toBeInTheDocument();
    expect(screen.getByText('Roadmap')).toBeInTheDocument();
  });
  it('marks the current phase with aria-current', () => {
    render(<PhaseContextBar phases={PHASES} />);
    expect(screen.getByText('Services & policy').closest('[aria-current="step"]')).toBeTruthy();
  });
  it('calls onSelect with the phase key when a done phase is clicked', () => {
    const onSelect = vi.fn();
    render(<PhaseContextBar phases={PHASES} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('Intake'));
    expect(onSelect).toHaveBeenCalledWith('intake');
  });
  it('does NOT call onSelect for an upcoming phase', () => {
    const onSelect = vi.fn();
    render(<PhaseContextBar phases={PHASES} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('Roadmap'));
    expect(onSelect).not.toHaveBeenCalled();
  });
});
