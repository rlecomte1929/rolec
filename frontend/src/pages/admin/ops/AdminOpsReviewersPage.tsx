import React, { useCallback, useEffect, useState } from 'react';
import { AdminOpsLayout } from './AdminOpsLayout';
import { adminOpsAnalyticsAPI } from '../../../api/client';

export const AdminOpsReviewersPage: React.FC = () => {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminOpsAnalyticsAPI.getReviewerWorkload();
      setData(res);
    } catch (e) {
      setError((e as Error)?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const byAssignee = (data?.by_assignee as Record<string, Record<string, number>>) ?? {};
  type ReviewerRow = { assignee: string; total?: number; in_progress?: number; blocked?: number; overdue?: number; critical?: number };
  const rows: ReviewerRow[] = Object.entries(byAssignee).map(([aid, metrics]) => ({ assignee: aid === '_unassigned' ? 'Unassigned' : aid, ...metrics }));

  return (
    <AdminOpsLayout title="Reviewer Workload" subtitle="Items by assignee">
      <div className="space-y-6">
        {error && <div className="rounded-lg bg-red-50 p-3 text-red-700">{error}</div>}
        {loading ? (
          <div className="py-12 text-center text-slate-500">Loading...</div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Assignee</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">Total</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">In progress</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">Blocked</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">Overdue</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">Critical</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-slate-500">No assigned items</td>
                  </tr>
                ) : (
                  rows.map((r) => (
                    <tr key={r.assignee} className="hover:bg-slate-50">
                      <td className="px-3 py-2 font-medium">{r.assignee}</td>
                      <td className="px-3 py-2 text-right">{r.total ?? 0}</td>
                      <td className="px-3 py-2 text-right">{r.in_progress ?? 0}</td>
                      <td className="px-3 py-2 text-right text-red-600">{r.blocked ?? 0}</td>
                      <td className="px-3 py-2 text-right text-amber-600">{r.overdue ?? 0}</td>
                      <td className="px-3 py-2 text-right text-red-600">{r.critical ?? 0}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AdminOpsLayout>
  );
};
