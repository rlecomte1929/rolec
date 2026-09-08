import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { JourneySpine, isIntakeComplete } from './JourneySpine';

afterEach(cleanup);

const baseProps = {
  intakeStep: 2,
  intakeTotalSteps: 5,
  onContinueIntake: () => {},
  onPreviewBenefits: () => {},
};

describe('JourneySpine', () => {
  it('renders the claimed station plus all three phase titles', () => {
    render(<JourneySpine {...baseProps} />);
    expect(screen.getByText('Assignment claimed')).toBeInTheDocument();
    expect(screen.getByText('Intake')).toBeInTheDocument();
    expect(screen.getByText('Services & policy')).toBeInTheDocument();
    expect(screen.getByText('Roadmap')).toBeInTheDocument();
  });

  it('shows progress and a Continue intake CTA mid-intake; click fires onContinueIntake', () => {
    const onContinueIntake = vi.fn();
    render(<JourneySpine {...baseProps} onContinueIntake={onContinueIntake} />);
    expect(screen.getByText('Step 2 of 5')).toBeInTheDocument();
    const cta = screen.getByRole('button', { name: 'Continue intake' });
    fireEvent.click(cta);
    expect(onContinueIntake).toHaveBeenCalledTimes(1);
  });

  it('reads "Review intake" when intake is complete', () => {
    render(<JourneySpine {...baseProps} intakeStep={5} intakeTotalSteps={5} />);
    expect(screen.getByRole('button', { name: 'Review intake' })).toBeInTheDocument();
  });

  it('reads "Start intake" when intake has not begun', () => {
    render(<JourneySpine {...baseProps} intakeStep={0} />);
    expect(screen.getByRole('button', { name: 'Start intake' })).toBeInTheDocument();
  });

  it('Preview benefits fires onPreviewBenefits', () => {
    const onPreviewBenefits = vi.fn();
    render(<JourneySpine {...baseProps} onPreviewBenefits={onPreviewBenefits} />);
    fireEvent.click(screen.getByRole('button', { name: 'Preview benefits' }));
    expect(onPreviewBenefits).toHaveBeenCalledTimes(1);
  });

  it('locks Roadmap when onViewRoadmap is omitted', () => {
    render(<JourneySpine {...baseProps} />);
    const locked = screen.getByRole('button', { name: /Locked until intake/i });
    expect(locked).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'View roadmap' })).not.toBeInTheDocument();
  });

  it('enables Roadmap when onViewRoadmap is provided; click fires it', () => {
    const onViewRoadmap = vi.fn();
    render(<JourneySpine {...baseProps} onViewRoadmap={onViewRoadmap} />);
    const cta = screen.getByRole('button', { name: 'View roadmap' });
    fireEvent.click(cta);
    expect(onViewRoadmap).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: /Locked until intake/i })).not.toBeInTheDocument();
  });

  it('marks intake done and surfaces Services as the active phase once intake completes', () => {
    render(<JourneySpine {...baseProps} intakeStep={5} intakeTotalSteps={5} />);
    // Services is the next actionable phase: its Preview benefits is primary.
    expect(screen.getByRole('button', { name: 'Preview benefits' })).toBeInTheDocument();
    expect(screen.getByText('Ready')).toBeInTheDocument();
  });
});

describe('isIntakeComplete', () => {
  it('is true for submit-and-beyond statuses (case-insensitive)', () => {
    for (const s of ['submitted', 'approved', 'rejected', 'closed', 'SUBMITTED']) {
      expect(isIntakeComplete(s)).toBe(true);
    }
  });
  it('is false for pre-submit / empty statuses', () => {
    for (const s of ['created', 'assigned', 'awaiting_intake', '', undefined, null]) {
      expect(isIntakeComplete(s as string | undefined)).toBe(false);
    }
  });
});

describe('JourneySpine — status is the source of truth (overrides stale intakeStep)', () => {
  it('submitted case: intake Done + roadmap unlocked + NO "Step X of 5", even with intakeStep=1', () => {
    render(
      <JourneySpine {...baseProps} intakeStep={1} status="submitted" onViewRoadmap={() => {}} />,
    );
    // intake station reads Done despite intakeStep=1
    expect(screen.getByText('Done')).toBeInTheDocument();
    expect(screen.queryByText(/Step 1 of 5/)).not.toBeInTheDocument();
    // roadmap unlocked (EmployeeJourney passes onViewRoadmap when complete)
    expect(screen.getByRole('button', { name: 'View roadmap' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Locked until intake/i })).not.toBeInTheDocument();
  });

  it('awaiting_intake: still shows the real in-progress step from intakeStep', () => {
    render(<JourneySpine {...baseProps} intakeStep={2} status="awaiting_intake" />);
    expect(screen.getByText('Step 2 of 5')).toBeInTheDocument();
    expect(screen.getByText('In progress')).toBeInTheDocument();
  });
});
