import React from 'react';

/**
 * Simplified system diagram for Platform page hero.
 * Case at center, connected to Employee, Policy, Documents, Services.
 */
export const PlatformSystemDiagram: React.FC<{ className?: string }> = ({
  className = '',
}) => {
  return (
    <div
      className={`w-full max-w-md aspect-square rounded-2xl border border-marketing-border bg-marketing-surface flex items-center justify-center p-8 ${className}`}
      aria-hidden
    >
      <svg
        viewBox="0 0 200 200"
        className="w-full h-full max-h-[240px]"
        fill="none"
      >
        {/* Center: Case */}
        <circle
          cx="100"
          cy="100"
          r="28"
          fill="var(--marketing-surface-muted)"
          stroke="var(--marketing-accent)"
          strokeWidth="2"
        />
        <text
          x="100"
          y="106"
          textAnchor="middle"
          style={{
            fontSize: 11,
            fontFamily: 'Inter, sans-serif',
            fontWeight: 600,
            fill: 'var(--marketing-accent)',
          }}
        >
          Case
        </text>
        {/* Connecting lines to nodes */}
        {[
          { x: 50, y: 50, label: 'Employee' },
          { x: 150, y: 50, label: 'Policy' },
          { x: 50, y: 150, label: 'Documents' },
          { x: 150, y: 150, label: 'Services' },
        ].map((node, i) => (
          <g key={i}>
            <line
              x1="100"
              y1="100"
              x2={node.x}
              y2={node.y}
              stroke="var(--marketing-border)"
              strokeWidth="1"
              strokeLinecap="round"
            />
            <circle
              cx={node.x}
              cy={node.y}
              r="18"
              fill="var(--marketing-surface)"
              stroke="var(--marketing-border)"
              strokeWidth="1"
            />
            <text
              x={node.x}
              y={node.y + 5}
              textAnchor="middle"
              style={{
                fontSize: 8,
                fontFamily: 'Inter, sans-serif',
                fontWeight: 500,
                fill: 'var(--marketing-text-muted)',
              }}
            >
              {node.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
};
