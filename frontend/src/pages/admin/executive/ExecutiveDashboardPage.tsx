import React, { useEffect, useState } from 'react';
import { AdminLayout } from '../AdminLayout';
import { Alert, Badge, Button, Card } from '../../../components/antigravity';
import { StatCard } from '../../../components/admin/overview/StatCard';
import { getExecOverview, type ExecOverview, type ExecPanel } from '../../../api/execOverview';

function num(panel: ExecPanel | undefined, key: string): number | null {
  if (!panel?.available) return null;
  const v = panel[key];
  return typeof v === 'number' ? v : null;
}

/**
 * AIQ-1564: a panel's provenance label. `unavailable` is a claim about the DATA — the
 * backend telling us that panel isn't instrumented (reliability lives in Sentry; NPS has
 * no capture yet). It must NEVER be shown because the request failed: when the fetch
 * 429'd, `data` was null, every panel read as undefined, and all eight tiles said
 * "unavailable" — which read as "the dashboard isn't connected to its endpoints" and is
 * exactly how BUG-260716-D23E was misdiagnosed. A load failure says "—" and the page
 * shows one error + Retry instead.
 */
function source(panel: ExecPanel | undefined, loadFailed: boolean): string {
  if (loadFailed) return '—';
  if (!panel?.available) return 'unavailable';
  return panel.data_source || 'live';
}

export const ExecutiveDashboardPage: React.FC = () => {
  const [data, setData] = useState<ExecOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = React.useCallback(() => {
    let active = true;
    setLoading(true);
    setError(null);
    getExecOverview()
      .then((d) => { if (active) { setData(d); setLoading(false); } })
      .catch((e: unknown) => {
        if (!active) return;
        // Name the rate-limit case: it's transient and retrying actually works, which a
        // generic "could not load" doesn't tell you.
        const status = (e as { response?: { status?: number } })?.response?.status;
        setError(
          status === 429
            ? 'Too many admin requests just now — this is a rate limit, not missing data. Retry in a moment.'
            : 'Could not load the executive overview.',
        );
        setLoading(false);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => load(), [load]);

  const loadFailed = error !== null;

  // When the whole payload failed, every tile's value is null — and MetricValue's default
  // marker is an amber "Unavailable", which is a statement about the DATA. Eight of those
  // is precisely what BUG-260716-D23E reported ("most tiles showing a status as
  // unavailable") after a 429. Use MetricValue's own documented override: a muted dash,
  // with the page-level error + Retry carrying the actual explanation.
  const failFallback = loadFailed
    ? <span className="text-base font-medium text-slate-500">—</span>
    : undefined;

  const cost = num(data?.ai_cost, 'total_cost_usd');

  return (
    <AdminLayout
      title="Executive dashboard"
      subtitle="State of the platform — growth, activation, throughput, AI cost & health"
    >
      <Alert variant="info">
        Pre-launch — figures reflect test data. Each tile shows its data source (live / estimated / mock).
      </Alert>
      {error && (
        <Alert variant="error" className="mt-3">
          <div className="flex flex-wrap items-center gap-3" data-testid="exec-load-error">
            <span>{error}</span>
            <Button
              size="sm"
              variant="secondary"
              onClick={load}
              disabled={loading}
              data-testid="exec-retry"
            >
              {loading ? 'Retrying…' : 'Retry'}
            </Button>
          </div>
        </Alert>
      )}

      <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4" data-testid="exec-kpis">
        <StatCard testId="kpi-companies" label="Companies" value={num(data?.growth, 'companies')} sub={`tenants · ${source(data?.growth, loadFailed)}`} loading={loading} fallback={failFallback} definition="Real tenants, excluding synthetic QA/test tenants — the same count shown on Today and Companies (AIQ-2326)." />
        <StatCard testId="kpi-employees" label="Employees" value={num(data?.growth, 'employees')} sub={`seats · ${source(data?.growth, loadFailed)}`} loading={loading} fallback={failFallback} definition="People with the EMPLOYEE role, excluding test accounts." />
        <StatCard testId="kpi-signups" label="Signups" value={num(data?.funnel, 'signups')} sub={`profiles · ${source(data?.funnel, loadFailed)}`} loading={loading} fallback={failFallback} definition="All real people profiles (any role), excluding test accounts." />
        <StatCard testId="kpi-cases" label="Cases" value={num(data?.funnel, 'cases')} sub={`total · ${source(data?.funnel, loadFailed)}`} loading={loading} fallback={failFallback} definition="All case assignments ever created." />
        <StatCard testId="kpi-intake" label="In intake" value={num(data?.funnel, 'in_intake')} sub="active intake" loading={loading} fallback={failFallback} />
        <StatCard testId="kpi-completed" label="Completed" value={num(data?.funnel, 'completed')} sub="closed cases" loading={loading} fallback={failFallback} />
        <StatCard testId="kpi-median" label="Median completion" value={num(data?.throughput, 'median_completion_days')} sub={`days · ${source(data?.throughput, loadFailed)}`} loading={loading} fallback={failFallback} />
        <StatCard testId="kpi-cost" label="AI spend (30d)" value={cost !== null ? Math.round(cost * 100) / 100 : null} sub={`USD · ${source(data?.ai_cost, loadFailed)}`} loading={loading} fallback={failFallback} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <div className="p-1" data-testid="ai-health">
            <div className="flex items-center gap-2">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">AI health</p>
              <Badge variant={source(data?.ai_health, loadFailed) === 'live' ? 'success' : 'neutral'} size="sm">{source(data?.ai_health, loadFailed)}</Badge>
            </div>
            <p className="mt-2 text-3xl font-semibold text-navy-800">
              {num(data?.ai_health, 'score') ?? '—'}<span className="text-base text-slate-500"> / 100</span>
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {data?.ai_health?.healthy ?? '—'} of {data?.ai_health?.total ?? '—'} eval metrics healthy
            </p>
          </div>
        </Card>

        <Card>
          <div className="p-1" data-testid="reliability">
            <div className="flex items-center gap-2">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Reliability</p>
              <Badge variant="warning" size="sm">not instrumented</Badge>
            </div>
            <p className="mt-2 text-xs text-slate-500">{data?.reliability?.note ?? 'Error rate / latency not tracked in-platform yet.'}</p>
          </div>
        </Card>

        <Card>
          <div className="p-1" data-testid="nps">
            <div className="flex items-center gap-2">
              <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">NPS / CSAT</p>
              <Badge variant="warning" size="sm">not instrumented</Badge>
            </div>
            <p className="mt-2 text-xs text-slate-500">{data?.nps?.note ?? 'No customer-satisfaction instrumentation yet.'}</p>
          </div>
        </Card>
      </div>
    </AdminLayout>
  );
};
