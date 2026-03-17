import React from 'react';

export interface FlowStep {
  title: string;
  description?: string;
}

type FlowStepsLayout = 'default' | 'six';

interface FlowStepsProps {
  steps: readonly FlowStep[];
  /** Layout: 'default' (5 cols on lg) | 'six' (3 cols on lg for 6-step flows) */
  layout?: FlowStepsLayout;
  className?: string;
}

const gridClass: Record<FlowStepsLayout, string> = {
  default: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-5',
  six: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
};

export const FlowSteps: React.FC<FlowStepsProps> = ({
  steps,
  layout = 'default',
  className = '',
}) => {
  return (
    <div className={className}>
      <ol
        className={`grid ${gridClass[layout]} gap-6 lg:gap-4`}
        role="list"
      >
        {steps.map((step, index) => (
          <li key={index} className="flex flex-col">
            <div className="flex items-start gap-4">
              <span
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-marketing-accent bg-marketing-surface text-sm font-semibold text-marketing-accent"
                aria-hidden
              >
                {index + 1}
              </span>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-semibold text-marketing-primary">
                  {step.title}
                </h3>
                {step.description && (
                  <p className="mt-1 text-sm text-marketing-text-muted leading-relaxed">
                    {step.description}
                  </p>
                )}
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
};
