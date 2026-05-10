import React from 'react';

export interface CoreModelElement {
  label: string;
  description?: string;
}

interface CoreModelDiagramProps {
  elements: readonly CoreModelElement[];
  /** Center element index (0-based), if any - gets emphasized */
  centerIndex?: number;
  className?: string;
}

/**
 * Modular grid diagram for core model elements.
 * Case-centric: first element (Case) is emphasized; others in a grid.
 */
export const CoreModelDiagram: React.FC<CoreModelDiagramProps> = ({
  elements,
  centerIndex = 0,
  className = '',
}) => {
  const centerEl = elements[centerIndex];
  const rest = elements.filter((_, i) => i !== centerIndex);

  return (
    <div
      className={`rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8 ${className}`}
      aria-hidden
    >
      {/* Case / center element - full width, emphasized */}
      {centerEl && (
        <div className="rounded-lg border-2 border-marketing-accent bg-marketing-surface-muted p-4 sm:p-5 text-center mb-4">
          <span className="block text-sm font-semibold text-marketing-accent">
            {centerEl.label}
          </span>
          {centerEl.description && (
            <span className="block mt-1 text-xs text-marketing-text-muted">
              {centerEl.description}
            </span>
          )}
        </div>
      )}
      {/* Remaining elements in grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 sm:gap-4">
        {rest.map((el) => (
          <div
            key={el.label}
            className="rounded-lg border border-marketing-border bg-marketing-surface p-3 sm:p-4 text-center"
          >
            <span className="block text-sm font-semibold text-marketing-primary">
              {el.label}
            </span>
            {el.description && (
              <span className="block mt-1 text-xs text-marketing-text-muted">
                {el.description}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
