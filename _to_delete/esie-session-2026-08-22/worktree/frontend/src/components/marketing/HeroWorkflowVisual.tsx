import React from 'react';

/**
 * Minimal abstract workflow visual for hero.
 * Suggests: HR → case → employee → docs → services
 * Refined, non-busy, Stripe-inspired.
 */
export const HeroWorkflowVisual: React.FC<{ className?: string }> = ({
  className = '',
}) => {
  return (
    <div
      className={`w-full max-w-md aspect-[4/3] rounded-2xl border border-marketing-border bg-marketing-surface flex items-center justify-center p-8 ${className}`}
      aria-hidden
    >
      <svg
        viewBox="0 0 320 180"
        className="w-full h-full max-h-[200px]"
        fill="none"
      >
        {/* Horizontal flow line */}
        <path
          d="M20 90 L300 90"
          stroke="var(--marketing-border)"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        {/* Nodes */}
        {[
          { cx: 45, label: 'HR', r: 14 },
          { cx: 110, label: 'Case', r: 14 },
          { cx: 160, label: 'Employee', r: 14 },
          { cx: 220, label: 'Docs', r: 14 },
          { cx: 275, label: 'Services', r: 14 },
        ].map((node, i) => (
          <g key={i}>
            <circle
              cx={node.cx}
              cy={90}
              r={node.r}
              fill="var(--marketing-surface)"
              stroke={
                i === 1 || i === 2
                  ? 'var(--marketing-accent)'
                  : 'var(--marketing-border)'
              }
              strokeWidth={i === 1 || i === 2 ? 2 : 1}
            />
            <text
              x={node.cx}
              y={94}
              textAnchor="middle"
              style={{
                fontSize: 9,
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
