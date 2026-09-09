import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, StatCard } from '../../../components/antigravity';
import { CountryFlag } from '../../../components/antigravity/CountryFlag';
import type { CoverageCountry, CoverageSummary } from '../../../api/coverage';

export const CAT_LABELS: Record<string, string> = {
  movers: 'Movers',
  housing_agencies: 'Housing',
  living_areas: 'Housing',
  legal_admin: 'Legal',
  tax_finance: 'Tax',
  banks: 'Banks',
  schools: 'Schools',
  insurance: 'Insurance',
  transport: 'Transport',
  electricity: 'Electricity',
  medical: 'Medical',
  telecom: 'Telecom',
  childcare: 'Childcare',
  storage: 'Storage',
  language_integration: 'Language',
  healthcare_ipmi: 'Health',
};

export function categoryLabel(key: string): string {
  return CAT_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

const fmt = (n: number): string => n.toLocaleString('en-US');

function catDetail(c: CoverageCountry, key: string) {
  return c.providers.by_cat_detail[key] ?? { approved: 0, pending: 0, total: 0 };
}

function cellClass(approved: number, pending: number, hatched: boolean): string {
  const base = 'inline-flex h-8 min-w-[2.25rem] items-center justify-center rounded-md font-mono text-[11px] tabular-nums';
  if (approved <= 0 && pending <= 0) {
    return `${base} bg-slate-50 text-slate-500 ${hatched ? 'border border-dashed border-slate-200' : ''}`;
  }
  if (approved <= 0) return `${base} bg-amber-50 text-amber-800`;
  if (approved >= 8) return `${base} bg-accent-700 text-white`;
  if (approved >= 4) return `${base} bg-accent-500 text-white`;
  if (approved >= 2) return `${base} bg-accent-100 text-accent-800`;
  return `${base} bg-accent-50 text-accent-700`;
}

export type CoverageLens = 'catalog' | 'suppliers';

interface Props {
  data: CoverageSummary;
  lens: CoverageLens;
}

/**
 * Destinations × services heatmap — live fill from requirement facts + provider
 * capabilities. Catalog lens emphasises immigration facts; suppliers lens
 * drills into the registry from a cell click.
 */
export const CoverageMasterGrid: React.FC<Props> = ({ data, lens }) => {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [liveOnly, setLiveOnly] = useState(false);
  const [populatedOnly, setPopulatedOnly] = useState(false);

  const serving = data.serving_categories;
  const extra = data.extra_categories ?? [];

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return data.countries.filter((c) => {
      if (q && !c.name.toLowerCase().includes(q) && !c.iso.toLowerCase().includes(q)) return false;
      if (liveOnly && c.facts.approved === 0 && c.providers.approved === 0) return false;
      if (populatedOnly && c.facts.total === 0 && c.providers.total === 0) return false;
      return true;
    });
  }, [data.countries, query, liveOnly, populatedOnly]);

  const t = data.totals;
  const th = 'px-1.5 py-3 text-center text-[10.5px] font-semibold uppercase tracking-wide text-slate-500 whitespace-nowrap';

  const goFacts = (c: CoverageCountry) => {
    const code = encodeURIComponent(c.catalog_name || c.name.toUpperCase());
    navigate(`/admin/countries/${code}`);
  };

  const goRegistry = (iso: string, category?: string) => {
    const params = new URLSearchParams();
    params.set('country', iso);
    if (category) params.set('category', category);
    navigate(`/admin/suppliers/registry?${params.toString()}`);
  };

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard emphasis label="Destinations" value={t.destinations} sub="with facts or providers in the database" />
        <StatCard
          label="Requirement facts"
          value={fmt(t.facts_total)}
          sub={`${fmt(t.facts_approved)} approved · ${fmt(t.facts_pending)} pending`}
        />
        <StatCard
          label="Provider capabilities"
          value={fmt(t.caps_total)}
          sub={`${fmt(t.caps_approved)} approved · ${fmt(t.suppliers)} suppliers`}
        />
        <StatCard
          label={lens === 'suppliers' ? 'Awaiting vetting' : 'Expert-verified facts'}
          value={lens === 'suppliers' ? fmt(t.caps_pending) : fmt(t.expert_verified)}
          sub={lens === 'suppliers' ? 'capabilities not yet live' : 'highest-confidence served facts'}
        />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="sr-only" htmlFor="coverage-search">Filter destinations</label>
        <input
          id="coverage-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter destinations…"
          className="h-11 w-56 rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800 placeholder:text-slate-500"
        />
        <label className="flex min-h-11 items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={liveOnly} onChange={(e) => setLiveOnly(e.target.checked)} />
          Serving only
        </label>
        <label className="flex min-h-11 items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={populatedOnly} onChange={(e) => setPopulatedOnly(e.target.checked)} />
          Hide empty
        </label>
        <div className="ml-auto flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
          <span className="inline-flex items-center gap-1.5"><span className="h-3 w-4 rounded bg-accent-100" />Approved</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-3 w-4 rounded bg-amber-50 ring-1 ring-amber-200" />Pending review</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-3 w-4 rounded border border-dashed border-slate-200 bg-slate-50" />Empty / not serving-capable</span>
        </div>
      </div>

      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[920px] border-collapse" data-testid="coverage-master-grid">
          <thead>
            <tr className="border-b border-slate-200">
              <th className={`${th} pl-4 text-left`}>Destination</th>
              <th className={th}>Facts</th>
              {serving.map((k) => (
                <th key={k} className={`${th} text-accent-700`}>{categoryLabel(k)}</th>
              ))}
              {extra.map((k) => (
                <th key={k} className={`${th} text-slate-500`}>{categoryLabel(k)}</th>
              ))}
              <th className={th}>Providers</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.iso} className="hover:bg-slate-50">
                <td className="h-11 border-b border-slate-100 pl-4">
                  <button
                    type="button"
                    className="flex min-h-11 items-center text-left"
                    onClick={() => (lens === 'suppliers' ? goRegistry(c.iso) : goFacts(c))}
                  >
                    <CountryFlag country={c.name} className="font-semibold text-slate-800" />
                    {c.facts.approved > 0 && (
                      <span className="ml-2 text-[9.5px] font-bold uppercase tracking-wide text-accent-600">Serving</span>
                    )}
                  </button>
                </td>
                <td className="h-11 border-b border-slate-100 text-center">
                  <button
                    type="button"
                    className={cellClass(c.facts.approved, c.facts.pending, false)}
                    title={`${c.name}: ${c.facts.approved} approved / ${c.facts.pending} pending facts`}
                    onClick={() => goFacts(c)}
                  >
                    {c.facts.approved > 0 ? c.facts.approved : c.facts.pending > 0 ? c.facts.pending : '·'}
                  </button>
                </td>
                {serving.map((k) => {
                  const d = catDetail(c, k);
                  return (
                    <td key={k} className="h-11 border-b border-slate-100 text-center">
                      <button
                        type="button"
                        className={cellClass(d.approved, d.pending, false)}
                        title={`${c.name} · ${categoryLabel(k)}: ${d.approved} approved / ${d.pending} pending`}
                        onClick={() => goRegistry(c.iso, k)}
                      >
                        {d.approved > 0 ? d.approved : d.pending > 0 ? d.pending : '·'}
                      </button>
                    </td>
                  );
                })}
                {extra.map((k) => {
                  const d = catDetail(c, k);
                  return (
                    <td key={k} className="h-11 border-b border-slate-100 text-center">
                      <button
                        type="button"
                        className={cellClass(d.approved, d.pending, true)}
                        title={`${c.name} · ${categoryLabel(k)} (not a serving category)`}
                        onClick={() => goRegistry(c.iso, k)}
                      >
                        {d.total > 0 ? d.total : '·'}
                      </button>
                    </td>
                  );
                })}
                <td className="h-11 border-b border-slate-100 text-center font-mono text-[13px] font-semibold tabular-nums text-navy-800">
                  {c.providers.total || '·'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && (
          <p className="px-4 py-10 text-center text-sm text-slate-500">No destinations match these filters.</p>
        )}
      </Card>
    </div>
  );
};
