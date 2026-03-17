import React from 'react';
import { CTAButton } from './CTAButton';

interface AccessOptionCardProps {
  label: string;
  description: string;
  cta: string;
  /** Route path for internal navigation */
  to?: string;
  /** External URL (e.g. mailto:) - takes precedence over to */
  href?: string;
  /** Primary = filled, secondary = outline */
  variant?: 'primary' | 'outline';
}

/**
 * Single option card for Access page.
 * Label, 1-line description, CTA.
 */
export const AccessOptionCard: React.FC<AccessOptionCardProps> = ({
  label,
  description,
  cta,
  to,
  href,
  variant = 'primary',
}) => {
  const Cta = () =>
    href ? (
      <CTAButton href={href} variant={variant} fullWidth>
        {cta}
      </CTAButton>
    ) : to ? (
      <CTAButton to={to} variant={variant} fullWidth>
        {cta}
      </CTAButton>
    ) : (
      <CTAButton variant={variant} fullWidth>
        {cta}
      </CTAButton>
    );

  return (
    <div className="rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8 flex flex-col">
      <h3 className="text-marketing-h3 font-semibold text-marketing-primary">
        {label}
      </h3>
      <p className="mt-2 text-sm text-marketing-text-muted leading-relaxed flex-1">
        {description}
      </p>
      <div className="mt-6">
        <Cta />
      </div>
    </div>
  );
};
