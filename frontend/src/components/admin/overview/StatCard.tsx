import React from 'react';
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
  /** AIQ-2326: hover tooltip explaining what this number means and its as-of time. */
  definition?: string;
}

export const StatCard: React.FC<StatCardProps> = ({ testId, label, value, sub, loading, fallback, definition }) => (
  <div data-testid={testId} title={definition} className="bg-white rounded-xl border border-slate-200 px-5 py-4">
    <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-2">{label}</p>
    <p className="text-3xl font-semibold text-slate-900">
      {loading ? <Skeleton className="h-7 w-16" /> : <MetricValue value={value} fallback={fallback} />}
    </p>
    {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
  </div>
);
