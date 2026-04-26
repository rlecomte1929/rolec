/**
 * Error tracking — captures frontend errors and sends to the
 * capture-error Edge Function.
 *
 * Four capture sources are wired up externally:
 * - window.onerror          → via initErrorTracking() in main.tsx
 * - unhandledrejection      → via initErrorTracking() in main.tsx
 * - React ErrorBoundary     → via reportError() called in onError prop
 * - useErrorReporter hook   → via reportError() in try/catch blocks
 */

import { getAuthItem } from '../utils/demo';

// ---------------------------------------------------------------------------
// Breadcrumb buffer — last 10 navigation events, module-level (no re-renders)
// ---------------------------------------------------------------------------

interface Breadcrumb {
  type: 'navigation' | 'error';
  message: string;
  timestamp: string;
}

const MAX_BREADCRUMBS = 10;
const breadcrumbs: Breadcrumb[] = [];

export function addBreadcrumb(entry: Omit<Breadcrumb, 'timestamp'>): void {
  breadcrumbs.push({ ...entry, timestamp: new Date().toISOString() });
  if (breadcrumbs.length > MAX_BREADCRUMBS) breadcrumbs.shift();
}

// ---------------------------------------------------------------------------
// Fingerprint — deterministic hash of message + first user-code stack frame
// ---------------------------------------------------------------------------

function computeFingerprint(message: string, stack: string | null): string {
  const firstUserFrame =
    stack
      ?.split('\n')
      .find((line) => line.includes('.tsx') || line.includes('.ts'))
      ?.trim() ?? '';
  const input = `${message}::${firstUserFrame}`;
  // djb2 hash
  let hash = 5381;
  for (let i = 0; i < input.length; i++) {
    hash = ((hash << 5) + hash) ^ input.charCodeAt(i);
    hash = hash >>> 0; // keep unsigned 32-bit
  }
  return hash.toString(36);
}

// ---------------------------------------------------------------------------
// Core report function — fire-and-forget, never throws
// ---------------------------------------------------------------------------

let reporting = false; // guard against recursive reporting

export interface ErrorContext {
  message: string;
  stack: string | null;
  componentName?: string | null;
  severity?: 'error' | 'warning';
}

export async function reportError(ctx: ErrorContext): Promise<void> {
  if (reporting) return; // prevent infinite loops

  // Skip in test / SSR environments
  if (typeof window === 'undefined') return;

  // Skip localhost in development to avoid noise during coding.
  // Remove this guard if you want to capture local errors too.
  if (
    import.meta.env.DEV &&
    (window.location.hostname === 'localhost' ||
      window.location.hostname === '127.0.0.1')
  ) {
    console.warn('[ErrorTracking] Skipped (dev):', ctx.message);
    return;
  }

  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
  if (!supabaseUrl) return;

  const fingerprint = computeFingerprint(ctx.message, ctx.stack);
  const userId = getAuthItem('relopass_user_id') || null;

  const payload = {
    fingerprint,
    message:        ctx.message.slice(0, 1000),
    stack:          ctx.stack?.slice(0, 5000) ?? null,
    url:            window.location.href,
    user_id:        userId,
    component_name: ctx.componentName ?? null,
    browser:        navigator.userAgent.slice(0, 300),
    breadcrumbs:    [...breadcrumbs],
    severity:       ctx.severity ?? 'error',
  };

  reporting = true;
  try {
    await fetch(`${supabaseUrl}/functions/v1/capture-error`, {
      method:    'POST',
      headers:   { 'Content-Type': 'application/json' },
      body:      JSON.stringify(payload),
      keepalive: true, // ensures delivery even on page unload
    });
  } catch {
    // Silent — error reporting must never surface errors to the user
  } finally {
    reporting = false;
  }
}

// ---------------------------------------------------------------------------
// Global handlers — called by initErrorTracking() in main.tsx
// ---------------------------------------------------------------------------

export function initErrorTracking(): void {
  if (typeof window === 'undefined') return;

  window.onerror = (message, _source, _lineno, _colno, error) => {
    reportError({
      message: error?.message ?? String(message),
      stack:   error?.stack ?? null,
    });
    return false; // do not suppress default browser behavior
  };

  window.addEventListener('unhandledrejection', (event) => {
    const err = event.reason;
    reportError({
      message: err instanceof Error ? err.message : String(err),
      stack:   err instanceof Error ? err.stack ?? null : null,
    });
  });
}
