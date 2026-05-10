import React, { useEffect, useState } from 'react';
import { adminNotificationsAPI } from '../../api/client';

export const AdminNotificationBadge: React.FC = () => {
  const [count, setCount] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    adminNotificationsAPI
      .getStats()
      .then((s) => {
        if (!cancelled) setCount(s.open_count ?? 0);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <span
      className="relative inline-flex items-center"
      aria-label={count > 0 ? `${count} open notifications` : 'No open notifications'}
    >
      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
        />
      </svg>
      {count > 0 && (
        <span className="absolute -right-2 -top-2 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-medium text-white">
          {count > 99 ? '99+' : count}
        </span>
      )}
    </span>
  );
};
