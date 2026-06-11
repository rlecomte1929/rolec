import React from 'react';
import { StepRail, type RailStep } from '../../components/antigravity';

// Real v2 wizard steps (CaseWizardPage Step1..Step5).
const LABELS = ['Relocation basics', 'Your details', 'Your household', 'Assignment', 'Review'];

interface WizardStepRailProps {
  currentStep: number;        // 1-based
  completedSteps: number[];   // 1-based completed step numbers
  maxUnlocked: number;        // highest navigable step (1-based)
  onSelect: (stepNumber: number) => void; // 1-based
}

export const WizardStepRail: React.FC<WizardStepRailProps> = ({ currentStep, completedSteps, maxUnlocked, onSelect }) => {
  const steps: RailStep[] = LABELS.map((label, i) => {
    const n = i + 1;
    const status: RailStep['status'] =
      n === currentStep ? 'current' : completedSteps.includes(n) ? 'done' : 'upcoming';
    return { label, status };
  });
  return (
    <StepRail
      steps={steps}
      onSelect={(index) => {
        const n = index + 1;
        if (n <= maxUnlocked) onSelect(n);
      }}
    />
  );
};
