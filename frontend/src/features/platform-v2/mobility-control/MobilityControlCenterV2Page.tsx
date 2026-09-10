import { useCallback, useMemo, useState } from 'react';
import type * as React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { PlaneTakeoff } from 'lucide-react';
import { Button } from '../../../components/antigravity/Button';
import { ConversationalEmptyState, TableScroll } from '../../../components/antigravity';
import { buildRoute } from '../../../navigation/routes';
import { AppShell } from '../../../components/AppShell';
import { Breadcrumb } from '../../../components/Breadcrumb';
import api, { hrAPI } from '../../../api/client';
import type { CommandCenterCaseRow } from '../../../api/client';
import { displayNameOrEmail } from '../../../utils/caseDisplay';
import { getCaseStatusLabel } from '../../../utils/caseStatusLabel';
import { DataTable, ResetColumnsLink, type DataTableColumn } from '../data-table';
import { useHrCompanyContext } from '../../../contexts/HrCompanyContext';
import { fetchExecSummary } from '../../../api/nlg';
import { HrCaseHealthPanel } from '../../../components/case/HrCaseHealthPanel';
import { getCountryName } from '../../../utils/countries';

/**
 * Mobility Control Center — V2.
 *
 * Mock-aligned redesign of the legacy /hr/command-center "Dashboard" page.
 * Data still comes from the existing endpoints:
 *   - GET /api/hr/command-center/kpis
 *   - GET /api/hr/command-center/cases
 *   - GET /api/exception-requests?status=pending  (Pending approvals sidebar)
 *
 * Surfaces are derived client-side from the case list:
 *   - Corridor mix:    aggregate by (originCountry → destCountry)
 *   - Risk feed:       cases with riskStatus != green, sorted by recency
 *   - Pending approvals: from /api/exception-requests
 *
 * The mock includes Visa / Household columns which are not yet first-class
 * fields on case_assignments — they fall back to derived placeholders
 * ("—") so the layout matches without inventing data.
 */

type ApprovalRow = {
  id: string;
  category: string;
  reason?: string;
  status?: string;
  case_id?: string;
  requested_amount?: number;
  cap_amount?: number;
  currency?: string;
};

// ── Country resolver: accepts ISO-2, ISO-3, or full name in any case ────────
// Source values on wizard_cases.{origin,dest}_country / relocation_cases.host_country
// are inconsistent in practice — sometimes "FR", sometimes "France", sometimes
// "FRA". This maps any of those to a canonical ISO-2 code so flags render
// consistently. Add to this map as new corridors come online.
const ISO2_TO_NAME: Record<string, string> = {
  FR: 'France', NO: 'Norway', DE: 'Germany', IN: 'India', MX: 'Mexico', US: 'United States',
  GB: 'United Kingdom', UK: 'United Kingdom', ES: 'Spain', CA: 'Canada', BR: 'Brazil',
  NL: 'Netherlands', SG: 'Singapore', JP: 'Japan', AE: 'United Arab Emirates',
  IT: 'Italy', AU: 'Australia', HK: 'Hong Kong', CH: 'Switzerland', IE: 'Ireland',
  PT: 'Portugal', BE: 'Belgium', AT: 'Austria', SE: 'Sweden', DK: 'Denmark',
  FI: 'Finland', PL: 'Poland', CZ: 'Czechia', LU: 'Luxembourg', IL: 'Israel',
  ZA: 'South Africa', KR: 'South Korea', CN: 'China', TW: 'Taiwan', NZ: 'New Zealand',
  AR: 'Argentina', CL: 'Chile', CO: 'Colombia', PE: 'Peru', TR: 'Turkey',
  SA: 'Saudi Arabia', QA: 'Qatar', KW: 'Kuwait', MA: 'Morocco', EG: 'Egypt',
  NG: 'Nigeria', KE: 'Kenya', GR: 'Greece', HU: 'Hungary', RO: 'Romania',
  BG: 'Bulgaria', HR: 'Croatia', SK: 'Slovakia', SI: 'Slovenia', EE: 'Estonia',
  LV: 'Latvia', LT: 'Lithuania', IS: 'Iceland', MT: 'Malta', CY: 'Cyprus',
  MY: 'Malaysia', TH: 'Thailand', VN: 'Vietnam', PH: 'Philippines', ID: 'Indonesia',
};

// Reverse: every other shape we might see → ISO-2.
const ALIAS_TO_ISO2: Record<string, string> = (() => {
  const out: Record<string, string> = {};
  for (const [iso2, name] of Object.entries(ISO2_TO_NAME)) {
    out[iso2] = iso2;
    out[name.toUpperCase()] = iso2;
  }
  // Common alternates / ISO-3 codes we want to catch.
  Object.assign(out, {
    FRA: 'FR', DEU: 'DE', GER: 'DE', NOR: 'NO', IND: 'IN', MEX: 'MX',
    USA: 'US', GBR: 'GB', ESP: 'ES', CAN: 'CA', BRA: 'BR', NLD: 'NL',
    SGP: 'SG', JPN: 'JP', ARE: 'AE', ITA: 'IT', AUS: 'AU', HKG: 'HK',
    CHE: 'CH', IRL: 'IE', PRT: 'PT', BEL: 'BE', AUT: 'AT', SWE: 'SE',
    DNK: 'DK', FIN: 'FI', POL: 'PL', CZE: 'CZ', LUX: 'LU', ISR: 'IL',
    'UNITED STATES OF AMERICA': 'US', 'UNITED KINGDOM': 'GB', UK: 'GB',
    'HONG KONG SAR': 'HK', UAE: 'AE',
  });
  return out;
})();

function resolveISO2(raw?: string | null): string | null {
  if (!raw) return null;
  const norm = raw.trim().toUpperCase();
  if (!norm) return null;
  if (ALIAS_TO_ISO2[norm]) return ALIAS_TO_ISO2[norm];
  if (norm.length === 2 && /^[A-Z]{2}$/.test(norm)) return norm; // unknown but valid ISO-2 shape
  return null;
}

/** Render the country as a flag emoji built from regional indicator characters,
 *  which works for any ISO-2 code without needing a hard-coded table. */
function flagEmoji(iso2: string | null): string {
  if (!iso2 || iso2.length !== 2) return '';
  const base = 0x1f1e6;
  const a = iso2.charCodeAt(0) - 65;
  const b = iso2.charCodeAt(1) - 65;
  if (a < 0 || a > 25 || b < 0 || b > 25) return '';
  return String.fromCodePoint(base + a) + String.fromCodePoint(base + b);
}

// ── Status → pill tone (driven by raw backend status strings) ───────────────
const STATUS_PILL: Record<string, string> = {
  approved: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  done: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  completed: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  visa_submitted: 'bg-sky-50 text-sky-700 ring-sky-200',
  housing: 'bg-accent-50 text-accent-700 ring-accent-200',
  dossier: 'bg-accent-50 text-accent-700 ring-accent-200',
  roadmap: 'bg-accent-50 text-accent-700 ring-accent-200',
  discovery: 'bg-amber-50 text-amber-700 ring-amber-200',
  awaiting_intake: 'bg-amber-50 text-amber-700 ring-amber-200',
  submitted: 'bg-sky-50 text-sky-700 ring-sky-200',
  blocked: 'bg-rose-50 text-rose-700 ring-rose-200',
  at_risk: 'bg-rose-50 text-rose-700 ring-rose-200',
};

function statusLabel(raw: string): string {
  // TASK-005: shared with the Cases list so a case reads the same on both pages.
  return getCaseStatusLabel(raw);
}
function statusTone(raw: string, risk: string): string {
  const key = (raw || '').toLowerCase();
  if (STATUS_PILL[key]) return STATUS_PILL[key];
  if (risk === 'red') return STATUS_PILL.blocked!;
  if (risk === 'yellow') return STATUS_PILL.discovery!;
  return 'bg-slate-100 text-slate-700 ring-slate-200';
}

// ── Owner tones (deterministic colour bucket by string) ─────────────────────
const OWNER_TONES = [
  'bg-accent-100 text-accent-700',
  'bg-emerald-100 text-emerald-700',
  'bg-amber-100 text-amber-700',
  'bg-sky-100 text-sky-700',
  'bg-rose-100 text-rose-700',
  'bg-accent-100 text-accent-700',
];
function ownerTone(seed: string): string {
  let hash = 5381;
  for (let i = 0; i < seed.length; i++) hash = ((hash << 5) + hash + seed.charCodeAt(i)) | 0;
  return OWNER_TONES[Math.abs(hash) % OWNER_TONES.length]!;
}
function initials(name?: string | null): string {
  if (!name) return '—';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase();
  return ((parts[0]![0] || '') + (parts[parts.length - 1]![0] || '')).toUpperCase();
}

function formatMoney(n?: number | null, currency = 'EUR'): string {
  if (n == null || Number.isNaN(n)) return '—';
  if (n >= 1000) return `${currency === 'EUR' ? '€' : '$'}${Math.round(n / 1000)}k`;
  return `${currency === 'EUR' ? '€' : '$'}${Math.round(n)}`;
}

function daysAgo(iso?: string | null): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return null;
  return Math.max(0, Math.floor((Date.now() - t) / (1000 * 60 * 60 * 24)));
}

// ── MOBCC-FU1: header filters (corridor + time period) ───────────────────────
// Canonical corridor key — identical to the corridorMix histogram key so the
// filter, the table, and the sidebar mix all agree on what "US → FR" means.
function corridorKey(originCountry?: string | null, destCountry?: string | null): string {
  const o = resolveISO2(originCountry);
  const d = resolveISO2(destCountry);
  return `${o ?? `?${originCountry ?? ''}`}|${d ?? `?${destCountry ?? ''}`}`;
}
function corridorLabel(originCountry?: string | null, destCountry?: string | null): string {
  const o = getCountryName(originCountry) || originCountry?.trim() || '—';
  const d = getCountryName(destCountry) || destCountry?.trim() || '—';
  return `${o} → ${d}`;
}

type PeriodFilter = 'all' | '7d' | '30d' | '90d';
const PERIOD_OPTIONS: { value: PeriodFilter; label: string; days: number | null }[] = [
  { value: 'all', label: 'All time', days: null },
  { value: '7d', label: 'Last 7 days', days: 7 },
  { value: '30d', label: 'Last 30 days', days: 30 },
  { value: '90d', label: 'Last 90 days', days: 90 },
];
// Terminal/green statuses — used to split filtered cases into active vs completed
// when recomputing the KPI tiles client-side (mirrors STATUS_PILL's green set).
const COMPLETED_STATUSES = new Set(['completed', 'done', 'approved', 'closed']);

// ── Small visual primitives ─────────────────────────────────────────────────

function Pill({ children, className = '', title }: { children: React.ReactNode; className?: string; title?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${className}`} title={title}>
      {children}
    </span>
  );
}

/**
 * Marker for a case-row cell whose data isn't available yet. BRAND-5: this is
 * a buyer-facing case table, so it must read as an intentional empty state
 * ("Not set") in muted slate, never a "tbd" dev flag. The reason a column has
 * no value is preserved for engineers in the `title` tooltip (the backing-data
 * gap), not in the visible label.
 */
function NotLinked({ label = 'Not set', title }: { label?: string; title?: string }) {
  return (
    <span
      title={title || 'Not yet linked to Supabase — placeholder.'}
      className="text-[12.5px] text-slate-500"
    >
      {label}
    </span>
  );
}

function Flag({ iso2, raw }: { iso2: string | null; raw?: string | null }) {
  const name = getCountryName(iso2 || raw || '');
  if (!iso2) {
    // BRAND-5: muted intentional empty — show the raw value if we have one
    // (even unresolved, it's information), otherwise "Not set", never "tbd".
    return (
      <span title={raw ? `Unknown country: ${raw}` : 'No country recorded'} className="text-slate-500">
        {name || raw || 'Not set'}
      </span>
    );
  }
  const emoji = flagEmoji(iso2);
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="text-[14px] leading-none" aria-hidden>{emoji}</span>
      <span className="text-[12px] text-slate-700">{name || iso2}</span>
    </span>
  );
}

interface KpiProps {
  label: string;
  value: string | number;
  sub: string;
  tone?: 'default' | 'success' | 'warning' | 'accent' | 'danger';
  progress?: number; // 0–100; renders a thin coloured bar at the bottom
  /** Optional hover tooltip explaining the metric (TASK-014). */
  title?: string;
}

function Kpi({ label, value, sub, tone = 'default', progress, title }: KpiProps) {
  const valueColor = 'text-navy-800';
  const bar: Record<NonNullable<KpiProps['tone']>, string> = {
    default: 'bg-slate-400',
    success: 'bg-emerald-500',
    warning: 'bg-rose-500',
    accent: 'bg-accent-500',
    danger: 'bg-rose-500',
  };
  const pct = Math.max(0, Math.min(100, progress ?? 100));
  return (
    <div
      className="relative overflow-hidden rounded-lg border border-slate-200 bg-white px-4 py-3 transition-colors hover:border-slate-300"
      title={title}
    >
      <div className="truncate text-[10px] font-semibold uppercase tracking-widest text-slate-500">{label}</div>
      <div className={`mt-1 text-[28px] font-semibold leading-none tracking-tight tabular-nums ${valueColor}`}>
        {value}
      </div>
      <div className="mt-1.5 text-[11px] text-slate-500 text-pretty">{sub}</div>
      <div className="absolute inset-x-0 bottom-0 h-1 bg-slate-100">
        <div className={`h-full ${bar[tone]}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// ── Sidebar card primitive ──────────────────────────────────────────────────

function SidebarCard({ eyebrow, children }: { eyebrow: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-slate-500">{eyebrow}</div>
      {children}
    </div>
  );
}

// ── Progress bar (inline, for table cell) ───────────────────────────────────

function ProgressBar({ value, risk }: { value: number; risk: string }) {
  const v = Math.max(0, Math.min(100, value));
  const tone = risk === 'red' ? 'bg-rose-500' : risk === 'yellow' ? 'bg-amber-500' : v >= 99 ? 'bg-emerald-500' : 'bg-accent-500';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full ${tone}`} style={{ width: `${v}%` }} />
      </div>
      <span className="w-8 text-right text-[11.5px] tabular-nums text-slate-600">{v}%</span>
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export function MobilityControlCenterV2Page() {
  const navigate = useNavigate();
  // MOBCC-FU1: header filters applied client-side over the already-scoped case
  // list — they never widen tenant visibility (no scope/endpoint change).
  const [corridorFilter, setCorridorFilter] = useState<string | null>(null);
  const [periodFilter, setPeriodFilter] = useState<PeriodFilter>('all');
  const { companyId } = useHrCompanyContext();

  // Single parallel read of KPIs + cases + pending approvals. Promise.allSettled
  // never rejects, so the query always resolves; partial failures surface via the
  // `degraded` flag exactly as the hand-rolled `backendDegraded` did (KPIs/cases
  // failing degrades; an approvals failure just empties that sidebar).
  const dashboardQuery = useQuery({
    queryKey: ['hr', 'mobility-control'],
    queryFn: async () => {
      const [kpisRes, casesRes, approvalsRes] = await Promise.allSettled([
        hrAPI.getCommandCenterKPIs(),
        hrAPI.listCommandCenterCases({ page: 1, limit: 100 }),
        // Reuse the HR exception requests endpoint — pending = awaiting HR sign-off
        api.get('/api/exception-requests', { params: { status: 'pending' } }).then((r) => r.data as ApprovalRow[]),
      ]);
      let degraded = false;
      let kpis: {
        activeCases: number;
        atRiskCount: number;
        completedCount: number;
        budgetOverrunsCount: number;
      } | null = null;
      if (kpisRes.status === 'fulfilled') {
        kpis = {
          activeCases: kpisRes.value.activeCases ?? 0,
          atRiskCount: kpisRes.value.atRiskCount ?? 0,
          completedCount: kpisRes.value.completedCount ?? 0,
          budgetOverrunsCount: kpisRes.value.budgetOverrunsCount ?? 0,
        };
      } else {
        degraded = true;
      }
      let cases: CommandCenterCaseRow[] = [];
      if (casesRes.status === 'fulfilled') {
        cases = casesRes.value;
      } else {
        degraded = true;
      }
      let approvals: ApprovalRow[] = [];
      if (approvalsRes.status === 'fulfilled' && Array.isArray(approvalsRes.value)) {
        approvals = approvalsRes.value;
      }
      return { kpis, cases, approvals, degraded };
    },
  });

  const kpis: {
    activeCases: number;
    atRiskCount: number;
    completedCount: number;
    budgetOverrunsCount: number;
  } | null = dashboardQuery.data?.kpis ?? null;
  const cases: CommandCenterCaseRow[] = useMemo(() => dashboardQuery.data?.cases ?? [], [dashboardQuery.data]);
  const approvals: ApprovalRow[] = dashboardQuery.data?.approvals ?? [];
  const backendDegraded = dashboardQuery.data?.degraded ?? false;
  const loading = dashboardQuery.isLoading;
  // AIQ-1411: show the warm onboarding empty state only at TRUE zero (the tenant
  // has no cases at all) — never during load (a cold query must not render a
  // false empty; cf. AIQ-1375 cold-start spinner class) and never for a
  // filtered-but-non-empty result (that keeps the plain table string).
  const noCasesYet = !loading && cases.length === 0;

  // Parker-J: classical data-to-text exec summary (LLM-free, env-flag gated
  // server-side). Dependent on the resolved companyId. Null = provider deferred
  // to LLM (env flag) or unavailable.
  const execSummaryQuery = useQuery({
    queryKey: ['hr', 'mobility-control', 'exec-summary', companyId],
    enabled: !!companyId,
    queryFn: ({ signal }) => fetchExecSummary(companyId as string, signal).then((res) => res.summary),
  });
  const execSummary: string | null = execSummaryQuery.data ?? null;

  // ── MOBCC-FU1: client-side header filters ─────────────────────────────────
  const filterActive = corridorFilter !== null || periodFilter !== 'all';

  // Corridor dropdown options come from the FULL scoped list (so you can switch
  // corridors), unlike corridorMix below which reflects the active filter.
  const corridorOptions = useMemo(() => {
    const m = new Map<string, { key: string; label: string; count: number }>();
    for (const c of cases) {
      if (!c.originCountry && !c.destCountry) continue;
      const key = corridorKey(c.originCountry, c.destCountry);
      const cur = m.get(key);
      if (cur) cur.count += 1;
      else m.set(key, { key, label: corridorLabel(c.originCountry, c.destCountry), count: 1 });
    }
    return [...m.values()].sort((a, b) => b.count - a.count);
  }, [cases]);

  const filteredCases = useMemo(() => {
    const maxDays = PERIOD_OPTIONS.find((p) => p.value === periodFilter)?.days ?? null;
    return cases.filter((c) => {
      if (corridorFilter && corridorKey(c.originCountry, c.destCountry) !== corridorFilter) return false;
      if (maxDays != null) {
        const d = daysAgo(c.updatedAt);
        if (d == null || d > maxDays) return false;
      }
      return true;
    });
  }, [cases, corridorFilter, periodFilter]);

  // KPI tiles come from a backend endpoint (authoritative totals). When a filter
  // is active, recompute them from the filtered rows so the whole dashboard stays
  // coherent; with no filter, fall back to the backend KPIs.
  const displayKpis = useMemo(() => {
    if (!filterActive) return kpis;
    const completed = filteredCases.filter((c) => COMPLETED_STATUSES.has((c.status ?? '').toLowerCase())).length;
    return {
      activeCases: filteredCases.length - completed,
      atRiskCount: filteredCases.filter((c) => c.riskStatus === 'red' || c.riskStatus === 'yellow').length,
      completedCount: completed,
      budgetOverrunsCount: filteredCases.filter((c) => (c.budgetEstimated ?? 0) > (c.budgetLimit ?? 0) && (c.budgetLimit ?? 0) > 0).length,
    };
  }, [filterActive, kpis, filteredCases]);

  // ── Derived sidebar data ──────────────────────────────────────────────────
  // Aggregate the (filtered) case list into a corridor histogram keyed by
  // canonical ISO-2 codes so the sidebar matches the table flag rendering exactly
  // (e.g. "France" + "FR" + "FRA" all collapse onto the same FR row).
  const corridorMix = useMemo(() => {
    const counts = new Map<string, { origin: string | null; dest: string | null; rawOrigin: string | null; rawDest: string | null; count: number }>();
    for (const c of filteredCases) {
      const o = resolveISO2(c.originCountry);
      const d = resolveISO2(c.destCountry);
      if (!o && !d && !c.originCountry && !c.destCountry) continue;
      const key = `${o ?? `?${c.originCountry ?? ''}`}|${d ?? `?${c.destCountry ?? ''}`}`;
      const cur = counts.get(key);
      if (cur) cur.count += 1;
      else counts.set(key, { origin: o, dest: d, rawOrigin: c.originCountry ?? null, rawDest: c.destCountry ?? null, count: 1 });
    }
    return [...counts.values()].sort((a, b) => b.count - a.count).slice(0, 6);
  }, [filteredCases]);

  const riskFeed = useMemo(() => {
    return filteredCases
      .filter((c) => c.riskStatus && c.riskStatus !== 'green')
      .sort((a, b) => {
        // red first, then yellow
        if (a.riskStatus === b.riskStatus) return 0;
        if (a.riskStatus === 'red') return -1;
        if (b.riskStatus === 'red') return 1;
        return 0;
      })
      .slice(0, 5);
  }, [filteredCases]);

  // AIQ-1109: "Mobility spend" is the sum of each active case's ESTIMATED
  // relocation budget (`budgetEstimated`), shown against the total policy budget
  // (`budgetLimit`). It is an estimate — NOT invoiced/actual spend. Both fields
  // arrive per-case from hrAPI.listCommandCenterCases → GET /api/hr/command-center/cases
  // → db.list_command_center_cases (case_assignments.budget_estimated / budget_limit),
  // and are summed client-side here. The figure is company-scoped server-side.
  const totalBudget = useMemo(() => {
    const limit = filteredCases.reduce((acc, c) => acc + (c.budgetLimit ?? 0), 0);
    const est = filteredCases.reduce((acc, c) => acc + (c.budgetEstimated ?? 0), 0);
    return { limit, est };
  }, [filteredCases]);

  // ── DataTable columns ─────────────────────────────────────────────────────
  const goToCase = useCallback((row: CommandCenterCaseRow) => {
    navigate(`/hr/command-center/cases/${row.id}`);
  }, [navigate]);

  const columns = useMemo<DataTableColumn<CommandCenterCaseRow>[]>(() => [
    {
      id: 'employee',
      header: 'Employee',
      defaultWidth: 220,
      minWidth: 160,
      sortValue: (row) => (row.employeeIdentifier || '').toLowerCase(),
      cell: (row) => {
        // BRAND-5: CommandCenterCaseRow has no name field today, so email is the
        // legitimate fallback; displayNameOrEmail keeps it intentional (and is the
        // single switch point if a name field is added to the payload later).
        const name = displayNameOrEmail(null, row.employeeIdentifier);
        const tone = ownerTone(name);
        return (
          <div className="flex items-center gap-2.5">
            <span className={`inline-flex h-7 w-7 items-center justify-center rounded text-[11px] font-semibold ${tone}`}>
              {initials(name)}
            </span>
            <div className="min-w-0">
              <div className="truncate text-[12.5px] font-medium text-slate-900">{name}</div>
              {row.employeeRole && (
                <div className="truncate text-[11px] text-slate-500">{row.employeeRole}</div>
              )}
            </div>
          </div>
        );
      },
    },
    {
      id: 'corridor',
      header: 'Corridor',
      defaultWidth: 160,
      minWidth: 120,
      sortValue: (row) => `${row.originCountry ?? ''}›${row.destCountry ?? ''}`,
      cell: (row) => {
        const o = resolveISO2(row.originCountry);
        const d = resolveISO2(row.destCountry);
        // BRAND-5: when neither side is known, a single intentional label reads
        // better than "Not set › Not set".
        if (!(row.originCountry || '').trim() && !(row.destCountry || '').trim()) {
          return <span className="text-[12.5px] text-slate-500">Route not set</span>;
        }
        return (
          <div className="flex items-center gap-2 text-[12.5px] text-slate-700">
            <Flag iso2={o} raw={row.originCountry} />
            <span className="text-slate-500">›</span>
            <Flag iso2={d} raw={row.destCountry} />
          </div>
        );
      },
    },
    {
      id: 'visa',
      header: 'Visa',
      defaultWidth: 150,
      minWidth: 110,
      sortValue: (row) => row.visaLabel ?? '',
      cell: (row) => {
        // visaLabel = wizard_cases.purpose (closest first-class signal).
        // case_assignments has no dedicated visa_type column today, so the
        // value is a surrogate; we surface NotLinked when nothing flows.
        if (!row.visaLabel) {
          return <NotLinked title="No visa_type column on case_assignments — surrogate would come from wizard_cases.purpose / employees.assignment_type." />;
        }
        const label = row.visaLabel.replace(/_/g, ' ');
        return (
          <span className="text-[12.5px] text-slate-700" title="Best-available visa surrogate (wizard_cases.purpose)">
            {label}
          </span>
        );
      },
    },
    {
      id: 'household',
      header: 'Household',
      defaultWidth: 160,
      minWidth: 120,
      sortValue: (row) => row.household ?? '',
      cell: (row) => {
        if (!row.household) {
          return <NotLinked title="No household column — derive from employee_profiles.profile_json (spouse + children) once that schema is locked." />;
        }
        // Pick an icon based on composition: 👤 solo, 👫 partner, 👨‍👩‍👧 family.
        const icon = (row.childCount ?? 0) > 0
          ? '👨‍👩‍👧'
          : row.hasSpouse
            ? '👫'
            : '👤';
        return (
          <span className="inline-flex items-center gap-1.5 text-[12.5px] text-slate-700">
            <span aria-hidden className="text-[14px] leading-none">{icon}</span>
            <span>{row.household}</span>
          </span>
        );
      },
    },
    {
      id: 'progress',
      header: 'Progress',
      defaultWidth: 160,
      minWidth: 130,
      sortValue: (row) => row.tasksDonePercent ?? 0,
      cell: (row) => <ProgressBar value={row.tasksDonePercent} risk={row.riskStatus} />,
    },
    {
      id: 'owner',
      header: 'Owner',
      defaultWidth: 140,
      minWidth: 110,
      sortValue: (row) => row.ownerName ?? '',
      cell: (row) => {
        if (!row.ownerName) {
          return <NotLinked label="unassigned" title="No HR owner — profiles.full_name missing for ca.hr_user_id. Either backfill the profile or assign an HR user." />;
        }
        return <span className="text-[12.5px] text-slate-700">{row.ownerName}</span>;
      },
    },
    {
      id: 'status',
      header: 'Status',
      defaultWidth: 150,
      minWidth: 110,
      sortValue: (row) => row.status ?? '',
      cell: (row) => (
        <Pill className={statusTone(row.status, row.riskStatus)}>
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${row.riskStatus === 'red' ? 'bg-rose-500' : row.riskStatus === 'yellow' ? 'bg-amber-500' : 'bg-emerald-500'}`} />
          {statusLabel(row.status)}
        </Pill>
      ),
    },
  ], []);

  return (
    <AppShell wide>
      <div className="px-2 py-2 xl:px-4 xl:py-4">
        {/* Header — breadcrumb above h1; the 'HR · Global mobility' eyebrow was
            removed per P4 audit ('Mobility Control Center no longer shows
            HR · GLOBAL MOBILITY as a standalone sub-header'). */}
        <Breadcrumb section="HR Operations" title="Mobility command center" className="mb-3" />
        <div className="mb-5">
          <div className="flex flex-wrap items-baseline gap-3">
            <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Mobility command center</h1>
            <div className="ml-auto flex items-center gap-2">
              {/* MOBCC-FU1: corridor filter — narrows the table, corridor mix, and
                  KPIs to one origin→dest. Options come from the scoped case list. */}
              <select
                value={corridorFilter ?? ''}
                onChange={(e) => setCorridorFilter(e.target.value || null)}
                aria-label="Filter by corridor"
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                <option value="">All corridors</option>
                {corridorOptions.map((o) => (
                  <option key={o.key} value={o.key}>{o.label} ({o.count})</option>
                ))}
              </select>
              {/* MOBCC-FU1: time-period filter — keeps cases updated within the window. */}
              <select
                value={periodFilter}
                onChange={(e) => setPeriodFilter(e.target.value as PeriodFilter)}
                aria-label="Filter by time period"
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                {PERIOD_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
              <Button unstyled
                type="button"
                // AIQ-1568: same dead '/employees/new' path — the tester reported this
                // button "also does nothing". It lands on the Cases page, where the case
                // list and the New-case form both live.
                onClick={() => navigate(buildRoute('hrDashboard'))}
                className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800"
              >
                Manage cases
              </Button>
            </div>
          </div>
          <p className="mt-1 max-w-3xl text-[13px] text-slate-500">
            {displayKpis ? displayKpis.activeCases : '—'} active relocation{displayKpis && displayKpis.activeCases === 1 ? '' : 's'} across {corridorMix.length} corridor{corridorMix.length === 1 ? '' : 's'}
          </p>
        </div>

        {/* KPI strip */}
        <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Kpi
            label="Active cases"
            value={displayKpis?.activeCases ?? (loading ? '…' : 0)}
            sub={`across ${corridorMix.length} corridor${corridorMix.length === 1 ? '' : 's'}`}
            tone="accent"
            progress={Math.min(100, (displayKpis?.activeCases ?? 0) * 5)}
          />
          <Kpi
            label="At risk"
            value={displayKpis?.atRiskCount ?? (loading ? '…' : 0)}
            sub="Delayed by 5+ days"
            tone="warning"
            title="Flagged when a provider task is more than 5 days past its due date."
            progress={displayKpis?.activeCases ? Math.min(100, ((displayKpis.atRiskCount ?? 0) / displayKpis.activeCases) * 100) : 0}
          />
          <Kpi
            label="Completed YTD"
            value={displayKpis?.completedCount ?? (loading ? '…' : 0)}
            sub="completed relocations this year"
            tone="success"
            progress={displayKpis?.completedCount ? Math.min(100, displayKpis.completedCount * 5) : 0}
          />
          <Kpi
            label="Mobility spend"
            value={formatMoney(totalBudget.est)}
            sub={totalBudget.limit ? `est. of ${formatMoney(totalBudget.limit)} budget` : '—'}
            tone={displayKpis?.budgetOverrunsCount ? 'danger' : 'default'}
            title="Estimated relocation spend — the sum of each active case's estimated budget, shown against the total policy budget. Source: GET /api/hr/command-center/cases (case_assignments.budget_estimated / budget_limit). Estimate, not invoiced spend."
            progress={totalBudget.limit ? Math.min(100, (totalBudget.est / totalBudget.limit) * 100) : 0}
          />
        </div>

        {/* BRAND-3: hide the whole block (incl. the eyebrow) when every KPI is
            zero — an all-zero summary is noise on a fresh/empty tenant. */}
        {execSummary &&
          !(displayKpis && displayKpis.activeCases === 0 && displayKpis.atRiskCount === 0 && displayKpis.completedCount === 0) && (
          <div className="mb-5 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Executive summary</p>
            <p className="mt-1 text-[13px] leading-relaxed text-slate-700 text-pretty break-words">{execSummary}</p>
          </div>
        )}

        {backendDegraded && (
          <div className="mb-4 flex items-start justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <span>
              Some data couldn&apos;t load — showing partial results. Refresh to try again.
            </span>
            <Button unstyled type="button" onClick={() => void dashboardQuery.refetch()} className="text-amber-700 hover:underline">Retry</Button>
          </div>
        )}

        {/* [AIQ-2041] Action-first: what needs doing sits ABOVE the case table, so
            the page opens with work rather than with a list to scan. */}
        <HrCaseHealthPanel />

        {/* Two-column layout: cases table + right-rail. The right rail grows
            up to 360px on wider monitors but the table always gets the
            remaining viewport (no max-width cap). On <lg the rail stacks
            below the table. */}
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
          <div>
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-baseline gap-2">
                <h2 className="text-[15px] font-semibold text-slate-900">All relocation cases</h2>
                <span className="text-[12px] text-slate-500">
                  {filteredCases.length} employee{filteredCases.length === 1 ? '' : 's'}
                </span>
              </div>
            </div>

            {noCasesYet ? (
              <ConversationalEmptyState
                icon={PlaneTakeoff}
                heading="Ready to set up your first relocation?"
                body="Add your first employee's move and ReloPass builds their roadmap, policy, and supplier options automatically — no blank spreadsheets to fill in."
                actions={[
                  // AIQ-1568 (TD-BUG-1): this pointed at '/employees/new', which is not a
                  // route. React Router fell through to <Route path="*"> -> NotFoundRedirect
                  // -> roleHomePath('HR') = /hr/dashboard -> useWelcomeRedirect -> /hr/welcome.
                  // That is the exact loop the tester hit 3x: the most prominent CTA on the HR
                  // side silently bounced to onboarding. Send them to the ONE real case form
                  // (HrDashboard's openNewCaseForm) via ?new=1, and use buildRoute like the
                  // sibling actions below — a typed key cannot rot into a dead path.
                  { label: 'Add your first relocation', onClick: () => navigate(`${buildRoute('hrDashboard')}?new=1`) },
                  { label: 'Import your team roster', onClick: () => navigate(buildRoute('hrEmployees')) },
                  { label: 'Set up your relocation policy', onClick: () => navigate(buildRoute('hrPolicy')) },
                ]}
                hint="Takes about 2 minutes — you'll add the employee, destination, and move date."
              />
            ) : (
              <TableScroll minWidthClass="min-w-[48rem]">
              <DataTable
                tableId="hr.mobility-control"
                columns={columns}
                rows={filteredCases}
                rowKey={(r) => r.id}
                onRowClick={goToCase}
                ariaLabel="Mobility control cases"
                emptyState={loading ? 'Loading cases…' : 'No active relocations yet. Cases created on the Assignments page appear here.'}
                footerSlot={
                  <div className="flex items-center justify-between px-4 py-2 text-[11.5px] text-slate-500">
                    <span>{filteredCases.length} case{filteredCases.length === 1 ? '' : 's'}</span>
                    <ResetColumnsLink tableId="hr.mobility-control" />
                  </div>
                }
              />
              </TableScroll>
            )}
          </div>

          {/* Right sidebar */}
          <div className="space-y-3">
            <SidebarCard eyebrow="Corridor mix">
              {corridorMix.length === 0 ? (
                <p className="text-[12px] text-slate-500">Corridors appear once a case has an origin and destination country.</p>
              ) : (
                <ul className="space-y-1.5">
                  {corridorMix.map((c) => (
                    <li key={`${c.origin ?? c.rawOrigin}-${c.dest ?? c.rawDest}`} className="flex items-center justify-between text-[12.5px]">
                      <span className="flex items-center gap-2 text-slate-700">
                        <Flag iso2={c.origin} raw={c.rawOrigin} />
                        <span className="text-slate-500">›</span>
                        <Flag iso2={c.dest} raw={c.rawDest} />
                      </span>
                      <span className="tabular-nums text-slate-500">{c.count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </SidebarCard>

            <SidebarCard eyebrow="Risk feed">
              {riskFeed.length === 0 ? (
                <p className="text-[12px] text-slate-500">All cases on track.</p>
              ) : (
                <ul className="space-y-2">
                  {riskFeed.map((row) => {
                    const age = daysAgo(row.updatedAt);
                    return (
                      // eslint-disable-next-line jsx-a11y/no-noninteractive-element-to-interactive-role -- <li> as interactive list item; button role enables keyboard activation
                      <li key={row.id} role="button" tabIndex={0}
                        className="cursor-pointer text-[12.5px] hover:opacity-90"
                        onClick={() => goToCase(row)}
                        onKeyDown={(e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); goToCase(row); } }}
                      >
                        <div className="flex items-center gap-1.5">
                          <span className={`inline-block h-1.5 w-1.5 rounded-full ${row.riskStatus === 'red' ? 'bg-rose-500' : 'bg-amber-500'}`} />
                          <span className="font-medium text-slate-900">{row.employeeIdentifier}</span>
                        </div>
                        <div className="ml-3 truncate text-[11.5px] text-slate-500">
                          {statusLabel(row.status)}{age != null ? ` · Updated ${age} day${age !== 1 ? 's' : ''} ago` : ''}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </SidebarCard>

            <SidebarCard eyebrow="Pending approvals">
              {approvals.length === 0 ? (
                <p className="text-[12px] text-slate-500">No pending approvals.</p>
              ) : (
                <ul className="space-y-2">
                  {approvals.slice(0, 5).map((a) => (
                    <li key={a.id} className="flex items-center justify-between gap-2 text-[12.5px]">
                      <div className="min-w-0">
                        <div className="truncate font-medium text-slate-900">
                          {a.category.replace(/_/g, ' ')}
                        </div>
                        <div className="truncate text-[11.5px] text-slate-500">
                          {a.requested_amount != null && a.cap_amount != null
                            ? `${formatMoney(a.requested_amount, a.currency)} vs ${formatMoney(a.cap_amount, a.currency)} cap`
                            : (a.reason || 'awaiting decision')}
                        </div>
                      </div>
                      <Button unstyled
                        type="button"
                        onClick={() => navigate(`/hr/cases/${a.case_id ?? ''}`)}
                        className="shrink-0 rounded-md border border-slate-300 px-2 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-50"
                      >
                        Review
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </SidebarCard>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

export default MobilityControlCenterV2Page;
