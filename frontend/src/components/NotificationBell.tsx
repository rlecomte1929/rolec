/**
 * NotificationBell - Message notifications (delivered/unread/read).
 * Shows unread message count; dropdown lists recent unread messages.
 * Polling every 60s when no realtime; refreshes on focus.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getUnreadMessageCount,
  listUnreadMessageNotifications,
  markConversationRead,
  dismissMessageNotification,
  type MessageNotificationItem,
} from '../api/messageNotifications';

function formatRelative(time: string): string {
  const d = new Date(time);
  const now = new Date();
  const sec = Math.floor((now.getTime() - d.getTime()) / 1000);
  if (sec < 60) return 'Just now';
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  if (sec < 604800) return `${Math.floor(sec / 86400)}d ago`;
  return d.toLocaleDateString();
}

export const NotificationBell: React.FC = () => {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<MessageNotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const panelRef = useRef<HTMLDivElement>(null);

  const fetchCount = useCallback(async () => {
    try {
      const count = await getUnreadMessageCount();
      setUnreadCount(count);
    } catch {
      setUnreadCount(0);
    }
  }, []);

  const fetchList = useCallback(async () => {
    try {
      const list = await listUnreadMessageNotifications(20);
      setNotifications(list);
    } catch {
      setNotifications([]);
    }
  }, []);

  useEffect(() => {
    fetchCount();
  }, [fetchCount]);

  useEffect(() => {
    const id = setInterval(fetchCount, 60_000);
    return () => clearInterval(id);
  }, [fetchCount]);

  useEffect(() => {
    window.addEventListener('focus', fetchCount);
    return () => window.removeEventListener('focus', fetchCount);
  }, [fetchCount]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [open]);

  const handleItemClick = async (n: MessageNotificationItem) => {
    try {
      await markConversationRead(n.conversation_id);
      setUnreadCount((c) => Math.max(0, c - 1));
      setNotifications((prev) => prev.filter((x) => x.message_id !== n.message_id));
    } catch {
      // ignore
    }
    setOpen(false);
    navigate(`/messages?assignmentId=${n.conversation_id}`);
  };

  const handleDismiss = async (e: React.MouseEvent, n: MessageNotificationItem) => {
    e.stopPropagation();
    try {
      await dismissMessageNotification(n.message_id);
      setUnreadCount((c) => Math.max(0, c - 1));
      setNotifications((prev) => prev.filter((x) => x.message_id !== n.message_id));
    } catch {
      // ignore
    }
  };

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o);
          if (!open) fetchList();
        }}
        onFocus={fetchCount}
        className="relative p-2 rounded-lg hover:bg-[#eef4f8] text-[#0b2b43] transition-colors"
        aria-label={`Messages${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
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
            Messages
          </div>
          <div className="max-h-72 overflow-auto">
            {notifications.length === 0 ? (
              <div className="px-4 py-6 text-sm text-[#6b7280] text-center">
                No unread messages
              </div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.message_id}
                  className="flex items-start gap-2 px-4 py-3 hover:bg-[#f8fafc] border-b border-[#f1f5f9] last:border-b-0 group"
                >
                  <button
                    type="button"
                    onClick={() => handleItemClick(n)}
                    className="flex-1 text-left min-w-0"
                  >
                    <div className="text-sm font-medium text-[#0b2b43]">{n.sender_name}</div>
                    <div className="text-xs text-[#6b7280] mt-0.5 line-clamp-2 truncate">
                      {n.snippet}
                    </div>
                    <div
                      className="text-[10px] text-[#94a3b8] mt-1"
                      title={new Date(n.created_at).toLocaleString()}
                    >
                      {formatRelative(n.created_at)}
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={(e) => handleDismiss(e, n)}
                    className="shrink-0 p-1 rounded hover:bg-[#e2e8f0] text-[#6b7280] opacity-0 group-hover:opacity-100 transition-opacity"
                    aria-label="Dismiss"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
