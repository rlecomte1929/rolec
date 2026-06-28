import React from 'react';
import { FadeIn } from './FadeIn';

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
        <h2 className="text-marketing-h1 font-bold text-marketing-primary tracking-tight">
          {title}
        </h2>
        <p className="mt-4 text-marketing-body-lg text-marketing-text-muted leading-relaxed max-w-lg">
          {body}
        </p>
      </div>
      <div className="rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8">
        <ul className="space-y-3">
          {checklist.map((item, i) => (
            // <li> must be a direct child of <ul> for valid list semantics
            // (Lighthouse a11y `listitem`); the FadeIn moves inside the <li> and
            // carries the flex layout, so the entrance animation is preserved.
            <li key={i}>
              <FadeIn delay={i * 80} className="flex gap-3 items-center">
                <span
                  className="h-2 w-2 shrink-0 rounded-full bg-marketing-accent"
                  aria-hidden
                />
                <span className="text-sm text-marketing-text leading-relaxed">
                  {item}
                </span>
              </FadeIn>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
