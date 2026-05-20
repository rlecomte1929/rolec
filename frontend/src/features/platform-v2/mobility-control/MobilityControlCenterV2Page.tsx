import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../../../components/AppShell';
import api, { hrAPI } from '../../../api/client';
import type { CommandCenterCaseRow } from '../../../api/client';
import { DataTable, ResetColumnsLink, type DataTableColumn } from '../data-table';

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
  if (ALIAS_TO_ISO2[norm]) return ALIAS_TO_ISO2[norm]!;
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
  housing: 'bg-violet-50 text-violet-700 ring-violet-200',
  dossier: 'bg-indigo-50 text-indigo-700 ring-indigo-200',
  roadmap: 'bg-indigo-50 text-indigo-700 ring-indigo-200',
  discovery: 'bg-amber-50 text-amber-700 ring-amber-200',
  awaiting_intake: 'bg-amber-50 text-amber-700 ring-amber-200',
  submitted: 'bg-sky-50 text-sky-700 ring-sky-200',
  blocked: 'bg-rose-50 text-rose-700 ring-rose-200',
  at_risk: 'bg-rose-50 text-rose-700 ring-rose-200',
};

function statusLabel(raw: string): string {
  if (!raw) return '—';
  return raw.replace(/_/g, ' ');
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
  'bg-indigo-100 text-indigo-700',
  'bg-emerald-100 text-emerald-700',
  'bg-amber-100 text-amber-700',
  'bg-sky-100 text-sky-700',
  'bg-rose-100 text-rose-700',
  'bg-violet-100 text-violet-700',
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

// ── Small visual primitives ─────────────────────────────────────────────────

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
  progress?: number; // 0–100; renders a thin coloured bar at the bottom
}

function Kpi({ label, value, sub, tone = 'default', progress }: KpiProps) {
  const valueColor: Record<NonNullable<KpiProps['tone']>, string> = {
    default: 'text-slate-900',
    success: 'text-emerald-700',
    warning: 'text-rose-700',
    accent: 'text-indigo-700',
    danger: 'text-rose-700',
  };
  const bar: Record<NonNullable<KpiProps['tone']>, string> = {
    default: 'bg-slate-400',
    success: 'bg-emerald-500',
    warning: 'bg-rose-500',
    accent: 'bg-indigo-500',
    danger: 'bg-rose-500',
  };
  const pct = Math.max(0, Math.min(100, progress ?? 100));
  return (
    <div className="relative overflow-hidden rounded-lg border border-slate-200 bg-white px-4 py-3 transition-colors hover:border-slate-300">
      <div className="truncate text-[10px] font-semibold uppercase tracking-widest text-slate-500">{label}</div>
      <div className={`mt-1 text-[28px] font-semibold leading-none tracking-tight tabular-nums ${valueColor[tone]}`}>
        {value}
      </div>
      <div className="mt-1.5 truncate text-[11px] text-slate-500">{sub}</div>
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
  const tone = risk === 'red' ? 'bg-rose-500' : risk === 'yellow' ? 'bg-amber-500' : v >= 99 ? 'bg-emerald-500' : 'bg-indigo-500';
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
  const [cases, setCases] = useState<CommandCenterCaseRow[]>([]);
  const [kpis, setKpis] = useState<{
    activeCases: number;
    atRiskCount: number;
    completedCount: number;
    budgetOverrunsCount: number;
  } | null>(null);
  const [approvals, setApprovals] = useState<ApprovalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [backendDegraded, setBackendDegraded] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setBackendDegraded(false);
    const [kpisRes, casesRes, approvalsRes] = await Promise.allSettled([
      hrAPI.getCommandCenterKPIs(),
      hrAPI.listCommandCenterCases({ page: 1, limit: 100 }),
      // Reuse the HR exception requests endpoint — pending = awaiting HR sign-off
      api.get('/api/exception-requests', { params: { status: 'pending' } }).then((r) => r.data as ApprovalRow[]),
    ]);
    if (kpisRes.status === 'fulfilled') {
      setKpis({
        activeCases: kpisRes.value.activeCases ?? 0,
        atRiskCount: kpisRes.value.atRiskCount ?? 0,
        completedCount: kpisRes.value.completedCount ?? 0,
        budgetOverrunsCount: kpisRes.value.budgetOverrunsCount ?? 0,
      });
    } else {
      setBackendDegraded(true);
    }
    if (casesRes.status === 'fulfilled') {
      setCases(casesRes.value);
    } else {
      setCases([]);
      setBackendDegraded(true);
    }
    if (approvalsRes.status === 'fulfilled' && Array.isArray(approvalsRes.value)) {
      setApprovals(approvalsRes.value);
    } else {
      setApprovals([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  // ── Derived sidebar data ──────────────────────────────────────────────────
  const corridorMix = useMemo(() => {
    const counts = new Map<string, { origin: string; dest: string; count: number }>();
    for (const c of cases) {
      const o = (c.originCountry || '').toUpperCase();
      const d = (c.destCountry || '').toUpperCase();
      if (!o && !d) continue;
      const key = `${o}|${d}`;
      const cur = counts.get(key);
      if (cur) cur.count += 1;
      else counts.set(key, { origin: o, dest: d, count: 1 });
    }
    return [...counts.values()].sort((a, b) => b.count - a.count).slice(0, 6);
  }, [cases]);

  const riskFeed = useMemo(() => {
    return cases
      .filter((c) => c.riskStatus && c.riskStatus !== 'green')
      .sort((a, b) => {
        // red first, then yellow
        if (a.riskStatus === b.riskStatus) return 0;
        if (a.riskStatus === 'red') return -1;
        if (b.riskStatus === 'red') return 1;
        return 0;
      })
      .slice(0, 5);
  }, [cases]);

  const totalBudget = useMemo(() => {
    const limit = cases.reduce((acc, c) => acc + (c.budgetLimit ?? 0), 0);
    const est = cases.reduce((acc, c) => acc + (c.budgetEstimated ?? 0), 0);
    return { limit, est };
  }, [cases]);

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
      cell: (row) => {
        const name = row.employeeIdentifier || '—';
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
      defaultWidth: 130,
      minWidth: 100,
      cell: (row) => (
        <div className="flex items-center gap-1.5 text-[12.5px] text-slate-700">
          {row.originCountry ? (
            <>
              <span className="text-[13px] leading-none">{flag(row.originCountry)}</span>
              <span className="font-mono text-[11px] text-slate-600">{row.originCountry.toUpperCase()}</span>
            </>
          ) : <span className="text-slate-400">—</span>}
          <span className="text-slate-400">›</span>
          {row.destCountry ? (
            <>
              <span className="text-[13px] leading-none">{flag(row.destCountry)}</span>
              <span className="font-mono text-[11px] text-slate-600">{row.destCountry.toUpperCase()}</span>
            </>
          ) : <span className="text-slate-400">—</span>}
        </div>
      ),
    },
    {
      id: 'visa',
      header: 'Visa',
      defaultWidth: 150,
      minWidth: 110,
      cell: (row) => {
        // visaLabel comes from wizard_cases.move_type / contract_type /
        // employees.assignment_type. None of those is a true visa-program
        // field, but it's the closest first-class signal we have today —
        // we'd need a real `visa_type` column to show "Skilled Worker"
        // exactly as the mock does.
        if (!row.visaLabel) {
          return <span className="text-[12.5px] text-slate-400">—</span>;
        }
        const label = row.visaLabel.replace(/_/g, ' ');
        return (
          <span className="text-[12.5px] text-slate-700" title="Best-available visa surrogate (move_type / contract_type)">
            {label}
          </span>
        );
      },
    },
    {
      id: 'household',
      header: 'Household',
      defaultWidth: 150,
      minWidth: 110,
      cell: (row) => {
        if (!row.household) {
          return <span className="text-[12.5px] text-slate-400">—</span>;
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
      cell: (row) => <ProgressBar value={row.tasksDonePercent} risk={row.riskStatus} />,
    },
    {
      id: 'owner',
      header: 'Owner',
      defaultWidth: 140,
      minWidth: 110,
      cell: (row) => {
        if (!row.ownerName) return <span className="text-[12px] italic text-slate-400">Unassigned</span>;
        return <span className="text-[12.5px] text-slate-700">{row.ownerName}</span>;
      },
    },
    {
      id: 'status',
      header: 'Status',
      defaultWidth: 150,
      minWidth: 110,
      cell: (row) => (
        <Pill className={statusTone(row.status, row.riskStatus)}>
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${row.riskStatus === 'red' ? 'bg-rose-500' : row.riskStatus === 'yellow' ? 'bg-amber-500' : 'bg-emerald-500'}`} />
          {statusLabel(row.status)}
        </Pill>
      ),
    },
  ], []);

  return (
    <AppShell>
      <div className="px-6 py-6">
        {/* Header */}
        <div className="mb-5">
          <div className="text-[11px] font-medium uppercase tracking-widest text-slate-400">
            HR · Global mobility
          </div>
          <div className="mt-1.5 flex flex-wrap items-baseline gap-3">
            <h1 className="text-[26px] font-semibold tracking-tight text-slate-900">Mobility control center</h1>
            <Pill className="bg-indigo-50 text-indigo-700 ring-indigo-200">v2 preview</Pill>
            <div className="ml-auto flex items-center gap-2">
              <button
                type="button"
                onClick={() => alert('Corridor filter — wire in follow-up')}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                ⏷ All corridors
              </button>
              <button
                type="button"
                onClick={() => alert('Time period filter — wire in follow-up')}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                📅 Current quarter
              </button>
              <button
                type="button"
                onClick={() => navigate('/employees/new')}
                className="rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800"
              >
                + New case
              </button>
            </div>
          </div>
          <p className="mt-1 max-w-3xl text-[13px] text-slate-500">
            {kpis ? kpis.activeCases : '—'} active relocations · {corridorMix.length} corridor{corridorMix.length === 1 ? '' : 's'} · global team.
          </p>
        </div>

        {/* KPI strip */}
        <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Kpi
            label="Active cases"
            value={kpis?.activeCases ?? (loading ? '…' : 0)}
            sub={`across ${corridorMix.length} corridor${corridorMix.length === 1 ? '' : 's'}`}
            tone="accent"
            progress={Math.min(100, (kpis?.activeCases ?? 0) * 5)}
          />
          <Kpi
            label="At risk"
            value={kpis?.atRiskCount ?? (loading ? '…' : 0)}
            sub="delays > 5 days"
            tone="warning"
            progress={kpis?.activeCases ? Math.min(100, ((kpis.atRiskCount ?? 0) / kpis.activeCases) * 100) : 0}
          />
          <Kpi
            label="Completed YTD"
            value={kpis?.completedCount ?? (loading ? '…' : 0)}
            sub="approved cases this year"
            tone="success"
            progress={kpis?.completedCount ? Math.min(100, kpis.completedCount * 5) : 0}
          />
          <Kpi
            label="Mobility spend"
            value={formatMoney(totalBudget.est)}
            sub={totalBudget.limit ? `of ${formatMoney(totalBudget.limit)} budget` : 'no budget set'}
            tone={kpis?.budgetOverrunsCount ? 'danger' : 'default'}
            progress={totalBudget.limit ? Math.min(100, (totalBudget.est / totalBudget.limit) * 100) : 0}
          />
        </div>

        {backendDegraded && (
          <div className="mb-4 flex items-start justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <span>
              Some command center endpoints didn't respond. Page renders the layout with whatever loaded successfully.
            </span>
            <button type="button" onClick={() => void load()} className="text-amber-700 hover:underline">Retry</button>
          </div>
        )}

        {/* Two-column layout: cases table + right-rail */}
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div>
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-baseline gap-2">
                <h2 className="text-[15px] font-semibold text-slate-900">All relocation cases</h2>
                <span className="text-[12px] text-slate-500">
                  {cases.length} employee{cases.length === 1 ? '' : 's'}
                </span>
              </div>
            </div>

            <DataTable
              tableId="hr.mobility-control"
              columns={columns}
              rows={cases}
              rowKey={(r) => r.id}
              onRowClick={goToCase}
              ariaLabel="Mobility control cases"
              emptyState={loading ? 'Loading cases…' : 'No active cases yet.'}
              footerSlot={
                <div className="flex items-center justify-between px-4 py-2 text-[11.5px] text-slate-500">
                  <span>{cases.length} case{cases.length === 1 ? '' : 's'}</span>
                  <ResetColumnsLink tableId="hr.mobility-control" />
                </div>
              }
            />
          </div>

          {/* Right sidebar */}
          <div className="space-y-3">
            <SidebarCard eyebrow="Corridor mix">
              {corridorMix.length === 0 ? (
                <p className="text-[12px] text-slate-400">No corridors mapped yet.</p>
              ) : (
                <ul className="space-y-1.5">
                  {corridorMix.map((c) => (
                    <li key={`${c.origin}-${c.dest}`} className="flex items-center justify-between text-[12.5px]">
                      <span className="flex items-center gap-1.5 text-slate-700">
                        <span>{flag(c.origin) || '🌐'}</span>
                        <span className="font-mono text-[11px] text-slate-600">{c.origin || '??'}</span>
                        <span className="text-slate-400">›</span>
                        <span>{flag(c.dest) || '🌐'}</span>
                        <span className="font-mono text-[11px] text-slate-600">{c.dest || '??'}</span>
                      </span>
                      <span className="tabular-nums text-slate-500">{c.count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </SidebarCard>

            <SidebarCard eyebrow="Risk feed">
              {riskFeed.length === 0 ? (
                <p className="text-[12px] text-slate-400">All cases on track.</p>
              ) : (
                <ul className="space-y-2">
                  {riskFeed.map((row) => {
                    const age = daysAgo(row.updatedAt);
                    return (
                      <li
                        key={row.id}
                        className="cursor-pointer text-[12.5px] hover:opacity-90"
                        onClick={() => goToCase(row)}
                      >
                        <div className="flex items-center gap-1.5">
                          <span className={`inline-block h-1.5 w-1.5 rounded-full ${row.riskStatus === 'red' ? 'bg-rose-500' : 'bg-amber-500'}`} />
                          <span className="font-medium text-slate-900">{row.employeeIdentifier}</span>
                        </div>
                        <div className="ml-3 truncate text-[11.5px] text-slate-500">
                          {statusLabel(row.status)}{age != null ? ` · ${age}d` : ''}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </SidebarCard>

            <SidebarCard eyebrow="Pending approvals">
              {approvals.length === 0 ? (
                <p className="text-[12px] text-slate-400">Nothing waiting on you.</p>
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
                      <button
                        type="button"
                        onClick={() => navigate(`/hr/cases/${a.case_id ?? ''}`)}
                        className="shrink-0 rounded-md border border-slate-300 px-2 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-50"
                      >
                        Review
                      </button>
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
