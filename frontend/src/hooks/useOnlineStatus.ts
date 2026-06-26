import { useEffect, useState } from 'react';

/**
 * Tracks the browser's offline state via the `online`/`offline` window events.
 * Returns `true` when offline. Preserves the offline-aware UX that the retired
 * `useResilientQuery` used to provide (pair it with TanStack Query's
 * `refetchOnReconnect` to auto-reload when the connection returns).
 */
export function useIsOffline(): boolean {
  const [offline, setOffline] = useState(
    typeof navigator !== 'undefined' ? !navigator.onLine : false,
  );
  useEffect(() => {
    const goOnline = () => setOffline(false);
    const goOffline = () => setOffline(true);
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
    };
  }, []);
  return offline;
}
