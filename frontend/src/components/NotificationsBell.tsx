// NotificationsBell.tsx — in-app notification bell for the AppShell topbar.
//
// Surfaces the `public.notifications` table (ASSIGNMENT_CREATED, HR_FEEDBACK_POSTED,
// INTAKE_SUBMITTED, dossier.*) which previously had NO UI consumer — the list/count
// API and the realtime subscriber existed but were never wired to a component.
//
// Distinct from the (unmounted) message NotificationBell and from ChangelogBell.
//
// Realtime + supabase are imported LAZILY inside effects: api/notificationsRealtime
// statically imports api/supabase, and a static import here would break jsdom vitest
// ("supabaseUrl is required"). Lazy import keeps this module test-safe; the realtime
// subscriber falls back to a 60s poll when realtime is unavailable.

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell } from 'lucide-react';
import {
  listNotifications,
  markNotificationRead,
  type NotificationListItem,
} from '../api/notifications';
import { getNotificationTarget } from '../constants/notificationTypes';
import { getAuthItem, normalizeStoredRole } from '../utils/demo';
import { Button } from './antigravity/Button';

function formatRelative(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const sec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (sec < 60) return 'Just now';
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  if (sec < 604800) return `${Math.floor(sec / 86400)}d ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function targetRole(): 'HR' | 'EMPLOYEE' | 'ADMIN' {
  const r = normalizeStoredRole(getAuthItem('relopass_role'));
  return r === 'HR' || r === 'ADMIN' ? r : 'EMPLOYEE';
}

export const NotificationsBell: React.FC = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState<NotificationListItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await listNotifications({ limit: 20 });
      setItems(list);
      // [AIQ-1618] Reconcile the badge with the list actually shown (single source of
      // truth): derive the unread count from the fetched notifications, so the badge can
      // never appear over an empty "No notifications yet" panel. The separate
      // /unread-count aggregate could over-count rows the list endpoint filters out,
      // producing a red dot with nothing behind it.
      setUnread(list.filter((n) => !n.read_at).length);
    } catch {
      /* transient — keep last good state */
    }
  }, []);

  // Initial load.
  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Realtime (lazy import — keeps supabase out of the static graph for vitest).
  // The subscriber resolves the auth user id itself is not needed: we pass the
  // Supabase auth uuid so the channel filter matches notifications.user_id; any
  // event (or the built-in 60s fallback poll) triggers a refresh.
  useEffect(() => {
    let cleanup: (() => void) | undefined;
    let cancelled = false;
    void (async () => {
      try {
        const [{ subscribeToNotificationsRealtime }, { supabase }] = await Promise.all([
          import('../api/notificationsRealtime'),
          import('../api/supabase'),
        ]);
        const { data } = await supabase.auth.getUser();
        const userId = data.user?.id;
        if (cancelled || !userId) return;
        cleanup = subscribeToNotificationsRealtime(userId, {
          onInsert: () => void refresh(),
          onUpdate: () => void refresh(),
          onReconnect: () => void refresh(),
        });
      } catch {
        /* realtime unavailable — initial fetch + focus refresh still apply */
      }
    })();
    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, [refresh]);

  // Refresh on window focus (cheap freshness without realtime).
  useEffect(() => {
    const onFocus = () => void refresh();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [refresh]);

  // Close on outside click + Escape.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      const t = e.target as Node;
      if (containerRef.current && !containerRef.current.contains(t)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const handleItemClick = useCallback(
    async (n: NotificationListItem) => {
      setOpen(false);
      if (!n.read_at) {
        setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x)));
        setUnread((c) => Math.max(0, c - 1));
        try {
          await markNotificationRead(n.id);
        } catch {
          /* best-effort */
        }
      }
      navigate(getNotificationTarget(targetRole(), n));
    },
    [navigate]
  );

  const badge = useMemo(() => (unread > 9 ? '9+' : String(unread)), [unread]);
  const notificationsName = unread > 0 ? `Notifications, ${unread} unread` : 'Notifications';

  return (
    <div ref={containerRef} className="relative">
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        {unread > 0 ? notificationsName : ''}
      </span>
      <Button
        unstyled
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={notificationsName}
        aria-haspopup="dialog"
        aria-expanded={open}
        className="relative grid h-8 w-8 place-items-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors"
      >
        <Bell className="h-4 w-4" aria-hidden="true" />
        {unread > 0 && (
          <span
            data-testid="notifications-bell-badge"
            aria-hidden="true"
            className="absolute -right-0.5 -top-0.5 inline-flex min-w-[15px] h-[15px] items-center justify-center rounded-full bg-rose-500 px-1 text-[11px] font-semibold leading-none text-white"
          >
            {badge}
          </span>
        )}
      </Button>

      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          className="absolute right-0 z-50 mt-2 w-80 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg"
        >
          <div className="flex items-center justify-between border-b border-slate-100 px-3.5 py-2.5">
            <span className="text-[13px] font-semibold text-[#0b2b43]">Notifications</span>
            {unread > 0 && <span className="text-[11px] text-slate-500">{unread} unread</span>}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <div className="px-3.5 py-6 text-center text-[12.5px] text-slate-500">No notifications yet</div>
            ) : (
              items.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => void handleItemClick(n)}
                  className={`flex w-full flex-col items-start gap-0.5 border-b border-slate-50 px-3.5 py-2.5 text-left hover:bg-slate-50 ${
                    n.read_at ? '' : 'bg-teal-50/40'
                  }`}
                >
                  <span className="flex w-full items-center gap-2">
                    {!n.read_at && <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-teal-500" />}
                    <span className="flex-1 text-[13px] font-semibold text-[#0b2b43]">{n.title}</span>
                    <span className="shrink-0 text-[11px] text-slate-500">{formatRelative(n.created_at)}</span>
                  </span>
                  {n.body && <span className="line-clamp-2 text-[12px] text-slate-500">{n.body}</span>}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
