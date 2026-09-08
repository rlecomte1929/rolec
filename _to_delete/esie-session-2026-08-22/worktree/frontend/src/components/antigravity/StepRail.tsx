import React from 'react';

export type StepStatus = 'done' | 'current' | 'upcoming';
export interface RailStep {
  label: string;
  status: StepStatus;
  icon?: React.ReactNode;
}

interface StepRailProps {
  steps: RailStep[];
  /** Fired when a done step is clicked (navigation back). Current/upcoming are not navigable. */
  onSelect?: (index: number) => void;
  className?: string;
}

export const StepRail: React.FC<StepRailProps> = ({ steps, onSelect, className = '' }) => {
  const currentIndex = steps.findIndex((s) => s.status === 'current');
  return (
    <section className={`rounded-xl border border-[#e2e8f0] bg-white px-7 py-5 shadow-sm ${className}`}>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-[13px] font-semibold uppercase tracking-wider text-[#6b7280]">Your relocation plan</h2>
        <span className="text-[13px] font-semibold text-navy-800">
          Step {currentIndex + 1} of {steps.length}
        </span>
      </div>
      <ol className="grid" style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }}>
        {steps.map((s, i) => {
          const navigable = s.status === 'done' && Boolean(onSelect);
          const dot =
            s.status === 'done' ? 'bg-navy-800 text-white'
            : s.status === 'current' ? 'ring-4 ring-accent-500 text-accent-600 bg-white'
            : 'border-2 border-[#e2e8f0] text-[#9aa6b2] bg-white';
          return (
            <li key={s.label} className="flex flex-col items-center text-center">
              <button
                type="button"
                disabled={!navigable}
                aria-current={s.status === 'current' ? 'step' : undefined}
                onClick={() => navigable && onSelect?.(i)}
                className={`flex flex-col items-center gap-2 ${navigable ? 'cursor-pointer' : 'cursor-default'}`}
              >
                <span className={`flex h-10 w-10 items-center justify-center rounded-full text-[13px] ${dot}`}>
                  {s.status === 'done' ? '✓' : s.icon ?? i + 1}
                </span>
                <span className={`text-[13px] font-semibold ${s.status === 'upcoming' ? 'text-[#6b7280]' : 'text-navy-800'}`}>
                  {s.label}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
};
