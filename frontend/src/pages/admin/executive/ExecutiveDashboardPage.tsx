import React, { useEffect, useState } from 'react';
import { AdminLayout } from '../AdminLayout';
import { Alert, Badge, Card } from '../../../components/antigravity';
import { StatCard } from '../../../components/admin/overview/StatCard';
import { getExecOverview, type ExecOverview, type ExecPanel } from '../../../api/execOverview';

function num(panel: ExecPanel | undefined, key: string): number | null {
  if (!panel?.available) return null;
  const v = panel[key];
  return typeof v === 'number' ? v : null;
}

function source(panel?: ExecPanel): string {
  if (!panel?.available) return 'unavailable';
  return panel.data_source || 'live';
}

export const ExecutiveDashboardPage: React.FC = () => {
  const [data, setData] = useState<ExecOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getExecOverview()
      .then((d) => { if (active) { setData(d); setLoading(false); } })
      .catch(() => { if (active) { setError('Could not load the executive overview.'); setLoading(false); } });
    return () => { active = false; };
  }, []);

  const cost = num(data?.ai_cost, 'total_cost_usd');

  return (
    <AdminLayout
      title="Executive dashboard"
      subtitle="State of the platform — growth, activation, throughput, AI cost & health"
    >
      <Alert variant="info">
        Pre-launch — figures reflect test data. Each tile shows its data source (live / estimated / mock).
      </Alert>
      {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}

      <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4" data-testid="exec-kpis">
        <StatCard testId="kpi-companies" label="Companies" value={num(data?.growth, 'companies')} sub={`tenants · ${source(data?.growth)}`} loading={loading} />
        <StatCard testId="kpi-employees" label="Employees" value={num(data?.growth, 'employees')} sub={`seats · ${source(data?.growth)}`} loading={loading} />
        <StatCard testId="kpi-signups" label="Signups" value={num(data?.funnel, 'signups')} sub={`profiles · ${source(data?.funnel)}`} loading={loading} />
        <StatCard testId="kpi-cases" label="Cases" value={num(data?.funnel, 'cases')} sub={`total · ${source(data?.funnel)}`} loading={loading} />
        <StatCard testId="kpi-intake" label="In intake" value={num(data?.funnel, 'in_intake')} sub="active intake" loading={loading} />
        <StatCard testId="kpi-completed" label="Completed" value={num(data?.funnel, 'completed')} sub="closed cases" loading={loading} />
        <StatCard testId="kpi-median" label="Median completion" value={num(data?.throughput, 'median_completion_days')} sub={`days · ${source(data?.throughput)}`} loading={loading} />
        <StatCard testId="kpi-cost" label="AI spend (30d)" value={cost !== null ? Math.round(cost * 100) / 100 : null} sub={`USD · ${source(data?.ai_cost)}`} loading={loading} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <div className="p-1" data-testid="ai-health">
            <div className="flex items-center gap-2">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">AI health</p>
              <Badge variant={source(data?.ai_health) === 'live' ? 'success' : 'neutral'} size="sm">{source(data?.ai_health)}</Badge>
            </div>
            <p className="mt-2 text-3xl font-semibold text-navy-800">
              {num(data?.ai_health, 'score') ?? '—'}<span className="text-base text-slate-400"> / 100</span>
            </p>
            <p className="mt-1 text-xs text-slate-400">
              {data?.ai_health?.healthy ?? '—'} of {data?.ai_health?.total ?? '—'} eval metrics healthy
            </p>
          </div>
        </Card>

        <Card>
          <div className="p-1" data-testid="reliability">
            <div className="flex items-center gap-2">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">Reliability</p>
              <Badge variant="warning" size="sm">not instrumented</Badge>
            </div>
            <p className="mt-2 text-xs text-slate-500">{data?.reliability?.note ?? 'Error rate / latency not tracked in-platform yet.'}</p>
          </div>
        </Card>

        <Card>
          <div className="p-1" data-testid="nps">
            <div className="flex items-center gap-2">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">NPS / CSAT</p>
              <Badge variant="warning" size="sm">not instrumented</Badge>
            </div>
            <p className="mt-2 text-xs text-slate-500">{data?.nps?.note ?? 'No customer-satisfaction instrumentation yet.'}</p>
          </div>
        </Card>
      </div>
    </AdminLayout>
  );
};
