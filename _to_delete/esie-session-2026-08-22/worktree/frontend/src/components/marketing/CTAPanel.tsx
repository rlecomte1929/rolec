import React from 'react';

interface CTAPanelProps {
  title: string;
  subtitle?: string;
  /** Primary CTA slot */
  primaryAction?: React.ReactNode;
  /** Secondary action (link, etc.) */
  secondaryAction?: React.ReactNode;
  /** Tertiary action (e.g. Sign in) */
  tertiaryAction?: React.ReactNode;
  /** Alternative: pass multiple actions as a single node */
  actions?: React.ReactNode;
  /** Background: 'surface' | 'muted' | 'accent' */
  variant?: 'surface' | 'muted' | 'accent';
  className?: string;
}

export const CTAPanel: React.FC<CTAPanelProps> = ({
  title,
  subtitle,
  primaryAction,
  secondaryAction,
  tertiaryAction,
  actions,
  variant = 'muted',
  className = '',
}) => {
  const bgClass =
    variant === 'surface'
      ? 'bg-marketing-surface border-marketing-border'
      : variant === 'accent'
        ? 'bg-marketing-primary border-transparent'
        : 'bg-marketing-surface-muted border-marketing-border';

  const titleClass =
    variant === 'accent' ? 'text-white' : 'text-marketing-primary';
  const subtitleClass =
    variant === 'accent' ? 'text-white/90' : 'text-marketing-text-muted';

  return (
    <div
      className={`rounded-2xl border px-8 py-12 sm:px-12 sm:py-16 text-center ${bgClass} ${className}`}
    >
      <h3 className={`text-marketing-h2 font-semibold ${titleClass}`}>
        {title}
      </h3>
      {subtitle && (
        <p
          className={`mt-4 text-marketing-body-lg max-w-xl mx-auto ${subtitleClass}`}
        >
          {subtitle}
        </p>
      )}
      <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4 flex-wrap">
        {actions ?? (
          <>
            {primaryAction}
            {secondaryAction}
            {tertiaryAction}
          </>
        )}
      </div>
    </div>
  );
};
