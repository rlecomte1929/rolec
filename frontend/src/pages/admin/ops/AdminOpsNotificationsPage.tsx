import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminOpsLayout } from './AdminOpsLayout';
import { adminOpsAnalyticsAPI } from '../../../api/client';
import { buildRoute } from '../../../navigation/routes';

export const AdminOpsNotificationsPage: React.FC = () => {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(7);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminOpsAnalyticsAPI.getNotificationMetrics({ days });
      setData(res);
    } catch (e) {
      setError((e as Error)?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  const byType = (data?.by_type as Record<string, number>) ?? {};

  return (
    <AdminOpsLayout title="Alert Analytics" subtitle="Notification metrics and trends">
      <div className="space-y-6">
        <div className="flex justify-between">
          <select
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
        {error && <div className="rounded-lg bg-red-50 p-3 text-red-700">{error}</div>}
        {loading ? (
          <div className="py-12 text-center text-slate-500">Loading...</div>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="text-2xl font-semibold text-[#0b2b43]">{Number(data?.created_count ?? 0)}</div>
                <div className="text-sm text-slate-600">Created</div>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="text-2xl font-semibold text-amber-600">{Number(data?.open_count ?? 0)}</div>
                <div className="text-sm text-slate-600">Open</div>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="text-2xl font-semibold text-green-600">{Number(data?.resolved_count ?? 0)}</div>
                <div className="text-sm text-slate-600">Resolved</div>
              </div>
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
            <Link to={buildRoute('adminNotifications')} className="text-sm text-[#0b2b43] underline">
              → View notifications
            </Link>
          </>
        )}
      </div>
    </AdminOpsLayout>
  );
};
