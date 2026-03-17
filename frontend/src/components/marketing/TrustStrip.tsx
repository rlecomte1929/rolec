import React from 'react';

interface TrustStripProps {
  /** Eyebrow label above the logos */
  label?: string;
  /** Placeholder: array of company names (or use children for custom content) */
  logos?: string[];
  children?: React.ReactNode;
  className?: string;
}

export const TrustStrip: React.FC<TrustStripProps> = ({
  label = 'Trusted by operations teams',
  logos,
  children,
  className = '',
}) => {
  return (
    <div
      className={`rounded-xl border border-marketing-border bg-marketing-surface px-6 py-8 sm:px-8 sm:py-10 ${className}`}
    >
      {label && (
        <p className="text-xs font-semibold uppercase tracking-wider text-marketing-text-subtle mb-6 text-center">
          {label}
        </p>
      )}
      {children ? (
        children
      ) : logos && logos.length > 0 ? (
        <div className="flex flex-wrap items-center justify-center gap-8 sm:gap-12">
          {logos.map((name) => (
            <span
              key={name}
              className="text-sm font-medium text-marketing-text-muted"
            >
              {name}
            </span>
          ))}
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-center gap-8 sm:gap-12">
          <span className="text-sm text-marketing-text-subtle">Logo placeholder</span>
          <span className="text-sm text-marketing-text-subtle">Logo placeholder</span>
          <span className="text-sm text-marketing-text-subtle">Logo placeholder</span>
          <span className="text-sm text-marketing-text-subtle">Logo placeholder</span>
        </div>
      )}
    </div>
  );
};
