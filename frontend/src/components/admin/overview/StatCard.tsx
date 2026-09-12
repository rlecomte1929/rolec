import React from 'react';
import { STAT_CARD_TOOLTIP_CLASS } from '../../antigravity/StatCard';
import { Skeleton } from './Skeleton';
import { MetricValue } from './MetricValue';

interface StatCardProps {
  testId: string;
  label: string;
  value: number | null;
  sub?: string;
  loading?: boolean;
  /** Passed through to MetricValue — override the amber 'Unavailable' marker where it
   *  would over-alarm, e.g. when the whole payload failed to load and a page-level
   *  error + Retry already says so (AIQ-1564). */
  fallback?: React.ReactNode;
  /** Hover tooltip: "<definition> · as of <time>". */
  definition?: string;
}

export const StatCard: React.FC<StatCardProps> = ({ testId, label, value, sub, loading, fallback, definition }) => (
  <div data-testid={testId} className="group relative overflow-visible rounded-xl border border-slate-200 bg-white px-5 py-4">
    <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-2">{label}</p>
    <p className="text-3xl font-semibold text-slate-900">
      {loading ? <Skeleton className="h-7 w-16" /> : <MetricValue value={value} fallback={fallback} />}
    </p>
    {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    {definition ? (
      <span data-testid="stat-card-definition" role="tooltip" className={STAT_CARD_TOOLTIP_CLASS}>
        {definition}
      </span>
    ) : null}
  </div>
);
