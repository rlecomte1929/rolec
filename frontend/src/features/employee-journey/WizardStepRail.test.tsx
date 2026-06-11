import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { WizardStepRail } from './WizardStepRail';

afterEach(cleanup);

describe('WizardStepRail', () => {
  it('maps current + completed steps onto the rail', () => {
    render(<WizardStepRail currentStep={2} completedSteps={[1]} maxUnlocked={2} onSelect={() => {}} />);
    expect(screen.getByText('Relocation basics')).toBeInTheDocument();
    expect(screen.getByText('Your household')).toBeInTheDocument();
    expect(screen.getByText(/Step 2 of 5/i)).toBeInTheDocument();
  });
  it('selects a completed, unlocked step', () => {
    const onSelect = vi.fn();
    render(<WizardStepRail currentStep={2} completedSteps={[1]} maxUnlocked={2} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('Relocation basics'));
    expect(onSelect).toHaveBeenCalledWith(1);
  });
});
