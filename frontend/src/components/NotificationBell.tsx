/**
 * NotificationBell - Option 6A/6B in-app notifications.
 * Uses Supabase Realtime (6B) when available; falls back to polling.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getAuthItem } from '../utils/demo';
import {
  listNotifications,
  getUnreadCount,
  markNotificationRead,
  type NotificationListItem,
} from '../api/notifications';
import { subscribeToNotificationsRealtime } from '../api/notificationsRealtime';
import { getNotificationTarget } from '../constants/notificationTypes';
import { buildRoute } from '../navigation/routes';

function dedupeById(items: NotificationListItem[]): NotificationListItem[] {
  const seen = new Set<string>();
  return items.filter((n) => {
    if (seen.has(n.id)) return false;
    seen.add(n.id);
    return true;
  });
}

export const NotificationBell: React.FC = () => {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationListItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);
  const role = (getAuthItem('relopass_role') as 'HR' | 'EMPLOYEE' | 'ADMIN') || 'EMPLOYEE';
  const userId = getAuthItem('relopass_user_id');

  const fetchAll = useCallback(async () => {
    try {
      const [list, count] = await Promise.all([
        listNotifications({ limit: 25 }),
        getUnreadCount(),
      ]);
      setNotifications(list);
      setUnreadCount(count);
    } catch {
      setNotifications([]);
      setUnreadCount(0);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  useEffect(() => {
    if (!userId) {
      const id = setInterval(fetchAll, 60_000);
      return () => clearInterval(id);
    }

    const unsubscribe = subscribeToNotificationsRealtime(userId, {
      onInsert: (n) => {
        setNotifications((prev) => dedupeById([n, ...prev]).slice(0, 25));
        if (!n.read_at) {
          setUnreadCount((c) => c + 1);
        }
      },
      onUpdate: (n) => {
        setNotifications((prev) =>
          prev.map((x) => (x.id === n.id ? { ...x, read_at: n.read_at } : x))
        );
        if (n.read_at) {
          setUnreadCount((c) => Math.max(0, c - 1));
        }
      },
      onReconnect: fetchAll,
    });

    return unsubscribe;
  }, [userId, fetchAll]);

  const handleFocus = useCallback(() => {
    fetchAll();
  }, [fetchAll]);

  useEffect(() => {
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, [handleFocus]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [open]);

  const handleNotificationClick = async (n: NotificationListItem) => {
    if (!n.read_at) {
      try {
        await markNotificationRead(n.id);
        setUnreadCount((c) => Math.max(0, c - 1));
        setNotifications((prev) =>
          prev.map((x) => (x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x))
        );
      } catch {
        // ignore
      }
    }
    const target = getNotificationTarget(role, n);
    setOpen(false);
    navigate(target);
  };

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        onFocus={handleFocus}
        className="relative p-2 rounded-lg hover:bg-[#eef4f8] text-[#0b2b43] transition-colors"
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
      >
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 max-h-96 overflow-auto rounded-xl border border-[#e2e8f0] bg-white shadow-lg z-50">
          <div className="px-4 py-3 border-b border-[#e2e8f0] font-semibold text-sm text-[#0b2b43]">
            Notifications
          </div>
          <div className="max-h-72 overflow-auto">
            {notifications.length === 0 ? (
              <div className="px-4 py-6 text-sm text-[#6b7280] text-center">
                No notifications
              </div>
            ) : (
              <>
              {notifications.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => handleNotificationClick(n)}
                  className={`w-full text-left px-4 py-3 hover:bg-[#f8fafc] border-b border-[#f1f5f9] last:border-b-0 transition-colors ${
                    !n.read_at ? 'bg-[#eff6ff]' : ''
                  }`}
                >
                  <div className="text-sm font-medium text-[#0b2b43]">{n.title}</div>
                  {n.body && (
                    <div className="text-xs text-[#6b7280] mt-0.5 line-clamp-2">{n.body}</div>
                  )}
                  <div className="text-[10px] text-[#94a3b8] mt-1">
                    {new Date(n.created_at).toLocaleString()}
                  </div>
                </button>
              ))}
              <Link
                to={buildRoute('notificationSettings')}
                className="block w-full text-center py-3 text-sm text-[#0b2b43] hover:bg-[#f8fafc] border-t border-[#f1f5f9]"
                onClick={() => setOpen(false)}
              >
                Notification settings
              </Link>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
