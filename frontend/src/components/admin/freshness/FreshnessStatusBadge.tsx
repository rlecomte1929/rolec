import React from 'react';

type FreshnessState = 'fresh' | 'warning' | 'stale' | 'overdue' | 'error';

const STYLES: Record<FreshnessState, string> = {
  fresh: 'bg-green-100 text-green-800',
  warning: 'bg-amber-100 text-amber-800',
  stale: 'bg-orange-100 text-orange-800',
  overdue: 'bg-red-100 text-red-800',
  error: 'bg-red-200 text-red-900',
};

interface Props {
  state: FreshnessState | string;
  label?: string;
}

export const FreshnessStatusBadge: React.FC<Props> = ({ state, label }) => {
  const s = (state || 'stale').toLowerCase() as FreshnessState;
  const cls = STYLES[s] || STYLES.stale;
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${cls}`}>
      {label ?? s}
    </span>
  );
};
