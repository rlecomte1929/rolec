import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminFreshnessLayout } from './AdminFreshnessLayout';
import { adminFreshnessAPI } from '../../../api/client';
import { buildRoute } from '../../../navigation/routes';

type Overview = {
  active_schedules_count?: number;
  due_schedules_count?: number;
  overdue_schedules_count?: number;
  last_24h_crawl_success_count?: number;
  last_24h_crawl_failure_count?: number;
  documents_changed_recently?: number;
  new_staged_resources_pending?: number;
  live_resources_stale_count?: number;
  live_events_expired_count?: number;
  fresh_sources_count?: number;
  stale_sources_count?: number;
  overdue_sources_count?: number;
};

export const AdminFreshnessOverview: React.FC = () => {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [countries, setCountries] = useState<{ items: Array<Record<string, unknown>> } | null>(null);
  const [jobRuns, setJobRuns] = useState<{ items: Array<Record<string, unknown>> } | null>(null);
  const [changes, setChanges] = useState<{ items: Array<Record<string, unknown>> } | null>(null);
  const [staleResources, setStaleResources] = useState<{ items: Array<Record<string, unknown>> } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ov, co, jr, ch, sr] = await Promise.all([
        adminFreshnessAPI.getOverview(),
        adminFreshnessAPI.getCountries(),
        adminFreshnessAPI.listJobRuns({ limit: 10 }),
        adminFreshnessAPI.listDocumentChanges({ limit: 10 }),
        adminFreshnessAPI.getStaleResources({ limit: 10 }),
      ]);
      setOverview(ov);
      setCountries(co);
      setJobRuns(jr);
      setChanges(ch);
      setStaleResources(sr);
    } catch (e) {
      setError((e as Error)?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await adminFreshnessAPI.refreshFreshness();
      await load();
    } catch (e) {
      alert((e as Error)?.message || 'Refresh failed');
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) {
    return (
      <AdminFreshnessLayout title="Freshness" subtitle="Content freshness monitoring">
        <div className="py-12 text-center text-slate-500">Loading...</div>
      </AdminFreshnessLayout>
    );
  }

  if (error) {
    return (
      <AdminFreshnessLayout title="Freshness" subtitle="Content freshness monitoring">
        <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
        <button onClick={load} className="mt-2 rounded bg-red-100 px-3 py-1 text-sm hover:bg-red-200">
          Retry
        </button>
      </AdminFreshnessLayout>
    );
  }

  const o = overview || {};

  return (
    <AdminFreshnessLayout title="Freshness" subtitle="Content freshness monitoring">
      <div className="mb-4 flex justify-end">
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="rounded bg-[#0b2b43] px-3 py-1.5 text-sm text-white hover:bg-[#0d3a5c] disabled:opacity-50"
        >
          {refreshing ? 'Refreshing...' : 'Refresh metrics'}
        </button>
      </div>

      <div className="space-y-6">
        <div>
          <h2 className="mb-3 text-sm font-medium text-slate-700">Operational KPIs</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
            <KpiCard label="Active schedules" value={o.active_schedules_count ?? 0} />
            <KpiCard label="Due schedules" value={o.due_schedules_count ?? 0} status={o.due_schedules_count ? 'warning' : undefined} />
            <KpiCard label="Overdue schedules" value={o.overdue_schedules_count ?? 0} status={o.overdue_schedules_count ? 'overdue' : undefined} />
            <KpiCard label="Last 24h success" value={o.last_24h_crawl_success_count ?? 0} />
            <KpiCard label="Last 24h failed" value={o.last_24h_crawl_failure_count ?? 0} status={o.last_24h_crawl_failure_count ? 'error' : undefined} />
            <KpiCard label="Docs changed" value={o.documents_changed_recently ?? 0} />
            <KpiCard label="Pending review" value={o.new_staged_resources_pending ?? 0} />
            <KpiCard label="Stale resources" value={o.live_resources_stale_count ?? 0} status={o.live_resources_stale_count ? 'stale' : undefined} />
            <KpiCard label="Expired events" value={o.live_events_expired_count ?? 0} status={o.live_events_expired_count ? 'stale' : undefined} />
            <KpiCard label="Fresh sources" value={o.fresh_sources_count ?? 0} />
            <KpiCard label="Stale sources" value={o.stale_sources_count ?? 0} status={o.stale_sources_count ? 'stale' : undefined} />
            <KpiCard label="Overdue sources" value={o.overdue_sources_count ?? 0} status={o.overdue_sources_count ? 'overdue' : undefined} />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="mb-3 font-medium text-slate-800">Freshness by country</h3>
            {(countries?.items?.length ?? 0) === 0 ? (
              <p className="text-sm text-slate-500">No country data</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-slate-600">
                      <th className="pb-2 pr-2">Country</th>
                      <th className="pb-2 pr-2">Fresh</th>
                      <th className="pb-2 pr-2">Stale</th>
                      <th className="pb-2">Overdue</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(countries?.items ?? []).slice(0, 8).map((c: Record<string, unknown>) => (
                      <tr key={String(c.country_code)} className="border-b border-slate-100">
                        <td className="py-1.5 pr-2 font-medium">{String(c.country_code)}</td>
                        <td className="py-1.5 pr-2">{Number(c.fresh_count ?? 0)}</td>
                        <td className="py-1.5 pr-2">{Number(c.stale_count ?? 0)}</td>
                        <td className="py-1.5">{Number(c.overdue_count ?? 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <Link to={buildRoute('adminFreshnessCountries')} className="mt-2 block text-sm text-[#0b2b43] hover:underline">
              View all countries →
            </Link>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="mb-3 font-medium text-slate-800">Recent job runs</h3>
            {(jobRuns?.items?.length ?? 0) === 0 ? (
              <p className="text-sm text-slate-500">No recent runs</p>
            ) : (
              <ul className="space-y-1.5 text-sm">
                {(jobRuns?.items ?? []).slice(0, 6).map((j: Record<string, unknown>) => (
                  <li key={String(j.id)} className="flex items-center justify-between">
                    <span>{String(j.job_type ?? 'crawl')} — {j.started_at ? new Date(j.started_at as string).toLocaleString() : '-'}</span>
                    <span className={`rounded px-1.5 text-xs ${
                      j.status === 'succeeded' ? 'bg-green-100 text-green-800' :
                      j.status === 'failed' ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-700'
                    }`}>
                      {String(j.status ?? '-')}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <Link to={buildRoute('adminCrawlJobRuns')} className="mt-2 block text-sm text-[#0b2b43] hover:underline">
              View all job runs →
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="mb-3 font-medium text-slate-800">Recent document changes</h3>
            {(changes?.items?.length ?? 0) === 0 ? (
              <p className="text-sm text-slate-500">No recent changes</p>
            ) : (
              <ul className="space-y-1.5 text-sm">
                {(changes?.items ?? []).slice(0, 6).map((c: Record<string, unknown>) => (
                  <li key={String(c.id)}>
                    <Link to={buildRoute('adminFreshnessChanges')} className="text-[#0b2b43] hover:underline">
                      {String(c.source_name ?? 'Unknown')} — {String(c.change_type ?? '-')}
                    </Link>
                    <span className="ml-1 text-slate-500">
                      {c.detected_at ? new Date(c.detected_at as string).toLocaleString() : ''}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <Link to={buildRoute('adminFreshnessChanges')} className="mt-2 block text-sm text-[#0b2b43] hover:underline">
              View all changes →
            </Link>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="mb-3 font-medium text-slate-800">Stale live content</h3>
            {(staleResources?.items?.length ?? 0) === 0 ? (
              <p className="text-sm text-slate-500">No stale resources</p>
            ) : (
              <ul className="space-y-1.5 text-sm">
                {(staleResources?.items ?? []).slice(0, 6).map((r: Record<string, unknown>) => (
                  <li key={String(r.id)}>
                    <Link to={`/admin/resources/${r.id}`} className="text-[#0b2b43] hover:underline">
                      {String(r.title ?? 'Untitled')}
                    </Link>
                    <span className="ml-1 text-slate-500">
                      {String(r.country_code ?? '')}/{String(r.city_name ?? '')} — {String(r.stale_reason ?? 'old_updated_at')}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <Link to={buildRoute('adminFreshnessStaleContent')} className="mt-2 block text-sm text-[#0b2b43] hover:underline">
              View stale content →
            </Link>
          </div>
        </div>
      </div>
    </AdminFreshnessLayout>
  );
};

function KpiCard({
  label,
  value,
  status,
}: {
  label: string;
  value: number;
  status?: 'fresh' | 'warning' | 'stale' | 'overdue' | 'error';
}) {
  return (
    <div className={`rounded-lg border p-3 ${status === 'overdue' || status === 'error' ? 'border-red-200 bg-red-50' : status === 'warning' || status === 'stale' ? 'border-amber-200 bg-amber-50' : 'border-slate-200 bg-white'}`}>
      <div className="text-xl font-semibold text-slate-800">{value}</div>
      <div className="text-xs text-slate-600">{label}</div>
    </div>
  );
}
