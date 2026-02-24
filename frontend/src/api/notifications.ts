/**
 * Notifications API - Option 6A/6B/6C.
 */

import api from './client';
import { upsertNotificationPreference as upsertPrefRpc } from './rpc';

const POLL_INTERVAL_MS = 30_000;

export interface NotificationListItem {
  id: string;
  created_at: string;
  assignment_id: string | null;
  case_id: string | null;
  type: string;
  title: string;
  body: string | null;
  metadata: Record<string, unknown>;
  read_at: string | null;
}

export async function listNotifications(opts?: {
  limit?: number;
  onlyUnread?: boolean;
}): Promise<NotificationListItem[]> {
  const params = new URLSearchParams();
  if (opts?.limit != null) params.set('limit', String(opts.limit));
  if (opts?.onlyUnread) params.set('only_unread', 'true');
  const res = await api.get<NotificationListItem[]>(
    `/api/notifications${params.toString() ? `?${params}` : ''}`
  );
  return res.data ?? [];
}

export async function getUnreadCount(): Promise<number> {
  const res = await api.get<{ count: number }>('/api/notifications/unread-count');
  return res.data?.count ?? 0;
}

export async function markNotificationRead(notificationId: string): Promise<void> {
  await api.patch(`/api/notifications/${notificationId}/read`);
}

export async function notifyHrEmployeeSaved(assignmentId: string): Promise<void> {
  await api.post('/api/notifications/notify-hr', { assignment_id: assignmentId });
}

/** 6C: Notification preference row */
export interface NotificationPreference {
  type: string;
  in_app: boolean;
  email: boolean;
  muted_until: string | null;
}

/** 6C: Fetch notification preferences (Supabase). */
export async function getNotificationPreferences(): Promise<NotificationPreference[]> {
  const { supabase } = await import('./supabase');
  const { data, error } = await supabase
    .from('notification_preferences')
    .select('type, in_app, email, muted_until');
  if (error) throw new Error(error.message);
  return (data || []) as NotificationPreference[];
}

/** 6C: Upsert preference (Supabase RPC). */
export async function upsertNotificationPreference(opts: {
  type: string;
  in_app: boolean;
  email: boolean;
  muted_until?: string | null;
}): Promise<void> {
  const res = await upsertPrefRpc(opts);
  if (res.error) throw new Error(res.error);
}

/**
 * 6B stub: isolate transport for future realtime swap.
 * Currently uses polling; call onNew when fetch returns new items.
 */
export function subscribeToNotifications(
  onNew: (notifications: NotificationListItem[]) => void,
  opts?: { pollIntervalMs?: number }
): () => void {
  const intervalMs = opts?.pollIntervalMs ?? POLL_INTERVAL_MS;
  let lastCount = 0;
  const poll = async () => {
    try {
      const [list, count] = await Promise.all([
        listNotifications({ limit: 25, onlyUnread: true }),
        getUnreadCount(),
      ]);
      if (count > lastCount && list.length > 0) {
        onNew(list);
      }
      lastCount = count;
    } catch {
      // ignore
    }
  };
  poll();
  const id = setInterval(poll, intervalMs);
  return () => clearInterval(id);
}
