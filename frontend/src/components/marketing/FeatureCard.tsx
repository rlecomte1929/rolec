import React from 'react';

interface FeatureCardProps {
  eyebrow?: string;
  title: string;
  description?: string;
  children?: React.ReactNode;
  /** Optional icon/visual slot */
  icon?: React.ReactNode;
  className?: string;
}

export const FeatureCard: React.FC<FeatureCardProps> = ({
  eyebrow,
  title,
  description,
  children,
  icon,
  className = '',
}) => {
  return (
    <div
      className={`rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8 transition-shadow hover:shadow-sm ${className}`}
    >
      {icon && <div className="mb-4">{icon}</div>}
      {eyebrow && (
        <p className="text-xs font-semibold uppercase tracking-wider text-marketing-accent mb-2">
          {eyebrow}
        </p>
      )}
      <h3 className="text-marketing-h3 font-semibold text-marketing-primary">
        {title}
      </h3>
      {description && (
        <p className="mt-3 text-sm text-marketing-text-muted leading-relaxed">
          {description}
        </p>
      )}
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
};
