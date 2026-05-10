import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { AdminFreshnessLayout } from './AdminFreshnessLayout';
import { adminFreshnessAPI } from '../../../api/client';
import { buildRoute } from '../../../navigation/routes';

export const AdminCrawlJobRunDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<Record<string, unknown> | null>(null);
  const [changes, setChanges] = useState<{ items: Array<Record<string, unknown>> } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      adminFreshnessAPI.getJobRun(id),
      adminFreshnessAPI.listDocumentChanges({ job_run_id: id, limit: 20 }),
    ])
      .then(([j, c]) => {
        setJob(j);
        setChanges(c);
      })
      .catch((e) => setError((e as Error)?.message || 'Failed'))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <AdminFreshnessLayout title="Job run" subtitle="Loading...">
        <div className="py-12 text-center text-slate-500">Loading...</div>
      </AdminFreshnessLayout>
    );
  }
  if (error || !job) {
    return (
      <AdminFreshnessLayout title="Job run" subtitle="Error">
        <div className="rounded-lg bg-red-50 p-4 text-red-700">{error || 'Not found'}</div>
        <Link to={buildRoute('adminCrawlJobRuns')} className="mt-2 inline-block text-sm text-[#0b2b43] hover:underline">
          ← Back to job runs
        </Link>
      </AdminFreshnessLayout>
    );
  }

  const status = job.status as string;
  const statusColor = status === 'succeeded' ? 'bg-green-100 text-green-800' :
    status === 'failed' ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-700';

  return (
    <AdminFreshnessLayout title="Job run" subtitle={String(job.job_type ?? 'Detail')}>
      <div className="mb-4">
        <Link to={buildRoute('adminCrawlJobRuns')} className="text-sm text-[#0b2b43] hover:underline">
          ← Back to job runs
        </Link>
      </div>

      <div className="space-y-6">
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 font-medium text-slate-800">Summary</h3>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-slate-500">Status</dt>
              <dd><span className={`rounded px-2 py-0.5 text-xs ${statusColor}`}>{status}</span></dd>
            </div>
            <div>
              <dt className="text-slate-500">Job type</dt>
              <dd>{String(job.job_type ?? '-')}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Trigger</dt>
              <dd>{String(job.trigger_type ?? '-')}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Started</dt>
              <dd>{job.started_at ? new Date(job.started_at as string).toLocaleString() : '-'}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Finished</dt>
              <dd>{job.finished_at ? new Date(job.finished_at as string).toLocaleString() : '-'}</dd>
            </div>
          </dl>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 font-medium text-slate-800">Results</h3>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-slate-500">Documents fetched</dt>
              <dd>{String(job.documents_fetched_count ?? '-')}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Documents changed</dt>
              <dd>{String(job.documents_changed_count ?? '-')}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Chunks created</dt>
              <dd>{String(job.chunks_created_count ?? '-')}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Staged resources</dt>
              <dd>{String(job.staged_resources_count ?? '-')}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Staged events</dt>
              <dd>{String(job.staged_events_count ?? '-')}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Errors</dt>
              <dd>{String(job.errors_count ?? '-')}</dd>
            </div>
          </dl>
        </div>

        {Boolean(job.error_summary) && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4">
            <h3 className="mb-2 font-medium text-red-800">Error summary</h3>
            <p className="text-sm text-red-700">{String(job.error_summary)}</p>
          </div>
        )}

        {(changes?.items?.length ?? 0) > 0 && (
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="mb-3 font-medium text-slate-800">Changed documents</h3>
            <ul className="space-y-1 text-sm">
              {((changes?.items ?? []) as Array<Record<string, unknown>>).map((c) => {
                const label = `${String(c.source_name ?? 'Unknown')} · ${String(c.change_type ?? '-')}`;
                return (
                  <li key={String(c.id)}>
                    <Link to={buildRoute('adminFreshnessChanges')} className="text-[#0b2b43] hover:underline">
                      {label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </AdminFreshnessLayout>
  );
};
