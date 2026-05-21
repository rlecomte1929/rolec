/**
 * [P1-5B] useCaseFormsRealtime — subscribes to INSERT/UPDATE on
 * public.case_forms for a specific case. When an event arrives, the caller's
 * `onRefresh` runs — the caller decides what to do (typically refetch the
 * full list via dossierAPI.list).
 *
 * Mirrors the existing useProviderRealtime pattern:
 *   - Exponential-backoff reconnect (max 5 attempts)
 *   - Polling fallback after reconnect ceiling (60s)
 *   - Channel scoped per case_id
 *
 * RLS: the existing `case_forms_via_case` policy gates which rows each
 * subscriber sees. Subscribing as an anon Supabase client is fine — the
 * channel only delivers events the user could SELECT.
 *
 * Realtime publication: case_forms was added to `supabase_realtime` in
 * migration 20260521030000_case_forms_realtime_publication.sql.
 */
import { useCallback, useEffect, useRef } from 'react';
import { RealtimeChannel } from '@supabase/supabase-js';
import { supabase } from '../api/supabase';

const FALLBACK_POLL_MS = 60_000;
const MAX_RECONNECT   = 5;
const INITIAL_BACKOFF = 1_000;

export interface CaseFormsRealtimeCallbacks {
  onInsert: () => void;
  onUpdate: () => void;
  onReconnect?: () => void;
  onDisconnect?: () => void;
}

/**
 * Subscribe to case_forms realtime events for a specific case.
 * Returns a cleanup function.
 */
export function subscribeToCaseFormsRealtime(
  caseId: string,
  callbacks: CaseFormsRealtimeCallbacks,
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
    if (channel) { supabase.removeChannel(channel); channel = null; }
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
      .channel(`case_forms:case:${caseId}`)
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'case_forms', filter: `case_id=eq.${caseId}` },
        () => callbacks.onInsert(),
      )
      .on(
        'postgres_changes',
        { event: 'UPDATE', schema: 'public', table: 'case_forms', filter: `case_id=eq.${caseId}` },
        () => callbacks.onUpdate(),
      )
      .subscribe((status) => {
        if (status === 'SUBSCRIBED') {
          stopFallback();
          reconnectAttempts = 0;
          return;
        }
        if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT') {
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
 * React hook: subscribe to case_forms realtime updates for a case.
 * Calls `onRefresh` whenever an INSERT or UPDATE arrives. The caller is
 * expected to re-fetch the full list (the raw row payload doesn't have
 * enough info to enrich client-side — we need the joined CaseFormSummary).
 */
export function useCaseFormsRealtime(
  caseId: string | undefined,
  onRefresh: () => void,
): void {
  const onRefreshRef = useRef(onRefresh);
  useEffect(() => { onRefreshRef.current = onRefresh; }, [onRefresh]);

  const stableRefresh = useCallback(() => onRefreshRef.current(), []);

  useEffect(() => {
    if (!caseId) return;
    const unsub = subscribeToCaseFormsRealtime(caseId, {
      onInsert: stableRefresh,
      onUpdate: stableRefresh,
      onReconnect: stableRefresh,
    });
    return unsub;
  }, [caseId, stableRefresh]);
}
