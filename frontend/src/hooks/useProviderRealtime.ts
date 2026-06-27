/**
 * useProviderRealtime — subscribes to INSERT/UPDATE on provider_tasks
 * for a specific case, with exponential-backoff reconnect and polling
 * fallback (mirrors the notifications realtime pattern).
 */

import { useEffect, useRef, useCallback } from 'react';
import { RealtimeChannel } from '@supabase/supabase-js';
import { supabase } from '../api/supabase';
import type { ProviderTaskItem } from '../api/providers';

const FALLBACK_POLL_MS = 60_000;
const MAX_RECONNECT   = 5;
const INITIAL_BACKOFF = 1_000;

export interface ProviderRealtimeCallbacks {
  onInsert: (task: ProviderTaskItem) => void;
  onUpdate: (task: ProviderTaskItem) => void;
  onReconnect?: () => void;
  onDisconnect?: () => void;
}

function rowToTask(row: Record<string, unknown>): ProviderTaskItem {
  return {
    id:            String(row.id ?? ''),
    case_id:       String(row.case_id ?? ''),
    provider_id:   String(row.provider_id ?? ''),
    provider_name: row.provider_name != null ? String(row.provider_name) : null,
    title:         String(row.title ?? ''),
    description:   row.description != null ? String(row.description) : null,
    status:        (row.status as ProviderTaskItem['status']) ?? 'pending',
    due_date:      row.due_date != null ? String(row.due_date) : null,
    notes:         row.notes != null ? String(row.notes) : null,
    created_at:    String(row.created_at ?? ''),
    updated_at:    String(row.updated_at ?? ''),
  };
}

/**
 * Subscribe to provider_tasks realtime events for a specific case.
 * Returns a cleanup function.
 */
export function subscribeToProviderTasksRealtime(
  caseId: string,
  callbacks: ProviderRealtimeCallbacks,
): () => void {
  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
  const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseKey || !caseId) {
    return () => {};
  }

  let channel: RealtimeChannel | null = null;
  let fallbackTimer: ReturnType<typeof setInterval> | null = null;
  let reconnectAttempts = 0;

  const cleanup = () => {
    if (channel) { void supabase.removeChannel(channel); channel = null; }
    if (fallbackTimer) { clearInterval(fallbackTimer); fallbackTimer = null; }
  };

  const startFallback = () => {
    callbacks.onDisconnect?.();
    if (fallbackTimer) return;
    callbacks.onReconnect?.();
    fallbackTimer = setInterval(() => callbacks.onReconnect?.(), FALLBACK_POLL_MS);
  };

  const stopFallback = () => {
    if (fallbackTimer) { clearInterval(fallbackTimer); fallbackTimer = null; }
  };

  const subscribe = () => {
    channel = supabase
      .channel(`provider_tasks:case:${caseId}`)
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'provider_tasks', filter: `case_id=eq.${caseId}` },
        (payload) => {
          const row = payload.new as Record<string, unknown>;
          if (row) callbacks.onInsert(rowToTask(row));
        },
      )
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'provider_tasks', filter: `case_id=eq.${caseId}` },
        (payload) => {
          const row = payload.new as Record<string, unknown>;
          if (row) callbacks.onUpdate(rowToTask(row));
        },
      )
      .subscribe((status) => {
        if ((status as string) === 'SUBSCRIBED') {
          stopFallback();
          reconnectAttempts = 0;
          return;
        }
        if ((status as string) === 'CHANNEL_ERROR' || (status as string) === 'TIMED_OUT') {
          reconnectAttempts += 1;
          if (reconnectAttempts >= MAX_RECONNECT) { startFallback(); return; }
          const backoff = INITIAL_BACKOFF * Math.pow(2, reconnectAttempts - 1);
          setTimeout(subscribe, backoff);
        }
      });
  };

  subscribe();
  return cleanup;
}

/**
 * React hook: subscribe to provider_tasks realtime updates for a case.
 * Calls onRefresh whenever an INSERT or UPDATE arrives so the caller
 * can re-fetch the full list.
 */
export function useProviderRealtime(
  caseId: string | undefined,
  onRefresh: () => void,
): void {
  const onRefreshRef = useRef(onRefresh);
  useEffect(() => { onRefreshRef.current = onRefresh; }, [onRefresh]);

  const stableRefresh = useCallback(() => onRefreshRef.current(), []);

  useEffect(() => {
    if (!caseId) return;
    const unsub = subscribeToProviderTasksRealtime(caseId, {
      onInsert: stableRefresh,
      onUpdate: stableRefresh,
      onReconnect: stableRefresh,
    });
    return unsub;
  }, [caseId, stableRefresh]);
}
