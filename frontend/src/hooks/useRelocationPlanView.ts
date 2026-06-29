import { useCallback, useEffect, useState } from 'react';
import { fetchRelocationPlanView, type FetchRelocationPlanViewOptions } from '../api/relocationPlanView';
import type { RelocationPlanViewResponseDTO } from '../types/relocationPlanView';
import { getApiErrorMessage, getClientTransportErrorMessage } from '../utils/apiDetail';

export type UseRelocationPlanViewOptions = FetchRelocationPlanViewOptions & {
  /** When false, no network request (e.g. use legacy timeline instead). */
  enabled?: boolean;
};

// [AIQ-1377] The roadmap API works (DEEP-ROADMAP-API passes), so an intermittent cold-start / 5xx
// blip must not immediately surface "We couldn't load your roadmap". Retry transient failures a
// couple of times before giving up; deterministic 4xx fail fast.
const ROADMAP_FETCH_ATTEMPTS = 3; // 1 try + 2 retries
const ROADMAP_RETRY_BASE_MS = 300;

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Worth retrying: no HTTP response (network/timeout) or a 5xx. A 4xx is deterministic. */
export function isRetryableFetchError(err: unknown): boolean {
  const status = (err as { response?: { status?: number } } | null)?.response?.status;
  if (typeof status === 'number') return status >= 500;
  return true;
}

export function useRelocationPlanView(
  caseId: string | null | undefined,
  options?: UseRelocationPlanViewOptions
): {
  data: RelocationPlanViewResponseDTO | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
} {
  const enabled = options?.enabled !== false;
  const role = options?.role;
  const debug = options?.debug;

  const [data, setData] = useState<RelocationPlanViewResponseDTO | null>(null);
  const [loading, setLoading] = useState(Boolean(enabled && caseId));
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    if (!caseId || !enabled) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    let lastErr: unknown;
    for (let attempt = 1; attempt <= ROADMAP_FETCH_ATTEMPTS; attempt++) {
      try {
        const res = await fetchRelocationPlanView(caseId, { role, debug });
        setData(res);
        setLoading(false);
        return;
      } catch (err: unknown) {
        lastErr = err;
        if (attempt < ROADMAP_FETCH_ATTEMPTS && isRetryableFetchError(err)) {
          await delay(ROADMAP_RETRY_BASE_MS * attempt); // 300ms, 600ms backoff
          continue;
        }
        break;
      }
    }
    const transport = getClientTransportErrorMessage(lastErr);
    const msg = transport ?? getApiErrorMessage(lastErr, (lastErr as Error)?.message || '');
    setError(msg.trim() ? msg : 'Failed to load relocation plan');
    setData(null);
    setLoading(false);
  }, [caseId, enabled, role, debug]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return { data, loading, error, refetch };
}
