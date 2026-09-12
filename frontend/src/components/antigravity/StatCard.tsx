import React from 'react';

/** Shared hover copy for both StatCard implementations — muted, overlay, no layout shift. */
export const STAT_CARD_TOOLTIP_CLASS =
  'pointer-events-none absolute left-0 top-full z-20 mt-1 max-w-xs rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-normal normal-case tracking-normal text-slate-500 opacity-0 shadow-sm transition-opacity group-hover:opacity-100 group-focus-within:opacity-100';

export interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  /** One inverted navy tile per page max. */
  emphasis?: boolean;
  className?: string;
  title?: string;
  /** Hover tooltip: "<definition> · as of <time>". Takes precedence over `title`. */
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
    title={definition ? undefined : title}
    className={`group relative overflow-visible rounded-xl border p-4 ${
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
    {definition ? (
      <span data-testid="stat-card-definition" role="tooltip" className={STAT_CARD_TOOLTIP_CLASS}>
        {definition}
      </span>
    ) : null}
  </div>
);
