import React from 'react';

export interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  /** One inverted navy tile per page max. */
  emphasis?: boolean;
  className?: string;
  title?: string;
  /** AIQ-2326: hover tooltip explaining what this number means and its as-of time.
   *  Takes precedence over `title` when both are set. */
  definition?: string;
}

/** Shared KPI tile: navy number, optional caption. Semantic color lives in `sub`, not the figure. */
export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  sub,
  emphasis = false,
  className = '',
  title,
  definition,
}) => (
  <div
    title={definition || title}
    className={`rounded-xl border p-4 ${
      emphasis ? 'border-transparent bg-navy-800' : 'border-slate-200 bg-white'
    } ${className}`}
  >
    <div
      className={`text-[11px] font-semibold uppercase tracking-wider ${
        emphasis ? 'text-white/60' : 'text-slate-500'
      }`}
    >
      {label}
    </div>
    <div
      className={`mt-1 font-semibold tabular-nums text-2xl ${
        emphasis ? 'text-white' : 'text-navy-800'
      }`}
    >
      {value}
    </div>
    {sub ? (
      <div className={`mt-0.5 text-xs ${emphasis ? 'text-white/70' : 'text-slate-500'}`}>{sub}</div>
    ) : null}
  </div>
);
