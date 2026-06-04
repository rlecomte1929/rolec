/**
 * [P2-07c · AIQ-700] AvailableNowWidget — France→Norway "Marc Bouchard" case.
 *
 * Covers:
 *   1. Shows the two dependency-free actions (TB tests, EEA registration).
 *   2. Hides "Sign lease" (depends on viewings, which is not complete).
 *   3. Caps the list at 3 + shows the see-all link when more are available.
 *   4. Empty state names the blocker when nothing is available.
 *   5. Auto-refresh: re-rendering with an updated step set re-computes the
 *      available actions within one render cycle (P2-07d · AIQ-701).
 */
import '@testing-library/jest-dom/vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';

import { AvailableNowWidget, type AvailableNowStep } from './AvailableNowWidget';

afterEach(() => cleanup());

/** France→Norway relocation roadmap for fixture employee "Marc Bouchard". */
function marcBouchardSteps(): AvailableNowStep[] {
  return [
    { id: 'tb-tests', title: 'TB tests for minors', status: 'pending', owner: 'employee', dependency_ids: [] },
    { id: 'eea-registration', title: 'EEA registration appointment', status: 'pending', owner: 'employee', dependency_ids: [] },
    { id: 'viewings', title: 'Book apartment viewings', status: 'in_progress', owner: 'employee', dependency_ids: [] },
    { id: 'sign-lease', title: 'Sign lease', status: 'pending', owner: 'employee', dependency_ids: ['viewings'] },
  ];
}

describe('AvailableNowWidget — Marc Bouchard (France→Norway)', () => {
  it('shows the two unblocked actions', () => {
    render(<AvailableNowWidget steps={marcBouchardSteps()} />);
    expect(screen.getByText('TB tests for minors')).toBeInTheDocument();
    expect(screen.getByText('EEA registration appointment')).toBeInTheDocument();
  });

  it('does not show "Sign lease" (depends on incomplete viewings)', () => {
    render(<AvailableNowWidget steps={marcBouchardSteps()} />);
    expect(screen.queryByText('Sign lease')).not.toBeInTheDocument();
  });

  it('caps at 3 items and shows the see-all link when more are available', () => {
    const steps: AvailableNowStep[] = [
      { id: 's1', title: 'Action 1', status: 'pending', owner: 'employee', dependency_ids: [] },
      { id: 's2', title: 'Action 2', status: 'pending', owner: 'hr', dependency_ids: [] },
      { id: 's3', title: 'Action 3', status: 'pending', owner: 'vendor', dependency_ids: [] },
      { id: 's4', title: 'Action 4', status: 'pending', owner: 'employee', dependency_ids: [] },
    ];
    render(<AvailableNowWidget steps={steps} />);
    expect(screen.getByText('Action 1')).toBeInTheDocument();
    expect(screen.getByText('Action 3')).toBeInTheDocument();
    expect(screen.queryByText('Action 4')).not.toBeInTheDocument(); // beyond max 3
    expect(screen.getByText(/See all available steps/)).toBeInTheDocument();
  });

  it('shows an empty state naming the blocker when nothing is available', () => {
    const steps: AvailableNowStep[] = [
      { id: 'viewings', title: 'Book apartment viewings', status: 'in_progress', owner: 'employee', dependency_ids: [] },
      { id: 'sign-lease', title: 'Sign lease', status: 'pending', owner: 'employee', dependency_ids: ['viewings'] },
    ];
    render(<AvailableNowWidget steps={steps} />);
    expect(screen.getByText(/No actions available/)).toBeInTheDocument();
    expect(screen.getByText(/Book apartment viewings/)).toBeInTheDocument();
  });

  it('renders the owner badge for an available action', () => {
    render(<AvailableNowWidget steps={marcBouchardSteps()} />);
    // employee owner → "You"
    expect(screen.getAllByText('You').length).toBeGreaterThan(0);
  });

  it('auto-refreshes: completing the blocker unlocks the dependent step on re-render', () => {
    const blocked = marcBouchardSteps();
    const { rerender } = render(<AvailableNowWidget steps={blocked} />);
    expect(screen.queryByText('Sign lease')).not.toBeInTheDocument();

    // Host refetches after "viewings" is marked complete → re-render with new data.
    const unblocked = blocked.map(s =>
      s.id === 'viewings' ? { ...s, status: 'completed' } : s,
    );
    rerender(<AvailableNowWidget steps={unblocked} />);
    expect(screen.getByText('Sign lease')).toBeInTheDocument();
  });

  it('flags a circular dependency gracefully instead of looping', () => {
    const steps: AvailableNowStep[] = [
      { id: 'a', title: 'A', status: 'pending', owner: 'employee', dependency_ids: ['b'] },
      { id: 'b', title: 'B', status: 'pending', owner: 'employee', dependency_ids: ['a'] },
    ];
    render(<AvailableNowWidget steps={steps} />);
    expect(screen.getByRole('alert')).toHaveTextContent(/circular dependency/i);
  });
});
