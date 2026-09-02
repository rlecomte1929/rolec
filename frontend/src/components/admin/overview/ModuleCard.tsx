import React from 'react';
import { Link } from 'react-router-dom';
import { Skeleton } from './Skeleton';
import { MetricValue } from './MetricValue';

export interface ModuleRow {
  label: string;
  value: string | number | null;
}

interface ModuleCardProps {
  testId: string;
  to: string;
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  metric: string | number | null;
  rows?: ModuleRow[];
  loading?: boolean;
}

// Module cards surface secondary, drill-down metrics — a failed source should
// read as 'no number yet' (a muted dash), not the amber 'Unavailable' alarm we
// reserve for the top KPI tiles. A dash here is unambiguous because the card
// links to the detail page that owns the real number.
const MUTED_DASH = <span className="text-slate-300">—</span>;

export const ModuleCard: React.FC<ModuleCardProps> = ({ testId, to, icon, title, subtitle, metric, rows = [], loading }) => (
  <Link data-testid={testId} to={to} className="block bg-white rounded-xl border border-slate-200 p-5 hover:border-slate-300 hover:shadow-sm transition-all">
    <div className="flex items-start justify-between mb-4">
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-600 shrink-0">
          {icon}
        </div>
        <div>
          <p className="text-sm font-semibold text-slate-900">{title}</p>
          <p className="text-xs text-slate-500">{subtitle}</p>
        </div>
      </div>
      <span className="text-2xl font-semibold text-slate-900">
        {loading ? <Skeleton className="h-6 w-10" /> : <MetricValue value={metric} fallback={MUTED_DASH} />}
      </span>
    </div>
    <div className="space-y-1.5">
      {rows.map((row) => (
        <div key={row.label} className="flex items-center justify-between">
          <span className="text-xs text-slate-500">{row.label}</span>
          <span className="text-xs font-medium text-slate-700">
            {loading ? <Skeleton className="h-3 w-8" /> : <MetricValue value={row.value} fallback={MUTED_DASH} />}
          </span>
        </div>
      ))}
    </div>
  </Link>
);
