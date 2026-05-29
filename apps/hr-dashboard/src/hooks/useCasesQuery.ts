import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { listCases } from '../api/cases';
import type {
  CaseRow,
  CasesFilterState,
} from '../features/cases/types';

/**
 * Apply client-side filters to the raw list returned by the API.
 *
 * The brief expects sort by target_arrival_date desc by default; the API
 * already returns rows ordered by updated_at desc, but TanStack Table will
 * own the user-facing sort (the user clicks column headers). We sort
 * defensively here only to ensure a stable initial order so the virtual
 * scroller's row mapping doesn't jump on identity-equal data.
 */
function applyFilters(rows: CaseRow[], filters: CasesFilterState): CaseRow[] {
  const search = filters.search.trim().toLowerCase();
  const statusSet = new Set(filters.statuses);
  const corridorSet = new Set(filters.corridors);

  const filtered = rows.filter((row) => {
    if (statusSet.size > 0 && !statusSet.has(row.status)) return false;
    if (corridorSet.size > 0 && !(row.corridor && corridorSet.has(row.corridor))) {
      return false;
    }
    if (search) {
      const name = row.employee_name?.toLowerCase() ?? '';
      const id = row.id.toLowerCase();
      if (!name.includes(search) && !id.includes(search)) return false;
    }
    return true;
  });

  // Stable initial order by target_start_date desc (nulls last), then by id.
  // TanStack Table replaces this when the user clicks a sort header.
  return filtered.slice().sort((a, b) => {
    const aDate = a.target_start_date ?? '';
    const bDate = b.target_start_date ?? '';
    if (aDate !== bDate) return bDate.localeCompare(aDate);
    return a.id.localeCompare(b.id);
  });
}

export interface UseCasesQueryResult {
  /** Filtered, sorted rows ready to feed into TanStack Table. */
  rows: CaseRow[];
  /** Raw (unfiltered) rows — used by the filter UI to derive option lists. */
  allRows: CaseRow[];
  isLoading: boolean;
  isFetching: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => Promise<unknown>;
}

export function useCasesQuery(filters: CasesFilterState): UseCasesQueryResult {
  const query = useQuery({
    queryKey: ['hr-cases'],
    queryFn: () => listCases(),
  });

  const allRows = query.data ?? [];
  const rows = useMemo(() => applyFilters(allRows, filters), [allRows, filters]);

  return {
    rows,
    allRows,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}
