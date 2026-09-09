import React, { useMemo, useState } from 'react';
import { ChevronRight, Search } from 'lucide-react';
import { Badge } from '../antigravity/Badge';
import { Button } from '../antigravity/Button';
import { CountryFlag } from '../antigravity/CountryFlag';
import { Input } from '../antigravity/Input';
import type { CountryListDTO } from '../../types';
import {
  type CatalogAttention,
  type CatalogSortKey,
  type CountryListRow,
  catalogConfidenceScore,
  confidenceLevel,
  confidencePercent,
  displayCountryName,
  filterCatalog,
  formatUpdatedLabel,
  isCatalogStale,
  sortCatalog,
  summarizeCatalog,
} from './countryCatalog';

interface CountryTableProps {
  data: CountryListDTO;
  onSelect: (countryCode: string) => void;
}

const ATTENTION: { id: CatalogAttention; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'empty', label: 'Empty catalog' },
  { id: 'refresh', label: 'Needs refresh' },
];

const SORT_OPTIONS: { value: CatalogSortKey; label: string }[] = [
  { value: 'name', label: 'Name' },
  { value: 'requirements', label: 'Requirements' },
  { value: 'confidence', label: 'Confidence' },
  { value: 'updated', label: 'Last updated' },
];

function ConfidenceMark({ score }: { score: number | undefined }) {
  const level = confidenceLevel(score);
  const pct = confidencePercent(score);
  if (level === 'unknown') {
    return <Badge variant="neutral" size="sm">No catalog</Badge>;
  }
  const variant = level === 'high' ? 'success' : level === 'medium' ? 'warning' : 'error';
  const label = level === 'high' ? 'High' : level === 'medium' ? 'Medium' : 'Low';
  return (
    <div className="min-w-[7.5rem]">
      <div className="mb-1 flex items-center justify-between gap-2">
        <Badge variant={variant} size="sm">{label}</Badge>
        <span className="font-mono text-xs text-slate-500">{pct}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100" aria-hidden="true">
        <div
          className={`h-full rounded-full ${
            level === 'high' ? 'bg-accent-500' : level === 'medium' ? 'bg-amber-600' : 'bg-rose-700'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function RequirementCount({ count, max }: { count: number; max: number }) {
  const width = max > 0 ? Math.max(8, Math.round((count / max) * 100)) : 0;
  return (
    <div className="min-w-[5.5rem]">
      <div className="font-mono text-sm font-semibold text-navy-800">{count}</div>
      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100" aria-hidden="true">
        <div className="h-full rounded-full bg-navy-800" style={{ width: `${count === 0 ? 0 : width}%` }} />
      </div>
    </div>
  );
}

function DomainChips({ domains }: { domains: string[] }) {
  if (domains.length === 0) {
    return <span className="text-xs text-slate-500">No sources yet</span>;
  }
  const shown = domains.slice(0, 3);
  const extra = domains.length - shown.length;
  return (
    <div className="flex flex-wrap gap-1">
      {shown.map((domain) => (
        <span
          key={domain}
          className="max-w-[10rem] truncate rounded-md bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-slate-600"
          title={domain}
        >
          {domain}
        </span>
      ))}
      {extra > 0 && (
        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500">+{extra}</span>
      )}
    </div>
  );
}

function CountryIdentity({ code }: { code: string }) {
  const name = displayCountryName(code);
  return (
    <span className="flex min-w-0 items-center gap-3">
      <CountryFlag country={code} label={name} className="min-w-0 text-sm font-semibold text-navy-800" />
      <span className="shrink-0 font-mono text-[11px] uppercase tracking-wide text-slate-500">{code}</span>
    </span>
  );
}

export const CountryTable: React.FC<CountryTableProps> = ({ data, onSelect }) => {
  const [query, setQuery] = useState('');
  const [attention, setAttention] = useState<CatalogAttention>('all');
  const [sort, setSort] = useState<CatalogSortKey>('name');
  const now = useMemo(() => new Date(), []);
  const summary = useMemo(() => summarizeCatalog(data.countries, now), [data.countries, now]);
  const rows = useMemo(
    () => sortCatalog(filterCatalog(data.countries, query, attention, now), sort),
    [data.countries, query, attention, sort, now],
  );
  const maxRequirements = Math.max(1, ...data.countries.map((row) => row.requirementsCount || 0));

  return (
    <div className="space-y-4" data-testid="country-table">
      {/* fix: BUG-260908-9601 — catalog summary so coverage gaps are visible without scanning every row */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <SummaryTile
          testId="catalog-stat-countries"
          label="Destinations"
          value={summary.countries}
          selected={attention === 'all'}
          onSelect={() => setAttention('all')}
        />
        <SummaryTile
          testId="catalog-stat-requirements"
          label="Requirements"
          value={summary.requirements}
          onSelect={() => { setAttention('all'); setSort('requirements'); }}
        />
        <SummaryTile
          testId="catalog-stat-empty"
          label="Empty catalogs"
          value={summary.empty}
          tone={summary.empty > 0 ? 'warn' : 'ok'}
          selected={attention === 'empty'}
          onSelect={() => setAttention('empty')}
        />
        <SummaryTile
          testId="catalog-stat-refresh"
          label="Needs refresh"
          value={summary.needsRefresh}
          tone={summary.needsRefresh > 0 ? 'warn' : 'ok'}
          selected={attention === 'refresh'}
          onSelect={() => setAttention('refresh')}
        />
      </div>

      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="relative w-full md:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
          <Input
            unstyled
            value={query}
            onChange={setQuery}
            placeholder="Search country, code, or source domain"
            aria-label="Search country catalogs"
            className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm text-navy-800 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-navy-800"
          />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5" role="group" aria-label="Filter catalog">
            {ATTENTION.map((opt) => (
              <Button
                key={opt.id}
                unstyled
                onClick={() => setAttention(opt.id)}
                aria-pressed={attention === opt.id}
                className={`rounded-md px-3 py-1.5 text-xs font-medium ${
                  attention === opt.id
                    ? 'bg-navy-50 text-navy-800'
                    : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                {opt.label}
              </Button>
            ))}
          </div>
          <label className="flex items-center gap-2 text-xs text-slate-600">
            Sort
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as CatalogSortKey)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-navy-800 focus:outline-none focus:ring-2 focus:ring-navy-800"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-10 text-center text-sm text-slate-600">
          {data.countries.length === 0
            ? 'No destination catalogs yet.'
            : 'No countries match this search or filter.'}
        </div>
      ) : (
        <>
          <p className="text-xs text-slate-500">
            Showing {rows.length} of {data.countries.length} destinations
          </p>
          <div className="space-y-2 md:hidden">
            {rows.map((row) => (
              <CountryCard key={row.countryCode} row={row} now={now} max={maxRequirements} onSelect={onSelect} />
            ))}
          </div>
          <div className="hidden overflow-x-auto rounded-xl border border-slate-200 md:block">
            <div className="min-w-[56rem]">
            <div
              className="grid grid-cols-[minmax(14rem,1.6fr)_8.5rem_7rem_9rem_minmax(10rem,1fr)_1.5rem] gap-4 bg-slate-50 px-4 py-3 text-[11px] font-semibold uppercase tracking-wide text-slate-500"
              role="row"
            >
              <div>Country</div>
              <div>Last updated</div>
              <div>Requirements</div>
              <div>Confidence</div>
              <div>Top sources</div>
              <div className="sr-only">Open</div>
            </div>
            {rows.map((row) => {
              const updated = formatUpdatedLabel(row.lastUpdatedAt, now);
              const stale = isCatalogStale(row.lastUpdatedAt, now);
              return (
                <Button
                  key={row.countryCode}
                  unstyled
                  onClick={() => onSelect(row.countryCode)}
                  className="grid w-full grid-cols-[minmax(14rem,1.6fr)_8.5rem_7rem_9rem_minmax(10rem,1fr)_1.5rem] gap-4 border-t border-slate-200 px-4 py-3 text-left hover:bg-navy-50"
                >
                  <CountryIdentity code={row.countryCode} />
                  <div>
                    <div className="text-sm text-navy-800">{updated.relative}</div>
                    <div className="text-xs text-slate-500">{updated.absolute}</div>
                    {stale && <Badge variant="warning" size="sm">Needs refresh</Badge>}
                  </div>
                  <RequirementCount count={row.requirementsCount} max={maxRequirements} />
                  <ConfidenceMark score={catalogConfidenceScore(row.confidenceScore, row.requirementsCount)} />
                  <DomainChips domains={row.topDomains} />
                  <ChevronRight className="mt-1 h-4 w-4 text-slate-500" aria-hidden="true" />
                </Button>
              );
            })}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

function SummaryTile({
  label,
  value,
  testId,
  tone = 'ok',
  selected = false,
  onSelect,
}: {
  label: string;
  value: number;
  testId: string;
  tone?: 'ok' | 'warn';
  selected?: boolean;
  onSelect: () => void;
}) {
  return (
    <Button
      unstyled
      data-testid={testId}
      onClick={onSelect}
      aria-pressed={selected}
      className={`rounded-xl border px-4 py-3 text-left ${
        selected ? 'border-navy-800 bg-navy-50' : 'border-slate-200 bg-white hover:border-navy-800'
      }`}
    >
      <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${tone === 'warn' && value > 0 ? 'text-amber-800' : 'text-navy-800'}`}>
        {value}
      </p>
    </Button>
  );
}

function CountryCard({
  row,
  now,
  max,
  onSelect,
}: {
  row: CountryListRow;
  now: Date;
  max: number;
  onSelect: (code: string) => void;
}) {
  const updated = formatUpdatedLabel(row.lastUpdatedAt, now);
  return (
    <Button
      unstyled
      onClick={() => onSelect(row.countryCode)}
      className="w-full rounded-xl border border-slate-200 bg-white p-4 text-left hover:bg-navy-50"
    >
      <div className="flex items-start justify-between gap-3">
        <CountryIdentity code={row.countryCode} />
        <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-slate-500" aria-hidden="true" />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-slate-500">Updated</p>
          <p className="text-sm text-navy-800">{updated.relative}</p>
          {isCatalogStale(row.lastUpdatedAt, now) && (
            <Badge variant="warning" size="sm">Needs refresh</Badge>
          )}
        </div>
        <RequirementCount count={row.requirementsCount} max={max} />
        <ConfidenceMark score={catalogConfidenceScore(row.confidenceScore, row.requirementsCount)} />
        <DomainChips domains={row.topDomains} />
      </div>
    </Button>
  );
}
