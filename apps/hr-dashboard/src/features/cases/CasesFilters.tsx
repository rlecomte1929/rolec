import { useEffect, useMemo, useRef, useState } from 'react';
import { Search, X } from 'lucide-react';
import { cn } from '../../lib/utils';
import type {
  CaseRow,
  CaseStatus,
  CasesFilterState,
} from './types';

const DEFAULT_STATUS_OPTIONS: CaseStatus[] = [
  'draft',
  'in_progress',
  'on_hold',
  'completed',
  'cancelled',
];

const STATUS_LABELS: Record<string, string> = {
  draft: 'Draft',
  in_progress: 'In progress',
  on_hold: 'On hold',
  completed: 'Completed',
  cancelled: 'Cancelled',
};

interface CasesFiltersProps {
  filters: CasesFilterState;
  onChange: (next: CasesFilterState) => void;
  /** Used to derive corridor options dynamically from the visible dataset. */
  allRows: CaseRow[];
  /** Showing-N-of-M counts displayed next to the search input. */
  visibleCount: number;
  totalCount: number;
}

const SEARCH_DEBOUNCE_MS = 200;

export function CasesFilters({
  filters,
  onChange,
  allRows,
  visibleCount,
  totalCount,
}: CasesFiltersProps): JSX.Element {
  const [searchDraft, setSearchDraft] = useState(filters.search);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync external filter resets back into the local draft state.
  useEffect(() => {
    setSearchDraft(filters.search);
  }, [filters.search]);

  // Debounce search input so each keystroke doesn't re-filter 1000 rows.
  useEffect(() => {
    if (searchDraft === filters.search) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      onChange({ ...filters, search: searchDraft });
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // We intentionally read `filters` and `onChange` via closure but only
    // re-run when the local search draft changes — re-running on every
    // upstream filter mutation would cancel an in-flight debounce.
  }, [searchDraft]);

  const corridorOptions = useMemo(() => {
    const set = new Set<string>();
    for (const row of allRows) {
      if (row.corridor) set.add(row.corridor);
    }
    return Array.from(set).sort();
  }, [allRows]);

  const toggleStatus = (value: CaseStatus): void => {
    const next = new Set(filters.statuses);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    onChange({ ...filters, statuses: Array.from(next) });
  };

  const toggleCorridor = (value: string): void => {
    const next = new Set(filters.corridors);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    onChange({ ...filters, corridors: Array.from(next) });
  };

  const hasActiveFilters =
    filters.search !== '' ||
    filters.statuses.length > 0 ||
    filters.corridors.length > 0;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-3">
        <label className="relative flex flex-1 items-center">
          <Search
            className="pointer-events-none absolute left-3 h-4 w-4 text-muted-foreground"
            aria-hidden="true"
          />
          <input
            type="search"
            value={searchDraft}
            onChange={(event) => setSearchDraft(event.target.value)}
            placeholder="Search by employee name or case ID"
            aria-label="Search cases"
            className={cn(
              'w-full rounded-md border border-border bg-background py-2 pl-9 pr-3 text-sm',
              'placeholder:text-muted-foreground focus:outline-none focus-visible:shadow-focus',
            )}
          />
        </label>
        <span className="text-xs text-muted-foreground tabular-nums">
          Showing {visibleCount.toLocaleString()} of {totalCount.toLocaleString()}
        </span>
        {hasActiveFilters ? (
          <button
            type="button"
            onClick={() =>
              onChange({ search: '', statuses: [], corridors: [] })
            }
            className={cn(
              'inline-flex items-center gap-1 rounded-md border border-border px-2 py-1.5 text-xs font-medium',
              'text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
            )}
          >
            <X className="h-3 w-3" aria-hidden="true" />
            Clear filters
          </button>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Status
        </span>
        {DEFAULT_STATUS_OPTIONS.map((status) => {
          const selected = filters.statuses.includes(status);
          return (
            <button
              key={status}
              type="button"
              aria-pressed={selected}
              onClick={() => toggleStatus(status)}
              className={cn(
                'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                selected
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border bg-background text-muted-foreground hover:bg-muted',
              )}
            >
              {STATUS_LABELS[status] ?? status}
            </button>
          );
        })}
      </div>

      {corridorOptions.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Corridor
          </span>
          {corridorOptions.map((corridor) => {
            const selected = filters.corridors.includes(corridor);
            return (
              <button
                key={corridor}
                type="button"
                aria-pressed={selected}
                onClick={() => toggleCorridor(corridor)}
                className={cn(
                  'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                  selected
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-border bg-background text-muted-foreground hover:bg-muted',
                )}
              >
                {corridor.replace('_', ' → ')}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
