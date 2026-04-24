import React from 'react';

interface SectionHeaderProps {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  /** Alignment */
  align?: 'left' | 'center';
  /** Max width of content for readability when centered */
  narrow?: boolean;
  /** Heading element. Default h2; use h1 when this is the page's primary heading. */
  as?: 'h1' | 'h2';
  className?: string;
}

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  eyebrow,
  title,
  subtitle,
  align = 'left',
  narrow = false,
  as: Heading = 'h2',
  className = '',
}) => {
  const alignClass = align === 'center' ? 'text-center' : '';
  const widthClass = narrow ? 'max-w-2xl' : '';
  const centerClass = align === 'center' ? 'mx-auto' : '';

  return (
    <div className={`${alignClass} ${widthClass} ${centerClass} ${className}`.trim()}>
      {eyebrow && (
        <p className="text-xs font-semibold uppercase tracking-wider text-marketing-accent mb-3">
          {eyebrow}
        </p>
      )}
      <Heading className="text-marketing-h1 font-semibold text-marketing-primary tracking-tight">
        {title}
      </Heading>
      {subtitle && (
        <p className="mt-4 text-marketing-body-lg text-marketing-text-muted leading-relaxed">
          {subtitle}
        </p>
      )}
    </div>
  );
};
