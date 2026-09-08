import React, { useEffect, useMemo, useState } from 'react';
import { AdminLayout } from '../AdminLayout';
import { Alert, Button, Card } from '../../../components/antigravity';
import {
  getCoverage,
  type CoverageCountry,
  type CoverageSummary,
} from '../../../api/coverage';

/**
 * Admin coverage dashboard — the live, in-product equivalent of the "Coverage
 * Master" and "Coverage Gaps" snapshots. Two views over one payload:
 *   • Coverage    — what we've acquired per destination (facts + providers).
 *   • Gaps & focus — the inverse, every destination ranked by what's still missing.
 * Loads the backend's cached snapshot instantly; Refresh forces a live recompute.
 */

// Display order + labels for the six serving service categories.
const CATS: ReadonlyArray<readonly [string, string]> = [
  ['banks', 'Banks'],
  ['movers', 'Movers'],
  ['schools', 'Schools'],
  ['legal_admin', 'Legal'],
  ['tax_finance', 'Tax'],
  ['housing_agencies', 'Housing'],
];
const CAT_KEYS: string[] = CATS.map(([k]) => k);

const fmt = (n: number): string => n.toLocaleString('en-US');
const catVal = (c: CoverageCountry, k: string): number => c.providers.by_cat[k] ?? 0;

type Lane = 'serve' | 'review' | 'gap';
interface Metrics {
  svcMiss: number;
  backlog: number;
  serving: boolean;
  lane: Lane;
  focus: number;
}

function metricsFor(c: CoverageCountry): Metrics {
  const svcHave = CAT_KEYS.filter((k) => catVal(c, k) > 0).length;
  const svcMiss = 6 - svcHave;
  const backlog = Math.max(0, c.providers.total - c.providers.approved);
  const serving = c.facts.approved > 0 || c.providers.approved > 0;
  const lane: Lane = serving
    ? 'serve'
    : c.facts.pending > 0 || c.providers.total > 0
      ? 'review'
      : 'gap';
  const svcG = svcMiss / 6;
  const immG = c.facts.approved > 0 ? 0 : c.facts.total > 0 ? 0.5 : 1;
  const provG = c.providers.approved > 0 ? 0 : c.providers.total > 0 ? 0.4 : 1;
  const focus = Math.round(100 * (0.45 * svcG + 0.3 * immG + 0.25 * provG));
  return { svcMiss, backlog, serving, lane, focus };
}

const LANE_STYLE: Record<Lane, { stripe: string; tag: string; label: string }> = {
  serve: { stripe: 'bg-accent-500', tag: 'bg-accent-50 text-accent-600', label: 'Serving' },
  review: { stripe: 'bg-amber-500', tag: 'bg-amber-50 text-amber-700', label: 'In review' },
  gap: { stripe: 'bg-rose-500', tag: 'bg-rose-50 text-rose-700', label: 'Untouched' },
};

// ── small presentational helpers ────────────────────────────────────────────

const StatTile: React.FC<{ label: string; value: string | number; sub: string; accent?: boolean }> = ({
  label,
  value,
  sub,
  accent,
}) => (
  <div className={`rounded-xl border p-4 ${accent ? 'border-transparent bg-[#0b2b43]' : 'border-slate-200 bg-white'}`}>
    <div className={`text-[11px] font-semibold uppercase tracking-wider ${accent ? 'text-white/60' : 'text-slate-500'}`}>
      {label}
    </div>
    <div className={`mt-1 font-mono text-2xl font-semibold tabular-nums ${accent ? 'text-white' : 'text-navy-800'}`}>
      {value}
    </div>
    <div className={`mt-0.5 text-xs ${accent ? 'text-white/70' : 'text-slate-500'}`}>{sub}</div>
  </div>
);

const SortBar: React.FC<{
  options: ReadonlyArray<readonly [string, string]>;
  value: string;
  onChange: (k: string) => void;
}> = ({ options, value, onChange }) => (
  <div className="flex flex-wrap gap-1.5">
    {options.map(([k, label]) => (
      <button
        key={k}
        type="button"
        aria-pressed={value === k}
        onClick={() => onChange(k)}
        className={`rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors ${
          value === k
            ? 'border-[#0b2b43] bg-[#0b2b43] text-white'
            : 'border-slate-200 bg-white text-slate-600 hover:border-accent-500'
        }`}
      >
        {label}
      </button>
    ))}
  </div>
);

const th = 'px-2 py-3 text-center text-[10.5px] font-semibold uppercase tracking-wide text-slate-500 whitespace-nowrap';
const td = 'px-2 h-11 border-b border-slate-100 text-center text-[13px]';

function NameCell({ c, lane }: { c: CoverageCountry; lane?: Lane }): React.ReactElement {
  return (
    <span className="flex items-center gap-2.5">
      {lane && <span className={`h-5 w-1 shrink-0 rounded-r ${LANE_STYLE[lane].stripe}`} />}
      {c.flag && <span aria-hidden>{c.flag}</span>}
      <span className="py-2.5 font-semibold text-slate-800">{c.name}</span>
      {lane && (
        <span className={`rounded px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-wide ${LANE_STYLE[lane].tag}`}>
          {LANE_STYLE[lane].label}
        </span>
      )}
    </span>
  );
}

// ── Coverage (Master) view — what we've acquired ────────────────────────────

const MASTER_SORTS = [
  ['tot', 'Most coverage'],
  ['facts', 'Facts'],
  ['prov', 'Providers'],
  ['served', 'Serving'],
  ['az', 'A–Z'],
] as const;

const masterSorters: Record<string, (a: CoverageCountry, b: CoverageCountry) => number> = {
  tot: (a, b) => b.facts.total + b.providers.total - (a.facts.total + a.providers.total),
  facts: (a, b) => b.facts.total - a.facts.total,
  prov: (a, b) => b.providers.total - a.providers.total,
  served: (a, b) => b.facts.approved - a.facts.approved || b.providers.approved - a.providers.approved,
  az: (a, b) => a.name.localeCompare(b.name),
};

const CoverageView: React.FC<{ data: CoverageSummary }> = ({ data }) => {
  const [sort, setSort] = useState<string>('tot');
  const rows = useMemo(
    () => [...data.countries].sort(masterSorters[sort] ?? masterSorters.tot),
    [data.countries, sort],
  );
  const t = data.totals;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile accent label="Destinations" value={t.destinations} sub="with facts or providers" />
        <StatTile label="Facts" value={fmt(t.facts_total)} sub={`${t.facts_approved} approved · ${t.facts_pending} pending`} />
        <StatTile label="Provider capabilities" value={fmt(t.caps_total)} sub={`${t.caps_approved} approved · ${fmt(t.suppliers)} suppliers`} />
        <StatTile label="Serving now" value={t.facts_approved} sub="reviewed facts live to users" />
      </div>

      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-bold text-navy-800">Coverage by destination &amp; service</h3>
        <SortBar options={MASTER_SORTS} value={sort} onChange={setSort} />
      </div>

      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[820px] border-collapse">
          <thead>
            <tr className="border-b border-slate-200">
              <th className={`${th} pl-4 text-left`}>Destination</th>
              <th className={th}>Facts · appr / pend</th>
              {CATS.map(([k, label]) => (
                <th key={k} className={`${th} text-accent-600`}>{label}</th>
              ))}
              <th className={th}>Providers</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.iso} className="hover:bg-slate-50">
                <td className={`${td} pl-4 text-left`}>
                  <span className="flex items-center gap-2.5">
                    {c.flag && <span aria-hidden>{c.flag}</span>}
                    <span className="font-semibold text-slate-800">{c.name}</span>
                    {c.facts.approved > 0 && (
                      <span className="text-[9.5px] font-bold uppercase tracking-wide text-accent-600">◆ Serving</span>
                    )}
                  </span>
                </td>
                <td className={td}>
                  <span className="font-mono text-xs tabular-nums text-slate-600">
                    {c.facts.approved > 0 ? (
                      <span className="font-semibold text-navy-800">{c.facts.approved}</span>
                    ) : (
                      <span className="text-slate-500">0</span>
                    )}
                    {' / '}
                    {c.facts.pending}
                  </span>
                </td>
                {CAT_KEYS.map((k) => {
                  const v = catVal(c, k);
                  return (
                    <td key={k} className={td}>
                      <span className={`font-mono text-xs tabular-nums ${v > 0 ? 'text-slate-700' : 'text-slate-500'}`}>
                        {v > 0 ? v : '·'}
                      </span>
                    </td>
                  );
                })}
                <td className={td}>
                  <span className="font-mono text-[13px] font-semibold tabular-nums text-navy-800">
                    {c.providers.total || '·'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
};

// ── Gaps & focus view — what's still missing ────────────────────────────────

const GAP_SORTS = [
  ['focus', 'Biggest gaps'],
  ['quick', 'Quick wins'],
  ['svc', 'Services missing'],
  ['prov', 'Vetting backlog'],
  ['az', 'A–Z'],
] as const;

const gapSorters: Record<string, (a: CoverageCountry, b: CoverageCountry) => number> = {
  focus: (a, b) => metricsFor(b).focus - metricsFor(a).focus || a.name.localeCompare(b.name),
  quick: (a, b) => {
    const ma = metricsFor(a);
    const mb = metricsFor(b);
    return (
      Number(ma.serving) - Number(mb.serving) ||
      b.facts.pending + mb.backlog - (a.facts.pending + ma.backlog) ||
      a.name.localeCompare(b.name)
    );
  },
  svc: (a, b) => metricsFor(b).svcMiss - metricsFor(a).svcMiss || metricsFor(b).focus - metricsFor(a).focus,
  prov: (a, b) => metricsFor(b).backlog - metricsFor(a).backlog || a.name.localeCompare(b.name),
  az: (a, b) => a.name.localeCompare(b.name),
};

function ImmCell({ c }: { c: CoverageCountry }): React.ReactElement {
  if (c.facts.approved > 0) {
    return (
      <span className="font-mono text-xs tabular-nums text-accent-600">
        ◆ <span className="font-semibold">{c.facts.approved}</span> live
        {c.facts.pending > 0 ? ` · ${c.facts.pending}▲` : ''}
      </span>
    );
  }
  if (c.facts.pending > 0) {
    return (
      <span className="font-mono text-xs tabular-nums text-amber-700">
        ▲ <span className="font-semibold">{c.facts.pending}</span> pending
      </span>
    );
  }
  return <span className="font-mono text-xs text-slate-500">— none</span>;
}

const FocusCard: React.FC<{
  rank: string;
  accent: string;
  title: string;
  body: string;
  pills: Array<[string, number]>;
}> = ({ rank, accent, title, body, pills }) => (
  <Card className="relative overflow-hidden">
    <span className={`absolute inset-y-0 left-0 w-1 ${accent}`} />
    <div className="pl-2">
      <div className="font-mono text-[11px] font-semibold tracking-wider text-slate-500">{rank}</div>
      <h4 className="mt-2 text-sm font-bold leading-snug text-navy-800">{title}</h4>
      <p className="mt-1.5 text-xs text-slate-600">{body}</p>
      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {pills.map(([label, n]) => (
          <span key={label} className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-[11.5px] font-semibold text-slate-600">
            {label} <span className="font-mono text-navy-800">{n}</span>
          </span>
        ))}
      </div>
    </div>
  </Card>
);

const GapsView: React.FC<{ data: CoverageSummary }> = ({ data }) => {
  const [sort, setSort] = useState<string>('focus');
  const rows = useMemo(
    () => [...data.countries].sort(gapSorters[sort] ?? gapSorters.focus),
    [data.countries, sort],
  );

  const lanes = useMemo(() => {
    const acc = { serve: 0, review: 0, gap: 0 } as Record<Lane, number>;
    data.countries.forEach((c) => {
      acc[metricsFor(c).lane] += 1;
    });
    return acc;
  }, [data.countries]);

  const notServing = data.countries.filter((c) => !metricsFor(c).serving);
  const emptySlots = data.countries.reduce((s, c) => s + metricsFor(c).svcMiss, 0);
  const provBacklog = data.countries.reduce((s, c) => s + metricsFor(c).backlog, 0);
  const factsPending = data.countries.reduce((s, c) => s + c.facts.pending, 0);

  const unlock: Array<[string, number]> = [...notServing]
    .filter((c) => c.facts.pending > 0)
    .sort((a, b) => b.facts.pending - a.facts.pending)
    .slice(0, 4)
    .map((c) => [c.name, c.facts.pending]);
  const catMiss: Array<[string, number]> = CATS.map(([k, label]) => [
    label,
    data.countries.filter((c) => catVal(c, k) === 0).length,
  ] as [string, number]).sort((a, b) => b[1] - a[1]);
  const thin: Array<[string, number]> = [...data.countries]
    .sort((a, b) => metricsFor(b).focus - metricsFor(a).focus)
    .slice(0, 4)
    .map((c) => [c.name, metricsFor(c).focus]);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile accent label="Not serving yet" value={notServing.length} sub={`of ${data.totals.destinations} destinations`} />
        <StatTile label="Facts awaiting review" value={fmt(factsPending)} sub="approve to go live" />
        <StatTile label="Providers to vet" value={fmt(provBacklog)} sub="found, not yet approved" />
        <StatTile label="Empty service slots" value={emptySlots} sub="category cells with no provider" />
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-[13px] text-slate-600">
        <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-accent-500" />Serving <b className="font-mono text-navy-800">{lanes.serve}</b></span>
        <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-amber-500" />In review <b className="font-mono text-navy-800">{lanes.review}</b></span>
        <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-rose-500" />Untouched <b className="font-mono text-navy-800">{lanes.gap}</b></span>
        <span className="ml-auto text-xs text-slate-500">The bottleneck is approval, not research — every candidate sits behind the review gate.</span>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-bold text-navy-800">Where to focus first</h3>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <FocusCard rank="01 · QUICK WIN" accent="bg-amber-500" title={`${fmt(factsPending)} facts one approval from live`} body="Nothing serves that hasn't been reviewed, so clearing the queue is the fastest gain. Most pending:" pills={unlock} />
          <FocusCard rank="02 · SERVICE WHITESPACE" accent="bg-rose-500" title={`${catMiss[0]?.[0] ?? '—'} is the most common gap`} body="Categories with no provider across the most destinations. One register per category closes the widest gaps:" pills={catMiss.slice(0, 4)} />
          <FocusCard rank="03 · THINNEST OVERALL" accent="bg-[#0b2b43]" title="Deepest gaps by combined score" body="Least service coverage, nothing live, providers unvetted. The destinations needing the most across the board:" pills={thin} />
        </div>
      </div>

      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-bold text-navy-800">Gap board — every destination</h3>
        <SortBar options={GAP_SORTS} value={sort} onChange={setSort} />
      </div>

      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[880px] border-collapse">
          <thead>
            <tr className="border-b border-slate-200">
              <th className={`${th} pl-0 text-left`}>Destination</th>
              <th className={th}>Immigration</th>
              {CATS.map(([k, label]) => (
                <th key={k} className={`${th} text-accent-600`}>{label}</th>
              ))}
              <th className={th}>Providers live / total</th>
              <th className={th}>Focus</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => {
              const m = metricsFor(c);
              return (
                <tr key={c.iso} className="hover:bg-slate-50">
                  <td className={`${td} pl-0 text-left`}>
                    <NameCell c={c} lane={m.lane} />
                  </td>
                  <td className={td}><ImmCell c={c} /></td>
                  {CAT_KEYS.map((k) => {
                    const v = catVal(c, k);
                    return (
                      <td key={k} className={td}>
                        {v > 0 ? (
                          <span className="inline-flex h-6 w-8 items-center justify-center rounded-md border border-slate-200 bg-slate-50 font-mono text-xs text-slate-600">
                            {v}
                          </span>
                        ) : (
                          <span
                            className="inline-flex h-6 w-8 items-center justify-center rounded-md bg-rose-50 font-mono text-xs font-bold text-rose-700"
                            title="no provider"
                          >
                            –
                          </span>
                        )}
                      </td>
                    );
                  })}
                  <td className={td}>
                    <span className="font-mono text-[13px] tabular-nums text-slate-600">
                      <span className="font-semibold text-navy-800">{c.providers.approved}</span> / {c.providers.total}
                      {m.backlog > 0 && <span className="text-amber-700"> +{m.backlog}</span>}
                    </span>
                  </td>
                  <td className={td}>
                    <span className="flex items-center justify-end gap-2 pr-2">
                      <span className="w-6 text-right font-mono text-xs font-semibold tabular-nums text-navy-800">{m.focus}</span>
                      <span className="h-2 w-14 overflow-hidden rounded bg-slate-100">
                        <span className="block h-full rounded bg-rose-500" style={{ width: `${m.focus}%` }} />
                      </span>
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>

      <p className="text-xs text-slate-500">
        Focus score (0–100): 45% missing service categories, 30% immigration status, 25% provider status. Higher = more missing.
      </p>
    </div>
  );
};

// ── Page ────────────────────────────────────────────────────────────────────

export const CoverageDashboardPage: React.FC = () => {
  const [data, setData] = useState<CoverageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<'gaps' | 'master'>('gaps');

  const load = React.useCallback((refresh: boolean) => {
    let active = true;
    if (refresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    getCoverage(refresh)
      .then((d) => {
        if (active) setData(d);
      })
      .catch((e: unknown) => {
        if (!active) return;
        const status = (e as { response?: { status?: number } })?.response?.status;
        setError(
          status === 429
            ? 'Too many admin requests just now — this is a rate limit, not missing data. Retry in a moment.'
            : 'Could not load coverage data.',
        );
      })
      .finally(() => {
        if (active) {
          setLoading(false);
          setRefreshing(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => load(false), [load]);

  const asOf = data ? new Date(data.generated_at).toLocaleString() : '';

  const headerRight = (
    <div className="flex items-center gap-3">
      {data && <span className="hidden text-xs text-slate-500 sm:inline">as of {asOf}</span>}
      <Button size="sm" variant="secondary" onClick={() => load(true)} disabled={loading || refreshing}>
        {refreshing ? 'Refreshing…' : 'Refresh'}
      </Button>
    </div>
  );

  return (
    <AdminLayout
      title="Coverage"
      subtitle="Live acquisition coverage & gaps — immigration facts and vetted providers per destination"
      headerRight={headerRight}
    >
      <Alert variant="info">
        Live from the database. Everything is candidate data behind the human review gate — nothing is served until
        approved at <b>/admin/countries</b> and <b>/admin/vetting-queue</b>.
      </Alert>

      {error && (
        <Alert variant="error" className="mt-3">
          <div className="flex flex-wrap items-center gap-3">
            <span>{error}</span>
            <Button size="sm" variant="secondary" onClick={() => load(false)} disabled={loading || refreshing}>
              {loading ? 'Retrying…' : 'Retry'}
            </Button>
          </div>
        </Alert>
      )}

      <div className="mt-4 inline-flex rounded-lg border border-slate-200 bg-white p-0.5">
        {(['gaps', 'master'] as const).map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => setView(v)}
            aria-pressed={view === v}
            className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${
              view === v ? 'bg-[#0b2b43] text-white' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            {v === 'gaps' ? 'Gaps & focus' : 'Coverage'}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {loading && !data ? (
          <div className="py-16 text-center text-sm text-slate-500">Loading coverage…</div>
        ) : data ? (
          view === 'gaps' ? (
            <GapsView data={data} />
          ) : (
            <CoverageView data={data} />
          )
        ) : null}
      </div>
    </AdminLayout>
  );
};
