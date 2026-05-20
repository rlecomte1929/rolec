import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminLayout } from '../../../pages/admin/AdminLayout';
import { adminOpsAnalyticsAPI } from '../../../api/client';
import { buildRoute } from '../../../navigation/routes';

/**
 * Admin Ops Analytics — V2.
 *
 * Renders the dashboard shape from the Claude design mock
 * (frontend/public/design-preview/platform-s9-admin.jsx → OpsAnalyticsScreen):
 *
 *   1. 4-card KPI strip — SLA met / Median ack / Reviewer load / Open bottleneck
 *   2. Two-column row — SLA performance bars + Top destinations rows
 *   3. Reviewer workload table
 *
 * Below the dashboard, the same five views currently exposed as pill tabs on
 * the legacy /admin/ops layout (SLA / Queue / Reviewers / Destinations / Alerts)
 * are folded into accordion sections, so the detail data is still one click
 * away without a route change.
 *
 * All data is fetched via the existing adminOpsAnalyticsAPI (admin-only
 * endpoints in backend/app/routers/admin_ops_analytics.py). When an endpoint
 * fails (commonly 500 in environments where the review_queue_items table
 * isn't populated), the page degrades to a soft "backend unavailable" banner
 * instead of the red error block the legacy page surfaces.
 *
 * Default-off until enabled via the platform_v2_ops_analytics flag.
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
  critical_resolved?: number;
  critical_breach_count?: number;
}

interface QueueBacklog {
  total?: number;
  by_status?: Record<string, number>;
  by_priority?: Record<string, number>;
  by_queue_item_type?: Record<string, number>;
}

interface BreachItem {
  id: string;
  title?: string;
  priority_band?: string;
  country_code?: string;
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
  critical?: number;
}

interface DestinationsResponse {
  items?: DestinationRow[];
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

interface BottlenecksResponse {
  top_backlog_destination?: DestinationRow | null;
  total_backlog?: number;
  unassigned_count?: number;
}

interface NotificationMetrics {
  created_count?: number;
  open_count?: number;
  resolved_count?: number;
  by_type?: Record<string, number>;
}

// ── Helpers ────────────────────────────────────────────────────────────────

const COUNTRY_NAMES: Record<string, string> = {
  NO: 'Norway', DE: 'Germany', US: 'United States', SG: 'Singapore', CA: 'Canada',
  FR: 'France', GB: 'United Kingdom', UK: 'United Kingdom', IN: 'India', AU: 'Australia',
  NL: 'Netherlands', ES: 'Spain', IT: 'Italy', BR: 'Brazil', MX: 'Mexico',
  JP: 'Japan', CN: 'China', KR: 'South Korea', SE: 'Sweden', DK: 'Denmark',
  FI: 'Finland', CH: 'Switzerland', AT: 'Austria', BE: 'Belgium', IE: 'Ireland',
  PL: 'Poland', PT: 'Portugal',
};

const COUNTRY_NAME = (code?: string) => (code ? (COUNTRY_NAMES[code.toUpperCase()] ?? code) : '—');

const OWNER_TONES = ['bg-indigo-100 text-indigo-700', 'bg-emerald-100 text-emerald-700', 'bg-amber-100 text-amber-700', 'bg-sky-100 text-sky-700', 'bg-rose-100 text-rose-700', 'bg-violet-100 text-violet-700'];

function ownerTone(userId: string): string {
  let hash = 5381;
  for (let i = 0; i < userId.length; i++) hash = ((hash << 5) + hash + userId.charCodeAt(i)) | 0;
  return OWNER_TONES[Math.abs(hash) % OWNER_TONES.length]!;
}

function ownerInitials(userId: string): string {
  return userId.replace(/[^A-Za-z0-9]/g, '').slice(0, 2).toUpperCase() || '??';
}

function fmtNum(n: number | undefined): string {
  return typeof n === 'number' && Number.isFinite(n) ? n.toLocaleString() : '—';
}

function fmtPct(n: number | undefined): string {
  return typeof n === 'number' && Number.isFinite(n) ? `${n}%` : '—';
}

// ── Small visual primitives ────────────────────────────────────────────────

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
  tone?: 'default' | 'success' | 'warning' | 'accent' | 'danger' | 'teal';
  notConnected?: boolean;
}

function Kpi({ label, value, sub, tone = 'default', notConnected = false }: KpiProps) {
  const valueColor: Record<NonNullable<KpiProps['tone']>, string> = {
    default: 'text-slate-900',
    success: 'text-emerald-700',
    warning: 'text-amber-700',
    accent: 'text-indigo-700',
    danger: 'text-rose-700',
    teal: 'text-teal-700',
  };
  const dot: Record<NonNullable<KpiProps['tone']>, string> = {
    default: 'bg-slate-200',
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    accent: 'bg-indigo-500',
    danger: 'bg-rose-500',
    teal: 'bg-teal-500',
  };
  return (
    <div className="relative rounded-lg border border-slate-200 bg-white px-4 py-3 transition-colors hover:border-slate-300">
      <span className={`absolute right-3 top-3 block h-1.5 w-1.5 rounded-full ${dot[tone]}`} aria-hidden />
      <div className="flex items-center gap-1.5">
        <div className="truncate text-[10px] font-semibold uppercase tracking-widest text-slate-500">{label}</div>
        {notConnected && (
          <span className="rounded bg-amber-50 px-1 text-[9px] font-semibold uppercase tracking-wider text-amber-700 ring-1 ring-inset ring-amber-200" title="Data source not yet connected">
            stub
          </span>
        )}
      </div>
      <div className={`mt-1 text-[28px] font-semibold leading-none tracking-tight tabular-nums ${valueColor[tone]}`}>
        {value}
      </div>
      <div className="mt-1.5 truncate text-[11px] text-slate-500">{sub}</div>
    </div>
  );
}

function SectionHeading({ label }: { label: string }) {
  return (
    <h4 className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-slate-500">{label}</h4>
  );
}

/**
 * SLA performance bar chart. The backend does not yet return per-day SLA met
 * percentages, so this renders a synthetic 30-bar shape derived from the
 * single on-time resolution rate we DO have. Marked as `stub` so it can be
 * swapped when the time-series endpoint lands.
 */
function SlaBars({ rate }: { rate: number | undefined }) {
  // Deterministic visual: jitter around the actual rate so the chart has the
  // expected per-day shape without lying about the underlying data.
  const center = typeof rate === 'number' ? rate : 95;
  const bars = useMemo(() => {
    const out: number[] = [];
    let seed = 7;
    for (let i = 0; i < 30; i++) {
      seed = (seed * 9301 + 49297) % 233280;
      const jitter = ((seed / 233280) - 0.5) * 12;
      out.push(Math.max(60, Math.min(100, Math.round(center + jitter))));
    }
    return out;
  }, [center]);
  return (
    <div className="flex h-24 items-end gap-[3px]">
      {bars.map((v, i) => (
        <div
          key={i}
          title={`${v}%`}
          className="flex-1 rounded-t-[2px] opacity-90"
          style={{
            height: `${v}%`,
            background: v >= 95 ? '#10b981' : v >= 85 ? '#6366f1' : '#f59e0b',
          }}
        />
      ))}
    </div>
  );
}

function CountryFlag({ code, className = '' }: { code: string; className?: string }) {
  const lc = (code || '').trim().toLowerCase();
  if (!lc) return <span className={`inline-block ${className}`} aria-hidden>🌍</span>;
  // flagcdn.com — public SVG/PNG flag CDN, no auth required.
  return (
    <img
      src={`https://flagcdn.com/w40/${lc}.png`}
      srcSet={`https://flagcdn.com/w40/${lc}.png 1x, https://flagcdn.com/w80/${lc}.png 2x`}
      alt={`${COUNTRY_NAME(code)} flag`}
      width={20}
      height={15}
      className={`inline-block rounded-[2px] object-cover shadow-[0_0_0_1px_rgba(15,23,42,0.06)] ${className}`}
      loading="lazy"
    />
  );
}

function CorridorRow({ code, count }: { code: string; count: number }) {
  return (
    <div className="flex items-center gap-3 border-b border-slate-100 py-2 last:border-b-0">
      <CountryFlag code={code} />
      <span className="flex-1 text-[13px] font-medium text-slate-800">{COUNTRY_NAME(code)}</span>
      <span className="w-10 text-right font-mono text-[12px] font-semibold text-slate-700 tabular-nums">{count}</span>
    </div>
  );
}

// ── Accordion section ──────────────────────────────────────────────────────

function AccordionSection({
  id,
  title,
  subtitle,
  badge,
  children,
  defaultOpen = false,
}: {
  id: string;
  title: string;
  subtitle?: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={`acc-${id}`}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-slate-50"
      >
        <span className={`inline-block transition-transform ${open ? 'rotate-90' : ''}`} aria-hidden>▸</span>
        <span className="flex-1">
          <span className="block text-[13px] font-semibold text-slate-900">{title}</span>
          {subtitle && <span className="mt-0.5 block text-[11.5px] text-slate-500">{subtitle}</span>}
        </span>
        {badge}
      </button>
      {open && (
        <div id={`acc-${id}`} className="border-t border-slate-100 px-4 py-4">
          {children}
        </div>
      )}
    </div>
  );
}

function NotConnectedPill() {
  return (
    <Pill className="bg-amber-50 text-amber-700 ring-amber-200">not connected</Pill>
  );
}

function ConnectedPill() {
  return (
    <Pill className="bg-emerald-50 text-emerald-700 ring-emerald-200">live</Pill>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────

export function OpsAnalyticsV2Page() {
  const [sla, setSla] = useState<SlaOverview | null>(null);
  const [backlog, setBacklog] = useState<QueueBacklog | null>(null);
  const [breaches, setBreaches] = useState<BreachItem[]>([]);
  const [reviewers, setReviewers] = useState<ReviewerWorkload | null>(null);
  const [destinations, setDestinations] = useState<DestinationRow[]>([]);
  const [topRequests, setTopRequests] = useState<RequestDestinationRow[]>([]);
  const [topRequestsTotal, setTopRequestsTotal] = useState<number | null>(null);
  const [bottlenecks, setBottlenecks] = useState<BottlenecksResponse | null>(null);
  const [notifications, setNotifications] = useState<NotificationMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [degraded, setDegraded] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setDegraded([]);
    const results = await Promise.allSettled([
      adminOpsAnalyticsAPI.getSlaOverview({ days }),
      adminOpsAnalyticsAPI.getQueueBacklog(),
      adminOpsAnalyticsAPI.getQueueBreaches({ limit: 20 }),
      adminOpsAnalyticsAPI.getReviewerWorkload(),
      adminOpsAnalyticsAPI.getDestinations(),
      adminOpsAnalyticsAPI.getBottlenecks(),
      adminOpsAnalyticsAPI.getNotificationMetrics({ days: 7 }),
      adminOpsAnalyticsAPI.getTopDestinationsByRequest({ limit: 5 }),
    ]);
    const labels = ['SLA overview', 'Queue backlog', 'Recent breaches', 'Reviewer workload', 'Destinations', 'Bottlenecks', 'Notifications', 'Top requested destinations'];
    const failed: string[] = [];
    results.forEach((r, i) => {
      if (r.status === 'rejected') failed.push(labels[i]!);
    });
    setDegraded(failed);

    if (results[0].status === 'fulfilled') setSla(results[0].value as SlaOverview);
    if (results[1].status === 'fulfilled') setBacklog(results[1].value as QueueBacklog);
    if (results[2].status === 'fulfilled') {
      const v = results[2].value as { items?: BreachItem[] };
      setBreaches(v.items ?? []);
    }
    if (results[3].status === 'fulfilled') setReviewers(results[3].value as ReviewerWorkload);
    if (results[4].status === 'fulfilled') {
      const v = results[4].value as DestinationsResponse;
      setDestinations(v.items ?? []);
    }
    if (results[5].status === 'fulfilled') setBottlenecks(results[5].value as BottlenecksResponse);
    if (results[6].status === 'fulfilled') setNotifications(results[6].value as NotificationMetrics);
    if (results[7].status === 'fulfilled') {
      const v = results[7].value as TopRequestsResponse;
      setTopRequests(v.items ?? []);
      setTopRequestsTotal(typeof v.total_requests === 'number' ? v.total_requests : null);
    }
    setLoading(false);
  }, [days]);

  useEffect(() => {
    void load();
  }, [load]);

  // Derived KPIs.
  const slaRate = sla?.on_time_resolution_rate_pct;
  const medianAck = sla?.avg_time_to_assign_hours;
  const reviewerRows = useMemo(() => {
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

  const sortedDestinations = useMemo(
    () => [...destinations].sort((a, b) => (b.total ?? 0) - (a.total ?? 0)),
    [destinations],
  );
  // Hero card shows the request-driven Top 5 (destinations users actually
  // picked across all relocation cases). The ops-backlog destinations are
  // still surfaced under the "Destinations" accordion below.
  const topFiveRequests = useMemo(
    () => [...topRequests].sort((a, b) => (b.total ?? 0) - (a.total ?? 0)).slice(0, 5),
    [topRequests],
  );

  // Bottleneck: prefer top destination if backend returned it, else top queue type.
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

  const backendUnavailable = degraded.length > 0 && degraded.length === 8;

  return (
    <AdminLayout>
      <div className="px-6 py-6">
        {/* Header */}
        <div className="mb-5">
          <div className="text-[11px] font-medium uppercase tracking-widest text-slate-400">
            ReloPass · /admin/ops
          </div>
          <div className="mt-1.5 flex flex-wrap items-baseline gap-3">
            <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Ops analytics</h1>
            <Pill className="bg-indigo-50 text-indigo-700 ring-indigo-200">v2 preview</Pill>
            <div className="ml-auto flex items-center gap-2">
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                <option value={7}>Last 7 days</option>
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
              </select>
              <button
                type="button"
                onClick={() => alert('Export — not yet wired')}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                ⇣ Export
              </button>
            </div>
          </div>
          <p className="mt-1 max-w-3xl text-[13px] text-slate-500">
            SLA performance, reviewer workload, top destinations, and operational bottlenecks across all tenants.
          </p>
        </div>

        {/* Soft banner instead of red error when backend isn't available */}
        {backendUnavailable && (
          <div className="mb-4 flex items-start justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <span>
              All ops analytics endpoints failed in this environment (likely the Supabase
              <code className="mx-1">review_queue_items</code> and related tables aren't populated).
              Page renders the layout but no real numbers.
            </span>
            <button type="button" onClick={() => void load()} className="text-amber-700 hover:underline">
              Retry
            </button>
          </div>
        )}
        {!backendUnavailable && degraded.length > 0 && (
          <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800">
            Partial data: {degraded.join(', ')} unavailable.
          </div>
        )}

        {/* KPI strip — 4 cards from the Claude mock */}
        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Kpi
            label="SLA met"
            value={fmtPct(slaRate)}
            sub={typeof slaRate === 'number' ? `target 95%${slaRate >= 95 ? ' ✓' : ''}` : 'no data yet'}
            tone={typeof slaRate === 'number' && slaRate >= 95 ? 'success' : 'warning'}
          />
          <Kpi
            label="Median ack time"
            value={typeof medianAck === 'number' ? `${medianAck}h` : '—'}
            sub={typeof sla?.avg_time_to_resolve_hours === 'number' ? `resolve ${sla.avg_time_to_resolve_hours}h` : 'avg time to assign'}
            tone="accent"
          />
          <Kpi
            label="Reviewer load"
            value={reviewerLoadAvg !== null ? `${reviewerLoadAvg}/wk` : '—'}
            sub={reviewerCount > 0 ? `avg per FTE · ${reviewerCount} reviewers` : 'no assignees'}
            tone="teal"
            notConnected={!reviewers?.by_assignee}
          />
          <Kpi
            label="Open bottleneck"
            value={bottleneckLabel}
            sub={bottleneckSub}
            tone="warning"
          />
        </div>

        {/* Chart + Destinations row */}
        <div className="mb-4 grid gap-3 lg:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-baseline justify-between">
              <SectionHeading label={`SLA performance · last ${days} days`} />
              <Pill className="bg-amber-50 text-amber-700 ring-amber-200">trend stub</Pill>
            </div>
            <SlaBars rate={slaRate} />
            <p className="mt-3 text-[11.5px] text-slate-500">
              Per-day SLA series is not yet exposed by the backend. Bars derive from the
              current rolling rate ({fmtPct(slaRate)}) with deterministic jitter, so the
              shape is illustrative until <code>/api/admin/ops/sla/series</code> ships.
            </p>
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
                {topFiveRequests.length > 0 ? <ConnectedPill /> : <NotConnectedPill />}
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
            {reviewerRows.length > 0 ? <ConnectedPill /> : <NotConnectedPill />}
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
                      Closed (30d) <span className="text-[9px] text-amber-600">stub</span>
                    </th>
                    <th className="px-3 py-2 text-right font-semibold text-amber-700">
                      Median ack <span className="text-[9px] text-amber-600">stub</span>
                    </th>
                    <th className="px-3 py-2 text-right font-semibold text-amber-700">
                      SLA met <span className="text-[9px] text-amber-600">stub</span>
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

        {/* ── Accordion: detail sub-sections (replaces pill tabs) ─────────── */}
        <div className="mt-8">
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-[15px] font-semibold text-slate-900">Detail views</h2>
            <span className="text-[11.5px] text-slate-500">— same data the old pill tabs showed, folded inline</span>
          </div>
          <div className="space-y-2">
            <AccordionSection
              id="sla"
              title="SLA"
              subtitle="Open / overdue / breached counts, on-time resolution rate, recent SLA breaches."
              badge={sla ? <ConnectedPill /> : <NotConnectedPill />}
            >
              <SlaDetail sla={sla} breaches={breaches} />
            </AccordionSection>
            <AccordionSection
              id="queue"
              title="Queue"
              subtitle="Backlog broken down by status, priority, and queue item type."
              badge={backlog ? <ConnectedPill /> : <NotConnectedPill />}
            >
              <QueueDetail backlog={backlog} />
            </AccordionSection>
            <AccordionSection
              id="reviewers"
              title="Reviewers"
              subtitle="Full per-assignee workload table (above shows the same data)."
              badge={reviewerRows.length > 0 ? <ConnectedPill /> : <NotConnectedPill />}
            >
              <ReviewersDetail rows={reviewerRows} />
            </AccordionSection>
            <AccordionSection
              id="destinations"
              title="Destinations"
              subtitle="Queue volume by country and city (complete table, not just top 5)."
              badge={destinations.length > 0 ? <ConnectedPill /> : <NotConnectedPill />}
            >
              <DestinationsDetail rows={sortedDestinations} />
            </AccordionSection>
            <AccordionSection
              id="alerts"
              title="Alerts"
              subtitle="Notification volume — created / open / resolved, broken down by type."
              badge={notifications ? <ConnectedPill /> : <NotConnectedPill />}
            >
              <AlertsDetail data={notifications} />
            </AccordionSection>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}

// ── Accordion bodies ───────────────────────────────────────────────────────

function SlaDetail({ sla, breaches }: { sla: SlaOverview | null; breaches: BreachItem[] }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <MiniStat label="Open" value={fmtNum(sla?.open_count)} />
        <MiniStat label="Overdue" value={fmtNum(sla?.overdue_count)} tone="warning" />
        <MiniStat label="Breached" value={fmtNum(sla?.breached_count)} tone="danger" />
        <MiniStat label="On-time" value={fmtPct(sla?.on_time_resolution_rate_pct)} tone="success" />
        <MiniStat label="Avg resolve" value={typeof sla?.avg_time_to_resolve_hours === 'number' ? `${sla.avg_time_to_resolve_hours}h` : '—'} />
        <MiniStat label="Resolved" value={fmtNum(sla?.resolved_count)} />
      </div>
      <div>
        <SectionHeading label="Recent SLA breaches" />
        {breaches.length === 0 ? (
          <p className="text-[12.5px] text-slate-500">No breaches in current open items.</p>
        ) : (
          <ul className="space-y-1">
            {breaches.slice(0, 10).map((b) => (
              <li key={b.id}>
                <Link
                  to={buildRoute('adminReviewQueueDetail', { id: b.id })}
                  className="block rounded bg-slate-50 px-3 py-1.5 text-[12.5px] hover:bg-slate-100"
                >
                  <span className="font-medium text-slate-800">{(b.title ?? 'Queue item').slice(0, 80)}</span>
                  <span className="ml-2 text-[11px] text-slate-500">· {b.priority_band ?? 'unknown'}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
        {breaches.length > 0 && (
          <Link to={`${buildRoute('adminReviewQueue')}?overdue=1`} className="mt-2 inline-block text-[12px] text-indigo-700 underline">
            View all overdue →
          </Link>
        )}
      </div>
    </div>
  );
}

function QueueDetail({ backlog }: { backlog: QueueBacklog | null }) {
  if (!backlog) return <p className="text-[12.5px] text-slate-500">No queue data available.</p>;
  const byStatus = backlog.by_status ?? {};
  const byPriority = backlog.by_priority ?? {};
  const byType = backlog.by_queue_item_type ?? {};
  return (
    <div className="space-y-4">
      <MiniStat label="Total backlog" value={fmtNum(backlog.total)} tone="accent" />
      <div className="grid gap-3 sm:grid-cols-3">
        <BreakdownList title="By status" entries={byStatus} />
        <BreakdownList title="By priority" entries={byPriority} />
        <BreakdownList title="By type" entries={byType} />
      </div>
      <Link to={buildRoute('adminReviewQueue')} className="inline-block text-[12px] text-indigo-700 underline">
        → View review queue
      </Link>
    </div>
  );
}

function ReviewersDetail({ rows }: { rows: ReviewerRow[] }) {
  if (rows.length === 0) return <p className="text-[12.5px] text-slate-500">No assigned items.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-[12.5px]">
        <thead>
          <tr className="border-b border-slate-200 text-[10.5px] uppercase tracking-wider text-slate-500">
            <th className="px-3 py-2 text-left font-semibold">Assignee</th>
            <th className="px-3 py-2 text-right font-semibold">Total</th>
            <th className="px-3 py-2 text-right font-semibold">In progress</th>
            <th className="px-3 py-2 text-right font-semibold">Blocked</th>
            <th className="px-3 py-2 text-right font-semibold">Overdue</th>
            <th className="px-3 py-2 text-right font-semibold">Critical</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => (
            <tr key={r.id} className="hover:bg-slate-50">
              <td className="px-3 py-2 text-slate-800">{r.label}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmtNum(r.total)}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmtNum(r.in_progress)}</td>
              <td className="px-3 py-2 text-right tabular-nums text-rose-600">{fmtNum(r.blocked)}</td>
              <td className="px-3 py-2 text-right tabular-nums text-amber-600">{fmtNum(r.overdue)}</td>
              <td className="px-3 py-2 text-right tabular-nums text-rose-600">{fmtNum(r.critical)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type ReviewerRow = { id: string; label: string } & ReviewerMetrics;

function DestinationsDetail({ rows }: { rows: DestinationRow[] }) {
  if (rows.length === 0) return <p className="text-[12.5px] text-slate-500">No destination data.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-[12.5px]">
        <thead>
          <tr className="border-b border-slate-200 text-[10.5px] uppercase tracking-wider text-slate-500">
            <th className="px-3 py-2 text-left font-semibold">Country</th>
            <th className="px-3 py-2 text-left font-semibold">City</th>
            <th className="px-3 py-2 text-right font-semibold">Total</th>
            <th className="px-3 py-2 text-right font-semibold">Critical</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((d, i) => (
            <tr key={`${d.country_code}-${d.city_name}-${i}`} className="hover:bg-slate-50">
              <td className="px-3 py-2 text-slate-800">
                <CountryFlag code={d.country_code ?? ''} className="mr-2 align-middle" />
                {COUNTRY_NAME(d.country_code)}
              </td>
              <td className="px-3 py-2 text-slate-700">{d.city_name ?? '—'}</td>
              <td className="px-3 py-2 text-right tabular-nums">{fmtNum(d.total)}</td>
              <td className="px-3 py-2 text-right tabular-nums text-rose-600">{fmtNum(d.critical)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AlertsDetail({ data }: { data: NotificationMetrics | null }) {
  if (!data) return <p className="text-[12.5px] text-slate-500">No notification data available.</p>;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <MiniStat label="Created" value={fmtNum(data.created_count)} />
        <MiniStat label="Open" value={fmtNum(data.open_count)} tone="warning" />
        <MiniStat label="Resolved" value={fmtNum(data.resolved_count)} tone="success" />
      </div>
      <BreakdownList title="By type" entries={data.by_type ?? {}} />
    </div>
  );
}

function MiniStat({ label, value, tone = 'default' }: { label: string; value: string; tone?: 'default' | 'success' | 'warning' | 'danger' | 'accent' }) {
  const color: Record<string, string> = {
    default: 'text-slate-900',
    success: 'text-emerald-700',
    warning: 'text-amber-700',
    danger: 'text-rose-700',
    accent: 'text-indigo-700',
  };
  return (
    <div className="rounded-md border border-slate-200 bg-white px-3 py-2">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">{label}</div>
      <div className={`mt-0.5 text-lg font-semibold tabular-nums ${color[tone]}`}>{value}</div>
    </div>
  );
}

function BreakdownList({ title, entries }: { title: string; entries: Record<string, number> }) {
  const list = Object.entries(entries).sort((a, b) => b[1] - a[1]);
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <div className="mb-2 text-[10.5px] font-semibold uppercase tracking-widest text-slate-500">{title}</div>
      {list.length === 0 ? (
        <p className="text-[12px] text-slate-400">No data.</p>
      ) : (
        <ul className="space-y-1 text-[12.5px]">
          {list.map(([k, v]) => (
            <li key={k} className="flex justify-between">
              <span className="capitalize text-slate-700">{k.replace(/_/g, ' ')}</span>
              <span className="tabular-nums font-medium text-slate-900">{v}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default OpsAnalyticsV2Page;
