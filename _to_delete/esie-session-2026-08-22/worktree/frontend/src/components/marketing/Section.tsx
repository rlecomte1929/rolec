import React from 'react';

interface SectionProps {
  children: React.ReactNode;
  /** Vertical spacing: 'lg' (8rem) | 'default' (6rem) | 'sm' (4rem) | 'none' */
  spacing?: 'lg' | 'default' | 'sm' | 'none';
  /** Background: 'transparent' | 'surface' | 'muted' | 'subtle' */
  background?: 'transparent' | 'surface' | 'muted' | 'subtle';
  /** Fill viewport and center content vertically (for hero sections) */
  fillViewport?: boolean;
  className?: string;
}

export const Section: React.FC<SectionProps> = ({
  children,
  spacing = 'default',
  background = 'transparent',
  fillViewport = false,
  className = '',
}) => {
  const spacingClass =
    spacing === 'lg'
      ? 'py-20 sm:py-24'
      : spacing === 'default'
        ? 'py-section'
        : spacing === 'sm'
          ? 'py-section-sm'
          : 'py-0';

  const viewportClass = fillViewport
    ? 'min-h-[calc(100vh-5.5rem)] flex flex-col justify-center'
    : '';

  const bgClass =
    background === 'surface'
      ? 'bg-marketing-surface'
      : background === 'muted'
        ? 'bg-marketing-surface-muted'
        : background === 'subtle'
          ? 'bg-marketing-surface-subtle'
          : '';

  return (
    <section className={`${spacingClass} ${viewportClass} ${bgClass} ${className}`.trim()}>
      {children}
    </section>
  );
};
