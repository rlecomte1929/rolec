import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../../components/antigravity/Button';
import { AdminLayout } from '../../../pages/admin/AdminLayout';
import { adminReviewQueueAPI } from '../../../api/client';
import { buildRoute } from '../../../navigation/routes';
import { DataTable, ResetColumnsLink, type DataTableColumn } from '../data-table';

/**
 * Admin Review Queue — V2.
 *
 * Mock-driven redesign of /admin/review-queue. Renders the same data the
 * legacy page does (via `adminReviewQueueAPI.list()` + `getStats()`), but
 * with the prototype's compact 4-KPI strip + clean DataTable layout
 * (resize + drag-reorder + persistence from day one).
 *
 * Backend behaviour: if /api/admin/review-queue 500s (which it does in
 * environments where the Supabase `review_queue_items` table isn't
 * populated), the page renders a friendly empty state with a small
 * advisory banner — NOT a red error block. Default-off until enabled
 * via the platform_v2_review_queue flag.
 */

// ── Data shape (matches the legacy page's QueueItem) ────────────────────────

interface QueueItem {
  id: string;
  queue_item_type: string;
  status: string;
  priority_score: number;
  priority_band: string;
  title: string;
  country_code?: string;
  city_name?: string;
  content_domain?: string;
  source_name?: string;
  trust_tier?: string;
  assigned_to_user_id?: string | null;
  due_at?: string | null;
  created_at?: string | null;
  priority_reasons?: string[];
}

// ── Constants ──────────────────────────────────────────────────────────────

/** Friendly labels for queue item types. Includes both real backend values
 *  and the mock's labels so future backend additions Just Work. */
const QUEUE_TYPE_LABELS: Record<string, string> = {
  vendor_approval: 'Vendor approval',
  resource_publish: 'Resource publish',
  policy_exception: 'Policy exception',
  form_template: 'Form template',
  source_refresh: 'Source refresh',
  tax_rule: 'Tax rule',
  tenant_onboarding: 'Tenant onboarding',
  staged_resource_candidate: 'Staged Resource',
  staged_event_candidate: 'Staged Event',
  source_change_review: 'Source change',
  stale_live_resource_review: 'Stale resource',
  stale_live_event_review: 'Stale event',
  duplicate_resolution: 'Duplicate',
  crawl_failure_review: 'Crawl failure',
  coverage_gap_review: 'Coverage gap',
};

const PRIORITY_PILL: Record<string, string> = {
  high: 'bg-rose-50 text-rose-700 ring-rose-200',
  medium: 'bg-amber-50 text-amber-700 ring-amber-200',
  low: 'bg-slate-100 text-slate-600 ring-slate-200',
};

const PRIORITY_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

const OWNER_TONES = ['bg-accent-100 text-accent-700', 'bg-emerald-100 text-emerald-700', 'bg-amber-100 text-amber-700', 'bg-sky-100 text-sky-700', 'bg-rose-100 text-rose-700', 'bg-accent-100 text-accent-700'];

/**
 * The queue's "open" universe: canonical granular statuses + synthetic item
 * statuses ('open' = provider invites, 'pending' = exception requests).
 *
 * Mirrors the legacy workload page's client-side filter. Passing
 * `status: 'open'` to the API instead literal-matches status == "open", which
 * silently drops every canonical item (they use the granular statuses) and
 * leaves only synthetic invites — that mismatch is what made the "Open" KPI
 * and the table row count disagree.
 */
const OPEN_QUEUE_STATUSES = new Set([
  'new', 'triaged', 'assigned', 'in_progress', 'blocked', 'waiting', 'reopened',
  'open', 'pending',
]);

// ── Helpers ────────────────────────────────────────────────────────────────

/** UUID → "rq-xxxx" so the ID column is scannable. Real UUIDs are too long. */
function shortId(uuid: string): string {
  if (!uuid) return '—';
  const trimmed = uuid.replace(/-/g, '').slice(0, 4);
  return `rq-${trimmed}`;
}

/** Compact relative age. "2h", "1d", "3wk", etc. */
function relativeAge(iso: string | null | undefined): string {
  if (!iso) return '—';
  const ms = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(ms)) return '—';
  const min = Math.floor(ms / 60_000);
  if (min < 60) return `${Math.max(0, min)}m`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h`;
  const days = Math.floor(hr / 24);
  if (days < 14) return `${days}d`;
  const wk = Math.floor(days / 7);
  if (wk < 8) return `${wk}wk`;
  const mo = Math.floor(days / 30);
  return `${mo}mo`;
}

/** Deterministic colour bucket from a user id, mirrors the company-logo tone. */
function ownerTone(userId: string): string {
  let hash = 5381;
  for (let i = 0; i < userId.length; i++) hash = ((hash << 5) + hash + userId.charCodeAt(i)) | 0;
  return OWNER_TONES[Math.abs(hash) % OWNER_TONES.length]!;
}

function ownerInitials(userId: string): string {
  return userId.replace(/[^A-Za-z0-9]/g, '').slice(0, 2).toUpperCase() || '??';
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
  sub?: string;
  tone?: 'default' | 'success' | 'warning' | 'accent' | 'danger';
}

function Kpi({ label, value, sub, tone = 'default' }: KpiProps) {
  const valueColor: Record<NonNullable<KpiProps['tone']>, string> = {
    default: 'text-slate-900',
    success: 'text-emerald-700',
    warning: 'text-rose-700',
    accent: 'text-amber-700',
    danger: 'text-rose-700',
  };
  const dot: Record<NonNullable<KpiProps['tone']>, string> = {
    default: 'bg-slate-200',
    success: 'bg-emerald-500',
    warning: 'bg-rose-500',
    accent: 'bg-amber-500',
    danger: 'bg-rose-500',
  };
  return (
    <div className="relative rounded-lg border border-slate-200 bg-white px-4 py-3 transition-colors hover:border-slate-300">
      <span className={`absolute right-3 top-3 block h-1.5 w-1.5 rounded-full ${dot[tone]}`} aria-hidden />
      <div className="truncate text-[10px] font-semibold uppercase tracking-widest text-slate-500">{label}</div>
      <div className={`mt-1 text-[28px] font-semibold leading-none tracking-tight tabular-nums ${valueColor[tone]}`}>
        {value}
      </div>
      {sub && <div className="mt-1.5 truncate text-[11px] text-slate-500">{sub}</div>}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────

export function AdminReviewQueueV2Page() {
  const navigate = useNavigate();
  const [items, setItems] = useState<QueueItem[]>([]);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [backendUnavailable, setBackendUnavailable] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setBackendUnavailable(false);
    const [statsRes, listRes] = await Promise.allSettled([
      adminReviewQueueAPI.getStats(),
      adminReviewQueueAPI.list({ limit: 200, sort: 'priority' }),
    ]);
    if (statsRes.status === 'fulfilled') {
      setStats(statsRes.value as Record<string, unknown>);
    }
    if (listRes.status === 'fulfilled') {
      const data = listRes.value as { items?: QueueItem[] };
      // status filtering happens client-side: the API returns every status
      // when unfiltered, so keep only the open universe (see OPEN_QUEUE_STATUSES).
      setItems((data.items ?? []).filter((it) => OPEN_QUEUE_STATUSES.has(it.status)));
    } else {
      // 500s, network errors, missing tables — all degrade to "no data" with
      // a soft banner. Avoids the red "Request failed with status code 500"
      // block the legacy page surfaces.
      setItems([]);
      setBackendUnavailable(true);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // KPIs: derived from items + stats where available.
  const kpis = useMemo(() => {
    // "Open" counts exactly the rows the table renders. (The old code read
    // stats.by_status.open, which is keyed by granular status and has no
    // aggregate "open" bucket — it was effectively undefined.)
    const open = items.length;
    const highPriority = items.filter((it) => it.priority_band === 'high').length;
    const unassigned = items.filter((it) => !it.assigned_to_user_id).length;
    const closedTodayRaw = (stats as { closed_today?: number })?.closed_today;
    const closedToday = typeof closedTodayRaw === 'number' ? closedTodayRaw : '—';
    return {
      open,
      highPriority,
      unassigned,
      closedToday,
      categoryCount: new Set(items.map((it) => it.queue_item_type)).size,
    };
  }, [items, stats]);

  const goToDetail = useCallback(
    (id: string) => navigate(buildRoute('adminReviewQueueDetail', { id })),
    [navigate],
  );

  const columns = useMemo<DataTableColumn<QueueItem>[]>(
    () => [
      {
        id: 'id',
        header: 'ID',
        defaultWidth: 85,
        minWidth: 70,
        sortValue: (it) => it.id ?? '',
        cell: (it) => <span className="font-mono text-[11.5px] text-slate-500">{shortId(it.id)}</span>,
      },
      {
        id: 'type',
        header: 'Type',
        defaultWidth: 150,
        minWidth: 110,
        sortValue: (it) => QUEUE_TYPE_LABELS[it.queue_item_type] ?? it.queue_item_type ?? '',
        cell: (it) => (
          <Pill className="bg-slate-100 text-slate-700 ring-slate-200">
            {QUEUE_TYPE_LABELS[it.queue_item_type] ?? it.queue_item_type}
          </Pill>
        ),
      },
      {
        id: 'title',
        header: 'Item',
        defaultWidth: 280,
        minWidth: 180,
        sortValue: (it) => it.title?.toLowerCase() ?? '',
        cell: (it) => <span className="text-slate-900">{it.title}</span>,
      },
      {
        id: 'tenant',
        header: 'Tenant',
        defaultWidth: 140,
        minWidth: 100,
        sortValue: (it) => (it.country_code ? it.country_code.toUpperCase() : 'Internal'),
        cell: (it) => {
          // No tenant field on QueueItem; surface country_code or "Internal".
          const label = it.country_code ? it.country_code.toUpperCase() : 'Internal';
          return <span className="text-slate-700">{label}</span>;
        },
      },
      {
        id: 'age',
        header: 'Age',
        defaultWidth: 70,
        minWidth: 50,
        sortValue: (it) => (it.created_at ? Date.parse(it.created_at) : 0),
        cell: (it) => <span className="text-[12px] text-slate-500">{relativeAge(it.created_at)}</span>,
      },
      {
        id: 'priority',
        header: 'Priority',
        defaultWidth: 100,
        minWidth: 80,
        sortValue: (it) => PRIORITY_RANK[it.priority_band] ?? 0,
        cell: (it) => (
          <Pill className={PRIORITY_PILL[it.priority_band] ?? PRIORITY_PILL.low}>
            {it.priority_band || 'low'}
          </Pill>
        ),
      },
      {
        id: 'owner',
        header: 'Owner',
        defaultWidth: 150,
        minWidth: 110,
        sortValue: (it) => (it.assigned_to_user_id ? ownerInitials(it.assigned_to_user_id) : ''),
        cell: (it) => {
          if (!it.assigned_to_user_id) {
            return <span className="text-[12px] italic text-slate-400">Unassigned</span>;
          }
          return (
            <div className="flex items-center gap-1.5">
              <span className={`inline-flex h-5 w-5 items-center justify-center rounded text-[10px] font-semibold ${ownerTone(it.assigned_to_user_id)}`}>
                {ownerInitials(it.assigned_to_user_id)}
              </span>
              <span className="truncate text-[12px] text-slate-700">{ownerInitials(it.assigned_to_user_id)}</span>
            </div>
          );
        },
      },
      {
        id: 'actions',
        header: () => <span className="sr-only">Actions</span>,
        defaultWidth: 80,
        minWidth: 80,
        maxWidth: 80,
        unsortable: true,
        unmovable: true,
        cellClassName: 'text-right',
        cell: (it) => (
          <Button unstyled
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              goToDetail(it.id);
            }}
            className="rounded border border-slate-300 px-2.5 py-1 text-[11.5px] font-medium text-slate-700 hover:bg-slate-50"
          >
            Open
          </Button>
        ),
      },
    ],
    [goToDetail],
  );

  return (
    <AdminLayout>
      <div className="px-6 py-6">
        {/* Header */}
        <div className="mb-5">
          <div className="text-[11px] font-medium uppercase tracking-widest text-slate-400">
            ReloPass · /admin/review-queue
          </div>
          <div className="mt-1.5 flex flex-wrap items-baseline gap-3">
            <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Review queue</h1>
            {/* Filters / Assign-batch / New-item controls were unwired stubs (alert-only);
                removed until the handlers exist rather than ship dead buttons. */}
          </div>
          <p className="mt-1 max-w-3xl text-[13px] text-slate-500">
            Vendor approvals, policy exceptions, source refreshes, and tenant onboarding all funnel here.
            Claim or assign before the SLA timer runs out.
          </p>
        </div>

        {/* KPI strip — 4 cards from the mock */}
        <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Kpi label="Open" value={kpis.open} sub={`across ${kpis.categoryCount || 0} categories`} />
          <Kpi label="High priority" value={kpis.highPriority} sub="SLA breach risk" tone="warning" />
          <Kpi label="Unassigned" value={kpis.unassigned} sub="awaiting an owner" tone="accent" />
          <Kpi label="Closed today" value={kpis.closedToday} tone="default" />
        </div>

        {/* Soft banner instead of red error when backend isn't available */}
        {backendUnavailable && (
          <div className="mb-4 flex items-start justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <span>
              The review queue isn&rsquo;t available in this environment yet. It will populate once its
              data source is connected.
            </span>
            <Button unstyled
              type="button"
              onClick={() => void load()}
              className="text-amber-700 hover:underline"
            >
              Retry
            </Button>
          </div>
        )}

        <DataTable
          tableId="admin.review-queue"
          columns={columns}
          rows={items}
          rowKey={(it) => it.id}
          onRowClick={(it) => goToDetail(it.id)}
          ariaLabel="Review queue"
          emptyState={
            loading
              ? 'Loading review items…'
              : backendUnavailable
                ? 'Cannot load queue items — see banner above.'
                : 'No open review items.'
          }
          footerSlot={
            <div className="flex items-center justify-between px-4 py-2 text-[11.5px] text-slate-500">
              <span>
                {items.length} item{items.length === 1 ? '' : 's'}
                {kpis.categoryCount > 0 ? ` · ${kpis.categoryCount} categor${kpis.categoryCount === 1 ? 'y' : 'ies'}` : ''}
              </span>
              <ResetColumnsLink tableId="admin.review-queue" />
            </div>
          }
        />
      </div>
    </AdminLayout>
  );
}

export default AdminReviewQueueV2Page;
