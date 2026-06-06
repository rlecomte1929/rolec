import { useMemo, useState } from 'react';
import { Button } from '../../../components/antigravity/Button';
import { AppShell } from '../../../components/AppShell';

/**
 * HR Policy vs. Reality — V2.
 *
 * Compliance heatmap comparing policy commitments against what employees
 * are actually selecting from service providers. Four sections:
 *   1. KPI strip (compliance %, active cases, avg overage, most-exceeded benefit)
 *   2. Compliance heatmap (benefits × cases grid)
 *   3. Per-case table with inline compliance bars
 *   4. Case detail drawer (click a row to open)
 *
 * Backend: no dedicated endpoint exists yet. Page starts with mock data
 * structured to swap for a real API call.
 * TODO: const { data } = await hrAPI.getPolicyReality(); setData(data);
 */

// ── Types ─────────────────────────────────────────────────────────────────────

type CellStatus = 'green' | 'amber' | 'red' | 'grey' | 'blue';
type AssignmentType = 'long_term' | 'short_term' | 'permanent';

interface Benefit {
  category: string;
  key: string;
  label: string;
}

interface CaseRow {
  id: string;
  name: string;
  initials: string;
  corridor: string;
  flag: string;
  tier: string;
  type: AssignmentType;
  start: string;
  budget: number;
  spend: number;
  status: string;
  cells: Record<string, CellStatus>;
}

// ── Static data ───────────────────────────────────────────────────────────────

const BENEFITS: Benefit[] = [
  { category: 'Pre-assignment', key: 'visa_work_permit',   label: 'Visa & work permit assistance' },
  { category: 'Pre-assignment', key: 'language_training',  label: 'Language training' },
  { category: 'Pre-assignment', key: 'cultural_training',  label: 'Cultural training' },
  { category: 'Relocation',     key: 'removal_expenses',   label: 'Removal & shipping' },
  { category: 'Relocation',     key: 'temporary_living',   label: 'Temporary living' },
  { category: 'Relocation',     key: 'settling_in',        label: 'Settling-in services' },
  { category: 'Compensation',   key: 'mobility_premium',   label: 'Mobility premium' },
  { category: 'Compensation',   key: 'host_housing_cap',   label: 'Host country housing cap' },
  { category: 'Compensation',   key: 'host_transportation', label: 'Host country transportation' },
  { category: 'Family',         key: 'child_education',    label: 'Child education support' },
  { category: 'Family',         key: 'spouse_assistance',  label: 'Spouse / partner assistance' },
  { category: 'Leave',          key: 'home_leave_trips',   label: 'Home leave trips' },
  { category: 'Tax',            key: 'tax_equalisation',   label: 'Tax equalisation' },
];

const MOCK_CASES: CaseRow[] = [
  { id: 'c1', name: 'Marc Bouchard',     initials: 'MB', corridor: 'FR→NO', flag: '🇳🇴', tier: 'Manager',  type: 'long_term',  start: '2026-06-12', budget: 22000, spend: 23400, status: 'Active',  cells: { visa_work_permit: 'green', language_training: 'green', cultural_training: 'green', removal_expenses: 'green', temporary_living: 'amber', settling_in: 'green', mobility_premium: 'green', host_housing_cap: 'amber', host_transportation: 'green', child_education: 'red',   spouse_assistance: 'green', home_leave_trips: 'green', tax_equalisation: 'grey'  } },
  { id: 'c2', name: 'Priya Nair',        initials: 'PN', corridor: 'IN→DE', flag: '🇩🇪', tier: 'Director', type: 'long_term',  start: '2026-04-22', budget: 38000, spend: 41200, status: 'Active',  cells: { visa_work_permit: 'green', language_training: 'green', cultural_training: 'green', removal_expenses: 'amber', temporary_living: 'green', settling_in: 'green', mobility_premium: 'green', host_housing_cap: 'red',   host_transportation: 'green', child_education: 'grey',  spouse_assistance: 'red',   home_leave_trips: 'green', tax_equalisation: 'green' } },
  { id: 'c3', name: 'Yuki Tanaka',       initials: 'YT', corridor: 'JP→DE', flag: '🇩🇪', tier: 'Manager',  type: 'long_term',  start: '2026-03-08', budget: 22000, spend: 21100, status: 'Active',  cells: { visa_work_permit: 'red',   language_training: 'green', cultural_training: 'green', removal_expenses: 'green', temporary_living: 'green', settling_in: 'green', mobility_premium: 'grey',  host_housing_cap: 'green', host_transportation: 'amber', child_education: 'grey',  spouse_assistance: 'grey',  home_leave_trips: 'green', tax_equalisation: 'grey'  } },
  { id: 'c4', name: 'Lucas Reyes',       initials: 'LR', corridor: 'MX→US', flag: '🇺🇸', tier: 'Director', type: 'long_term',  start: '2026-04-30', budget: 38000, spend: 39800, status: 'Active',  cells: { visa_work_permit: 'amber', language_training: 'grey',  cultural_training: 'green', removal_expenses: 'green', temporary_living: 'amber', settling_in: 'green', mobility_premium: 'green', host_housing_cap: 'amber', host_transportation: 'green', child_education: 'green', spouse_assistance: 'green', home_leave_trips: 'green', tax_equalisation: 'green' } },
  { id: 'c5', name: 'Aïcha Idrissi',    initials: 'AI', corridor: 'ES→CA', flag: '🇨🇦', tier: 'Manager',  type: 'long_term',  start: '2026-02-14', budget: 22000, spend: 19800, status: 'Active',  cells: { visa_work_permit: 'green', language_training: 'green', cultural_training: 'green', removal_expenses: 'red',   temporary_living: 'green', settling_in: 'green', mobility_premium: 'grey',  host_housing_cap: 'green', host_transportation: 'grey',  child_education: 'grey',  spouse_assistance: 'grey',  home_leave_trips: 'green', tax_equalisation: 'grey'  } },
  { id: 'c6', name: 'Tomás Weber',       initials: 'TW', corridor: 'BR→NL', flag: '🇳🇱', tier: 'Manager',  type: 'long_term',  start: '2026-01-12', budget: 22000, spend: 24600, status: 'Active',  cells: { visa_work_permit: 'green', language_training: 'red',   cultural_training: 'green', removal_expenses: 'green', temporary_living: 'amber', settling_in: 'green', mobility_premium: 'grey',  host_housing_cap: 'amber', host_transportation: 'green', child_education: 'grey',  spouse_assistance: 'green', home_leave_trips: 'blue',  tax_equalisation: 'green' } },
  { id: 'c7', name: 'Sarah Kim',         initials: 'SK', corridor: 'US→JP', flag: '🇯🇵', tier: 'Director', type: 'long_term',  start: '2025-12-04', budget: 38000, spend: 36400, status: 'Active',  cells: { visa_work_permit: 'green', language_training: 'amber', cultural_training: 'green', removal_expenses: 'green', temporary_living: 'green', settling_in: 'green', mobility_premium: 'green', host_housing_cap: 'green', host_transportation: 'green', child_education: 'grey',  spouse_assistance: 'grey',  home_leave_trips: 'green', tax_equalisation: 'green' } },
  { id: 'c8', name: 'James Holt',        initials: 'JH', corridor: 'GB→AU', flag: '🇦🇺', tier: 'VP',       type: 'permanent',  start: '2025-11-08', budget: 68000, spend: 64200, status: 'Active',  cells: { visa_work_permit: 'green', language_training: 'grey',  cultural_training: 'green', removal_expenses: 'green', temporary_living: 'green', settling_in: 'green', mobility_premium: 'green', host_housing_cap: 'green', host_transportation: 'green', child_education: 'amber', spouse_assistance: 'green', home_leave_trips: 'green', tax_equalisation: 'green' } },
  { id: 'c9', name: 'Saanvi Mehra',      initials: 'SM', corridor: 'IN→SG', flag: '🇸🇬', tier: 'Manager',  type: 'short_term', start: '2026-03-22', budget: 14000, spend: 15800, status: 'Active',  cells: { visa_work_permit: 'green', language_training: 'grey',  cultural_training: 'green', removal_expenses: 'amber', temporary_living: 'red',   settling_in: 'green', mobility_premium: 'grey',  host_housing_cap: 'red',   host_transportation: 'green', child_education: 'grey',  spouse_assistance: 'grey',  home_leave_trips: 'blue',  tax_equalisation: 'grey'  } },
  { id: 'c10', name: 'Camille Fontaine', initials: 'CF', corridor: 'FR→US', flag: '🇺🇸', tier: 'Manager',  type: 'long_term',  start: '2026-05-01', budget: 22000, spend: 18200, status: 'Pending', cells: { visa_work_permit: 'green', language_training: 'grey',  cultural_training: 'blue',  removal_expenses: 'blue',  temporary_living: 'blue',  settling_in: 'blue',  mobility_premium: 'green', host_housing_cap: 'blue',  host_transportation: 'blue',  child_education: 'grey',  spouse_assistance: 'blue',  home_leave_trips: 'blue',  tax_equalisation: 'grey'  } },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

const CELL_CHAR: Record<CellStatus, string> = { green: '✓', amber: '~', red: '!', grey: '—', blue: '○' };

const CELL_STYLES: Record<CellStatus, string> = {
  green: 'bg-emerald-50 text-emerald-600',
  amber: 'bg-amber-50 text-amber-600',
  red:   'bg-rose-50 text-rose-600 font-semibold',
  grey:  'text-slate-300',
  blue:  'text-slate-400',
};

const COMPLIANCE_BAR: Record<string, string> = {
  green: 'bg-emerald-500',
  amber: 'bg-amber-400',
  red:   'bg-rose-500',
};

function complianceToneForPct(pct: number): string {
  return pct >= 80 ? 'green' : pct >= 60 ? 'amber' : 'red';
}

function caseStats(c: CaseRow) {
  const values = Object.values(c.cells);
  const countable = values.filter((s) => s !== 'grey' && s !== 'blue');
  const ok = countable.filter((s) => s === 'green').length;
  const over = countable.filter((s) => s === 'amber' || s === 'red').length;
  return {
    pct: countable.length > 0 ? Math.round((ok / countable.length) * 100) : 0,
    over,
  };
}

function fmt(n: number) {
  return `€${n.toLocaleString()}`;
}

// Group benefits by category, preserving insertion order
function groupByCategory(benefits: Benefit[]): Map<string, Benefit[]> {
  const map = new Map<string, Benefit[]>();
  for (const b of benefits) {
    if (!map.has(b.category)) map.set(b.category, []);
    map.get(b.category)!.push(b);
  }
  return map;
}

// ── Case detail drawer ────────────────────────────────────────────────────────

function CaseDrawer({
  c,
  onClose,
  onPrev,
  onNext,
  hasPrev,
  hasNext,
  privacy,
  caseIdx,
}: {
  c: CaseRow;
  onClose: () => void;
  onPrev: () => void;
  onNext: () => void;
  hasPrev: boolean;
  hasNext: boolean;
  privacy: boolean;
  caseIdx: number;
}) {
  const cells = Object.entries(c.cells);
  const countable = cells.filter(([, s]) => s !== 'grey' && s !== 'blue');
  const ok = countable.filter(([, s]) => s === 'green').length;
  const pct = countable.length > 0 ? Math.round((ok / countable.length) * 100) : 0;
  const tone = complianceToneForPct(pct);
  const variance = c.spend - c.budget;

  const displayName = privacy ? `Case #${caseIdx + 1}` : c.name;
  const displayInitials = privacy ? `#${caseIdx + 1}` : c.initials;

  const toneCls: Record<string, string> = {
    green: 'text-emerald-700 bg-emerald-50 ring-emerald-200',
    amber: 'text-amber-700 bg-amber-50 ring-amber-200',
    red: 'text-rose-700 bg-rose-50 ring-rose-200',
  };

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/20" onClick={onClose} />
      <aside className="fixed right-0 top-0 bottom-0 z-50 w-[420px] bg-white border-l border-slate-200 shadow-xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-5 pt-5 pb-4 border-b border-slate-100 flex items-start gap-3">
          <div className="w-10 h-10 rounded-full bg-slate-200 text-slate-600 text-sm font-semibold flex items-center justify-center shrink-0">
            {displayInitials}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-slate-900">{displayName}</p>
            <div className="flex flex-wrap items-center gap-1.5 mt-0.5 text-xs text-slate-400">
              <span>{c.flag} {c.corridor}</span>
              <span>·</span>
              <span>{c.tier}</span>
              <span>·</span>
              <span>{c.type.replace('_', '-')}</span>
              <span>·</span>
              <span>Started {c.start}</span>
            </div>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <Button unstyled disabled={!hasPrev} onClick={onPrev} className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 disabled:opacity-30 transition-colors">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7"/></svg>
            </Button>
            <Button unstyled disabled={!hasNext} onClick={onNext} className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 disabled:opacity-30 transition-colors">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7"/></svg>
            </Button>
            <Button unstyled onClick={onClose} className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 ml-1 transition-colors">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12"/></svg>
            </Button>
          </div>
        </div>

        {/* Stats strip */}
        <div className="grid grid-cols-3 border-b border-slate-100 divide-x divide-slate-100">
          <div className="px-4 py-3">
            <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider mb-0.5">Compliance</p>
            <p className={`text-sm font-semibold px-2 py-0.5 rounded-full ring-1 inline-block ${toneCls[tone]}`}>{pct}%</p>
          </div>
          <div className="px-4 py-3">
            <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider mb-0.5">Variance</p>
            <p className={`text-sm font-semibold ${variance > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
              {variance > 0 ? '+' : ''}{fmt(Math.abs(variance))}
            </p>
          </div>
          <div className="px-4 py-3">
            <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider mb-0.5">Status</p>
            <p className="text-sm font-semibold text-slate-700">{c.status}</p>
          </div>
        </div>

        {/* Benefit table */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Benefit breakdown</p>
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="text-left text-xs text-slate-400 font-medium pb-2">Benefit</th>
                <th className="text-center text-xs text-slate-400 font-medium pb-2 w-16">Policy</th>
                <th className="text-center text-xs text-slate-400 font-medium pb-2 w-16">Actual</th>
                <th className="text-center text-xs text-slate-400 font-medium pb-2 w-16">Status</th>
              </tr>
            </thead>
            <tbody>
              {Array.from(groupByCategory(BENEFITS)).map(([cat, blist]) => (
                <>
                  <tr key={cat}>
                    <td colSpan={4} className="pt-3 pb-1">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{cat}</span>
                    </td>
                  </tr>
                  {blist.map((b, ix) => {
                    const status = c.cells[b.key] || 'grey';
                    const seed = (c.id.charCodeAt(1) + ix * 17) % 100;
                    const base = 200 + seed * 30;
                    const overPct = status === 'red' ? 1.32 : status === 'amber' ? 1.12 : 0.88;
                    const hasVal = status !== 'grey' && status !== 'blue';
                    return (
                      <tr key={b.key} className="border-t border-slate-50">
                        <td className="py-1.5 text-slate-700 text-xs">{b.label}</td>
                        <td className="py-1.5 text-center text-xs text-slate-400 font-mono">{hasVal ? fmt(base) : '—'}</td>
                        <td className="py-1.5 text-center text-xs font-mono">
                          {status === 'blue' ? <span className="text-slate-400">pending</span>
                           : !hasVal ? <span className="text-slate-300">n/a</span>
                           : <span className={status === 'red' ? 'text-rose-600 font-semibold' : status === 'amber' ? 'text-amber-600' : 'text-emerald-600'}>
                               {fmt(Math.round(base * overPct))}
                             </span>}
                        </td>
                        <td className="py-1.5 text-center">
                          <span className={`inline-flex w-5 h-5 items-center justify-center rounded text-[10px] font-bold ${CELL_STYLES[status]}`}>
                            {CELL_CHAR[status]}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </>
              ))}
            </tbody>
          </table>
        </div>
      </aside>
    </>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function HrPolicyRealityPage() {
  const [destFilter, setDestFilter] = useState('all');
  const [tierFilter, setTierFilter] = useState('all');
  const [privacy, setPrivacy] = useState(false);
  const [activeCaseId, setActiveCaseId] = useState<string | null>(null);

  const cases = useMemo(
    () =>
      MOCK_CASES.filter(
        (c) =>
          (destFilter === 'all' || c.corridor.endsWith(destFilter)) &&
          (tierFilter === 'all' || c.tier === tierFilter)
      ),
    [destFilter, tierFilter]
  );

  const kpis = useMemo(() => {
    let total = 0;
    let withinCap = 0;
    let overageSum = 0;
    let overageCount = 0;
    const benefitOverages: Record<string, number> = {};

    cases.forEach((c) => {
      Object.entries(c.cells).forEach(([k, s]) => {
        if (s === 'grey' || s === 'blue') return;
        total++;
        if (s === 'green') withinCap++;
        if (s === 'amber' || s === 'red') benefitOverages[k] = (benefitOverages[k] ?? 0) + 1;
      });
      const v = c.spend - c.budget;
      if (v > 0) { overageSum += v; overageCount++; }
    });

    const mostOver = Object.entries(benefitOverages).sort((a, b) => b[1] - a[1])[0];
    return {
      compliance: total > 0 ? Math.round((withinCap / total) * 100) : 0,
      active: cases.length,
      avgOverage: overageCount > 0 ? Math.round(overageSum / overageCount) : 0,
      mostOver: mostOver
        ? { key: mostOver[0], count: mostOver[1], total: cases.length }
        : null,
    };
  }, [cases]);

  const benefitsByCategory = useMemo(() => groupByCategory(BENEFITS), []);

  const complianceTone = complianceToneForPct(kpis.compliance);
  const complianceCls = {
    green: 'text-emerald-700 bg-emerald-50 ring-1 ring-emerald-200',
    amber: 'text-amber-700 bg-amber-50 ring-1 ring-amber-200',
    red:   'text-rose-700 bg-rose-50 ring-1 ring-rose-200',
  }[complianceTone];

  const activeCase = activeCaseId ? cases.find((c) => c.id === activeCaseId) ?? null : null;
  const activeIdx = activeCase ? cases.findIndex((c) => c.id === activeCaseId) : -1;

  return (
    <AppShell wide>
      {/* Page header */}
      <div className="px-6 py-5 border-b border-slate-100">
        <p className="text-xs text-slate-400 mb-0.5">HR · /hr/policy-vs-reality</p>
        <div className="flex items-end gap-3">
          <h1 className="text-xl font-semibold text-slate-900">Policy vs. Reality</h1>
          <div className="flex-1" />
          <Button unstyled className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors">
            <svg className="w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export CSV
          </Button>
        </div>
        <p className="mt-1 text-sm text-slate-500">
          Compare your company's policy commitments against what employees are actually selecting from service providers.
        </p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 px-6 py-3 border-b border-slate-100 bg-slate-50/60 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Destination:</span>
          <select
            value={destFilter}
            onChange={(e) => setDestFilter(e.target.value)}
            className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white focus:outline-none"
          >
            <option value="all">All countries</option>
            {['NO', 'DE', 'US', 'JP', 'SG', 'CA', 'NL', 'AU'].map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Tier:</span>
          <select
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value)}
            className="text-xs border border-slate-200 rounded-md px-2 py-1 bg-white focus:outline-none"
          >
            <option value="all">All tiers</option>
            {['Manager', 'Director', 'VP'].map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </div>
        <div className="flex-1" />
        <label className="flex items-center gap-2 text-xs text-slate-500 cursor-pointer">
          <input
            type="checkbox"
            checked={privacy}
            onChange={(e) => setPrivacy(e.target.checked)}
            className="rounded"
          />
          Privacy mode
        </label>
      </div>

      <div className="px-6 py-6 space-y-8">
        {/* KPI strip */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className={`rounded-xl border px-5 py-4 ${complianceCls}`}>
            <p className="text-[10px] font-semibold uppercase tracking-wider mb-2 opacity-70">Policy compliance</p>
            <p className="text-3xl font-semibold">{kpis.compliance}<span className="text-lg ml-0.5">%</span></p>
            <p className="text-xs mt-1 opacity-70">↑ 4% vs last quarter</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white px-5 py-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-2">Active relocations</p>
            <p className="text-3xl font-semibold text-slate-900">{kpis.active}</p>
            <p className="text-xs text-slate-400 mt-1">
              {cases.filter((c) => c.type === 'long_term').length} long-term ·{' '}
              {cases.filter((c) => c.type === 'short_term').length} short-term ·{' '}
              {cases.filter((c) => c.type === 'permanent').length} permanent
            </p>
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 text-amber-800 px-5 py-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider mb-2 opacity-70">Avg overage / case</p>
            <p className="text-3xl font-semibold">{fmt(kpis.avgOverage)}</p>
            <p className="text-xs mt-1 opacity-70">Across cases with at least one overage</p>
          </div>
          <div className="rounded-xl border border-rose-200 bg-rose-50 text-rose-800 px-5 py-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider mb-2 opacity-70">Most exceeded benefit</p>
            <p className="text-sm font-semibold leading-snug">
              {kpis.mostOver
                ? BENEFITS.find((b) => b.key === kpis.mostOver!.key)?.label ?? '—'
                : '—'}
            </p>
            <p className="text-xs mt-1 opacity-70">
              {kpis.mostOver
                ? `Exceeded in ${kpis.mostOver.count} of ${kpis.mostOver.total} cases`
                : 'No overages'}
            </p>
          </div>
        </div>

        {/* Heatmap */}
        <section>
          <div className="flex items-baseline gap-2 mb-3">
            <h2 className="text-sm font-semibold text-slate-800">Compliance heatmap</h2>
            <p className="text-xs text-slate-400">Each cell = one benefit × one case. Hover for details.</p>
          </div>

          {/* Legend */}
          <div className="flex items-center gap-4 mb-3">
            {(['green', 'amber', 'red', 'grey', 'blue'] as CellStatus[]).map((s) => (
              <div key={s} className="flex items-center gap-1.5">
                <span className={`w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold ${CELL_STYLES[s]}`}>
                  {CELL_CHAR[s]}
                </span>
                <span className="text-xs text-slate-400">
                  {s === 'green' ? 'Within cap' : s === 'amber' ? 'Soft overage' : s === 'red' ? 'Hard overage' : s === 'blue' ? 'Pending' : 'N/A'}
                </span>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
            <table className="text-xs w-full min-w-[640px]">
              <thead>
                <tr className="border-b border-slate-100">
                  <th className="text-left px-4 py-2.5 text-slate-500 font-medium w-48 border-r border-slate-100">Benefit</th>
                  {cases.map((c, i) => (
                    <th key={c.id} className="px-2 py-2.5 text-center font-medium text-slate-500 w-10" title={privacy ? undefined : c.name}>
                      {privacy ? `#${i + 1}` : c.initials}
                    </th>
                  ))}
                  <th className="px-3 py-2.5 text-right text-slate-400 font-medium w-24">Summary</th>
                </tr>
              </thead>
              <tbody>
                {Array.from(benefitsByCategory).map(([cat, blist]) => (
                  <>
                    <tr key={`cat-${cat}`} className="bg-slate-50">
                      <td colSpan={cases.length + 2} className="px-4 py-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider border-t border-slate-100">
                        {cat}
                      </td>
                    </tr>
                    {blist.map((b) => {
                      const rowVals = cases.map((c) => c.cells[b.key] ?? 'grey');
                      const exceeded = rowVals.filter((v) => v === 'amber' || v === 'red').length;
                      return (
                        <tr key={b.key} className="border-t border-slate-50 hover:bg-slate-50/50">
                          <td className="px-4 py-2 text-slate-600 border-r border-slate-100">{b.label}</td>
                          {cases.map((c) => {
                            const s = c.cells[b.key] ?? 'grey';
                            const tip = `${b.label} · ${privacy ? c.initials : c.name} · ${s === 'green' ? 'within cap' : s === 'amber' ? 'soft overage' : s === 'red' ? 'hard overage' : s === 'blue' ? 'pending' : 'n/a'}`;
                            return (
                              <td key={c.id} className="px-1 py-2 text-center" title={tip}>
                                <span className={`inline-flex w-5 h-5 items-center justify-center rounded text-[10px] font-bold ${CELL_STYLES[s]}`}>
                                  {CELL_CHAR[s]}
                                </span>
                              </td>
                            );
                          })}
                          <td className="px-3 py-2 text-right">
                            <span className={`text-[11px] font-medium ${exceeded > 3 ? 'text-rose-500' : exceeded > 0 ? 'text-amber-500' : 'text-slate-400'}`}>
                              {exceeded}/{cases.length} {exceeded > 0 ? 'exceeded' : 'ok'}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </>
                ))}
                {/* Compliance summary row */}
                <tr className="border-t-2 border-slate-200 bg-slate-50">
                  <td className="px-4 py-2.5 text-xs font-semibold text-slate-600 border-r border-slate-100">Compliance</td>
                  {cases.map((c) => {
                    const cs = caseStats(c);
                    const tone = complianceToneForPct(cs.pct);
                    const cls = { green: 'text-emerald-600', amber: 'text-amber-600', red: 'text-rose-600' }[tone];
                    return (
                      <td key={c.id} className="px-1 py-2.5 text-center">
                        <span className={`text-[11px] font-semibold ${cls}`}>{cs.pct}%</span>
                      </td>
                    );
                  })}
                  <td />
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* Per-case table */}
        <section>
          <div className="flex items-baseline gap-2 mb-3">
            <h2 className="text-sm font-semibold text-slate-800">Per-case detail</h2>
            <p className="text-xs text-slate-400">{cases.length} active assignment{cases.length === 1 ? '' : 's'} — click any row for a breakdown.</p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white overflow-x-auto">
            <table className="w-full text-sm min-w-[800px]">
              <thead>
                <tr className="border-b border-slate-100 text-left">
                  {['Case', 'Corridor', 'Tier', 'Type', 'Compliance', 'Overages', 'Policy budget', 'Actual spend', 'Variance', 'Status', ''].map((h) => (
                    <th key={h} className="px-4 py-3 text-xs font-medium text-slate-400">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cases.map((c, i) => {
                  const cs = caseStats(c);
                  const tone = complianceToneForPct(cs.pct);
                  const variance = c.spend - c.budget;
                  const displayName = privacy ? `Case #${i + 1}` : c.name;
                  const displayInitials = privacy ? `#${i + 1}` : c.initials;
                  return (
                    <tr
                      key={c.id}
                      onClick={() => setActiveCaseId(c.id)}
                      className="border-t border-slate-50 hover:bg-slate-50 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-full bg-slate-200 text-slate-600 text-xs font-semibold flex items-center justify-center shrink-0">
                            {displayInitials}
                          </div>
                          <span className="text-slate-800 font-medium">{displayName}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-slate-600">{c.flag} {c.corridor}</td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 ring-1 ring-blue-200">{c.tier}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600">{c.type.replace('_', '-')}</span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 bg-slate-100 rounded-full w-16">
                            <div
                              className={`h-full rounded-full ${COMPLIANCE_BAR[tone]}`}
                              style={{ width: `${cs.pct}%` }}
                            />
                          </div>
                          <span className={`text-xs font-semibold ${{ green: 'text-emerald-600', amber: 'text-amber-600', red: 'text-rose-600' }[tone]}`}>
                            {cs.pct}%
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {cs.over > 0
                          ? <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700 ring-1 ring-rose-200">{cs.over}</span>
                          : <span className="text-slate-300 text-xs">0</span>}
                      </td>
                      <td className="px-4 py-3 text-slate-600 font-mono text-xs">{fmt(c.budget)}</td>
                      <td className="px-4 py-3 text-slate-600 font-mono text-xs">{fmt(c.spend)}</td>
                      <td className="px-4 py-3 font-mono text-xs">
                        <span className={variance > 0 ? 'text-rose-600' : 'text-emerald-600'}>
                          {variance > 0 ? '+' : ''}{fmt(Math.abs(variance))}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-500">{c.status}</td>
                      <td className="px-4 py-3 text-xs font-medium text-blue-600">View →</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* Policy calibration banner */}
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-5 py-4">
          <svg className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div>
            <p className="text-sm font-semibold text-amber-800">
              Your housing cap in Germany (€2,500/mo) covers only 58% of actual selections over the last 12 months.
            </p>
            <p className="text-sm text-amber-700 mt-0.5">
              The market has moved — consider revising to €2,900/mo to align with current provider pricing.
            </p>
            <Button unstyled className="mt-2 text-xs font-semibold text-amber-700 underline underline-offset-2 hover:text-amber-900 transition-colors">
              Update policy →
            </Button>
          </div>
        </div>
      </div>

      {/* Case detail drawer */}
      {activeCase && (
        <CaseDrawer
          c={activeCase}
          caseIdx={activeIdx}
          privacy={privacy}
          onClose={() => setActiveCaseId(null)}
          onPrev={() => {
            const prev = cases[activeIdx - 1];
            if (prev) setActiveCaseId(prev.id);
          }}
          onNext={() => {
            const next = cases[activeIdx + 1];
            if (next) setActiveCaseId(next.id);
          }}
          hasPrev={activeIdx > 0}
          hasNext={activeIdx < cases.length - 1}
        />
      )}
    </AppShell>
  );
}
