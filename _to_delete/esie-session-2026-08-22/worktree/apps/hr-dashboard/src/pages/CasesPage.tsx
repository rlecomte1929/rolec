import { useState } from 'react';
import { EmptyState } from '../components/EmptyState';
import { CasesFilters } from '../features/cases/CasesFilters';
import { CasesTable } from '../features/cases/CasesTable';
import { CasesSkeleton } from '../features/cases/CasesSkeleton';
import { useCasesQuery } from '../hooks/useCasesQuery';
import { EMPTY_FILTERS, type CasesFilterState } from '../features/cases/types';

export function CasesPage(): JSX.Element {
  const [filters, setFilters] = useState<CasesFilterState>(EMPTY_FILTERS);
  const { rows, allRows, isLoading, isError, error, refetch, isFetching } =
    useCasesQuery(filters);

  const hasActiveFilters =
    filters.search !== '' ||
    filters.statuses.length > 0 ||
    filters.corridors.length > 0;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold text-foreground">Cases</h1>
        <p className="text-sm text-muted-foreground">
          All immigration cases routed to your team. Updates reflect server state at last load
          {isFetching ? ' — refreshing…' : ''}.
        </p>
      </header>

      {isLoading ? (
        <CasesSkeleton />
      ) : isError ? (
        <EmptyState
          title="Couldn't load the case list"
          description={
            error instanceof Error
              ? error.message
              : 'The case list failed to load. Try again in a moment.'
          }
        >
          <button
            type="button"
            onClick={() => void refetch()}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90"
          >
            Retry
          </button>
        </EmptyState>
      ) : allRows.length === 0 ? (
        <EmptyState
          title="No cases yet"
          description="When your HR team creates a case, it will appear here ordered by target start date."
        />
      ) : (
        <>
          <CasesFilters
            filters={filters}
            onChange={setFilters}
            allRows={allRows}
            visibleCount={rows.length}
            totalCount={allRows.length}
          />
          {rows.length === 0 ? (
            <EmptyState
              title="No cases match these filters"
              description={
                hasActiveFilters
                  ? 'Try clearing one or more filters to widen the view.'
                  : 'Adjust the search or status filters above to find the case you need.'
              }
            />
          ) : (
            <CasesTable rows={rows} />
          )}
        </>
      )}
    </div>
  );
}
