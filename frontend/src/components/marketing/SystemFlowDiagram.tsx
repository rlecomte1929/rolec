import React from 'react';

interface SystemFlowDiagramProps {
  nodes: readonly string[];
  className?: string;
}

/**
 * Horizontal flow diagram for system model.
 * Case → Employee → Documents → Policy → Services → Tracking
 */
export const SystemFlowDiagram: React.FC<SystemFlowDiagramProps> = ({
  nodes,
  className = '',
}) => {
  return (
    <div
      className={`rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8 overflow-x-auto ${className}`}
      aria-hidden
    >
      <div className="flex items-center justify-center gap-2 sm:gap-4 min-w-max">
        {nodes.map((label, i) => (
          <React.Fragment key={label}>
            <div
              className={`
                flex-shrink-0 rounded-lg border px-3 py-2 sm:px-4 sm:py-2.5 text-center
                ${
                  i === 0
                    ? 'border-2 border-marketing-accent bg-marketing-surface-muted'
                    : 'border-marketing-border bg-marketing-surface'
                }
              `}
            >
              <span
                className={`text-xs sm:text-sm font-semibold ${
                  i === 0 ? 'text-marketing-accent' : 'text-marketing-primary'
                }`}
              >
                {label}
              </span>
            </div>
            {i < nodes.length - 1 && (
              <svg
                className="flex-shrink-0 w-4 h-4 sm:w-5 sm:h-5 text-marketing-border"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};
