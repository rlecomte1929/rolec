import { useQuery } from '@tanstack/react-query';
import { adminAPI } from '../../../api/client';
import { listToV2Shape, type CompanyV2 } from './adapter';

/**
 * Data hook for the s9g Companies V2 screen.
 *
 * Wraps `adminAPI.listCompanies()` (60s cache, already in place) and runs
 * the response through the V2 adapter. Component never sees raw AdminCompany.
 *
 * State:
 *   companies — adapted V2 rows (empty until first load resolves)
 *   loading   — true while a request is in flight
 *   error     — non-null when the last request failed
 *
 * Returns a `refresh()` function bound to the underlying API call. The
 * underlying `adminAPI.listCompanies` is cache-backed for 60s; pass-through
 * is intentional — we don't bypass the cache.
 */
export function useCompaniesV2(): {
  companies: CompanyV2[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const query = useQuery({
    queryKey: ['companies', 'v2'],
    queryFn: async () => {
      const res = await adminAPI.listCompanies();
      return listToV2Shape(res.companies ?? []);
    },
  });

  const companies: CompanyV2[] = query.data ?? [];
  const loading = query.isLoading;
  const error = query.isError
    ? (query.error instanceof Error ? query.error.message : 'Failed to load companies')
    : null;
  const refresh = async () => {
    await query.refetch();
  };

  return { companies, loading, error, refresh };
}
