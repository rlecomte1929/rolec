import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminLayout } from '../AdminLayout';
import { adminStagingAPI } from '../../../api/client';
import { buildRoute } from '../../../navigation/routes';

type DashboardData = {
  resource_candidates_new?: number;
  resource_candidates_by_status?: Record<string, number>;
  event_candidates_new?: number;
  event_candidates_by_status?: Record<string, number>;
  recent_crawl_runs?: Array<{
    id: string;
    started_at: string;
    status: string;
    documents_fetched?: number;
    resources_staged?: number;
    events_staged?: number;
  }>;
};

export const AdminStagingDashboard: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    adminStagingAPI
      .getDashboard()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setError((e as Error)?.message || 'Failed to load dashboard');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <AdminLayout title="Staging Review" subtitle="Review extracted candidates before promotion">
        <div className="py-12 text-center text-slate-500">Loading...</div>
      </AdminLayout>
    );
  }

  if (error) {
    return (
      <AdminLayout title="Staging Review" subtitle="Review extracted candidates before promotion">
        <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
      </AdminLayout>
    );
  }

  const resNew = data?.resource_candidates_new ?? 0;
  const evNew = data?.event_candidates_new ?? 0;
  const resByStatus = data?.resource_candidates_by_status ?? {};
  const evByStatus = data?.event_candidates_by_status ?? {};
  const runs = data?.recent_crawl_runs ?? [];

  return (
    <AdminLayout title="Staging Review" subtitle="Review extracted candidates before promotion">
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Link
            to={buildRoute('adminStagingResources')}
            className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition hover:border-[#0b2b43] hover:shadow"
          >
            <div className="text-2xl font-semibold text-[#0b2b43]">
              {resNew}
            </div>
            <div className="text-sm text-slate-600">
              Resource candidates (new / needs review)
            </div>
          </Link>
          <Link
            to={buildRoute('adminStagingEvents')}
            className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition hover:border-[#0b2b43] hover:shadow"
          >
            <div className="text-2xl font-semibold text-[#0b2b43]">
              {evNew}
            </div>
            <div className="text-sm text-slate-600">
              Event candidates (new / needs review)
            </div>
          </Link>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="text-2xl font-semibold text-slate-700">
              {Object.values(resByStatus).reduce((a, b) => a + b, 0)}
            </div>
            <div className="text-sm text-slate-600">Total resource candidates</div>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="text-2xl font-semibold text-slate-700">
              {Object.values(evByStatus).reduce((a, b) => a + b, 0)}
            </div>
            <div className="text-sm text-slate-600">Total event candidates</div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="mb-3 font-medium text-slate-800">Resource candidates by status</h3>
            {Object.keys(resByStatus).length === 0 ? (
              <p className="text-sm text-slate-500">No candidates yet</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {Object.entries(resByStatus).map(([status, count]) => (
                  <li key={status} className="flex justify-between">
                    <span className="text-slate-600">{status}</span>
                    <span className="font-medium">{count}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="mb-3 font-medium text-slate-800">Event candidates by status</h3>
            {Object.keys(evByStatus).length === 0 ? (
              <p className="text-sm text-slate-500">No candidates yet</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {Object.entries(evByStatus).map(([status, count]) => (
                  <li key={status} className="flex justify-between">
                    <span className="text-slate-600">{status}</span>
                    <span className="font-medium">{count}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {runs.length > 0 && (
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="mb-3 font-medium text-slate-800">Recent crawl runs</h3>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-600">
                    <th className="pb-2 pr-4">Started</th>
                    <th className="pb-2 pr-4">Status</th>
                    <th className="pb-2 pr-4">Docs</th>
                    <th className="pb-2 pr-4">Resources</th>
                    <th className="pb-2">Events</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.id} className="border-b border-slate-100">
                      <td className="py-2 pr-4">
                        {r.started_at
                          ? new Date(r.started_at).toLocaleString()
                          : '-'}
                      </td>
                      <td className="py-2 pr-4">
                        <span
                          className={`rounded px-1.5 py-0.5 text-xs ${
                            r.status === 'completed'
                              ? 'bg-green-100 text-green-800'
                              : r.status === 'failed'
                                ? 'bg-red-100 text-red-800'
                                : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="py-2 pr-4">{r.documents_fetched ?? '-'}</td>
                      <td className="py-2 pr-4">{r.resources_staged ?? '-'}</td>
                      <td className="py-2">{r.events_staged ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="flex gap-3">
          <Link
            to={buildRoute('adminStagingResources')}
            className="rounded-lg bg-[#0b2b43] px-4 py-2 text-sm font-medium text-white hover:bg-[#0d3a5c]"
          >
            Review resource candidates
          </Link>
          <Link
            to={buildRoute('adminStagingEvents')}
            className="rounded-lg bg-[#0b2b43] px-4 py-2 text-sm font-medium text-white hover:bg-[#0d3a5c]"
          >
            Review event candidates
          </Link>
        </div>
      </div>
    </AdminLayout>
  );
};
