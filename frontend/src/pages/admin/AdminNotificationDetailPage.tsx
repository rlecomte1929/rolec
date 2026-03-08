import React, { useCallback, useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { adminNotificationsAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { InternalThreadPanel } from '../../components/admin/collaboration/InternalThreadPanel';

type Notification = {
  id: string;
  notification_type: string;
  severity: string;
  status: string;
  title: string;
  message?: string;
  country_code?: string;
  city_name?: string;
  content_domain?: string;
  trust_tier?: string;
  triggered_at?: string;
  last_retriggered_at?: string;
  acknowledged_at?: string;
  resolved_at?: string;
  related_queue_item_id?: string;
  related_live_resource_id?: string;
  related_live_event_id?: string;
  related_change_event_id?: string;
  related_source_name?: string;
  related_schedule_id?: string;
  payload_json?: string;
};

type Event = {
  id: string;
  event_type: string;
  actor_user_id?: string;
  details_json?: string;
  created_at: string;
};

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'bg-red-200 text-red-900',
  high: 'bg-orange-100 text-orange-800',
  warning: 'bg-amber-100 text-amber-800',
  info: 'bg-slate-100 text-slate-700',
};

export const AdminNotificationDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [item, setItem] = useState<Notification | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [n, ev] = await Promise.all([
        adminNotificationsAPI.getOne(id),
        adminNotificationsAPI.getEvents(id),
      ]);
      setItem(n);
      setEvents(ev.items ?? []);
    } catch (e) {
      setError((e as Error)?.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const runAction = async (fn: () => Promise<unknown>) => {
    setActionLoading(true);
    try {
      await fn();
      await load();
    } catch (e) {
      setError((e as Error)?.message || 'Action failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleAck = () => runAction(() => adminNotificationsAPI.acknowledge(id!));
  const handleResolve = () => runAction(() => adminNotificationsAPI.resolve(id!));
  const handleReopen = () => runAction(() => adminNotificationsAPI.reopen(id!));

  if (!id) {
    navigate(buildRoute('adminNotifications'));
    return null;
  }

  if (loading) {
    return (
      <AdminLayout title="Notification" subtitle="Loading...">
        <div className="py-12 text-center text-slate-500">Loading...</div>
      </AdminLayout>
    );
  }

  if (error || !item) {
    return (
      <AdminLayout title="Notification" subtitle="Error">
        <div className="rounded-lg bg-red-50 p-4 text-red-700">
          {error || 'Not found'}
          <Link to={buildRoute('adminNotifications')} className="ml-2 underline">Back</Link>
        </div>
      </AdminLayout>
    );
  }

  let payload: Record<string, unknown> = {};
  try {
    payload = typeof item.payload_json === 'string' ? JSON.parse(item.payload_json) : item.payload_json || {};
  } catch {
    // ignore
  }

  return (
    <AdminLayout title="Notification" subtitle={item.title?.slice(0, 80) || 'Detail'}>
      <div className="space-y-6">
        {error && <div className="rounded-lg bg-red-50 p-3 text-red-700">{error}</div>}

        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Summary</h3>
          <div className="space-y-2 text-sm">
            <div className="flex gap-2">
              <span className="text-slate-500">Severity:</span>
              <span className={`rounded px-2 py-0.5 text-xs font-medium ${SEVERITY_STYLES[item.severity] ?? SEVERITY_STYLES.info}`}>
                {item.severity}
              </span>
            </div>
            <div className="flex gap-2">
              <span className="text-slate-500">Status:</span>
              <span>{item.status}</span>
            </div>
            <div className="flex gap-2">
              <span className="text-slate-500">Type:</span>
              <span>{item.notification_type}</span>
            </div>
            <div className="flex gap-2">
              <span className="text-slate-500">Triggered:</span>
              <span>{item.triggered_at ? new Date(item.triggered_at).toLocaleString() : '-'}</span>
            </div>
            {item.message && (
              <div className="mt-2 rounded bg-slate-50 p-2 text-slate-700">{item.message}</div>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Related objects</h3>
          <div className="flex flex-wrap gap-2">
            {item.related_queue_item_id && (
              <Link
                to={buildRoute('adminReviewQueueDetail', { id: item.related_queue_item_id })}
                className="rounded bg-blue-100 px-2 py-1 text-sm text-blue-800 hover:bg-blue-200"
              >
                Queue item →
              </Link>
            )}
            {item.related_live_resource_id && (
              <Link
                to={buildRoute('adminResourcesEdit', { id: item.related_live_resource_id })}
                className="rounded bg-green-100 px-2 py-1 text-sm text-green-800 hover:bg-green-200"
              >
                Live resource →
              </Link>
            )}
            {item.related_live_event_id && (
              <Link
                to={buildRoute('adminEventsEdit', { id: item.related_live_event_id })}
                className="rounded bg-green-100 px-2 py-1 text-sm text-green-800 hover:bg-green-200"
              >
                Live event →
              </Link>
            )}
            {!item.related_queue_item_id && !item.related_live_resource_id && !item.related_live_event_id && (
              <span className="text-sm text-slate-500">No related links</span>
            )}
          </div>
        </div>

        {Object.keys(payload).length > 0 && (
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="mb-2 text-sm font-semibold text-slate-700">Payload</h3>
            <pre className="overflow-x-auto rounded bg-slate-50 p-2 text-xs">
              {JSON.stringify(payload, null, 2)}
            </pre>
          </div>
        )}

        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Actions</h3>
          <div className="flex gap-2">
            {item.status === 'open' && (
              <button
                type="button"
                onClick={handleAck}
                disabled={actionLoading}
                className="rounded bg-slate-200 px-3 py-1 text-sm hover:bg-slate-300 disabled:opacity-50"
              >
                Acknowledge
              </button>
            )}
            {['open', 'acknowledged'].includes(item.status) && (
              <button
                type="button"
                onClick={handleResolve}
                disabled={actionLoading}
                className="rounded bg-green-100 px-3 py-1 text-sm text-green-800 hover:bg-green-200 disabled:opacity-50"
              >
                Resolve
              </button>
            )}
            {['resolved', 'suppressed'].includes(item.status) && (
              <button
                type="button"
                onClick={handleReopen}
                disabled={actionLoading}
                className="rounded bg-blue-100 px-3 py-1 text-sm text-blue-800 hover:bg-blue-200 disabled:opacity-50"
              >
                Reopen
              </button>
            )}
          </div>
        </div>

        <InternalThreadPanel
          targetType="ops_notification"
          targetId={id}
          title="Notification discussion"
        />

        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Activity</h3>
          <div className="space-y-2 text-sm">
            {events.length === 0 ? (
              <p className="text-slate-500">No activity</p>
            ) : (
              events.map((e) => (
                <div key={e.id} className="rounded bg-slate-50 px-2 py-1">
                  <span className="font-medium">{e.event_type}</span>
                  {e.actor_user_id && <span className="text-slate-500"> by {e.actor_user_id}</span>}
                  <span className="text-slate-400"> • {new Date(e.created_at).toLocaleString()}</span>
                </div>
              ))
            )}
          </div>
        </div>

        <Link to={buildRoute('adminNotifications')} className="text-sm text-[#0b2b43] underline">
          ← Back to notifications
        </Link>
      </div>
    </AdminLayout>
  );
};
