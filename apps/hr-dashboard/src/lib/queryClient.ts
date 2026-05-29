import { QueryClient } from '@tanstack/react-query';

/**
 * Single QueryClient for the HR Dashboard.
 *
 * Defaults chosen for an internal-tooling surface where data changes happen
 * via user action (not background pushes) — we'd rather avoid double-fetches
 * than over-aggressively keep the cache warm.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});
