import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button } from '../../../components/antigravity/Button';
import { AdminOpsLayout } from '../../../pages/admin/ops/AdminOpsLayout';
import { adminOpsAnalyticsAPI } from '../../../api/client';
import {
  CountryFlag,
  COUNTRY_NAME,
  Kpi,
  OnHoldPill,
  ConnectedPill,
  SectionHeading,
  OpsPageActions,
  fmtNum,
  fmtPct,
  ownerTone,
  ownerInitials,
} from '../../../pages/admin/ops/opsShared';

/**
 * Ops Analytics — Dashboard tab (default landing when sidebar's "Ops analytics"
 * is clicked, mounted at /admin/ops). Renders the headline view from the
 * Claude design mock:
 *
 *   1. 4-card KPI strip — SLA met / Median ack / Reviewer load / Open bottleneck
 *   2. Two-column row — SLA performance bars + Top destinations rows
 *   3. Reviewer workload table
 *
 * SLA / Queue / Reviewers / Destinations / Alerts drill-downs are sibling
 * tabs (rendered by AdminOpsLayout's tab strip) at /admin/ops/{sla|queue|...}.
 *
 * All data is fetched via adminOpsAnalyticsAPI. When endpoints fail, the page
 * degrades to a soft "backend unavailable" banner; KPIs without usable data
 * show an "on hold" badge instead of a misleading zero.
 */

// ── Types ──────────────────────────────────────────────────────────────────

interface SlaOverview {
  open_count?: number;
  overdue_count?: number;
  breached_count?: number;
  resolved_count?: number;
  created_count?: number;
  on_time_resolution_rate_pct?: number;
  avg_time_to_assign_hours?: number;
  avg_time_to_resolve_hours?: number;
}

interface QueueBacklog {
  total?: number;
  by_status?: Record<string, number>;
  by_priority?: Record<string, number>;
  by_queue_item_type?: Record<string, number>;
}

interface ReviewerMetrics {
  total?: number;
  in_progress?: number;
  blocked?: number;
  overdue?: number;
  critical?: number;
}

interface ReviewerWorkload {
  by_assignee?: Record<string, ReviewerMetrics>;
}

interface DestinationRow {
  country_code?: string;
  city_name?: string;
  total?: number;
}

interface BottlenecksResponse {
  top_backlog_destination?: DestinationRow | null;
  total_backlog?: number;
  unassigned_count?: number;
}

interface RequestDestinationRow {
  country_code?: string;
  total?: number;
}

interface TopRequestsResponse {
  items?: RequestDestinationRow[];
  total_requests?: number;
  unique_countries?: number;
}

type ReviewerRow = { id: string; label: string } & ReviewerMetrics;

function CorridorRow({ code, count }: { code: string; count: number }) {
  return (
    <div className="flex items-center gap-3 border-b border-slate-100 py-2 last:border-b-0">
      <CountryFlag code={code} />
      <span className="flex-1 text-[13px] font-medium text-slate-800">{COUNTRY_NAME(code)}</span>
      <span className="w-10 text-right font-mono text-[12px] font-semibold text-slate-700 tabular-nums">{count}</span>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export function OpsAnalyticsV2Page() {
  const [sla, setSla] = useState<SlaOverview | null>(null);
  const [backlog, setBacklog] = useState<QueueBacklog | null>(null);
  const [reviewers, setReviewers] = useState<ReviewerWorkload | null>(null);
  const [topRequests, setTopRequests] = useState<RequestDestinationRow[]>([]);
  const [topRequestsTotal, setTopRequestsTotal] = useState<number | null>(null);
  const [bottlenecks, setBottlenecks] = useState<BottlenecksResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [degraded, setDegraded] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setDegraded([]);
    const results = await Promise.allSettled([
      adminOpsAnalyticsAPI.getSlaOverview({ days }),
      adminOpsAnalyticsAPI.getQueueBacklog(),
      adminOpsAnalyticsAPI.getReviewerWorkload(),
      adminOpsAnalyticsAPI.getBottlenecks(),
      adminOpsAnalyticsAPI.getTopDestinationsByRequest({ limit: 5 }),
    ]);
    const labels = ['SLA overview', 'Queue backlog', 'Reviewer workload', 'Bottlenecks', 'Top requested destinations'];
    const failed: string[] = [];
    results.forEach((r, i) => {
      if (r.status === 'rejected') failed.push(labels[i]!);
    });
    setDegraded(failed);

    if (results[0].status === 'fulfilled') setSla(results[0].value as SlaOverview);
    if (results[1].status === 'fulfilled') setBacklog(results[1].value as QueueBacklog);
    if (results[2].status === 'fulfilled') setReviewers(results[2].value as ReviewerWorkload);
    if (results[3].status === 'fulfilled') setBottlenecks(results[3].value as BottlenecksResponse);
    if (results[4].status === 'fulfilled') {
      const v = results[4].value as TopRequestsResponse;
      setTopRequests(v.items ?? []);
      setTopRequestsTotal(typeof v.total_requests === 'number' ? v.total_requests : null);
    }
    setLoading(false);
  }, [days]);

  useEffect(() => {
    void load();
  }, [load]);

  // ── Derived ──────────────────────────────────────────────────────────────

  const slaRate = sla?.on_time_resolution_rate_pct;
  const medianAck = sla?.avg_time_to_assign_hours;

  const reviewerRows = useMemo<ReviewerRow[]>(() => {
    const m = reviewers?.by_assignee ?? {};
    return Object.entries(m).map(([id, metrics]) => ({
      id,
      label: id === '_unassigned' ? 'Unassigned' : id,
      ...(metrics ?? {}),
    }));
  }, [reviewers]);

  const reviewerCount = reviewerRows.filter((r) => r.id !== '_unassigned').length;
  const reviewerLoadAvg = reviewerCount > 0
    ? Math.round(reviewerRows.filter((r) => r.id !== '_unassigned').reduce((s, r) => s + (r.total ?? 0), 0) / reviewerCount)
    : null;

  const topFiveRequests = useMemo(
    () => [...topRequests].sort((a, b) => (b.total ?? 0) - (a.total ?? 0)).slice(0, 5),
    [topRequests],
  );

  const bottleneckLabel = useMemo(() => {
    const dest = bottlenecks?.top_backlog_destination;
    if (dest?.country_code) {
      const city = dest.city_name ? ` · ${dest.city_name}` : '';
      return `${COUNTRY_NAME(dest.country_code)}${city}`;
    }
    const types = backlog?.by_queue_item_type;
    if (types) {
      const top = Object.entries(types).sort((a, b) => b[1] - a[1])[0];
      if (top) return top[0].replace(/_/g, ' ');
    }
    return '—';
  }, [bottlenecks, backlog]);

  const bottleneckSub = useMemo(() => {
    const totalBacklog = bottlenecks?.total_backlog ?? backlog?.total ?? 0;
    const topCount = bottlenecks?.top_backlog_destination?.total
      ?? (backlog?.by_queue_item_type ? Math.max(...Object.values(backlog.by_queue_item_type)) : 0);
    if (!totalBacklog) return 'no backlog';
    const pct = Math.round((topCount / totalBacklog) * 100);
    return `${pct}% of delays`;
  }, [bottlenecks, backlog]);

  const backendUnavailable = degraded.length > 0 && degraded.length === 5;

  return (
    <AdminOpsLayout
      title="Ops analytics"
      subtitle="SLA performance, reviewer workload, top destinations, and operational bottlenecks across all tenants."
      headerRight={<OpsPageActions days={days} onDaysChange={setDays} />}
    >
      {/* Soft banner instead of red error when backend isn't available */}
      {backendUnavailable && (
        <div className="mb-4 flex items-start justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <span>
            All ops analytics endpoints failed in this environment (likely the Supabase
            <code className="mx-1">review_queue_items</code> and related tables aren't populated).
          </span>
          <Button unstyled type="button" onClick={() => void load()} className="text-amber-700 hover:underline">
            Retry
          </Button>
        </div>
      )}
      {!backendUnavailable && degraded.length > 0 && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800">
          Partial data: {degraded.join(', ')} unavailable.
        </div>
      )}

      {/* KPI strip */}
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi
          label="SLA met"
          value={typeof slaRate === 'number' ? fmtPct(slaRate) : 'On hold'}
          sub={typeof slaRate === 'number' ? `target 95%${slaRate >= 95 ? ' ✓' : ''}` : 'awaiting first resolved item'}
          tone={typeof slaRate === 'number' && slaRate >= 95 ? 'success' : typeof slaRate === 'number' ? 'warning' : 'default'}
          onHold={typeof slaRate !== 'number'}
        />
        <Kpi
          label="Median ack time"
          value={typeof medianAck === 'number' && medianAck > 0 ? `${medianAck}h` : 'On hold'}
          sub={typeof sla?.avg_time_to_resolve_hours === 'number' && sla.avg_time_to_resolve_hours > 0
            ? `resolve ${sla.avg_time_to_resolve_hours}h`
            : 'awaiting first acknowledged item'}
          tone="accent"
          onHold={!(typeof medianAck === 'number' && medianAck > 0)}
        />
        <Kpi
          label="Reviewer load"
          value={reviewerLoadAvg !== null && reviewerLoadAvg > 0 ? `${reviewerLoadAvg}/wk` : 'On hold'}
          sub={reviewerCount > 0 ? `avg per FTE · ${reviewerCount} reviewers` : 'no assigned items yet'}
          tone="teal"
          onHold={!(reviewerLoadAvg !== null && reviewerLoadAvg > 0)}
        />
        <Kpi
          label="Open bottleneck"
          value={bottleneckLabel !== '—' ? bottleneckLabel : 'On hold'}
          sub={bottleneckLabel !== '—' ? bottleneckSub : 'no backlog data yet'}
          tone="warning"
          onHold={bottleneckLabel === '—'}
        />
      </div>

      {/* Chart + Destinations row */}
      <div className="mb-4 grid gap-3 lg:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="mb-3 flex items-baseline justify-between">
            <SectionHeading label={`SLA performance · last ${days} days`} />
            <OnHoldPill />
          </div>
          <div className="flex h-24 items-center justify-center rounded-md border border-dashed border-slate-200 bg-slate-50/60">
            <p className="px-4 text-center text-[12px] text-slate-500">
              SLA performance data will appear once the reporting endpoint
              (<code>/api/admin/ops/sla/series</code>) ships.
            </p>
          </div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="mb-3 flex items-baseline justify-between">
            <SectionHeading label="Top destinations · all requests" />
            <div className="flex items-center gap-2">
              {typeof topRequestsTotal === 'number' && topRequestsTotal > 0 && (
                <span className="text-[11px] text-slate-500">
                  {topRequestsTotal.toLocaleString()} request{topRequestsTotal === 1 ? '' : 's'}
                </span>
              )}
              {topFiveRequests.length > 0 ? <ConnectedPill /> : <OnHoldPill />}
            </div>
          </div>
          {loading ? (
            <div className="py-6 text-center text-[12.5px] text-slate-500">Loading…</div>
          ) : topFiveRequests.length === 0 ? (
            <div className="py-6 text-center text-[12.5px] text-slate-500">
              No requests with a destination yet. Each new case populates this list.
            </div>
          ) : (
            topFiveRequests.map((d) => (
              <CorridorRow
                key={d.country_code ?? 'unknown'}
                code={d.country_code ?? ''}
                count={d.total ?? 0}
              />
            ))
          )}
        </div>
      </div>

      {/* Reviewer workload table */}
      <div className="mb-4 rounded-lg border border-slate-200 bg-white p-4">
        <div className="mb-3 flex items-baseline justify-between">
          <SectionHeading label="Reviewer workload" />
          {reviewerRows.length > 0 ? <ConnectedPill /> : <OnHoldPill />}
        </div>
        {loading ? (
          <div className="py-6 text-center text-[12.5px] text-slate-500">Loading…</div>
        ) : reviewerRows.length === 0 ? (
          <div className="py-6 text-center text-[12.5px] text-slate-500">No assigned items.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-[12.5px]">
              <thead>
                <tr className="border-b border-slate-200 text-[10.5px] uppercase tracking-wider text-slate-500">
                  <th className="px-3 py-2 text-left font-semibold">Reviewer</th>
                  <th className="px-3 py-2 text-right font-semibold">Active items</th>
                  <th className="px-3 py-2 text-right font-semibold">In progress</th>
                  <th className="px-3 py-2 text-right font-semibold">Blocked</th>
                  <th className="px-3 py-2 text-right font-semibold">Overdue</th>
                  <th className="px-3 py-2 text-right font-semibold">Critical</th>
                  <th className="px-3 py-2 text-right font-semibold text-amber-700">
                    Closed (30d) <span className="text-[9px] text-amber-600">on hold</span>
                  </th>
                  <th className="px-3 py-2 text-right font-semibold text-amber-700">
                    Median ack <span className="text-[9px] text-amber-600">on hold</span>
                  </th>
                  <th className="px-3 py-2 text-right font-semibold text-amber-700">
                    SLA met <span className="text-[9px] text-amber-600">on hold</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {reviewerRows.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50">
                    <td className="px-3 py-2">
                      <span className="inline-flex items-center gap-2">
                        <span className={`inline-flex h-5 w-5 items-center justify-center rounded text-[10px] font-semibold ${ownerTone(r.id)}`}>
                          {ownerInitials(r.id)}
                        </span>
                        <span className="text-slate-800">{r.label}</span>
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmtNum(r.total)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmtNum(r.in_progress)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-rose-600">{fmtNum(r.blocked)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-amber-600">{fmtNum(r.overdue)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-rose-600">{fmtNum(r.critical)}</td>
                    <td className="px-3 py-2 text-right text-slate-300">—</td>
                    <td className="px-3 py-2 text-right text-slate-300">—</td>
                    <td className="px-3 py-2 text-right text-slate-300">—</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AdminOpsLayout>
  );
}

export default OpsAnalyticsV2Page;
