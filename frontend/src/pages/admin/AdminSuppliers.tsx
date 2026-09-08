import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Alert, Button } from '../../components/antigravity';
import { getCoverage, type CoverageSummary } from '../../api/coverage';
import { ROUTE_DEFS } from '../../navigation/routes';
import { AdminLayout } from './AdminLayout';
import { CoverageMasterGrid } from './coverage/CoverageMasterGrid';

/**
 * Suppliers landing — coverage master first. The category-by-category registry
 * is one click away; a heatmap cell deep-links into it with country + category set.
 */
export const AdminSuppliers: React.FC = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<CoverageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback((refresh: boolean) => {
    let active = true;
    if (refresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    getCoverage(refresh)
      .then((d) => {
        if (active) setData(d);
      })
      .catch((e: unknown) => {
        if (!active) return;
        const status = (e as { response?: { status?: number } })?.response?.status;
        setError(
          status === 429
            ? 'Too many admin requests just now — this is a rate limit, not missing data. Retry in a moment.'
            : 'Could not load supplier coverage.',
        );
      })
      .finally(() => {
        if (active) {
          setLoading(false);
          setRefreshing(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => load(false), [load]);

  const asOf = data ? new Date(data.generated_at).toLocaleString() : '';

  return (
    <AdminLayout
      title="Suppliers"
      subtitle="Where providers actually cover destinations — live from the database"
      headerRight={
        <div className="flex flex-wrap items-center gap-2">
          {data && <span className="hidden text-xs text-slate-500 sm:inline">as of {asOf}</span>}
          <Button size="sm" variant="outline" onClick={() => load(true)} disabled={loading || refreshing}>
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </Button>
          <Button size="sm" onClick={() => navigate(ROUTE_DEFS.adminSuppliersNew.path)}>Add supplier</Button>
          <Button size="sm" variant="outline" onClick={() => navigate(ROUTE_DEFS.adminSuppliersRegistry.path)}>
            Open registry
          </Button>
        </div>
      }
    >
      <p className="mb-4 text-sm text-slate-600">
        Each cell is a real capability count. Teal is approved and live; amber is still in the{' '}
        <Link className="font-medium text-accent-600 hover:text-accent-700" to={ROUTE_DEFS.adminVettingQueue.path}>
          vetting queue
        </Link>
        . Click a destination or a service cell to open that slice of the registry.
      </p>

      {error && (
        <Alert variant="error" className="mb-4">
          <div className="flex flex-wrap items-center gap-3">
            <span>{error}</span>
            <Button size="sm" variant="outline" onClick={() => load(false)} disabled={loading || refreshing}>
              {loading ? 'Retrying…' : 'Retry'}
            </Button>
          </div>
        </Alert>
      )}

      {loading && !data ? (
        <div className="py-16 text-center text-sm text-slate-500">Loading coverage…</div>
      ) : data ? (
        <CoverageMasterGrid data={data} lens="suppliers" />
      ) : null}
    </AdminLayout>
  );
};
