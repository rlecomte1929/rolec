import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminLayout } from '../AdminLayout';
import { Alert, Button, Card, StatCard } from '../../../components/antigravity';
import {
  getCoverage,
  type CoverageCountry,
  type CoverageSummary,
} from '../../../api/coverage';
import { buildRoute } from '../../../navigation/routes';
import { CoverageMasterGrid, categoryLabel } from './CoverageMasterGrid';

const CAT_KEYS = ['banks', 'movers', 'schools', 'legal_admin', 'tax_finance', 'housing_agencies'];

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

const GapsView: React.FC<{ data: CoverageSummary }> = ({ data }) => {
  const [sort, setSort] = useState<'focus' | 'az'>('focus');
  const rows = useMemo(() => {
    const next = [...data.countries];
    if (sort === 'az') return next.sort((a, b) => a.name.localeCompare(b.name));
    return next.sort((a, b) => metricsFor(b).focus - metricsFor(a).focus || a.name.localeCompare(b.name));
  }, [data.countries, sort]);

  const notServing = data.countries.filter((c) => !metricsFor(c).serving);
  const emptySlots = data.countries.reduce((s, c) => s + metricsFor(c).svcMiss, 0);
  const provBacklog = data.countries.reduce((s, c) => s + metricsFor(c).backlog, 0);
  const factsPending = data.countries.reduce((s, c) => s + c.facts.pending, 0);
  const lanes = {
    serve: data.countries.filter((c) => metricsFor(c).lane === 'serve').length,
    review: data.countries.filter((c) => metricsFor(c).lane === 'review').length,
    gap: data.countries.filter((c) => metricsFor(c).lane === 'gap').length,
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard emphasis label="Not serving yet" value={notServing.length} sub={`of ${data.totals.destinations} destinations`} />
        <StatCard label="Facts awaiting review" value={fmt(factsPending)} sub="approve to go live" />
        <StatCard label="Providers to vet" value={fmt(provBacklog)} sub="found, not yet approved" />
        <StatCard label="Empty service slots" value={emptySlots} sub="serving category with no provider" />
      </div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-[13px] text-slate-600">
        <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-accent-500" />Serving <b className="font-mono text-navy-800">{lanes.serve}</b></span>
        <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-amber-500" />In review <b className="font-mono text-navy-800">{lanes.review}</b></span>
        <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-rose-500" />Untouched <b className="font-mono text-navy-800">{lanes.gap}</b></span>
      </div>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-bold text-navy-800">Gap board</h3>
        <div className="flex gap-1.5">
          {(['focus', 'az'] as const).map((k) => (
            <button
              key={k}
              type="button"
              aria-pressed={sort === k}
              onClick={() => setSort(k)}
              className={`rounded-lg border px-2.5 py-1 text-xs font-medium ${
                sort === k ? 'border-navy-800 bg-navy-800 text-white' : 'border-slate-200 bg-white text-slate-600'
              }`}
            >
              {k === 'focus' ? 'Biggest gaps' : 'A–Z'}
            </button>
          ))}
        </div>
      </div>
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[720px] border-collapse">
          <thead>
            <tr className="border-b border-slate-200">
              <th className="px-4 py-3 text-left text-[10.5px] font-semibold uppercase tracking-wide text-slate-500">Destination</th>
              <th className="px-2 py-3 text-center text-[10.5px] font-semibold uppercase tracking-wide text-slate-500">Missing services</th>
              <th className="px-2 py-3 text-center text-[10.5px] font-semibold uppercase tracking-wide text-slate-500">Focus</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => {
              const m = metricsFor(c);
              const missing = CAT_KEYS.filter((k) => catVal(c, k) === 0).map(categoryLabel);
              return (
                <tr key={c.iso} className="hover:bg-slate-50">
                  <td className="h-11 border-b border-slate-100 px-4">
                    <span className="flex items-center gap-2.5">
                      <span className={`h-5 w-1 shrink-0 rounded-r ${LANE_STYLE[m.lane].stripe}`} />
                      <span className="font-semibold text-slate-800">{c.name}</span>
                      <span className={`rounded px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-wide ${LANE_STYLE[m.lane].tag}`}>
                        {LANE_STYLE[m.lane].label}
                      </span>
                    </span>
                  </td>
                  <td className="h-11 border-b border-slate-100 px-2 text-center text-xs text-slate-600">
                    {missing.length ? missing.join(', ') : '—'}
                  </td>
                  <td className="h-11 border-b border-slate-100 px-2">
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
    </div>
  );
};

export const CoverageDashboardPage: React.FC = () => {
  const [data, setData] = useState<CoverageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<'master' | 'gaps'>('master');

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

  return (
    <AdminLayout
      title="Coverage"
      subtitle="Live catalog fill — requirement facts and vetted providers per destination"
      headerRight={
        <div className="flex items-center gap-3">
          {data && <span className="hidden text-xs text-slate-500 sm:inline">as of {asOf}</span>}
          <Button size="sm" variant="outline" onClick={() => load(true)} disabled={loading || refreshing}>
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </Button>
        </div>
      }
    >
      <Alert variant="info" className="text-pretty">
        Counts come from the live database. Nothing is served to employees until a human approves it in{' '}
        <Link className="font-medium text-accent-600 hover:text-accent-700" to={buildRoute('adminCountries')}>
          Country requirements
        </Link>{' '}
        or the{' '}
        <Link className="font-medium text-accent-600 hover:text-accent-700" to={buildRoute('adminVettingQueue')}>
          vetting queue
        </Link>
        .
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
        {(['master', 'gaps'] as const).map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => setView(v)}
            aria-pressed={view === v}
            className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${
              view === v ? 'bg-navy-800 text-white' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            {v === 'master' ? 'Coverage master' : 'Gaps & focus'}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {loading && !data ? (
          <div className="py-16 text-center text-sm text-slate-500">Loading coverage…</div>
        ) : data ? (
          view === 'gaps' ? <GapsView data={data} /> : <CoverageMasterGrid data={data} lens="catalog" />
        ) : null}
      </div>
    </AdminLayout>
  );
};
