import React from 'react';

interface DualViewSectionProps {
  leftTitle: string;
  leftItems: readonly string[];
  rightTitle: string;
  rightItems: readonly string[];
  className?: string;
}

/**
 * Two-column comparison: HR view vs Employee experience.
 */
export const DualViewSection: React.FC<DualViewSectionProps> = ({
  leftTitle,
  leftItems,
  rightTitle,
  rightItems,
  className = '',
}) => {
  return (
    <div
      className={`grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-8 ${className}`}
    >
      <div className="rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8">
        <h3 className="text-marketing-h3 font-semibold text-marketing-primary mb-4">
          {leftTitle}
        </h3>
        <ul className="space-y-3" role="list">
          {leftItems.map((item, i) => (
            <li key={i} className="flex gap-3 items-center">
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full bg-marketing-accent"
                aria-hidden
              />
              <span className="text-sm text-marketing-text-muted leading-relaxed">
                {item}
              </span>
            </li>
          ))}
        </ul>
      </div>
      <div className="rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8">
        <h3 className="text-marketing-h3 font-semibold text-marketing-primary mb-4">
          {rightTitle}
        </h3>
        <ul className="space-y-3" role="list">
          {rightItems.map((item, i) => (
            <li key={i} className="flex gap-3 items-center">
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full bg-marketing-accent"
                aria-hidden
              />
              <span className="text-sm text-marketing-text-muted leading-relaxed">
                {item}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
