import { useQuery } from '@tanstack/react-query';
import { policyConfigMatrixAPI } from '../api/client';

/**
 * Whether the HR user's company has published a benefits policy.
 *
 * Returns `boolean | null`, where `null` means "unknown" — either still loading
 * or the check failed. Callers treat `null` as "don't nag" (the publish nudge is
 * gated on `=== false`). This mirrors the original fire-once effect: a single
 * attempt, no retry, and an error leaves the answer unknown rather than flipping
 * it to a false-positive `false`.
 */
export function usePolicyPublished(): boolean | null {
  const query = useQuery({
    queryKey: ['hr', 'policy-published'],
    queryFn: async () => {
      const resp = await policyConfigMatrixAPI.hrPublished();
      const r = (resp || {}) as { version_number?: number | null; published_at?: string | null };
      return Boolean(r.published_at) || (typeof r.version_number === 'number' && r.version_number > 0);
    },
    retry: false,
    staleTime: Infinity,
  });

  return query.isSuccess ? query.data : null;
}
