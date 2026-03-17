import React from 'react';

interface ProblemComparisonProps {
  todayTitle: string;
  todayItems: readonly string[];
  withReloPassTitle: string;
  withReloPassItems: readonly string[];
  className?: string;
}

export const ProblemComparison: React.FC<ProblemComparisonProps> = ({
  todayTitle,
  todayItems,
  withReloPassTitle,
  withReloPassItems,
  className = '',
}) => {
  return (
    <div
      className={`grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-8 ${className}`}
    >
      <div className="rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-marketing-text-subtle mb-4">
          {todayTitle}
        </h3>
        <ul className="space-y-3" role="list">
          {todayItems.map((item, i) => (
            <li key={i} className="flex gap-3 items-center">
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full bg-marketing-text-subtle"
                aria-hidden
              />
              <span className="text-sm text-marketing-text-muted leading-relaxed">
                {item}
              </span>
            </li>
          ))}
        </ul>
      </div>
      <div className="rounded-xl border-2 border-marketing-accent/30 bg-marketing-surface-muted p-6 sm:p-8">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-marketing-accent mb-4">
          {withReloPassTitle}
        </h3>
        <ul className="space-y-3" role="list">
          {withReloPassItems.map((item, i) => (
            <li key={i} className="flex gap-3 items-center">
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full bg-marketing-accent"
                aria-hidden
              />
              <span className="text-sm text-marketing-text leading-relaxed">
                {item}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
