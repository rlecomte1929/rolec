import { useEffect, useMemo, useState } from 'react';
import type * as React from 'react';
import { Checkbox } from '../../../components/antigravity/Checkbox';
import { Button } from '../../../components/antigravity/Button';
import { AppShell } from '../../../components/AppShell';
import {
  getPolicyComplianceMatrix,
  type ComplianceCaseRow,
  type ComplianceKpis,
} from '../../../api/hrAnalytics';

/**
 * HR Policy vs. Reality — V2.
 *
 * Compliance heatmap comparing policy commitments against what employees
 * are actually selecting from service providers. Four sections:
 *   1. KPI strip (compliance %, active cases, most-exceeded benefit)
 *   2. Compliance heatmap (benefits × cases grid)
 *   3. Per-case table with inline compliance bars
 *   4. Case detail drawer (click a row to open)
 *
 * Backend: GET /api/hr/policy-compliance-matrix
 * Spend columns are GATED ("coming soon") — backend stubs spend to 0/null
 * until real spend tracking is implemented (V2 feature).
 */

// ── Types ─────────────────────────────────────────────────────────────────────

type CellStatus = 'green' | 'amber' | 'red' | 'grey' | 'blue';

// Thin wrapper that normalises the API row into page-friendly fields
interface NormalisedCase {
  id: string;
  name: string;
  initials: string;
  corridor: string;
  destCode: string;
  flag: string;
  tier: string;
  type: string;
  start: string;
  cells: Record<string, CellStatus>;
}

// ── Country-flag helper (dest code → emoji) ────────────────────────────────

const FLAG_MAP: Record<string, string> = {
  AT: '🇦🇹', AU: '🇦🇺', BE: '🇧🇪', BR: '🇧🇷', CA: '🇨🇦', CH: '🇨🇭',
  CN: '🇨🇳', DE: '🇩🇪', DK: '🇩🇰', ES: '🇪🇸', FI: '🇫🇮', FR: '🇫🇷',
  GB: '🇬🇧', HK: '🇭🇰', IE: '🇮🇪', IN: '🇮🇳', IT: '🇮🇹', JP: '🇯🇵',
  KR: '🇰🇷', LU: '🇱🇺', MX: '🇲🇽', NL: '🇳🇱', NO: '🇳🇴', NZ: '🇳🇿',
  PL: '🇵🇱', PT: '🇵🇹', SE: '🇸🇪', SG: '🇸🇬', US: '🇺🇸', ZA: '🇿🇦',
};

function flagOf(code: string | null | undefined): string {
  if (!code) return '🌍';
  return FLAG_MAP[code.toUpperCase()] ?? '🌍';
}

function normaliseCases(apiCases: ComplianceCaseRow[]): NormalisedCase[] {
  return apiCases.map((c) => {
    const origin = c.origin ?? '';
    const dest = c.dest ?? '';
    const corridor = origin && dest ? `${origin}→${dest}` : dest || origin || '—';
    return {
      id: c.id,
      name: c.name,
      initials: c.init,
      corridor,
      destCode: dest,
      flag: flagOf(dest),
      tier: c.tier ?? '—',
      type: c.assignment_type ?? '—',
      start: c.start_date ?? '—',
      cells: (c.cells ?? {}) as Record<string, CellStatus>,
    };
  });
}

// ── Cell styles ────────────────────────────────────────────────────────────────

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

function caseStats(c: NormalisedCase) {
  const values = Object.values(c.cells);
  const countable = values.filter((s) => s !== 'grey' && s !== 'blue');
  const ok = countable.filter((s) => s === 'green').length;
  const over = countable.filter((s) => s === 'amber' || s === 'red').length;
  return {
    pct: countable.length > 0 ? Math.round((ok / countable.length) * 100) : 0,
    over,
  };
}

// ── Spend-gated cell ────────────────────────────────────────────────────────

function SpendComingSoon() {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] text-slate-400 bg-slate-50 ring-1 ring-slate-200 font-medium whitespace-nowrap">
      Spend tracking coming soon
    </span>
  );
}

// ── Case detail drawer ────────────────────────────────────────────────────────

function CaseDrawer({
  c,
  benefitColumns,
  benefitLabels,
  onClose,
  onPrev,
  onNext,
  hasPrev,
  hasNext,
  privacy,
  caseIdx,
}: {
  c: NormalisedCase;
  benefitColumns: string[];
  benefitLabels: Record<string, string>;
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

  const displayName = privacy ? `Case #${caseIdx + 1}` : c.name;
  const displayInitials = privacy ? `#${caseIdx + 1}` : c.initials;

  const toneCls: Record<string, string> = {
    green: 'text-emerald-700 bg-emerald-50 ring-emerald-200',
    amber: 'text-amber-700 bg-amber-50 ring-amber-200',
    red: 'text-rose-700 bg-rose-50 ring-rose-200',
  };

  return (
    <>
      {/* eslint-disable-next-line local/no-clickable-div -- presentational mouse-dismiss overlay (aria-hidden); keyboard users dismiss via the panel's own controls */}
      <div className="fixed inset-0 z-40 bg-black/20" aria-hidden="true" onClick={onClose} />
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
        <div className="grid grid-cols-2 border-b border-slate-100 divide-x divide-slate-100">
          <div className="px-4 py-3">
            <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider mb-0.5">Compliance</p>
            <p className={`text-sm font-semibold px-2 py-0.5 rounded-full ring-1 inline-block ${toneCls[tone]}`}>{pct}%</p>
          </div>
          <div className="px-4 py-3">
            <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider mb-0.5">Budget / spend</p>
            <SpendComingSoon />
          </div>
        </div>

        {/* Benefit table */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Benefit breakdown</p>
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="text-left text-xs text-slate-400 font-medium pb-2">Benefit</th>
                <th className="text-center text-xs text-slate-400 font-medium pb-2 w-16">Status</th>
              </tr>
            </thead>
            <tbody>
              {benefitColumns.map((key) => {
                const status = (c.cells[key] ?? 'grey') as CellStatus;
                return (
                  <tr key={key} className="border-t border-slate-50">
                    <td className="py-1.5 text-slate-700 text-xs">
                      {benefitLabels[key] ?? key}
                    </td>
                    <td className="py-1.5 text-center">
                      <span className={`inline-flex w-5 h-5 items-center justify-center rounded text-[10px] font-bold ${CELL_STYLES[status]}`}>
                        {CELL_CHAR[status]}
                      </span>
                    </td>
                  </tr>
                );
              })}
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

  // ── Data fetch ─────────────────────────────────────────────────────────────
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rawCases, setRawCases] = useState<NormalisedCase[]>([]);
  const [kpis, setKpis] = useState<ComplianceKpis | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getPolicyComplianceMatrix()
      .then((data) => {
        if (cancelled) return;
        setRawCases(normaliseCases(data.cases));
        setKpis(data.kpis);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load compliance data');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  // ── Benefit columns (from KPIs, or empty while loading) ───────────────────
  const benefitColumns = kpis?.benefit_columns ?? [];
  const benefitLabels = kpis?.benefit_labels ?? {};

  // ── Client-side filtering ──────────────────────────────────────────────────
  const cases = useMemo(
    () =>
      rawCases.filter(
        (c) =>
          (destFilter === 'all' || c.destCode === destFilter) &&
          (tierFilter === 'all' || c.tier === tierFilter)
      ),
    [rawCases, destFilter, tierFilter]
  );

  // Derive unique filter options from real data
  const destOptions = useMemo(
    () => Array.from(new Set(rawCases.map((c) => c.destCode).filter(Boolean))).sort(),
    [rawCases]
  );
  const tierOptions = useMemo(
    () => Array.from(new Set(rawCases.map((c) => c.tier).filter((t) => t !== '—'))).sort(),
    [rawCases]
  );

  // ── KPI computations (from API for counts; compliance also from API) ──────
  const compliancePct = kpis?.compliance_pct ?? 0;
  const complianceTone = complianceToneForPct(compliancePct);
  const complianceCls = {
    green: 'text-emerald-700 bg-emerald-50 ring-1 ring-emerald-200',
    amber: 'text-amber-700 bg-amber-50 ring-1 ring-amber-200',
    red:   'text-rose-700 bg-rose-50 ring-1 ring-rose-200',
  }[complianceTone];

  // Most-overrun benefit label (from API)
  const mostOverLabel = kpis?.most_overrun_benefit
    ? (benefitLabels[kpis.most_overrun_benefit] ?? kpis.most_overrun_benefit)
    : null;

  const activeCase = activeCaseId ? cases.find((c) => c.id === activeCaseId) ?? null : null;
  const activeIdx = activeCase ? cases.findIndex((c) => c.id === activeCaseId) : -1;

  // ── Render ────────────────────────────────────────────────────────────────

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
          Compare your company&apos;s policy commitments against what employees are actually selecting from service providers.
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
            {destOptions.map((d) => (
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
            {tierOptions.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </div>
        <div className="flex-1" />
        <label className="flex items-center gap-2 text-xs text-slate-500 cursor-pointer">
          <Checkbox
            checked={privacy}
            onChange={(e) => setPrivacy(e.target.checked)}
            className="rounded"
          />
          Privacy mode
        </label>
      </div>

      <div className="px-6 py-6 space-y-8">

        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center py-20 text-slate-400 text-sm">
            Loading compliance data…
          </div>
        )}

        {/* Error state */}
        {!loading && error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700">
            Could not load compliance data: {error}
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && cases.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <p className="text-slate-500 text-sm font-medium">No active cases yet</p>
            <p className="text-slate-400 text-xs mt-1">Active assignments will appear here once cases are created.</p>
          </div>
        )}

        {/* Main content — only when data is ready */}
        {!loading && !error && cases.length > 0 && (
          <>
            {/* KPI strip */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className={`rounded-xl border px-5 py-4 ${complianceCls}`}>
                <p className="text-[10px] font-semibold uppercase tracking-wider mb-2 opacity-70">Policy compliance</p>
                <p className="text-3xl font-semibold">{compliancePct}<span className="text-lg ml-0.5">%</span></p>
                <p className="text-xs mt-1 opacity-70">Based on active cases</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white px-5 py-4">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-2">Active relocations</p>
                <p className="text-3xl font-semibold text-slate-900">{cases.length}</p>
                <p className="text-xs text-slate-400 mt-1">
                  {cases.filter((c) => c.type === 'long_term').length} long-term ·{' '}
                  {cases.filter((c) => c.type === 'short_term').length} short-term ·{' '}
                  {cases.filter((c) => c.type === 'permanent').length} permanent
                </p>
              </div>
              {/* Spend KPI — gated until V2 spend tracking */}
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-5 py-4">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-2">Avg overage / case</p>
                <SpendComingSoon />
                <p className="text-xs text-slate-400 mt-2">Spend tracking coming in a future release</p>
              </div>
              <div className="rounded-xl border border-rose-200 bg-rose-50 text-rose-800 px-5 py-4">
                <p className="text-[10px] font-semibold uppercase tracking-wider mb-2 opacity-70">Most exceeded benefit</p>
                <p className="text-sm font-semibold leading-snug">
                  {mostOverLabel ?? '—'}
                </p>
                <p className="text-xs mt-1 opacity-70">
                  {kpis?.most_overrun_benefit ? 'Most exception requests' : 'No overages detected'}
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
                      {s === 'green' ? 'Within cap' : s === 'amber' ? 'Low headroom' : s === 'red' ? 'Over cap' : s === 'blue' ? 'Pending exception' : 'N/A'}
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
                    {benefitColumns.map((key) => {
                      const label = benefitLabels[key] ?? key;
                      const rowVals = cases.map((c) => (c.cells[key] ?? 'grey') as CellStatus);
                      const exceeded = rowVals.filter((v) => v === 'amber' || v === 'red').length;
                      return (
                        <tr key={key} className="border-t border-slate-50 hover:bg-slate-50/50">
                          <td className="px-4 py-2 text-slate-600 border-r border-slate-100">{label}</td>
                          {cases.map((c) => {
                            const s = (c.cells[key] ?? 'grey') as CellStatus;
                            const tip = `${label} · ${privacy ? c.initials : c.name} · ${s === 'green' ? 'within cap' : s === 'amber' ? 'low headroom' : s === 'red' ? 'over cap' : s === 'blue' ? 'exception pending' : 'n/a'}`;
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
                <table className="w-full text-sm min-w-[700px]">
                  <thead>
                    <tr className="border-b border-slate-100 text-left">
                      {['Case', 'Corridor', 'Tier', 'Type', 'Compliance', 'Overages', 'Budget / Spend', ''].map((h) => (
                        <th key={h} className="px-4 py-3 text-xs font-medium text-slate-400">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {cases.map((c, i) => {
                      const cs = caseStats(c);
                      const tone = complianceToneForPct(cs.pct);
                      const displayName = privacy ? `Case #${i + 1}` : c.name;
                      const displayInitials = privacy ? `#${i + 1}` : c.initials;
                      return (
                        <tr
                          key={c.id}
                          onClick={() => setActiveCaseId(c.id)}
                          onKeyDown={(e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setActiveCaseId(c.id); } }}
                          role="button"
                          tabIndex={0}
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
                          {/* Spend columns are gated — no real data yet */}
                          <td className="px-4 py-3">
                            <SpendComingSoon />
                          </td>
                          <td className="px-4 py-3 text-xs font-medium text-blue-600">View →</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </div>

      {/* Case detail drawer */}
      {activeCase && (
        <CaseDrawer
          c={activeCase}
          benefitColumns={benefitColumns}
          benefitLabels={benefitLabels}
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
