import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * AIQ-655 — standardised resilient data-fetch hook for critical-path routes.
 *
 * Encapsulates the loading / error / data state every page reimplements, plus
 * the resilience the frontend-resilience pass requires:
 *   - **AbortController**: each run aborts the previous in-flight request and
 *     aborts on unmount, so a slow/stale response never lands after navigation.
 *   - **Retry**: `retry()` re-runs the fetcher (used by the error-state CTA so
 *     recovery never means a full-page reload).
 *   - **Offline awareness**: tracks `navigator.onLine`; surfaces `isOffline` so
 *     a page can render an offline state, and auto-retries once on reconnect.
 *
 * Contract: the component renders exactly one of skeleton (`loading`),
 * `error`, offline, or content — never two at once.
 *
 * @param fetcher async function receiving an AbortSignal; reject to surface an error.
 * @param deps   re-run dependency list (like useEffect deps).
 */
export interface ResilientQueryResult<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  isOffline: boolean;
  /** Re-run the fetcher. Safe to wire directly to a Retry button. */
  retry: () => void;
}

export function useResilientQuery<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: React.DependencyList = [],
): ResilientQueryResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [isOffline, setIsOffline] = useState(
    typeof navigator !== 'undefined' ? !navigator.onLine : false,
  );

  // Keep the latest fetcher without making it a run-trigger dependency.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);
  // Bumping this re-runs the effect — the manual retry channel.
  const [runId, setRunId] = useState(0);

  const retry = useCallback(() => setRunId((n) => n + 1), []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Offline / online tracking. Auto-retry once when the connection returns and
  // we're currently in an error/empty state.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const goOffline = () => mountedRef.current && setIsOffline(true);
    const goOnline = () => {
      if (!mountedRef.current) return;
      setIsOffline(false);
      retry();
    };
    window.addEventListener('offline', goOffline);
    window.addEventListener('online', goOnline);
    return () => {
      window.removeEventListener('offline', goOffline);
      window.removeEventListener('online', goOnline);
    };
  }, [retry]);

  useEffect(() => {
    // Abort any prior in-flight request before starting a new one.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    fetcherRef
      .current(controller.signal)
      .then((result) => {
        if (controller.signal.aborted || !mountedRef.current) return;
        setData(result);
      })
      .catch((err: unknown) => {
        // Aborted runs are expected on re-run/unmount — never surface them.
        if (controller.signal.aborted || !mountedRef.current) return;
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => {
        if (controller.signal.aborted || !mountedRef.current) return;
        setLoading(false);
      });

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, runId]);

  return { data, error, loading, isOffline, retry };
}
