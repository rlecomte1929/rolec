import { useCallback, useEffect, useState } from 'react';
import { fetchRelocationPlanView, type FetchRelocationPlanViewOptions } from '../api/relocationPlanView';
import type { RelocationPlanViewResponseDTO } from '../types/relocationPlanView';
import { getApiErrorMessage, getClientTransportErrorMessage } from '../utils/apiDetail';

export type UseRelocationPlanViewOptions = FetchRelocationPlanViewOptions & {
  /** When false, no network request (e.g. use legacy timeline instead). */
  enabled?: boolean;
};

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
    try {
      const res = await fetchRelocationPlanView(caseId, { role, debug });
      setData(res);
    } catch (err: unknown) {
      const transport = getClientTransportErrorMessage(err);
      const msg = transport ?? getApiErrorMessage(err, (err as Error)?.message || '');
      setError(msg.trim() ? msg : 'Failed to load relocation plan');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [caseId, enabled, role, debug]);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  return { data, loading, error, refetch };
}
