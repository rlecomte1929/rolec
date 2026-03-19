import React from 'react';

interface HeroSurfaceProps {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  /** Slot for primary CTA(s) */
  actions?: React.ReactNode;
  /** Slot for secondary content (e.g. stats, trust strip) */
  aside?: React.ReactNode;
  /** Full-width visual (illustration, diagram placeholder) */
  visual?: React.ReactNode;
  className?: string;
}

export const HeroSurface: React.FC<HeroSurfaceProps> = ({
  eyebrow,
  title,
  subtitle,
  actions,
  aside,
  visual,
  className = '',
}) => {
  return (
    <div className={`${className}`}>
      <div className={`${visual ? 'grid grid-cols-1 lg:grid-cols-[1fr,minmax(0,1fr)] gap-12 lg:gap-16 items-center' : ''}`}>
        <div className={visual ? 'order-2 lg:order-1' : ''}>
          {eyebrow && (
            <p className="text-xs font-semibold uppercase tracking-wider text-marketing-accent mb-4">
              {eyebrow}
            </p>
          )}
          <h1 className="text-marketing-hero sm:text-marketing-hero-lg font-semibold text-marketing-primary tracking-tight leading-[1.1]">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-6 text-marketing-body-lg text-marketing-text-muted leading-relaxed max-w-xl">
              {subtitle}
            </p>
          )}
          {actions && (
            <div className="mt-8 flex flex-wrap gap-4">
              {actions}
            </div>
          )}
          {aside && <div className="mt-10">{aside}</div>}
        </div>
        {visual && (
          <div className="order-1 lg:order-2 flex justify-center lg:justify-end">
            {visual}
          </div>
        )}
      </div>
    </div>
  );
}
