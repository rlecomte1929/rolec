import { useMemo, useState } from 'react';
import { adminAPI } from '../../../api/client';
import type {
  CompanyV2,
  CompanyV2PlanTier,
  CompanyV2Status,
  CompanyV2Tone,
} from './adapter';
import { CompanyFormModal } from './CompanyFormModal';
import { RowActionMenu } from './RowActionMenu';

// ── Visual helpers ──────────────────────────────────────────────────────────

// Gradient + ring tones for the company logo chip — richer than flat bg.
const TONE_LOGO: Record<CompanyV2Tone, string> = {
  a: 'bg-gradient-to-br from-indigo-500 to-indigo-700 text-white',
  b: 'bg-gradient-to-br from-emerald-500 to-emerald-700 text-white',
  c: 'bg-gradient-to-br from-amber-500 to-amber-700 text-white',
  d: 'bg-gradient-to-br from-sky-500 to-sky-700 text-white',
  e: 'bg-gradient-to-br from-rose-500 to-rose-700 text-white',
  f: 'bg-gradient-to-br from-violet-500 to-violet-700 text-white',
};

const PLAN_PILL: Record<CompanyV2PlanTier, string> = {
  premium: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  medium:  'bg-amber-50  text-amber-700  ring-amber-200',
  low:     'bg-slate-100 text-slate-600  ring-slate-200',
};

const STATUS_PILL: Record<CompanyV2Status, string> = {
  active:   'bg-emerald-50 text-emerald-700 ring-emerald-200',
  inactive: 'bg-amber-50  text-amber-700  ring-amber-200',
  archived: 'bg-slate-100 text-slate-500  ring-slate-200',
};

const STATUS_DOT: Record<CompanyV2Status, string> = {
  active:   'bg-emerald-500',
  inactive: 'bg-amber-500',
  archived: 'bg-slate-400',
};

function Pill({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${className}`}
    >
      {children}
    </span>
  );
}

function logoInitials(name: string): string {
  return name
    .split(/[\s&]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]!)
    .join('')
    .toUpperCase();
}

function relativeDate(iso: string | null): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (Number.isNaN(days)) return '—';
  if (days === 0) return 'Today';
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

// ── Sub-components ──────────────────────────────────────────────────────────

interface KpiProps {
  label: string;
  value: string | number;
  sub: string;
  tone?: 'default' | 'success' | 'warning' | 'accent' | 'teal';
}

function Kpi({ label, value, sub, tone = 'default' }: KpiProps) {
  const card: Record<NonNullable<KpiProps['tone']>, string> = {
    default: 'border-slate-200 bg-white',
    success: 'border-slate-200 bg-white',
    warning: 'border-slate-200 bg-white',
    accent: 'border-slate-200 bg-white',
    teal: 'border-slate-200 bg-white',
  };
  const valueClass: Record<NonNullable<KpiProps['tone']>, string> = {
    default: 'text-slate-900',
    success: 'text-emerald-700',
    warning: 'text-amber-700',
    accent: 'text-indigo-700',
    teal: 'text-teal-700',
  };
  const dot: Record<NonNullable<KpiProps['tone']>, string> = {
    default: 'bg-slate-200',
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    accent: 'bg-indigo-500',
    teal: 'bg-teal-500',
  };
  return (
    <div className={`relative rounded-lg border ${card[tone]} px-3 py-2.5 transition-colors hover:border-slate-300`}>
      <span className={`absolute right-2.5 top-2.5 block h-1.5 w-1.5 rounded-full ${dot[tone]}`} aria-hidden />
      <div className="truncate text-[10px] font-semibold uppercase tracking-widest text-slate-500">
        {label}
      </div>
      <div className={`mt-1 text-[22px] font-semibold leading-none tracking-tight tabular-nums ${valueClass[tone]}`}>
        {value}
      </div>
      <div className="mt-1 truncate text-[10.5px] text-slate-500">{sub}</div>
    </div>
  );
}

interface CompanyLogoProps {
  name: string;
  tone: CompanyV2Tone;
  size?: 'sm' | 'lg';
}

function CompanyLogo({ name, tone, size = 'sm' }: CompanyLogoProps) {
  const sizeClass = size === 'lg' ? 'h-11 w-11 text-[13px]' : 'h-7 w-7 text-[10.5px]';
  return (
    <div
      className={`flex shrink-0 items-center justify-center rounded-md font-semibold shadow-sm ${TONE_LOGO[tone]} ${sizeClass}`}
      aria-hidden
    >
      {logoInitials(name)}
    </div>
  );
}

interface SeatCellProps {
  count: number;
  limit: number | null;
}

function SeatCell({ count, limit }: SeatCellProps) {
  if (limit == null) {
    return (
      <div className="text-[12.5px] tabular-nums text-slate-700">
        {count} <span className="text-slate-400">/ —</span>
      </div>
    );
  }
  const pct = limit > 0 ? Math.min(100, Math.round((count / limit) * 100)) : 0;
  const barColor =
    pct > 90 ? 'bg-rose-500' : pct > 75 ? 'bg-amber-500' : 'bg-emerald-500';
  return (
    <div className="min-w-[6rem] space-y-1">
      <div className="text-[12.5px] tabular-nums text-slate-700">
        {count} <span className="text-slate-400">/ {limit}</span>
      </div>
      <div className="h-1 w-full overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// ── Detail panel ────────────────────────────────────────────────────────────

interface DetailPanelProps {
  company: CompanyV2;
  onClose: () => void;
}

function DetailPanel({ company, onClose }: DetailPanelProps) {
  return (
    <>
      <div
        className="fixed inset-0 z-30 bg-slate-900/30"
        onClick={onClose}
        aria-hidden
      />
      <aside
        role="dialog"
        aria-label={`${company.name} detail`}
        className="fixed right-0 top-0 z-40 h-full w-full max-w-md overflow-y-auto bg-white shadow-2xl"
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-6 py-4">
          <div className="flex items-center gap-3">
            <CompanyLogo name={company.name} tone={company.tone} size="lg" />
            <div>
              <div className="text-lg font-semibold text-slate-900">{company.name}</div>
              <div className="text-xs text-slate-500">{company.legal_name}</div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            ✕
          </button>
        </div>

        <div className="space-y-4 px-6 py-5 text-sm">
          <Section label="Status">
            <Pill className={STATUS_PILL[company.status]}>
              <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[company.status]}`} />
              {company.status}
            </Pill>
            <span className="ml-2 inline-block">
              <Pill className={PLAN_PILL[company.plan_tier]}>{company.plan_tier} plan</Pill>
            </span>
          </Section>

          <Section label="Location">
            <div className="text-slate-700">{company.country ?? '—'}</div>
            {company.address && (
              <div className="text-xs text-slate-500">{company.address}</div>
            )}
          </Section>

          <Section label="Size">
            <div className="text-slate-700">{company.size_band ?? '—'}</div>
          </Section>

          <Section label="HR seats">
            <SeatCell count={company.hr_users_count} limit={company.hr_seat_limit} />
          </Section>

          <Section label="Employee seats">
            <SeatCell count={company.employee_count} limit={company.employee_seat_limit} />
          </Section>

          <Section label="Open cases">
            <div className="tabular-nums text-slate-700">{company.assignments_count}</div>
          </Section>

          <Section label="Primary contact">
            <div className="text-slate-700">{company.primary_contact_name ?? '—'}</div>
            {company.hr_contact && (
              <div className="text-xs text-slate-500">{company.hr_contact}</div>
            )}
            {company.support_email && (
              <div className="text-xs text-slate-500">{company.support_email}</div>
            )}
            {company.phone && (
              <div className="text-xs text-slate-500">{company.phone}</div>
            )}
          </Section>

          {(company.has_registry_issue || company.orphan_row_count > 0) && (
            <Section label="Data quality">
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                {company.has_registry_issue && (
                  <div>⚠ Missing from companies registry — users/cases reference this id but no company row exists.</div>
                )}
                {company.orphan_row_count > 0 && (
                  <div>⚠ {company.orphan_row_count} orphan row(s) reference this company.</div>
                )}
              </div>
            </Section>
          )}

          <Section label="Timestamps">
            <div className="text-xs text-slate-500">Created {relativeDate(company.created_at)}</div>
            {company.updated_at && (
              <div className="text-xs text-slate-500">Updated {relativeDate(company.updated_at)}</div>
            )}
          </Section>
        </div>
      </aside>
    </>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </div>
      <div className="leading-snug">{children}</div>
    </div>
  );
}

// ── Filter bar ──────────────────────────────────────────────────────────────

interface FilterState {
  search: string;
  status: '' | CompanyV2Status;
  plan: '' | CompanyV2PlanTier;
  country: string;
  sizeBand: string;
  issuesOnly: boolean;
}

const EMPTY_FILTERS: FilterState = {
  search: '',
  status: '',
  plan: '',
  country: '',
  sizeBand: '',
  issuesOnly: false,
};

// ── Main component ─────────────────────────────────────────────────────────

export interface CompaniesV2Props {
  companies: CompanyV2[];
  loading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
}

export function CompaniesV2({ companies, loading = false, error = null, onRefresh }: CompaniesV2Props) {
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editTarget, setEditTarget] = useState<CompanyV2 | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function handleArchive(c: CompanyV2) {
    if (!window.confirm(`Archive "${c.name}"? It will be hidden from active lists. Reversible.`)) return;
    setBusyId(c.id);
    setActionError(null);
    try {
      await adminAPI.archiveCompany(c.id);
      onRefresh?.();
    } catch (e) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (e as Error)?.message ??
        'Failed to archive company';
      setActionError(detail);
    } finally {
      setBusyId(null);
    }
  }

  function handleDelete(_c: CompanyV2) {
    // Delete with type-name confirmation lands in C3 of this work block.
    setActionError('Delete is not wired up yet — coming in C3.');
  }

  const countries = useMemo(
    () =>
      [...new Set(companies.map((c) => c.country).filter((x): x is string => Boolean(x)))].sort(),
    [companies],
  );
  const sizes = useMemo(
    () =>
      [...new Set(companies.map((c) => c.size_band).filter((x): x is string => Boolean(x)))].sort(),
    [companies],
  );

  const kpis = useMemo(() => {
    const sum = (k: keyof Pick<CompanyV2, 'hr_users_count' | 'employee_count' | 'assignments_count'>) =>
      companies.reduce((acc, c) => acc + c[k], 0);
    return {
      total: companies.length,
      active: companies.filter((c) => c.status === 'active').length,
      inactive: companies.filter((c) => c.status === 'inactive').length,
      archived: companies.filter((c) => c.status === 'archived').length,
      premium: companies.filter((c) => c.plan_tier === 'premium').length,
      hrUsers: sum('hr_users_count'),
      employees: sum('employee_count'),
      cases: sum('assignments_count'),
      issues: companies.filter((c) => c.has_registry_issue || c.orphan_row_count > 0).length,
    };
  }, [companies]);

  const filtered = useMemo(() => {
    const q = filters.search.trim().toLowerCase();
    return companies.filter((c) => {
      if (q) {
        const hay = [c.name, c.legal_name, c.primary_contact_name, c.hr_contact, c.support_email]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (filters.status && c.status !== filters.status) return false;
      if (filters.plan && c.plan_tier !== filters.plan) return false;
      if (filters.country && c.country !== filters.country) return false;
      if (filters.sizeBand && c.size_band !== filters.sizeBand) return false;
      if (filters.issuesOnly && !(c.has_registry_issue || c.orphan_row_count > 0)) return false;
      return true;
    });
  }, [companies, filters]);

  const anyFilter =
    filters.search !== '' ||
    filters.status !== '' ||
    filters.plan !== '' ||
    filters.country !== '' ||
    filters.sizeBand !== '' ||
    filters.issuesOnly;

  const activeCompany = activeId ? companies.find((c) => c.id === activeId) ?? null : null;

  return (
    <div className="px-6 py-6 mx-auto max-w-[1400px]">
      {/* Header */}
      <div className="mb-5">
        <div className="text-[11px] font-medium uppercase tracking-widest text-slate-400">
          ReloPass · /admin/companies/overview
        </div>
        <div className="mt-1.5 flex items-baseline gap-3">
          <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Companies</h1>
          <Pill className="bg-indigo-50 text-indigo-700 ring-indigo-200">v2 preview</Pill>
          <div className="ml-auto flex items-center gap-3">
            {onRefresh && (
              <button
                type="button"
                onClick={onRefresh}
                className="text-xs font-medium text-indigo-600 underline-offset-2 hover:underline disabled:opacity-50"
                disabled={loading}
              >
                {loading ? 'Refreshing…' : 'Refresh'}
              </button>
            )}
            <button
              type="button"
              onClick={() => setShowAddModal(true)}
              className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800"
            >
              + Add tenant
            </button>
          </div>
        </div>
        <p className="mt-1 max-w-3xl text-[13px] text-slate-500">
          Every tenant on the platform — people, activity, policy health and data quality, in one view. Click any row to inspect.
        </p>
      </div>

      {/* KPI strip */}
      <div className="mb-5 grid grid-cols-3 gap-3 md:grid-cols-5 lg:grid-cols-9">
        <Kpi label="Total" value={kpis.total} sub="all tenants" />
        <Kpi label="Active" value={kpis.active} sub="live" tone="success" />
        <Kpi label="Inactive" value={kpis.inactive} sub="paused" tone="warning" />
        <Kpi label="Archived" value={kpis.archived} sub="soft-deleted" />
        <Kpi label="Premium" value={kpis.premium} sub="top tier" tone="accent" />
        <Kpi label="HR users" value={kpis.hrUsers} sub="across tenants" />
        <Kpi label="Employees" value={kpis.employees.toLocaleString()} sub="across tenants" />
        <Kpi label="Open cases" value={kpis.cases} sub="active mobility" tone="accent" />
        <Kpi
          label="Data issues"
          value={kpis.issues}
          sub="orphan / registry"
          tone={kpis.issues > 0 ? 'warning' : 'default'}
        />
      </div>

      {/* Filter bar */}
      <div className="sticky top-2 z-10 mb-4 rounded-xl border border-slate-200 bg-white/70 px-3 py-2.5 backdrop-blur-md backdrop-saturate-150">
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="search"
            placeholder="Search by name, contact, email…"
            value={filters.search}
            onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
            className="min-w-[16rem] flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Search companies"
          />
          <select
            value={filters.status}
            onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value as FilterState['status'] }))}
            aria-label="Filter by status"
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="archived">Archived</option>
          </select>
          <select
            value={filters.plan}
            onChange={(e) => setFilters((f) => ({ ...f, plan: e.target.value as FilterState['plan'] }))}
            aria-label="Filter by plan"
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All plans</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="premium">Premium</option>
          </select>
          <select
            value={filters.country}
            onChange={(e) => setFilters((f) => ({ ...f, country: e.target.value }))}
            aria-label="Filter by country"
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All countries</option>
            {countries.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select
            value={filters.sizeBand}
            onChange={(e) => setFilters((f) => ({ ...f, sizeBand: e.target.value }))}
            aria-label="Filter by size"
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All sizes</option>
            {sizes.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-1.5 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={filters.issuesOnly}
              onChange={(e) => setFilters((f) => ({ ...f, issuesOnly: e.target.checked }))}
              className="h-4 w-4 rounded border-slate-300"
            />
            Issues only
          </label>
          {anyFilter && (
            <button
              type="button"
              onClick={() => setFilters(EMPTY_FILTERS)}
              className="text-xs text-slate-500 underline-offset-2 hover:underline"
            >
              Clear filters
            </button>
          )}
          <div className="ml-auto text-[11.5px] font-medium text-slate-500 tabular-nums">
            {filtered.length} of {companies.length}
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {actionError && (
        <div className="mb-4 flex items-start justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <span>{actionError}</span>
          <button
            type="button"
            onClick={() => setActionError(null)}
            className="text-amber-700 hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full text-[13px]">
            <thead className="bg-slate-50/80 text-left text-[10.5px] font-semibold uppercase tracking-widest text-slate-500">
              <tr>
                <Th className="pl-4">Company</Th>
                <Th>Plan</Th>
                <Th>Status</Th>
                <Th>Country</Th>
                <Th>Size</Th>
                <Th>HR seats</Th>
                <Th>Employee seats</Th>
                <Th className="text-right">Cases</Th>
                <Th>Contact</Th>
                <Th>Created</Th>
                <Th className="pr-4 w-12 text-right" aria-label="Actions"><span className="sr-only">Actions</span></Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && (
                <tr>
                  <td colSpan={11} className="px-4 py-8 text-center text-sm text-slate-400">
                    Loading companies…
                  </td>
                </tr>
              )}
              {!loading && filtered.length === 0 && (
                <tr>
                  <td colSpan={11} className="px-4 py-8 text-center text-sm text-slate-400">
                    {anyFilter ? 'No companies match your filters.' : 'No companies yet.'}
                  </td>
                </tr>
              )}
              {!loading &&
                filtered.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => setActiveId(c.id)}
                    className={`cursor-pointer hover:bg-slate-50 ${
                      activeId === c.id ? 'bg-indigo-50' : ''
                    }`}
                  >
                    <td className="pl-4 py-2.5">
                      <div className="flex items-center gap-2.5">
                        <CompanyLogo name={c.name} tone={c.tone} />
                        <div className="min-w-0">
                          <div className="font-medium text-slate-900 truncate">{c.name}</div>
                          {c.legal_name && c.legal_name !== c.name && (
                            <div className="text-xs text-slate-500 truncate">{c.legal_name}</div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="py-2.5">
                      <Pill className={PLAN_PILL[c.plan_tier]}>{c.plan_tier}</Pill>
                    </td>
                    <td className="py-2.5">
                      <Pill className={STATUS_PILL[c.status]}>
                        <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[c.status]}`} />
                        {c.status}
                      </Pill>
                    </td>
                    <td className="py-2.5 text-slate-700">{c.country ?? '—'}</td>
                    <td className="py-2.5 text-slate-700">{c.size_band ?? '—'}</td>
                    <td className="py-2.5">
                      <SeatCell count={c.hr_users_count} limit={c.hr_seat_limit} />
                    </td>
                    <td className="py-2.5">
                      <SeatCell count={c.employee_count} limit={c.employee_seat_limit} />
                    </td>
                    <td className="py-2.5 text-right font-semibold tabular-nums text-slate-700">
                      {c.assignments_count}
                    </td>
                    <td className="py-2.5">
                      <div className="text-slate-700">{c.primary_contact_name ?? '—'}</div>
                      {c.hr_contact && (
                        <div className="text-xs text-slate-500 truncate max-w-[14rem]">{c.hr_contact}</div>
                      )}
                    </td>
                    <td className="py-2.5 text-xs text-slate-500">
                      {relativeDate(c.created_at)}
                    </td>
                    <td className="pr-4 py-2.5 text-right">
                      {busyId === c.id ? (
                        <span className="text-[11px] text-slate-400">…</span>
                      ) : (
                        <RowActionMenu
                          onEdit={() => setEditTarget(c)}
                          onArchive={() => void handleArchive(c)}
                          onDelete={() => handleDelete(c)}
                          disableArchive={c.status === 'archived'}
                          ariaLabel={`Open actions for ${c.name}`}
                        />
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>

      {activeCompany && <DetailPanel company={activeCompany} onClose={() => setActiveId(null)} />}

      {showAddModal && (
        <CompanyFormModal
          mode="create"
          onClose={() => setShowAddModal(false)}
          onSaved={() => {
            setShowAddModal(false);
            onRefresh?.();
          }}
        />
      )}

      {editTarget && (
        <CompanyFormModal
          mode="edit"
          initial={editTarget}
          onClose={() => setEditTarget(null)}
          onSaved={() => {
            setEditTarget(null);
            onRefresh?.();
          }}
        />
      )}
    </div>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return <th className={`py-2.5 ${className ?? 'px-2'} font-semibold`}>{children}</th>;
}

export default CompaniesV2;
