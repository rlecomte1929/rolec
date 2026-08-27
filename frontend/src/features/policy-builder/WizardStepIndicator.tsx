import React from 'react';

export type WizardStep = {
  number: number;
  title: string;
  description: string;
};

export const WIZARD_STEPS: WizardStep[] = [
  { number: 1, title: 'Relocation tiers',   description: 'Who qualifies for what' },
  { number: 2, title: 'Budgets',            description: 'Caps per tier & destination' },
  { number: 3, title: 'Required documents', description: 'Checklists per visa type' },
  { number: 4, title: 'Vendors',            description: 'Approved service categories' },
  { number: 5, title: 'Review & activate',  description: 'Confirm and go live' },
];

type Props = {
  currentStep: number; // 1–5
};

export const WizardStepIndicator: React.FC<Props> = ({ currentStep }) => {
  return (
    <nav aria-label="Policy wizard progress" className="w-full">
      <ol className="flex items-start gap-0 w-full">
        {WIZARD_STEPS.map((step, idx) => {
          const done    = step.number < currentStep;
          const active  = step.number === currentStep;
          const pending = step.number > currentStep;
          const isLast  = idx === WIZARD_STEPS.length - 1;

          return (
            <li key={step.number} className="flex-1 flex items-start">
              {/* Step circle + label */}
              <div className="flex flex-col items-center w-full">
                <div className="flex items-center w-full">
                  {/* Left connector */}
                  <div
                    className={`flex-1 h-0.5 ${idx === 0 ? 'invisible' : done ? 'bg-[#0b2b43]' : 'bg-slate-200'}`}
                  />
                  {/* Circle */}
                  <div
                    aria-current={active ? 'step' : undefined}
                    className={[
                      'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-colors',
                      done    ? 'bg-[#0b2b43] text-white'        : '',
                      active  ? 'bg-[#1a5276] text-white ring-2 ring-[#0b2b43] ring-offset-2' : '',
                      pending ? 'bg-slate-100 text-slate-500 border border-slate-200' : '',
                    ].join(' ')}
                  >
                    {done ? (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      step.number
                    )}
                  </div>
                  {/* Right connector */}
                  <div
                    className={`flex-1 h-0.5 ${isLast ? 'invisible' : done ? 'bg-[#0b2b43]' : 'bg-slate-200'}`}
                  />
                </div>
                {/* Label — hidden on mobile for steps 4–5 to avoid overflow */}
                <div className="mt-1 text-center px-1 hidden sm:block">
                  <p className={`text-xs font-medium leading-tight ${active ? 'text-[#0b2b43]' : done ? 'text-slate-600' : 'text-slate-500'}`}>
                    {step.title}
                  </p>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
      {/* Mobile: show just the current step label */}
      <p className="sm:hidden mt-2 text-center text-sm font-medium text-[#0b2b43]">
        Step {currentStep} of {WIZARD_STEPS.length}: {WIZARD_STEPS[currentStep - 1]?.title}
      </p>
    </nav>
  );
};
