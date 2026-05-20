import { useCallback, useEffect, useMemo, useState } from 'react';
import { AppShell } from '../../../components/AppShell';
import { ProviderStatusGrid } from '../../../components/providers/ProviderStatusGrid';
import { hrAPI } from '../../../api/client';
import type { ProviderGridRow } from '../../../api/client';

/**
 * Provider Grid V2 — prototype-styled wrapper around the existing
 * ProviderStatusGrid component (verdict: ADOPT). No new data shape, no
 * adapter — the underlying ProviderStatusGrid is already prototype-aligned
 * in concept (Provider × Case matrix). This wrapper adds the platform-v2
 * page header (eyebrow + h1 + sub-line) and a small KPI strip computed
 * from the same row list.
 *
 * Endpoint: GET /api/hr/provider-status-grid (existing).
 * Mounted at sibling /hr/provider-grid-v2 + via V2Gate on /hr/provider-grid.
 */
export function ProviderGridV2Page() {
  const [rows, setRows] = useState<ProviderGridRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchGrid = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await hrAPI.getProviderStatusGrid();
      setRows(data.rows);
      setLastRefreshed(new Date());
    } catch {
      setError('Failed to load provider grid. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchGrid();
  }, [fetchGrid]);

  // KPIs computed from the same row list — keeps everything in one render path.
  const kpis = useMemo(() => {
    const byStatus = (s: ProviderGridRow['coordination_status']) =>
      rows.filter((r) => r.coordination_status === s).length;
    const blockedCells = rows.reduce((acc, r) => {
      let n = 0;
      for (const v of Object.values(r.cells)) if (v === 'blocked') n++;
      return acc + n;
    }, 0);
    return {
      total: rows.length,
      notStarted: byStatus('not-started'),
      inProgress: byStatus('in-progress'),
      atRisk: byStatus('at-risk'),
      complete: byStatus('complete'),
      blockedCells,
    };
  }, [rows]);

  return (
    <AppShell>
      {/* No max-width cap — list pages fill the viewport so wide tables fit
          without horizontal scroll on larger monitors. */}
      <div className="px-6 py-6">
        {/* Header */}
        <div className="mb-5">
          <div className="text-[11px] font-medium uppercase tracking-widest text-slate-400">
            ReloPass · /hr/provider-grid
          </div>
          <div className="mt-1.5 flex items-baseline gap-3">
            <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Provider status</h1>
            <Pill className="bg-indigo-50 text-indigo-700 ring-indigo-200">v2 preview</Pill>
            <button
              type="button"
              onClick={() => void fetchGrid()}
              disabled={loading}
              className="ml-auto text-xs font-medium text-indigo-600 underline-offset-2 hover:underline disabled:opacity-50"
            >
              {loading ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>
          <p className="mt-1 max-w-3xl text-[13px] text-slate-500">
            Real-time coordination state of every provider across active cases. Click any cell to drill into the case.
          </p>
        </div>

        {/* KPI strip */}
        <div className="mb-5 grid grid-cols-3 gap-3 md:grid-cols-6">
          <Kpi label="Active cases" value={kpis.total} sub="all in flight" />
          <Kpi label="Not started" value={kpis.notStarted} sub="awaiting coord." tone="default" />
          <Kpi label="In progress" value={kpis.inProgress} sub="under way" tone="accent" />
          <Kpi label="At risk" value={kpis.atRisk} sub="delays > 5d" tone="warning" />
          <Kpi label="Complete" value={kpis.complete} sub="ready" tone="success" />
          <Kpi label="Blocked cells" value={kpis.blockedCells} sub="across providers" tone={kpis.blockedCells > 0 ? 'danger' : 'default'} />
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <ProviderStatusGrid
          rows={rows}
          loading={loading}
          lastRefreshed={lastRefreshed}
          onRefresh={fetchGrid}
        />
      </div>
    </AppShell>
  );
}

// ── Local visual primitives (same idiom as CompaniesV2) ─────────────────────

function Pill({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${className}`}>
      {children}
    </span>
  );
}

interface KpiProps {
  label: string;
  value: string | number;
  sub: string;
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'accent';
}

function Kpi({ label, value, sub, tone = 'default' }: KpiProps) {
  const valueColor: Record<NonNullable<KpiProps['tone']>, string> = {
    default: 'text-slate-900',
    success: 'text-emerald-700',
    warning: 'text-amber-700',
    danger: 'text-rose-700',
    accent: 'text-indigo-700',
  };
  const dot: Record<NonNullable<KpiProps['tone']>, string> = {
    default: 'bg-slate-200',
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    danger: 'bg-rose-500',
    accent: 'bg-indigo-500',
  };
  return (
    <div className="relative rounded-lg border border-slate-200 bg-white px-3 py-2.5 transition-colors hover:border-slate-300">
      <span className={`absolute right-2.5 top-2.5 block h-1.5 w-1.5 rounded-full ${dot[tone]}`} aria-hidden />
      <div className="truncate text-[10px] font-semibold uppercase tracking-widest text-slate-500">{label}</div>
      <div className={`mt-1 text-[22px] font-semibold leading-none tracking-tight tabular-nums ${valueColor[tone]}`}>
        {value}
      </div>
      <div className="mt-1 truncate text-[10.5px] text-slate-500">{sub}</div>
    </div>
  );
}

export default ProviderGridV2Page;
