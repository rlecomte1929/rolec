import { useEffect, useState } from 'react';
import { policyConfigMatrixAPI } from '../../api/client';
import type { PolicyCapCompareResultRow } from './policyCapCompareTypes';

export interface ProviderEstimateInput {
  benefit_key: string;
  amount: number;
  currency: string;
}

export function usePolicyCapsCompare(params: {
  enabled: boolean;
  assignmentType?: string | null;
  familyStatus?: string | null;
  companyId?: string | null;
  estimates: ProviderEstimateInput[] | null;
}) {
  const { enabled, assignmentType, familyStatus, companyId, estimates } = params;
  const [results, setResults] = useState<PolicyCapCompareResultRow[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const estimatesKey = JSON.stringify(estimates ?? []);

  useEffect(() => {
    if (!enabled || !estimates?.length) {
      setResults(null);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    void (async () => {
      try {
        const data = await policyConfigMatrixAPI.hrCompareProviderEstimates(
          {
            assignment_type: assignmentType ?? undefined,
            family_status: familyStatus ?? undefined,
            estimates: estimates.map((e) => ({
              benefit_key: e.benefit_key,
              amount: e.amount,
              currency: e.currency,
            })),
          },
          companyId ?? undefined
        );
        if (!cancelled) {
          setResults((data.results as PolicyCapCompareResultRow[]) ?? []);
        }
      } catch (err: unknown) {
        const msg =
          err && typeof err === 'object' && 'response' in err
            ? (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
            : (err as Error)?.message;
        if (!cancelled) {
          setError(typeof msg === 'string' ? msg : 'Failed to compare estimates to policy caps');
          setResults(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [enabled, assignmentType, familyStatus, companyId, estimatesKey]);

  return { results, loading, error };
}
