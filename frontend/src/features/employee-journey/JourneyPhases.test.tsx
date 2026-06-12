import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { JourneyPhases } from './JourneyPhases';

afterEach(cleanup);

const baseProps = {
  intakeStep: 2,
  intakeTotalSteps: 5,
  onContinueIntake: () => {},
  onPreviewBenefits: () => {},
};

describe('JourneyPhases', () => {
  it('renders all three phase titles', () => {
    render(<JourneyPhases {...baseProps} />);
    expect(screen.getByText('Intake')).toBeInTheDocument();
    expect(screen.getByText('Services & policy')).toBeInTheDocument();
    expect(screen.getByText('Roadmap')).toBeInTheDocument();
  });

  it('shows progress and a Continue intake CTA mid-intake; click fires onContinueIntake', () => {
    const onContinueIntake = vi.fn();
    render(<JourneyPhases {...baseProps} onContinueIntake={onContinueIntake} />);
    expect(screen.getByText('Step 2 of 5')).toBeInTheDocument();
    const cta = screen.getByRole('button', { name: 'Continue intake' });
    fireEvent.click(cta);
    expect(onContinueIntake).toHaveBeenCalledTimes(1);
  });

  it('reads "Review intake" when intake is complete', () => {
    render(<JourneyPhases {...baseProps} intakeStep={5} intakeTotalSteps={5} />);
    expect(screen.getByRole('button', { name: 'Review intake' })).toBeInTheDocument();
  });

  it('reads "Start intake" when intake has not begun', () => {
    render(<JourneyPhases {...baseProps} intakeStep={0} />);
    expect(screen.getByRole('button', { name: 'Start intake' })).toBeInTheDocument();
  });

  it('Preview benefits fires onPreviewBenefits', () => {
    const onPreviewBenefits = vi.fn();
    render(<JourneyPhases {...baseProps} onPreviewBenefits={onPreviewBenefits} />);
    fireEvent.click(screen.getByRole('button', { name: 'Preview benefits' }));
    expect(onPreviewBenefits).toHaveBeenCalledTimes(1);
  });

  it('locks Roadmap when onViewRoadmap is omitted', () => {
    render(<JourneyPhases {...baseProps} />);
    const locked = screen.getByRole('button', { name: /Locked until intake/i });
    expect(locked).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'View roadmap' })).not.toBeInTheDocument();
  });

  it('enables Roadmap when onViewRoadmap is provided; click fires it', () => {
    const onViewRoadmap = vi.fn();
    render(<JourneyPhases {...baseProps} onViewRoadmap={onViewRoadmap} />);
    const cta = screen.getByRole('button', { name: 'View roadmap' });
    fireEvent.click(cta);
    expect(onViewRoadmap).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: /Locked until intake/i })).not.toBeInTheDocument();
  });
});
