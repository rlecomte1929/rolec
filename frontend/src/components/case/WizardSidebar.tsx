import React from 'react';

interface WizardSidebarProps {
  currentStep: number;
  completedSteps: number[];
  onSelect: (step: number) => void;
}

const steps = [
  'Relocation Basics',
  'Employee Profile',
  'Family Members',
  'Assignment / Context',
  'Review & Submit',
];

export const WizardSidebar: React.FC<WizardSidebarProps> = ({ currentStep, completedSteps, onSelect }) => {
  return (
    <div className="space-y-4">
      <div className="text-xs uppercase tracking-wide text-[#6b7280]">Wizard Steps</div>
      <div className="space-y-2">
        {steps.map((label, index) => {
          const stepNumber = index + 1;
          const isCurrent = stepNumber === currentStep;
          const isDone = completedSteps.includes(stepNumber);
          return (
            <button
              key={label}
              onClick={() => onSelect(stepNumber)}
              className={`w-full text-left px-3 py-2 rounded-lg border ${
                isCurrent ? 'border-[#0b2b43] bg-[#f8fafc]' : 'border-transparent hover:bg-[#f8fafc]'
              }`}
            >
              <div className="flex items-center gap-3">
                <span
                  className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-semibold ${
                    isDone
                      ? 'bg-[#eaf5f4] text-[#1f8e8b]'
                      : isCurrent
                      ? 'bg-[#0b2b43] text-white'
                      : 'bg-[#e2e8f0] text-[#6b7280]'
                  }`}
                >
                  {stepNumber}
                </span>
                <div>
                  <div className="text-sm font-medium text-[#0b2b43]">{label}</div>
                  {isCurrent && <div className="text-xs text-[#1f8e8b]">In progress</div>}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
