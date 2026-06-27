import React from 'react';
import { Skeleton } from './Skeleton';
import { MetricValue } from './MetricValue';

interface StatCardProps {
  testId: string;
  label: string;
  value: number | null;
  sub?: string;
  loading?: boolean;
}

export const StatCard: React.FC<StatCardProps> = ({ testId, label, value, sub, loading }) => (
  <div data-testid={testId} className="bg-white rounded-xl border border-slate-200 px-5 py-4">
    <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">{label}</p>
    <p className="text-3xl font-semibold text-slate-900">
      {loading ? <Skeleton className="h-7 w-16" /> : <MetricValue value={value} />}
    </p>
    {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
  </div>
);
