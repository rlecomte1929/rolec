import React from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { metricTooltip, useAdminMetrics } from '../../api/adminMetrics';
import { StatCard } from '../../components/admin/overview/StatCard';
import { buildRoute } from '../../navigation/routes';
import { getAuthItem, normalizeStoredRole } from '../../utils/demo';
import { AdminLayout } from './AdminLayout';

function JobRow({
  to,
  testId,
  label,
  destination,
  countLabel,
}: {
  to: string;
  testId: string;
  label: string;
  destination: string;
  countLabel?: string;
}) {
  return (
    <li>
      <Link
        to={to}
        data-testid={testId}
        className="flex min-h-11 items-center justify-between gap-3 px-4 py-3 text-sm hover:bg-slate-50 focus:outline-none focus-visible:bg-slate-50 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#0b2b43]/30"
      >
        <span className="min-w-0">
          <span className="block font-medium text-navy-800">{label}</span>
          <span className="block text-xs text-slate-600">{destination}</span>
        </span>
        <span className="flex items-center gap-2 shrink-0">
          {countLabel ? (
            <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-navy-800">
              {countLabel}
            </span>
          ) : null}
          <ChevronRight className="h-4 w-4 text-slate-500" aria-hidden="true" />
        </span>
      </Link>
    </li>
  );
}

export const AdminOverviewPage: React.FC = () => {
  const role = normalizeStoredRole(getAuthItem('relopass_role'));
  const metricsQuery = useAdminMetrics();
  const metrics = metricsQuery.data;
  const loading = metricsQuery.isLoading;
  const tenants = metrics?.tenants_total;
  const review = metrics?.content_review_pending;
  const prospects = metrics?.prospects_waiting;

  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Home">
        <p className="text-sm text-slate-500">You do not have access to the Admin Console.</p>
      </AdminLayout>
    );
  }

  const reviewEmpty = !loading && review?.value === 0;

  return (
    <AdminLayout
      title="Today"
      subtitle="What needs attention today — reviews, tenants, and the next job."
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
        ) : review ? (
          <StatCard
            testId="metric-review-open"
            label="Content review pending"
            value={review.value}
            loading={loading}
            definition={metricTooltip(review)}
          />
        ) : loading ? (
          <StatCard testId="metric-review-open" label="Content review pending" value={null} loading />
        ) : null}
        {tenants ? (
          <StatCard
            testId="metric-tenants"
            label="Tenants"
            value={tenants.value}
            loading={loading}
            definition={metricTooltip(tenants)}
          />
        ) : loading ? (
          <StatCard testId="metric-tenants" label="Tenants" value={null} loading />
        ) : null}
        {prospects ? (
          <StatCard
            testId="metric-prospects"
            label="Prospects waiting"
            value={prospects.value}
            loading={loading}
            definition={metricTooltip(prospects)}
          />
        ) : loading ? (
          <StatCard testId="metric-prospects" label="Prospects waiting" value={null} loading />
        ) : null}
      </div>

      {!loading && (
        <nav aria-label="Founder jobs" data-testid="job-doors">
          <ul className="divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white overflow-hidden">
            <JobRow
              to={buildRoute('adminCoverage')}
              testId="job-door-catalog"
              label="Catalog"
              destination="Coverage"
              countLabel={
                review && review.value > 0
                  ? `${review.value} pending`
                  : undefined
              }
            />
            <JobRow
              to={buildRoute('adminCompanies')}
              testId="job-door-usage"
              label="Usage"
              destination="Companies"
            />
            <JobRow
              to={buildRoute('adminProspects')}
              testId="job-door-pipeline"
              label="Pipeline"
              destination="Prospects"
              countLabel={prospects && prospects.value > 0 ? `${prospects.value}` : undefined}
            />
            <JobRow
              to={buildRoute('adminFeatureFlags')}
              testId="job-door-machine"
              label="Machine"
              destination="Feature flags"
            />
          </ul>
        </nav>
      )}
    </AdminLayout>
  );
};
