/**
 * Option 6B: Realtime notifications via Supabase.
 * Subscribes to INSERT/UPDATE on public.notifications, filtered by user_id.
 * Falls back to polling when Supabase is unavailable or subscription drops.
 */

import { RealtimeChannel } from '@supabase/supabase-js';
import { supabase } from './supabase';
import { listNotifications, getUnreadCount } from './notifications';
import type { NotificationListItem } from './notifications';

const FALLBACK_POLL_INTERVAL_MS = 60_000;
const MAX_RECONNECT_ATTEMPTS = 5;
const INITIAL_BACKOFF_MS = 1000;

export interface NotificationEvent {
  kind: 'insert' | 'update';
  payload: NotificationListItem;
}

export interface SubscribeCallbacks {
  onInsert: (n: NotificationListItem) => void;
  onUpdate: (n: NotificationListItem) => void;
  onReconnect?: () => void;
  onDisconnect?: () => void;
}

function rowToNotificationListItem(row: Record<string, unknown>): NotificationListItem {
  return {
    id: String(row.id ?? ''),
    created_at: String(row.created_at ?? ''),
    assignment_id: row.assignment_id != null ? String(row.assignment_id) : null,
    case_id: row.case_id != null ? String(row.case_id) : null,
    type: String(row.type ?? ''),
    title: String(row.title ?? ''),
    body: row.body != null ? String(row.body) : null,
    metadata: (row.metadata as Record<string, unknown>) ?? {},
    read_at: row.read_at != null ? String(row.read_at) : null,
  };
}

/**
 * Subscribe to realtime notification events for the current user.
 * Requires Supabase URL/key and an active session with matching user_id.
 * Falls back to polling when realtime is unavailable.
 */
export function subscribeToNotificationsRealtime(
  userId: string,
  callbacks: SubscribeCallbacks
): () => void {
  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
  const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseKey) {
    return startFallbackPolling(callbacks);
  }

  let channel: RealtimeChannel | null = null;
  let fallbackTimer: ReturnType<typeof setInterval> | null = null;
  let reconnectAttempts = 0;

  const cleanup = () => {
    if (channel) {
      supabase.removeChannel(channel);
      channel = null;
    }
    if (fallbackTimer) {
      clearInterval(fallbackTimer);
      fallbackTimer = null;
    }
  };

  const refreshAndNotify = async () => {
    try {
      await Promise.all([
        listNotifications({ limit: 25 }),
        getUnreadCount(),
      ]);
      callbacks.onReconnect?.();
    } catch {
      // ignore
    }
  };

  const startFallback = () => {
    callbacks.onDisconnect?.();
    if (fallbackTimer) return;
    refreshAndNotify();
    fallbackTimer = setInterval(refreshAndNotify, FALLBACK_POLL_INTERVAL_MS);
  };

  const stopFallback = () => {
    if (fallbackTimer) {
      clearInterval(fallbackTimer);
      fallbackTimer = null;
    }
  };

  const subscribe = () => {
    channel = supabase
      .channel(`notifications:${userId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'notifications',
          filter: `user_id=eq.${userId}`,
        },
        (payload) => {
          const newRow = payload.new as Record<string, unknown>;
          if (newRow) {
            const n = rowToNotificationListItem(newRow);
            callbacks.onInsert(n);
          }
        }
      )
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'notifications',
          filter: `user_id=eq.${userId}`,
        },
        (payload) => {
          const newRow = payload.new as Record<string, unknown>;
          if (newRow) {
            const n = rowToNotificationListItem(newRow);
            callbacks.onUpdate(n);
          }
        }
      )
      .subscribe((status, err) => {
        if (status === 'SUBSCRIBED') {
          stopFallback();
          reconnectAttempts = 0;
          return;
        }
        if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT') {
          reconnectAttempts += 1;
          if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            startFallback();
            return;
          }
          const backoff = INITIAL_BACKOFF_MS * Math.pow(2, reconnectAttempts - 1);
          setTimeout(subscribe, backoff);
        }
      });
  };

  subscribe();
  return cleanup;
}

function startFallbackPolling(callbacks: SubscribeCallbacks): () => void {
  const refresh = async () => {
    try {
      await Promise.all([
        listNotifications({ limit: 25 }),
        getUnreadCount(),
      ]);
      callbacks.onReconnect?.();
    } catch {
      // ignore
    }
  };
  refresh();
  const id = setInterval(refresh, FALLBACK_POLL_INTERVAL_MS);
  return () => clearInterval(id);
}
