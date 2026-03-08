import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { adminNotificationsAPI, adminCollaborationAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { ThreadSummaryBadge } from '../../components/admin/collaboration/ThreadSummaryBadge';

type Notification = {
  id: string;
  notification_type: string;
  severity: string;
  status: string;
  title: string;
  message?: string;
  country_code?: string;
  city_name?: string;
  triggered_at?: string;
  related_queue_item_id?: string;
  related_live_resource_id?: string;
  related_live_event_id?: string;
  related_source_name?: string;
};

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'bg-red-200 text-red-900',
  high: 'bg-orange-100 text-orange-800',
  warning: 'bg-amber-100 text-amber-800',
  info: 'bg-slate-100 text-slate-700',
};

const TYPE_LABELS: Record<string, string> = {
  queue_item_created_critical: 'Critical queue item',
  queue_item_unassigned_overdue: 'Unassigned overdue',
  queue_item_sla_breach: 'SLA breach',
  queue_item_blocked_too_long: 'Blocked too long',
  stale_live_resource_critical: 'Stale resource',
  crawl_failure_repeated: 'Crawl failure',
};

export const AdminNotificationsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const status = searchParams.get('status') || undefined;
  const severity = searchParams.get('severity') || undefined;
  const openOnly = searchParams.get('open') === '1';
  const escalationOnly = searchParams.get('escalation') === '1';

  const [items, setItems] = useState<Notification[]>([]);
  const [stats, setStats] = useState<{ open_count?: number; critical_count?: number } | null>(null);
  const [threadSummaries, setThreadSummaries] = useState<Record<string, { comment_count: number; last_comment_at?: string; status?: string; is_unread?: boolean }>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, st] = await Promise.all([
        adminNotificationsAPI.list({
          status,
          severity,
          open_only: openOnly,
          escalation_only: escalationOnly,
          limit: 50,
        }),
        adminNotificationsAPI.getStats(),
      ]);
      const listItems = list.items ?? [];
      setItems(listItems);
      setStats(st);
      if (listItems.length > 0) {
        adminCollaborationAPI.getSummariesBatch(
          listItems.map((i) => ({ target_type: 'ops_notification', target_id: i.id }))
        ).then((r) => setThreadSummaries(r.summaries || {})).catch(() => {});
      } else {
        setThreadSummaries({});
      }
    } catch (e) {
      setError((e as Error)?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [status, severity, openOnly, escalationOnly]);

  useEffect(() => {
    load();
  }, [load]);

  const updateFilter = (key: string, value: string | undefined) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  };

  const handleAcknowledge = async (id: string) => {
    setActionLoading(id);
    try {
      await adminNotificationsAPI.acknowledge(id);
      await load();
    } catch (e) {
      setError((e as Error)?.message || 'Action failed');
    } finally {
      setActionLoading(null);
    }
  };

  const handleResolve = async (id: string) => {
    setActionLoading(id);
    try {
      await adminNotificationsAPI.resolve(id);
      await load();
    } catch (e) {
      setError((e as Error)?.message || 'Action failed');
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <AdminLayout title="Ops Notifications" subtitle="Internal operational alerts and escalations">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex gap-3">
            <div className="rounded-lg border border-slate-200 bg-white px-4 py-2">
              <span className="text-2xl font-semibold text-[#0b2b43]">{stats?.open_count ?? 0}</span>
              <span className="ml-2 text-sm text-slate-600">Open</span>
            </div>
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2">
              <span className="text-2xl font-semibold text-red-700">{stats?.critical_count ?? 0}</span>
              <span className="ml-2 text-sm text-red-600">Critical</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              className="rounded border border-slate-300 px-2 py-1 text-sm"
              value={status ?? ''}
              onChange={(e) => updateFilter('status', e.target.value || undefined)}
            >
              <option value="">All statuses</option>
              <option value="open">Open</option>
              <option value="acknowledged">Acknowledged</option>
              <option value="resolved">Resolved</option>
            </select>
            <select
              className="rounded border border-slate-300 px-2 py-1 text-sm"
              value={severity ?? ''}
              onChange={(e) => updateFilter('severity', e.target.value || undefined)}
            >
              <option value="">All severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
            <label className="flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={openOnly}
                onChange={(e) => updateFilter('open', e.target.checked ? '1' : undefined)}
              />
              Open only
            </label>
            <label className="flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={escalationOnly}
                onChange={(e) => updateFilter('escalation', e.target.checked ? '1' : undefined)}
              />
              Escalation only
            </label>
            <button
              type="button"
              onClick={async () => {
                try {
                  await adminNotificationsAPI.recompute();
                  await adminNotificationsAPI.sync();
                  await load();
                } catch (e) {
                  setError((e as Error)?.message || 'Recompute failed');
                }
              }}
              className="rounded bg-[#0b2b43] px-3 py-1 text-sm text-white hover:bg-[#0d3552]"
            >
              Recompute & sync
            </button>
          </div>
        </div>

        {error && <div className="rounded-lg bg-red-50 p-3 text-red-700">{error}</div>}

        {loading ? (
          <div className="py-12 text-center text-slate-500">Loading...</div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Severity</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Title</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Type</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Status</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Scope</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Triggered</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-slate-600">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                      No notifications match filters.
                    </td>
                  </tr>
                ) : (
                  items.map((n) => (
                    <tr key={n.id} className="hover:bg-slate-50">
                      <td className="px-3 py-2">
                        <span
                          className={`inline-flex rounded px-2 py-0.5 text-xs font-medium ${
                            SEVERITY_STYLES[n.severity] ?? SEVERITY_STYLES.info
                          }`}
                        >
                          {n.severity}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-2">
                          <Link
                            to={buildRoute('adminNotificationDetail', { id: n.id })}
                            className="font-medium text-[#0b2b43] hover:underline"
                          >
                            {(n.title || 'Alert').slice(0, 60)}
                            {(n.title || '').length > 60 ? '…' : ''}
                          </Link>
                          <ThreadSummaryBadge
                            targetType="ops_notification"
                            targetId={n.id}
                            summary={threadSummaries[n.id] || null}
                            linkRoute="adminNotificationDetail"
                          />
                        </div>
                      </td>
                      <td className="px-3 py-2 text-sm text-slate-600">
                        {TYPE_LABELS[n.notification_type] ?? n.notification_type}
                      </td>
                      <td className="px-3 py-2 text-sm">{n.status}</td>
                      <td className="px-3 py-2 text-sm">
                        {[n.country_code, n.city_name].filter(Boolean).join(' / ') || '-'}
                      </td>
                      <td className="px-3 py-2 text-sm">
                        {n.triggered_at
                          ? new Date(n.triggered_at).toLocaleString()
                          : '-'}
                      </td>
                      <td className="px-3 py-2">
                        {n.status === 'open' && (
                          <button
                            type="button"
                            onClick={() => handleAcknowledge(n.id)}
                            disabled={actionLoading === n.id}
                            className="mr-2 rounded bg-slate-200 px-2 py-0.5 text-xs hover:bg-slate-300 disabled:opacity-50"
                          >
                            Ack
                          </button>
                        )}
                        {['open', 'acknowledged'].includes(n.status) && (
                          <button
                            type="button"
                            onClick={() => handleResolve(n.id)}
                            disabled={actionLoading === n.id}
                            className="rounded bg-green-100 px-2 py-0.5 text-xs text-green-800 hover:bg-green-200 disabled:opacity-50"
                          >
                            Resolve
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AdminLayout>
  );
};
