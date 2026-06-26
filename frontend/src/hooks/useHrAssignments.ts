import { useEffect, useMemo } from 'react';
import type { MutableRefObject } from 'react';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { hrAPI } from '../api/client';
import type { AssignmentSummary } from '../types';
import { trackAuthPerf } from '../perf/authPerf';
import { trackFirstMeaningfulContent } from '../perf/pagePerf';
import { safeNavigate } from '../navigation/safeNavigate';

const PAGE_SIZE = 25;

export interface HrAssignmentsFilters {
  /** Debounced raw search text. */
  search: string;
  /** `'all'` or a concrete assignment status. */
  status: string;
  /** Raw destination filter text. */
  destination: string;
}

interface AssignmentsPage {
  assignments: AssignmentSummary[];
  total: number;
  offset: number;
}

export interface UseHrAssignmentsResult {
  assignments: AssignmentSummary[];
  total: number;
  /** First-load skeleton (no data yet for this filter combo). */
  isLoading: boolean;
  /** A "Load more" page fetch is in flight. */
  isLoadingMore: boolean;
  /** Any fetch (initial, next page, or reload) is in flight. */
  isFetching: boolean;
  isError: boolean;
  /** More rows exist on the server than are currently loaded. */
  hasMore: boolean;
  /** Append the next page. */
  loadMore: () => void;
  /** Collapse back to page 0 and refetch (re-shows the skeleton). */
  reload: () => Promise<void>;
}

/**
 * HR assignments list as a TanStack infinite query (RX-2 pilot). Replaces the
 * hand-rolled `loadAssignments` + AbortController + offset/loading/error booleans.
 *
 * Behavior preserved from the original:
 *   - paginated "load more" (append) with the same PAGE_SIZE and total-based stop,
 *   - a filter change refetches from page 0 (the filters are part of the query key),
 *   - the `relopass_last_assignment_id` localStorage write on the first page,
 *   - the `trackAuthPerf` / `trackFirstMeaningfulContent` perf instrumentation, and
 *   - the 401 → landing navigation (the global axios interceptor also hard-redirects
 *     to /auth; both fire today, so we keep parity).
 *
 * `routePerfStartedAt` is the component's mount-time ref; the first page resolve
 * reports first-meaningful-content against it, then nulls it (one-shot).
 */
export function useHrAssignments(
  filters: HrAssignmentsFilters,
  routePerfStartedAt: MutableRefObject<number | null>,
): UseHrAssignmentsResult {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const normalized = {
    search: filters.search.trim() || undefined,
    status: filters.status !== 'all' ? filters.status : undefined,
    destination: filters.destination.trim() || undefined,
  };
  const queryKey = ['hr', 'assignments', normalized] as const;

  const query = useInfiniteQuery({
    queryKey,
    initialPageParam: 0,
    queryFn: async ({ pageParam, signal }): Promise<AssignmentsPage> => {
      const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();
      trackAuthPerf({ stage: 'bootstrap_start', route: '/hr/dashboard', meta: { endpoint: 'listAssignments' } });
      try {
        const res = await hrAPI.listAssignments({
          signal,
          limit: PAGE_SIZE,
          offset: pageParam,
          ...normalized,
        });
        const list = Array.isArray(res.assignments) ? res.assignments : [];
        const total =
          typeof res.total === 'number' && Number.isFinite(res.total) ? res.total : list.length;

        // First-page-only side-effects (matches the original `!append` guard).
        if (pageParam === 0) {
          const first = list[0];
          if (first) localStorage.setItem('relopass_last_assignment_id', first.id);
          if (routePerfStartedAt.current != null) {
            const now = typeof performance !== 'undefined' ? performance.now() : Date.now();
            trackFirstMeaningfulContent('/hr/dashboard', now - routePerfStartedAt.current);
            routePerfStartedAt.current = null;
          }
        }

        const dur = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0;
        trackAuthPerf({
          stage: 'bootstrap_end',
          route: '/hr/dashboard',
          durationMs: dur,
          meta: { endpoint: 'listAssignments', count: list.length },
        });
        return { assignments: list, total, offset: pageParam };
      } catch (err) {
        const dur = (typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0;
        trackAuthPerf({
          stage: 'bootstrap_end',
          route: '/hr/dashboard',
          durationMs: dur,
          meta: { endpoint: 'listAssignments', error: true },
        });
        throw err;
      }
    },
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce((n, p) => n + p.assignments.length, 0);
      return loaded < lastPage.total ? loaded : undefined;
    },
  });

  // Preserve the original 401 → landing navigation. 4xx is never retried (see
  // queryClient retry policy), so this fires promptly on an auth failure.
  useEffect(() => {
    const status = (query.error as { response?: { status?: number } } | null)?.response?.status;
    if (query.isError && status === 401) safeNavigate(navigate, 'landing');
  }, [query.isError, query.error, navigate]);

  const assignments = useMemo(
    () => query.data?.pages.flatMap((p) => p.assignments) ?? [],
    [query.data],
  );
  const total = query.data?.pages[query.data.pages.length - 1]?.total ?? 0;

  return {
    assignments,
    total,
    isLoading: query.isLoading,
    isLoadingMore: query.isFetchingNextPage,
    isFetching: query.isFetching,
    isError: query.isError,
    hasMore: assignments.length < total,
    loadMore: () => {
      void query.fetchNextPage();
    },
    reload: async () => {
      await queryClient.resetQueries({ queryKey });
    },
  };
}
