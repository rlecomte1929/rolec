import React from 'react';

interface ProductDiagramBlockProps {
  /** Section eyebrow */
  eyebrow?: string;
  /** Section title */
  title: string;
  /** Section subtitle */
  subtitle?: string;
  /** Placeholder for diagram/illustration - typically a simple SVG or styled div */
  diagram?: React.ReactNode;
  /** Supporting content (bullets, features) */
  children?: React.ReactNode;
  /** Layout: diagram left or right */
  diagramPosition?: 'left' | 'right';
  className?: string;
}

export const ProductDiagramBlock: React.FC<ProductDiagramBlockProps> = ({
  eyebrow,
  title,
  subtitle,
  diagram,
  children,
  diagramPosition = 'right',
  className = '',
}) => {
  const DiagramSlot = diagram ?? (
    <div className="aspect-video rounded-xl border-2 border-dashed border-marketing-border bg-marketing-surface-muted flex items-center justify-center">
      <span className="text-sm text-marketing-text-subtle">Product diagram placeholder</span>
    </div>
  );

  return (
    <div className={className}>
      <div
        className={`grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16 items-center ${
          diagramPosition === 'left' ? 'lg:grid-flow-dense' : ''
        }`}
      >
        <div className={diagramPosition === 'left' ? 'lg:col-start-2' : ''}>
          {eyebrow && (
            <p className="text-xs font-semibold uppercase tracking-wider text-marketing-accent mb-3">
              {eyebrow}
            </p>
          )}
          <h2 className="text-marketing-h1 font-semibold text-marketing-primary tracking-tight">
            {title}
          </h2>
          {subtitle && (
            <p className="mt-4 text-marketing-body-lg text-marketing-text-muted leading-relaxed">
              {subtitle}
            </p>
          )}
          {children && <div className="mt-6">{children}</div>}
        </div>
        <div className={diagramPosition === 'left' ? 'lg:col-start-1 lg:row-start-1' : ''}>
          {DiagramSlot}
        </div>
      </div>
    </div>
  );
};
