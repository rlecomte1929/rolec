import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminReviewQueueLayout } from './AdminReviewQueueLayout';
import { adminReviewQueueAPI } from '../../../api/client';
import { buildRoute } from '../../../navigation/routes';

type WorkloadRow = {
  assignee_id: string;
  assignee_display: string;
  total: number;
  in_progress: number;
  blocked: number;
  overdue: number;
  critical: number;
  high: number;
};

export const AdminReviewQueueWorkloadPage: React.FC = () => {
  const [assignees, setAssignees] = useState<Array<{ id: string; email?: string; full_name?: string }>>([]);
  const [items, setItems] = useState<Array<{
    id: string;
    assigned_to_user_id?: string;
    status: string;
    priority_band: string;
    due_at?: string;
  }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, assigneesRes] = await Promise.all([
        adminReviewQueueAPI.list({
          limit: 500,
          status: undefined,
          sort: 'priority',
        }),
        adminReviewQueueAPI.getAssignees(),
      ]);
      setAssignees(assigneesRes.items ?? []);
      const openStatuses = ['new', 'triaged', 'assigned', 'in_progress', 'blocked', 'waiting', 'reopened'];
      const open = (list.items ?? []).filter((i: { status: string }) => openStatuses.includes(i.status));
      setItems(open);
    } catch (e) {
      setError((e as Error)?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const now = new Date();
  const byAssignee: Record<string, WorkloadRow> = {};

  const assigneeMap = new Map(assignees.map((a) => [a.id, a.full_name || a.email || a.id]));

  for (const it of items) {
    const aid = it.assigned_to_user_id || '(unassigned)';
    const display = it.assigned_to_user_id
      ? (assigneeMap.get(it.assigned_to_user_id) ?? it.assigned_to_user_id.slice(0, 12) + '…')
      : 'Unassigned';
    if (!byAssignee[aid]) {
      byAssignee[aid] = {
        assignee_id: it.assigned_to_user_id || '',
        assignee_display: display,
        total: 0,
        in_progress: 0,
        blocked: 0,
        overdue: 0,
        critical: 0,
        high: 0,
      };
    }
    const row = byAssignee[aid];
    row.total += 1;
    if (it.status === 'in_progress') row.in_progress += 1;
    if (it.status === 'blocked') row.blocked += 1;
    if (it.due_at && new Date(it.due_at) < now) row.overdue += 1;
    if (it.priority_band === 'critical') row.critical += 1;
    if (it.priority_band === 'high') row.high += 1;
  }

  const rows = Object.values(byAssignee).sort((a, b) => b.total - a.total);

  return (
    <AdminReviewQueueLayout
      title="Review Queue Workload"
      subtitle="Items by assignee for workload balancing"
    >
      <div className="space-y-4">
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
                  <th className="px-3 py-2 text-right text-xs font-medium text-slate-600">High</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                      No assigned items. <Link to={buildRoute('adminReviewQueue')} className="underline">View queue</Link>
                    </td>
                  </tr>
                ) : (
                  rows.map((row) => (
                    <tr key={row.assignee_id || 'unassigned'} className="hover:bg-slate-50">
                      <td className="px-3 py-2 font-medium">
                        {row.assignee_id ? (
                          <span title={row.assignee_id}>{row.assignee_display}</span>
                        ) : (
                          <Link
                            to={buildRoute('adminReviewQueue') + '?unassigned=1'}
                            className="text-[#0b2b43] hover:underline"
                          >
                            Unassigned
                          </Link>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right">{row.total}</td>
                      <td className="px-3 py-2 text-right text-amber-700">{row.in_progress}</td>
                      <td className="px-3 py-2 text-right text-red-700">{row.blocked}</td>
                      <td className="px-3 py-2 text-right text-red-700">{row.overdue}</td>
                      <td className="px-3 py-2 text-right text-red-600">{row.critical}</td>
                      <td className="px-3 py-2 text-right text-orange-600">{row.high}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AdminReviewQueueLayout>
  );
};
