import { QueryClient } from '@tanstack/react-query';

/**
 * Shared TanStack Query client for the app (RX-2 pilot).
 *
 * Defaults are chosen to preserve the behavior of the reads we migrate off the
 * hand-rolled `useEffect + axios + useState` pattern:
 *   - no refetch on window focus / reconnect (the old fetches never did this), and
 *   - `staleTime: 0` so data is fetched fresh on mount, matching the old mount-effect.
 *
 * The one deliberate improvement is bounded `retry` for transient failures — the
 * capability the hand-rolled fetches lacked. 4xx (including 401) is never retried,
 * so auth failures and validation errors surface immediately; 5xx / network errors
 * get up to 3 attempts total.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
      staleTime: 0,
      retry: (failureCount, error) => {
        const status = (error as { response?: { status?: number } } | null)?.response?.status;
        if (typeof status === 'number' && status >= 400 && status < 500) return false;
        return failureCount < 2;
      },
    },
  },
});
