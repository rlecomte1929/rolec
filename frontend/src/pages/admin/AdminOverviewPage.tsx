import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  adminAPI,
  adminProspectsAPI,
} from '../../api/client';
import { getReviewSummary } from '../../api/contentReview';
import { StatCard } from '../../components/admin/overview/StatCard';
import { buildRoute } from '../../navigation/routes';
import { getAuthItem, normalizeStoredRole } from '../../utils/demo';
import { AdminLayout } from './AdminLayout';

type OverviewStats = {
  companies: number | null;
  contentReviewPending: number | null;
  prospectsTotal: number | null;
};

const EMPTY_STATS: OverviewStats = {
  companies: null,
  contentReviewPending: null,
  prospectsTotal: null,
};

function settledArrayCount<T>(
  result: PromiseSettledResult<T>,
  select: (value: T) => unknown,
): number | null {
  if (result.status !== 'fulfilled') return null;
  const rows = select(result.value);
  return Array.isArray(rows) ? rows.length : null;
}

function settledNumber<T>(
  result: PromiseSettledResult<T>,
  select: (value: T) => unknown,
): number | null {
  if (result.status !== 'fulfilled') return null;
  const value = select(result.value);
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export const AdminOverviewPage: React.FC = () => {
  const role = normalizeStoredRole(getAuthItem('relopass_role'));

  const statsQuery = useQuery({
    queryKey: ['admin', 'overview-stats'],
    queryFn: async (): Promise<OverviewStats> => {
      const results = await Promise.allSettled([
        adminAPI.listCompanies(),
        getReviewSummary(),
        adminProspectsAPI.list({ limit: 1 }),
      ]);

      return {
        companies: settledArrayCount(results[0], (value) => value.companies),
        contentReviewPending: settledNumber(results[1], (value) => value.pending),
        prospectsTotal: settledNumber(results[2], (value) => value.total),
      };
    },
    enabled: role === 'ADMIN',
  });
  const stats: OverviewStats = statsQuery.data ?? EMPTY_STATS;
  const loading = statsQuery.isLoading;

  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Home">
        <p className="text-sm text-slate-500">You do not have access to the Admin Console.</p>
      </AdminLayout>
    );
  }

  const reviewEmpty = !loading && stats.contentReviewPending === 0;
  const reviewFailed = !loading && stats.contentReviewPending === null;

  return (
    <AdminLayout
      title="Today"
      subtitle="Three numbers, then four jobs. Executive and Ops stay nested under Home in the sidebar."
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {reviewEmpty ? (
          <div data-testid="metric-review-open" className="bg-white rounded-xl border border-slate-200 px-5 py-4 shadow-sm">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-2">Content review pending</p>
            <p className="text-sm text-slate-700">No review waiting.</p>
            <Link to={buildRoute('adminCoverage')} className="mt-2 inline-block text-sm text-accent-600 hover:text-accent-700">
              Coverage
            </Link>
          </div>
        ) : (
          <StatCard
            testId="metric-review-open"
            label="Content review pending"
            value={stats.contentReviewPending}
            sub={reviewFailed ? 'Source unavailable' : undefined}
            loading={loading}
          />
        )}
        <StatCard
          testId="metric-tenants"
          label="Tenants"
          value={stats.companies}
          sub={!loading && stats.companies === null ? 'Source unavailable' : undefined}
          loading={loading}
        />
        <StatCard
          testId="metric-prospects"
          label="Prospects waiting"
          value={stats.prospectsTotal}
          sub={!loading && stats.prospectsTotal === null ? 'Source unavailable' : undefined}
          loading={loading}
        />
      </div>

      {!loading && (
        <nav aria-label="Founder jobs" data-testid="job-doors">
          <ul className="divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white overflow-hidden">
            <li>
              <Link
                to={buildRoute('adminCoverage')}
                data-testid="job-door-catalog"
                className="flex min-h-11 items-baseline justify-between gap-3 px-4 py-3 text-sm hover:bg-slate-50"
              >
                <span className="font-medium text-navy-800">Catalog</span>
                <span className="text-slate-500">
                  Coverage
                  {stats.contentReviewPending !== null && stats.contentReviewPending > 0
                    ? ` · ${stats.contentReviewPending} pending`
                    : ''}
                </span>
              </Link>
            </li>
            <li>
              <Link
                to={buildRoute('adminCompanies')}
                data-testid="job-door-usage"
                className="flex min-h-11 items-baseline justify-between gap-3 px-4 py-3 text-sm hover:bg-slate-50"
              >
                <span className="font-medium text-navy-800">Usage</span>
                <span className="text-slate-500">Companies</span>
              </Link>
            </li>
            <li>
              <Link
                to={buildRoute('adminProspects')}
                data-testid="job-door-pipeline"
                className="flex min-h-11 items-baseline justify-between gap-3 px-4 py-3 text-sm hover:bg-slate-50"
              >
                <span className="font-medium text-navy-800">Pipeline</span>
                <span className="text-slate-500">
                  Prospects
                  {stats.prospectsTotal !== null && stats.prospectsTotal > 0 ? ` · ${stats.prospectsTotal}` : ''}
                </span>
              </Link>
            </li>
            <li>
              <Link
                to={buildRoute('adminFeatureFlags')}
                data-testid="job-door-machine"
                className="flex min-h-11 items-baseline justify-between gap-3 px-4 py-3 text-sm hover:bg-slate-50"
              >
                <span className="font-medium text-navy-800">Machine</span>
                <span className="text-slate-500">Feature flags</span>
              </Link>
            </li>
          </ul>
        </nav>
      )}
    </AdminLayout>
  );
};
