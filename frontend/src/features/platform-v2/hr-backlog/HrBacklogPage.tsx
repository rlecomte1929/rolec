import { useCallback, useEffect, useMemo, useState } from 'react';
import { Button } from '../../../components/antigravity/Button';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../../../components/AppShell';
import { hrAPI, type HrBacklogTask } from '../../../api/client';
import { DataTable, ResetColumnsLink, type DataTableColumn } from '../data-table';
import { statusLabel } from '../../../lib/statusLabel';

/**
 * HR Backlog — pending employee tasks across the HR user's company.
 *
 * Backend: GET /api/hr/backlog → role-gated to HR/ADMIN, scoped server-side
 * to the caller's company_id (no global state, no impersonation tricks).
 *
 * Distinct from the admin Review Queue: admins see cross-tenant moderation
 * items (vendor approvals, policy exceptions); HR sees their own company's
 * pending employee work. See DECISIONS.md for the architectural split.
 *
 * Flag-gated behind platform_v2_hr_backlog; mounted at /hr/backlog (sibling
 * route exists at /hr/backlog-v2 if we ever V2Gate an older surface).
 */

// ── Visual primitives ──────────────────────────────────────────────────────

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
  tone?: 'default' | 'success' | 'warning' | 'accent' | 'danger';
}

function Kpi({ label, value, sub, tone = 'default' }: KpiProps) {
  const valueColor: Record<NonNullable<KpiProps['tone']>, string> = {
    default: 'text-slate-900',
    success: 'text-emerald-700',
    warning: 'text-rose-700',
    accent: 'text-accent-700',
    danger: 'text-rose-700',
  };
  const dot: Record<NonNullable<KpiProps['tone']>, string> = {
    default: 'bg-slate-200',
    success: 'bg-emerald-500',
    warning: 'bg-rose-500',
    accent: 'bg-accent-500',
    danger: 'bg-rose-500',
  };
  return (
    <div className="relative rounded-lg border border-slate-200 bg-white px-4 py-3 transition-colors hover:border-slate-300">
      <span className={`absolute right-3 top-3 block h-1.5 w-1.5 rounded-full ${dot[tone]}`} aria-hidden />
      <div className="truncate text-[10px] font-semibold uppercase tracking-widest text-slate-500">{label}</div>
      <div className={`mt-1 text-[28px] font-semibold leading-none tracking-tight tabular-nums ${valueColor[tone]}`}>
        {value}
      </div>
      <div className="mt-1.5 truncate text-[11px] text-slate-500">{sub}</div>
    </div>
  );
}

const STATUS_PILL: Record<string, string> = {
  pending: 'bg-amber-50 text-amber-700 ring-amber-200',
  revision_requested: 'bg-rose-50 text-rose-700 ring-rose-200',
};

// STATUS_LABEL removed — replaced by the shared statusLabel() utility (AUDIT-A5)

const OWNER_TONES = ['bg-accent-100 text-accent-700', 'bg-emerald-100 text-emerald-700', 'bg-amber-100 text-amber-700', 'bg-sky-100 text-sky-700', 'bg-rose-100 text-rose-700', 'bg-accent-100 text-accent-700'];

// ── Helpers ────────────────────────────────────────────────────────────────

function shortId(uuid: string | null | undefined): string {
  if (!uuid) return '—';
  return uuid.replace(/-/g, '').slice(0, 6);
}

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

function formatDueDate(iso: string | null | undefined): { label: string; overdue: boolean } {
  if (!iso) return { label: '—', overdue: false };
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return { label: '—', overdue: false };
  const overdue = d.getTime() < Date.now();
  return {
    label: d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' }),
    overdue,
  };
}

function ownerTone(id: string): string {
  let hash = 5381;
  for (let i = 0; i < id.length; i++) hash = ((hash << 5) + hash + id.charCodeAt(i)) | 0;
  return OWNER_TONES[Math.abs(hash) % OWNER_TONES.length]!;
}

function ownerInitials(name: string | null | undefined, fallbackId: string | null | undefined): string {
  if (name && name.trim()) {
    return name.trim().split(/\s+/).slice(0, 2).map((p) => p[0]).join('').toUpperCase();
  }
  if (fallbackId) return fallbackId.replace(/-/g, '').slice(0, 2).toUpperCase();
  return '??';
}

// ── Page ──────────────────────────────────────────────────────────────────

export function HrBacklogPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<HrBacklogTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasCompany, setHasCompany] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await hrAPI.getBacklog();
      setItems(res.items ?? []);
      setHasCompany(res.has_company);
    } catch (e) {
      const err = e as { response?: { status?: number; data?: { detail?: string } } };
      const detail = err?.response?.data?.detail;
      const status = err?.response?.status;
      setItems([]);
      setError(detail ?? (status ? `Server returned ${status}` : 'Could not load backlog.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // KPIs computed from the items array.
  const kpis = useMemo(() => {
    const overdue = items.filter((t) => {
      if (!t.due_date) return false;
      const d = new Date(t.due_date);
      return !Number.isNaN(d.getTime()) && d.getTime() < Date.now();
    }).length;
    const revisions = items.filter((t) => t.status === 'revision_requested').length;
    const employees = new Set(items.map((t) => t.employee_id).filter(Boolean)).size;
    return {
      total: items.length,
      revisions,
      overdue,
      employees,
    };
  }, [items]);

  const columns = useMemo<DataTableColumn<HrBacklogTask>[]>(
    () => [
      {
        id: 'id',
        header: 'ID',
        defaultWidth: 90,
        minWidth: 70,
        sortValue: (t) => t.id ?? '',
        cell: (t) => <span className="font-mono text-[11.5px] text-slate-500">{shortId(t.id)}</span>,
      },
      {
        id: 'title',
        header: 'Task',
        defaultWidth: 300,
        minWidth: 180,
        sortValue: (t) => t.title?.toLowerCase() ?? '',
        cell: (t) => (
          <div>
            <div className="font-medium text-slate-900">{t.title}</div>
            {t.description && (
              <div className="mt-0.5 truncate text-[11.5px] text-slate-500 max-w-[28rem]">
                {t.description}
              </div>
            )}
          </div>
        ),
      },
      {
        id: 'employee',
        header: 'Employee',
        defaultWidth: 200,
        minWidth: 140,
        sortValue: (t) => (t.employee_name?.trim() || t.employee_email?.trim() || '').toLowerCase(),
        cell: (t) => {
          const name = t.employee_name?.trim() || null;
          const email = t.employee_email?.trim() || null;
          const ident = t.employee_id || '';
          return (
            <div className="flex items-center gap-2">
              <span className={`inline-flex h-6 w-6 items-center justify-center rounded text-[10px] font-semibold ${ownerTone(ident || 'x')}`}>
                {ownerInitials(name, ident)}
              </span>
              <div className="min-w-0">
                <div className="truncate text-[12.5px] text-slate-700">
                  {name ?? shortId(ident) ?? '—'}
                </div>
                {email && (
                  <div className="truncate text-[11px] text-slate-400 max-w-[14rem]">{email}</div>
                )}
              </div>
            </div>
          );
        },
      },
      {
        id: 'type',
        header: 'Type',
        defaultWidth: 130,
        minWidth: 100,
        sortValue: (t) => t.type ?? '',
        cell: (t) => (
          <span className="text-[12.5px] text-slate-600">{t.type ?? '—'}</span>
        ),
      },
      {
        id: 'status',
        header: 'Status',
        defaultWidth: 140,
        minWidth: 110,
        sortValue: (t) => t.status ?? '',
        cell: (t) => (
          <Pill className={STATUS_PILL[t.status] ?? STATUS_PILL.pending}>
            {statusLabel(t.status)}
          </Pill>
        ),
      },
      {
        id: 'due',
        header: 'Due',
        defaultWidth: 130,
        minWidth: 100,
        sortValue: (t) => (t.due_date ? Date.parse(t.due_date) : Number.MAX_SAFE_INTEGER),
        cell: (t) => {
          const { label, overdue } = formatDueDate(t.due_date);
          return (
            <span className={overdue ? 'text-rose-600 font-medium' : 'text-slate-700'}>
              {label}
              {overdue && <span className="ml-1 text-[10px] uppercase">overdue</span>}
            </span>
          );
        },
      },
      {
        id: 'age',
        header: 'Age',
        defaultWidth: 70,
        minWidth: 50,
        sortValue: (t) => (t.created_at ? Date.parse(t.created_at) : 0),
        cell: (t) => <span className="text-[12px] text-slate-500">{relativeAge(t.created_at)}</span>,
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
        cell: (t) => (
          <Button unstyled
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              if (t.case_id) {
                // Drill into the HR case summary, which is the canonical place to act on a task.
                navigate(`/hr/cases/${t.case_id}`);
              }
            }}
            disabled={!t.case_id}
            className="rounded border border-slate-300 px-2.5 py-1 text-[11.5px] font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            title={t.case_id ? 'Open the case to act on this task' : 'No case linked'}
          >
            Open
          </Button>
        ),
      },
    ],
    [navigate],
  );

  return (
    <AppShell>
      <div className="px-6 py-6">
        {/* Header */}
        <div className="mb-5">
          <div className="text-[11px] font-medium uppercase tracking-widest text-slate-400">
            ReloPass · /hr/backlog
          </div>
          <div className="mt-1.5 flex flex-wrap items-baseline gap-3">
            <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Employee backlog</h1>
            <Pill className="bg-accent-50 text-accent-700 ring-accent-200">v2 preview</Pill>
            <div className="ml-auto flex items-center gap-2">
              <Button unstyled
                type="button"
                onClick={() => void load()}
                disabled={loading}
                className="text-xs font-medium text-accent-600 underline-offset-2 hover:underline disabled:opacity-50"
              >
                {loading ? 'Refreshing…' : 'Refresh'}
              </Button>
            </div>
          </div>
          <p className="mt-1 max-w-3xl text-[13px] text-slate-500">
            Everything your employees still owe action on — passport scans, form submissions, signed
            documents. Pending and revision-requested tasks for everyone in your company, one list.
          </p>
        </div>

        {/* KPI strip */}
        <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Kpi label="Open tasks" value={kpis.total} sub={`across ${kpis.employees} employee${kpis.employees === 1 ? '' : 's'}`} />
          <Kpi label="Needs revision" value={kpis.revisions} sub="HR flagged" tone="warning" />
          <Kpi label="Overdue" value={kpis.overdue} sub="past due date" tone="danger" />
          <Kpi label="Employees with work" value={kpis.employees} sub="active in backlog" tone="accent" />
        </div>

        {!hasCompany && (
          <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Your HR profile isn't linked to a company yet — there's nothing to show. Ask your admin
            to link your account, then refresh.
          </div>
        )}

        {error && (
          <div className="mb-4 flex items-start justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <span>{error}</span>
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
          tableId="hr.backlog"
          columns={columns}
          rows={items}
          rowKey={(t) => t.id}
          ariaLabel="Employee backlog"
          emptyState={
            loading
              ? 'Loading backlog…'
              : !hasCompany
                ? 'No company linked.'
                : 'No pending tasks — every employee is up to date.'
          }
          footerSlot={
            <div className="flex items-center justify-between px-4 py-2 text-[11.5px] text-slate-500">
              <span>
                {items.length} task{items.length === 1 ? '' : 's'}
                {kpis.overdue > 0 ? ` · ${kpis.overdue} overdue` : ''}
              </span>
              <ResetColumnsLink tableId="hr.backlog" />
            </div>
          }
        />
      </div>
    </AppShell>
  );
}

export default HrBacklogPage;
