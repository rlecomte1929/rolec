/**
 * GlobalApiErrorBanner — B13 fix.
 *
 * Listens for the `api_unavailable` custom event dispatched by the axios
 * response interceptor (client.ts) whenever a network error or timeout occurs.
 * Shows a dismissible banner above the page content with a "Try again" button
 * that reloads the current page.
 *
 * Mounted once inside AppShell so it appears on all authenticated pages.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Button } from './antigravity/Button';
/** How long before the banner auto-hides if not dismissed (ms). */
const AUTO_HIDE_MS = 30_000;

export const GlobalApiErrorBanner: React.FC = () => {
  const [visible, setVisible] = useState(false);

  const show = useCallback(() => {
    setVisible(true);
  }, []);

  const dismiss = useCallback(() => {
    setVisible(false);
  }, []);

  // Listen for the api_unavailable event fired by the axios interceptor.
  useEffect(() => {
    window.addEventListener('api_unavailable', show);
    return () => window.removeEventListener('api_unavailable', show);
  }, [show]);

  // Auto-hide after AUTO_HIDE_MS so the banner doesn't persist after recovery.
  useEffect(() => {
    if (!visible) return;
    const timer = window.setTimeout(dismiss, AUTO_HIDE_MS);
    return () => window.clearTimeout(timer);
  }, [visible, dismiss]);

  if (!visible) return null;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="bg-rose-50 border-b border-rose-200 px-6 py-2 flex items-center justify-between gap-4 shrink-0 text-sm text-rose-900"
    >
      <span>
        <strong>Cannot reach the server.</strong> Check your connection or try again.
      </span>
      <div className="flex items-center gap-3 shrink-0">
        <Button unstyled
          onClick={() => window.location.reload()}
          className="px-3 py-1 rounded-md bg-rose-100 hover:bg-rose-200 text-rose-900 font-medium text-xs transition-colors"
        >
          Try again
        </Button>
        <Button unstyled
          onClick={dismiss}
          aria-label="Dismiss"
          className="text-rose-400 hover:text-rose-700 transition-colors"
        >
          ✕
        </Button>
      </div>
    </div>
  );
};
