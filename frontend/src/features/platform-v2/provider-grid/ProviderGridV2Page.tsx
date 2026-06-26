import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../../../components/antigravity/Button';
import { AppShell } from '../../../components/AppShell';
import { Breadcrumb } from '../../../components/Breadcrumb';
import { ProviderStatusGrid } from '../../../components/providers/ProviderStatusGrid';
import { hrAPI } from '../../../api/client';
import type { ProviderGridRow } from '../../../api/client';
import { useV2Flag } from '../useV2Flag';
import { ROUTE_DEFS } from '../../../navigation/routes';
import { ProviderGridV2Table } from './ProviderGridV2Table';

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
 *
 * `embedded`: when rendered as the "Provider Status" tab inside another
 * AppShell (HrServiceProvidersPage, NAV-SP-1), skip the outer AppShell +
 * Breadcrumb to avoid double-shell nesting. Default off → standalone route
 * behaviour is unchanged.
 */
export function ProviderGridV2Page({ embedded = false }: { embedded?: boolean } = {}) {
  // Flag-gated resizable + drag-reorder table. Defaults off → renders the
  // existing ProviderStatusGrid unchanged. Set
  // localStorage.platform_v2_provider_grid_resizable='on' to opt in.
  const { on: resizableOn } = useV2Flag('provider_grid_resizable');

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

  const inner = (
    <>
      {/* No max-width cap — list pages fill the viewport so wide tables fit
          without horizontal scroll on larger monitors. */}
      <div className="px-6 py-6">
        {/* Header — Breadcrumb suppressed when embedded as a sub-tab. */}
        {!embedded && <Breadcrumb section="HR Operations" title="Provider status" className="mb-3" />}
        <div className="mb-5">
          <div className="flex items-baseline gap-3">
            <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Provider status</h1>
            <Button unstyled
              type="button"
              onClick={() => void fetchGrid()}
              disabled={loading}
              className="ml-auto text-xs font-medium text-accent-600 underline-offset-2 hover:underline disabled:opacity-50"
            >
              {loading ? 'Refreshing…' : 'Refresh'}
            </Button>
          </div>
          <p className="mt-1 max-w-3xl text-[13px] text-slate-500">
            Live status for each provider across active relocations. Click a cell to view the case.
          </p>
        </div>

        {/* KPI strip */}
        <div className="mb-5 grid grid-cols-3 gap-3 md:grid-cols-6">
          <Kpi label="Active cases" value={kpis.total} sub="all in flight" />
          <Kpi label="Not started" value={kpis.notStarted} sub="Awaiting coordination" tone="default" />
          <Kpi label="In progress" value={kpis.inProgress} sub="Work underway" tone="accent" />
          <Kpi label="At risk" value={kpis.atRisk} sub="Delayed by 5+ days" tone="warning" title="Flagged when a provider task is more than 5 days past its due date." />
          <Kpi label="Complete" value={kpis.complete} sub="Delivery complete" tone="success" />
          <Kpi label="Blocked" value={kpis.blockedCells} sub="Waiting on a blocker" tone={kpis.blockedCells > 0 ? 'danger' : 'default'} />
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Flag-gated table. Default: legacy ProviderStatusGrid (which has
            its own toolbar with row count + refresh button). Flag on:
            ProviderGridV2Table backed by <DataTable> for resize + drag-
            reorder + per-table layout persistence. */}
        {resizableOn ? (
          <ProviderGridV2Table
            rows={rows}
            emptyState={
              loading ? (
                'Loading provider grid…'
              ) : (
                <span>
                  No providers assigned. Assign providers in the{' '}
                  <Link to={ROUTE_DEFS.hrCommandCenter.path} className="text-[#1f8e8b] underline">
                    Mobility command center
                  </Link>{' '}
                  to track their status here.
                </span>
              )
            }
          />
        ) : (
          <ProviderStatusGrid
            rows={rows}
            loading={loading}
            lastRefreshed={lastRefreshed}
            onRefresh={fetchGrid}
          />
        )}
      </div>
    </>
  );

  return embedded ? inner : <AppShell>{inner}</AppShell>;
}

// ── Local visual primitives (same idiom as CompaniesV2) ─────────────────────

interface KpiProps {
  label: string;
  value: string | number;
  sub: string;
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'accent';
  /** Optional hover tooltip explaining the metric (TASK-014). */
  title?: string;
}

function Kpi({ label, value, sub, tone = 'default', title }: KpiProps) {
  const valueColor: Record<NonNullable<KpiProps['tone']>, string> = {
    default: 'text-slate-900',
    success: 'text-emerald-700',
    warning: 'text-amber-700',
    danger: 'text-rose-700',
    accent: 'text-accent-700',
  };
  const dot: Record<NonNullable<KpiProps['tone']>, string> = {
    default: 'bg-slate-200',
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    danger: 'bg-rose-500',
    accent: 'bg-accent-500',
  };
  return (
    <div
      className="relative rounded-lg border border-slate-200 bg-white px-3 py-2.5 transition-colors hover:border-slate-300"
      title={title}
    >
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
