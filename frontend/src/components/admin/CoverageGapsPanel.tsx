import React, { useMemo, useState } from 'react';
import { Badge, Button, Checkbox } from '../antigravity';
import type { DemandGap } from '../../api/adminCatalog';
import { getCountryName } from '../../utils/countries';

export type CoverageGapGroupBy = 'category' | 'city' | 'country';

function asText(value: string | null | undefined): string {
  return (value ?? '').trim();
}

export function coverageGapKey(g: DemandGap): string {
  return `${asText(g.category)}|${asText(g.city)}|${asText(g.country)}`;
}

function countryLabel(country: string | null | undefined): string {
  const raw = asText(country);
  return getCountryName(raw) || raw || 'Unknown country';
}

function locationLabel(g: DemandGap): string {
  const city = asText(g.city) || 'Unknown city';
  const country = asText(g.country);
  return country ? `${city}, ${countryLabel(country)}` : city;
}

function groupKeyFor(g: DemandGap, by: CoverageGapGroupBy): string {
  if (by === 'category') return asText(g.category).toLowerCase() || 'unknown';
  if (by === 'city') return `${asText(g.city).toLowerCase()}|${asText(g.country).toLowerCase()}`;
  return asText(g.country).toLowerCase() || 'unknown';
}

function groupTitle(g: DemandGap, by: CoverageGapGroupBy): string {
  if (by === 'category') return g.category;
  if (by === 'city') return locationLabel(g);
  return countryLabel(g.country);
}

function rowDetail(g: DemandGap, by: CoverageGapGroupBy): string {
  if (by === 'category') return locationLabel(g);
  if (by === 'city') return g.category;
  return `${g.category} · ${g.city}`;
}

const GROUP_TABS: { id: CoverageGapGroupBy; label: string }[] = [
  { id: 'category', label: 'Service' },
  { id: 'city', label: 'Location' },
  { id: 'country', label: 'Country' },
];

function uniqueSorted(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b, 'en'));
}

function toggleInSet(set: Set<string>, value: string): Set<string> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

export interface CoverageGapsPanelProps {
  gaps: DemandGap[];
  loading: boolean;
  filling: boolean;
  onFill: (gaps: DemandGap[]) => void;
}

export const CoverageGapsPanel: React.FC<CoverageGapsPanelProps> = ({
  gaps,
  loading,
  filling,
  onFill,
}) => {
  const rows = Array.isArray(gaps) ? gaps : [];
  const [groupBy, setGroupBy] = useState<CoverageGapGroupBy>('category');
  const [query, setQuery] = useState('');
  const [serviceFilter, setServiceFilter] = useState<Set<string>>(() => new Set());
  const [cityFilter, setCityFilter] = useState<Set<string>>(() => new Set());
  const [countryFilter, setCountryFilter] = useState<Set<string>>(() => new Set());
  const [selected, setSelected] = useState<Set<string>>(() => new Set());

  const services = useMemo(() => uniqueSorted(rows.map((g) => asText(g.category))), [rows]);
  const cities = useMemo(() => uniqueSorted(rows.map((g) => asText(g.city))), [rows]);
  const countries = useMemo(
    () => uniqueSorted(rows.map((g) => countryLabel(g.country))),
    [rows],
  );

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((g) => {
      if (serviceFilter.size > 0 && !serviceFilter.has(asText(g.category))) return false;
      if (cityFilter.size > 0 && !cityFilter.has(asText(g.city))) return false;
      if (countryFilter.size > 0 && !countryFilter.has(countryLabel(g.country))) return false;
      if (!q) return true;
      const hay = `${g.category} ${g.city} ${g.country} ${countryLabel(g.country)}`.toLowerCase();
      return hay.includes(q);
    });
  }, [rows, query, serviceFilter, cityFilter, countryFilter]);

  const groups = useMemo(() => {
    const map = new Map<string, { id: string; title: string; items: DemandGap[]; demand: number }>();
    for (const g of visible) {
      const key = groupKeyFor(g, groupBy);
      const existing = map.get(key);
      if (existing) {
        existing.items.push(g);
        existing.demand += g.demand;
      } else {
        map.set(key, { id: key, title: groupTitle(g, groupBy), items: [g], demand: g.demand });
      }
    }
    return [...map.values()].sort((a, b) => b.demand - a.demand || a.title.localeCompare(b.title, 'en'));
  }, [visible, groupBy]);

  const visibleKeys = useMemo(() => visible.map(coverageGapKey), [visible]);
  const allVisibleSelected = visibleKeys.length > 0 && visibleKeys.every((k) => selected.has(k));

  const selectedGaps = useMemo(
    () => visible.filter((g) => selected.has(coverageGapKey(g))),
    [visible, selected],
  );

  const toggleOne = (key: string, checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(key);
      else next.delete(key);
      return next;
    });
  };

  const toggleKeys = (keys: string[], checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      for (const key of keys) {
        if (checked) next.add(key);
        else next.delete(key);
      }
      return next;
    });
  };

  return (
    <div>
      <div className="mb-1 text-lg font-semibold text-[#0b2b43]">Coverage gaps employees are hitting</div>
      <p className="text-sm text-slate-500 mb-4">
        Group by service, location, or country, tick the rows you want, then fill them together.
        Highest-demand combos with no catalog coverage yet, across all companies.
      </p>

      <div className="flex flex-wrap items-center gap-2 mb-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Group by</span>
        {GROUP_TABS.map((tab) => (
          <Button
            unstyled
            key={tab.id}
            onClick={() => setGroupBy(tab.id)}
            className={`px-3 py-1 rounded-full border text-sm ${
              groupBy === tab.id
                ? 'border-[#0b2b43] bg-[#0b2b43] text-white'
                : 'border-[#cbd5e1] text-slate-600 hover:bg-[#f1f5f9]'
            }`}
          >
            {tab.label}
          </Button>
        ))}
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter by service, city, or country"
          aria-label="Filter coverage gaps"
          className="ml-auto min-w-[12rem] flex-1 max-w-sm rounded-lg border border-[#cbd5e1] bg-white px-3 py-1.5 text-sm text-[#0b2b43]"
        />
      </div>

      {(services.length > 1 || cities.length > 1 || countries.length > 1) && (
        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <FilterFieldset
            legend="Services"
            options={services}
            selected={serviceFilter}
            onToggle={(v) => setServiceFilter((s) => toggleInSet(s, v))}
            format={(v) => v}
          />
          <FilterFieldset
            legend="Locations"
            options={cities}
            selected={cityFilter}
            onToggle={(v) => setCityFilter((s) => toggleInSet(s, v))}
            format={(v) => v}
          />
          <FilterFieldset
            legend="Countries"
            options={countries}
            selected={countryFilter}
            onToggle={(v) => setCountryFilter((s) => toggleInSet(s, v))}
            format={(v) => v}
          />
        </div>
      )}

      {visible.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 mb-3">
          <label className="inline-flex items-center gap-2 text-sm text-[#0b2b43]">
            <Checkbox
              checked={allVisibleSelected}
              disabled={filling}
              onChange={(e) => toggleKeys(visibleKeys, e.target.checked)}
              aria-label="Select all visible gaps"
            />
            Select all ({visible.length})
          </label>
          <Button
            size="sm"
            disabled={filling || selectedGaps.length === 0}
            onClick={() => onFill(selectedGaps)}
          >
            {filling ? 'Filling…' : `Allowlist & scrape selected (${selectedGaps.length})`}
          </Button>
        </div>
      )}

      {rows.length === 0 ? (
        <p className="text-sm text-slate-500 py-2">
          {loading ? 'Loading…' : 'No uncovered demand right now. New gaps appear here as employees hit them.'}
        </p>
      ) : visible.length === 0 ? (
        <p className="text-sm text-slate-500 py-2">No gaps match this filter.</p>
      ) : (
        <div className="space-y-3">
          {groups.map((group) => {
            const keys = group.items.map(coverageGapKey);
            const groupAll = keys.every((k) => selected.has(k));
            return (
              <div key={group.id} className="border border-[#e2e8f0] rounded-lg overflow-hidden bg-white">
                <div className="flex flex-wrap items-center gap-3 px-4 py-2.5 bg-[#f8fafc] border-b border-[#e2e8f0]">
                  <label className="inline-flex items-center gap-2 min-w-0 flex-1">
                    <Checkbox
                      checked={groupAll}
                      disabled={filling}
                      onChange={(e) => toggleKeys(keys, e.target.checked)}
                      aria-label={`Select all in ${group.title}`}
                    />
                    <span className="font-semibold text-[#0b2b43] capitalize truncate">{group.title}</span>
                  </label>
                  <Badge variant="neutral" size="sm">
                    {group.items.length} gap{group.items.length === 1 ? '' : 's'}
                  </Badge>
                  <span className="text-xs text-slate-500 whitespace-nowrap">
                    {group.demand} request{group.demand === 1 ? '' : 's'}
                  </span>
                </div>
                <ul className="divide-y divide-[#e2e8f0]">
                  {group.items.map((g) => {
                    const key = coverageGapKey(g);
                    return (
                      <li key={key} className="px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-2">
                        <label className="inline-flex items-start gap-3 min-w-0 flex-1">
                          <Checkbox
                            className="mt-0.5"
                            checked={selected.has(key)}
                            disabled={filling}
                            onChange={(e) => toggleOne(key, e.target.checked)}
                            aria-label={`Select ${g.category} in ${locationLabel(g)}`}
                          />
                          <span className="min-w-0">
                            <span className="block font-medium text-[#0b2b43] capitalize">
                              {rowDetail(g, groupBy)}
                            </span>
                            <span className="block text-sm text-slate-500">
                              {g.demand} request{g.demand === 1 ? '' : 's'} from {g.companies}{' '}
                              compan{g.companies === 1 ? 'y' : 'ies'}
                              {g.allowlisted ? ' · already allowlisted' : ''}
                            </span>
                          </span>
                        </label>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={filling}
                          onClick={() => onFill([g])}
                        >
                          Fill
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

const FilterFieldset: React.FC<{
  legend: string;
  options: string[];
  selected: Set<string>;
  onToggle: (value: string) => void;
  format: (value: string) => string;
}> = ({ legend, options, selected, onToggle, format }) => {
  if (options.length <= 1) return null;
  return (
    <fieldset className="min-w-0">
      <legend className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
        {legend}
        <span className="ml-1 font-normal normal-case tracking-normal">
          {selected.size === 0 ? '(all)' : `(${selected.size})`}
        </span>
      </legend>
      <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
        {options.map((opt) => {
          const on = selected.has(opt);
          return (
            <label
              key={opt}
              className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs cursor-pointer ${
                on
                  ? 'border-[#0b2b43] bg-[#0b2b43]/8 text-[#0b2b43]'
                  : 'border-[#e2e8f0] text-slate-600 hover:bg-[#f8fafc]'
              }`}
            >
              <Checkbox
                checked={on}
                onChange={() => onToggle(opt)}
                aria-label={`Filter ${legend.toLowerCase()}: ${opt}`}
              />
              <span className="capitalize truncate max-w-[9rem]">{format(opt)}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
};
