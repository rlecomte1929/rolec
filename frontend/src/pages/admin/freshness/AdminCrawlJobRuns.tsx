import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminFreshnessLayout } from './AdminFreshnessLayout';
import { adminFreshnessAPI } from '../../../api/client';
import { buildRoute } from '../../../navigation/routes';

type JobRun = {
  id: string;
  job_type?: string;
  trigger_type?: string;
  status?: string;
  started_at?: string;
  finished_at?: string;
  scope_json?: Record<string, unknown>;
  documents_fetched_count?: number;
  documents_changed_count?: number;
  chunks_created_count?: number;
  staged_resources_count?: number;
  staged_events_count?: number;
  errors_count?: number;
};

export const AdminCrawlJobRuns: React.FC = () => {
  const [items, setItems] = useState<JobRun[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('');

  useEffect(() => {
    adminFreshnessAPI
      .listJobRuns({
        status: statusFilter || undefined,
        limit: 50,
      })
      .then((r) => {
        setItems(r.items ?? []);
        setTotal(r.total ?? 0);
      })
      .catch((e) => setError((e as Error)?.message || 'Failed'))
      .finally(() => setLoading(false));
  }, [statusFilter]);

  const statusColor = (s: string) => {
    switch (s) {
      case 'succeeded':
        return 'bg-green-100 text-green-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      case 'running':
      case 'queued':
        return 'bg-amber-100 text-amber-800';
      case 'partial_success':
        return 'bg-orange-100 text-orange-800';
      default:
        return 'bg-slate-100 text-slate-700';
    }
  };

  if (loading) {
    return (
      <AdminFreshnessLayout title="Job runs" subtitle="Crawl job run history">
        <div className="py-12 text-center text-slate-500">Loading...</div>
      </AdminFreshnessLayout>
    );
  }
  if (error) {
    return (
      <AdminFreshnessLayout title="Job runs" subtitle="Crawl job run history">
        <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
      </AdminFreshnessLayout>
    );
  }

  return (
    <AdminFreshnessLayout title="Job runs" subtitle="Crawl job run history">
      <div className="mb-4">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        >
          <option value="">All statuses</option>
          <option value="queued">queued</option>
          <option value="running">running</option>
          <option value="succeeded">succeeded</option>
          <option value="partial_success">partial_success</option>
          <option value="failed">failed</option>
        </select>
      </div>
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
              <th className="px-4 py-2">Started</th>
              <th className="px-4 py-2">Type</th>
              <th className="px-4 py-2">Trigger</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Docs</th>
              <th className="px-4 py-2">Changed</th>
              <th className="px-4 py-2">Resources</th>
              <th className="px-4 py-2">Events</th>
              <th className="px-4 py-2">Errors</th>
              <th className="px-4 py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {items.map((j) => (
              <tr key={j.id} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-2">
                  {j.started_at ? new Date(j.started_at).toLocaleString() : '-'}
                </td>
                <td className="px-4 py-2">{j.job_type ?? '-'}</td>
                <td className="px-4 py-2">{j.trigger_type ?? '-'}</td>
                <td className="px-4 py-2">
                  <span className={`rounded px-1.5 py-0.5 text-xs ${statusColor(j.status ?? '')}`}>
                    {j.status ?? '-'}
                  </span>
                </td>
                <td className="px-4 py-2">{j.documents_fetched_count ?? '-'}</td>
                <td className="px-4 py-2">{j.documents_changed_count ?? '-'}</td>
                <td className="px-4 py-2">{j.staged_resources_count ?? '-'}</td>
                <td className="px-4 py-2">{j.staged_events_count ?? '-'}</td>
                <td className="px-4 py-2">{j.errors_count ?? '-'}</td>
                <td className="px-4 py-2">
                  <Link to={buildRoute('adminCrawlJobRunDetail', { id: j.id })} className="text-[#0b2b43] hover:underline">
                    Detail
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 text-sm text-slate-500">Showing {items.length} of {total}</div>
      {items.length === 0 && (
        <div className="py-8 text-center text-slate-500">No job runs</div>
      )}
    </AdminFreshnessLayout>
  );
};
