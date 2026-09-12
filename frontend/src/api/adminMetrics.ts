import { useQuery } from '@tanstack/react-query';
import { apiGet } from './client';

/**
 * Admin KPI source-of-truth (AIQ-2326 / ADMIN-IA-0a).
 *
 * One payload, every admin surface reads from it, so a "tenant" means the same thing on
 * Today, Companies, Executive, Coverage and Country requirements. Each metric carries its
 * own definition + source + as-of so the number can be explained in a tooltip and, when it
 * cannot be computed, omitted rather than shown as "Unavailable".
 */
export interface AdminMetric {
  /** null when the metric could not be computed — render nothing, not "Unavailable". */
  value: number | null;
  definition: string;
  source: string;
  as_of: string;
}

export interface AdminMetricsSummary {
  tenants_total: AdminMetric;
  tenants_active: AdminMetric;
  hr_users: AdminMetric;
  employees: AdminMetric;
  signups: AdminMetric;
  cases_total: AdminMetric;
  cases_open: AdminMetric;
  cases_closed: AdminMetric;
  destinations_with_data: AdminMetric;
  destinations_curated: AdminMetric;
  content_review_pending: AdminMetric;
  prospects_waiting: AdminMetric;
  as_of: string;
}

export async function getAdminMetrics(): Promise<AdminMetricsSummary> {
  return apiGet<AdminMetricsSummary>('/api/admin/metrics/summary');
}

/**
 * Companies KPI strip counts (GET /api/admin/companies/overview) — the same shared metric
 * functions as the summary, so the Companies page and Executive never disagree.
 */
export interface CompaniesOverview {
  tenants_total: AdminMetric;
  tenants_active: AdminMetric;
  hr_users: AdminMetric;
  employees: AdminMetric;
  as_of: string;
}

export async function getCompaniesOverview(): Promise<CompaniesOverview> {
  return apiGet<CompaniesOverview>('/api/admin/companies/overview');
}

/** Compose the hover text: "<definition> · as of <local time>". */
export function metricTooltip(metric?: AdminMetric): string | undefined {
  if (!metric) return undefined;
  const when = metric.as_of ? new Date(metric.as_of).toLocaleString() : null;
  return when ? `${metric.definition} · as of ${when}` : metric.definition;
}

export function useAdminMetrics() {
  return useQuery({
    queryKey: ['admin', 'metrics', 'summary'],
    queryFn: getAdminMetrics,
    staleTime: 60_000,
  });
}
