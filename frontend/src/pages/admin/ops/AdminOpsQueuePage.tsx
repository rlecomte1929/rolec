import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminOpsLayout } from './AdminOpsLayout';
import { adminOpsAnalyticsAPI } from '../../../api/client';
import { buildRoute } from '../../../navigation/routes';

export const AdminOpsQueuePage: React.FC = () => {
  const [backlog, setBacklog] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminOpsAnalyticsAPI.getQueueBacklog();
      setBacklog(res);
    } catch (e) {
      setError((e as Error)?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const byStatus = (backlog?.by_status as Record<string, number>) ?? {};
  const byPriority = (backlog?.by_priority as Record<string, number>) ?? {};
  const byType = (backlog?.by_queue_item_type as Record<string, number>) ?? {};

  return (
    <AdminOpsLayout title="Queue Analytics" subtitle="Backlog by status, priority, and type">
      <div className="space-y-6">
        {error && <div className="rounded-lg bg-red-50 p-3 text-red-700">{error}</div>}
        {loading ? (
          <div className="py-12 text-center text-slate-500">Loading...</div>
        ) : (
          <>
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <h3 className="mb-2 font-semibold">Total backlog</h3>
              <div className="text-3xl font-bold text-[#0b2b43]">{Number(backlog?.total ?? 0)}</div>
            </div>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <h3 className="mb-2 font-semibold text-slate-700">By status</h3>
                <ul className="space-y-1 text-sm">
                  {Object.entries(byStatus).map(([k, v]) => (
                    <li key={k} className="flex justify-between">
                      <span>{String(k)}</span>
                      <span>{Number(v ?? 0)}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <h3 className="mb-2 font-semibold text-slate-700">By priority</h3>
                <ul className="space-y-1 text-sm">
                  {Object.entries(byPriority).map(([k, v]) => (
                    <li key={k} className="flex justify-between">
                      <span>{String(k)}</span>
                      <span>{Number(v ?? 0)}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <h3 className="mb-2 font-semibold text-slate-700">By type</h3>
                <ul className="space-y-1 text-sm">
                  {Object.entries(byType).map(([k, v]) => (
                    <li key={k} className="flex justify-between">
                      <span>{String(k)}</span>
                      <span>{Number(v ?? 0)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <Link to={buildRoute('adminReviewQueue')} className="text-sm text-[#0b2b43] underline">
              → View review queue
            </Link>
          </>
        )}
      </div>
    </AdminOpsLayout>
  );
};
