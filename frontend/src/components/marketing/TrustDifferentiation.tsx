import React from 'react';

interface TrustDifferentiationProps {
  title: string;
  body: string;
  checklist: readonly string[];
  className?: string;
}

/**
 * Trust section: left text column, right checklist.
 */
export const TrustDifferentiation: React.FC<TrustDifferentiationProps> = ({
  title,
  body,
  checklist,
  className = '',
}) => {
  return (
    <div
      className={`grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16 items-center ${className}`}
    >
      <div>
        <h2 className="text-marketing-h1 font-semibold text-marketing-primary tracking-tight">
          {title}
        </h2>
        <p className="mt-4 text-marketing-body-lg text-marketing-text-muted leading-relaxed max-w-lg">
          {body}
        </p>
      </div>
      <div className="rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8">
        <ul className="space-y-3" role="list">
          {checklist.map((item, i) => (
            <li key={i} className="flex gap-3 items-center">
              <span
                className="h-2 w-2 shrink-0 rounded-full bg-marketing-accent"
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
