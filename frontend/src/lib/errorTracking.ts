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
import { logger } from './logger';

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

/** Read-only copy of the breadcrumb trail (for the feedback diagnostics snapshot). */
export function getBreadcrumbs(): Breadcrumb[] {
  return breadcrumbs.map((b) => ({ ...b, message: scrubPii(b.message) }));
}

// ---------------------------------------------------------------------------
// Recent-errors ring buffer — last 5 captured errors, so a filed bug report can
// show the function that actually failed. Populated by reportError() below, even
// in dev/local where the Edge-Function report is skipped. Module-level.
// ---------------------------------------------------------------------------

export interface RecentError {
  message: string;
  failingFrame: string; // first user-code stack frame = the function that failed
  fingerprint: string;
  ts: string;
}

const MAX_RECENT_ERRORS = 5;
const recentErrors: RecentError[] = [];

export function getRecentErrors(): RecentError[] {
  return recentErrors.slice();
}

// ---------------------------------------------------------------------------
// Fingerprint — deterministic hash of message + first user-code stack frame
// ---------------------------------------------------------------------------

/** The first user-code stack frame — i.e. "the function that failed". */
export function firstUserFrame(stack: string | null): string {
  return (
    stack
      ?.split('\n')
      .find((line) => line.includes('.tsx') || line.includes('.ts'))
      ?.trim() ?? ''
  );
}

function computeFingerprint(message: string, stack: string | null): string {
  const input = `${message}::${firstUserFrame(stack)}`;
  // djb2 hash
  let hash = 5381;
  for (let i = 0; i < input.length; i++) {
    hash = ((hash << 5) + hash) ^ input.charCodeAt(i);
    hash = hash >>> 0; // keep unsigned 32-bit
  }
  return hash.toString(36);
}

// ---------------------------------------------------------------------------
// EH-2 — PII scrubbing. Error payloads go to an external sub-processor, so under
// the repo's GDPR posture no raw PII may leave in a message/url/breadcrumb. We
// strip URL query strings and redact emails / bearer-tokens-JWTs / UUIDs.
// ---------------------------------------------------------------------------

const EMAIL_RE = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
const TOKEN_RE = /\b(?:eyJ[A-Za-z0-9._-]{8,}|sk-[A-Za-z0-9]{8,})\b|Bearer\s+[A-Za-z0-9._-]+/gi;
const UUID_RE = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi;

export function scrubPii(text: string): string {
  return text
    .replace(EMAIL_RE, '[email]')
    .replace(TOKEN_RE, '[token]')
    .replace(UUID_RE, '[id]');
}

/** Keep origin + path; drop the query string (it routinely carries ids/tokens). */
export function redactUrl(url: string): string {
  try {
    const u = new URL(url);
    return scrubPii(u.origin + u.pathname);
  } catch {
    return scrubPii(url.split('?')[0] ?? url);
  }
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

  // Record into the recent-errors buffer FIRST — this feeds the feedback diagnostics
  // snapshot and must capture even in dev/local where the Edge-Function report below is
  // skipped.
  const fingerprint = computeFingerprint(ctx.message, ctx.stack);
  recentErrors.push({
    message: scrubPii(ctx.message).slice(0, 500),
    failingFrame: scrubPii(firstUserFrame(ctx.stack)).slice(0, 300),
    fingerprint,
    ts: new Date().toISOString(),
  });
  if (recentErrors.length > MAX_RECENT_ERRORS) recentErrors.shift();

  // Skip localhost in development to avoid noise during coding.
  // Remove this guard if you want to capture local errors too.
  if (
    import.meta.env.DEV &&
    (window.location.hostname === 'localhost' ||
      window.location.hostname === '127.0.0.1')
  ) {
    logger.warn('[ErrorTracking] Skipped (dev):', ctx.message);
    return;
  }

  const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
  if (!supabaseUrl) return;

  const userId = getAuthItem('relopass_user_id') || null;

  const payload = {
    fingerprint,
    message:        scrubPii(ctx.message).slice(0, 1000),
    stack:          ctx.stack ? scrubPii(ctx.stack).slice(0, 5000) : null,
    url:            redactUrl(window.location.href),
    user_id:        userId,
    component_name: ctx.componentName ?? null,
    browser:        navigator.userAgent.slice(0, 300),
    breadcrumbs:    breadcrumbs.map((b) => ({ ...b, message: scrubPii(b.message) })),
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
// EH-3 — instrument intentional swallows
// ---------------------------------------------------------------------------

/**
 * Route an intentionally-ignored ("fire-and-forget") error through the
 * observability path instead of dropping it on the floor with `() => undefined`.
 *
 * Logs a dev-only warning (stripped in prod by `logger`) and forwards a
 * `severity: 'warning'` report to error tracking (PII-scrubbed, fire-and-forget,
 * never throws). Returns `undefined` so it drops straight into a `.catch`:
 *
 *   somePromise().catch((e) => swallow(e, 'GuidancePackPanel: prefetch'));
 *
 * Use ONLY for genuinely non-load-bearing work (best-effort prefetch, mark-read,
 * analytics, clipboard). For load-bearing operations (autosave / publish / save)
 * surface a real UI error state instead of swallowing.
 */
export function swallow(err: unknown, context: string): void {
  const e = err instanceof Error ? err : new Error(typeof err === 'string' ? err : 'Non-Error thrown');
  logger.warn(`[swallow] ${context}:`, err);
  void reportError({
    message: `[swallowed] ${context}: ${e.message}`,
    stack: e.stack ?? null,
    componentName: context,
    severity: 'warning',
  });
}

// ---------------------------------------------------------------------------
// Global handlers — called by initErrorTracking() in main.tsx
// ---------------------------------------------------------------------------

export function initErrorTracking(): void {
  if (typeof window === 'undefined') return;

  window.onerror = (message, _source, _lineno, _colno, error) => {
    void reportError({
      message: error?.message ?? (typeof message === 'string' ? message : ''),
      stack:   error?.stack ?? null,
    });
    return false; // do not suppress default browser behavior
  };

  window.addEventListener('unhandledrejection', (event) => {
    const err: unknown = event.reason;
    void reportError({
      message: err instanceof Error ? err.message : String(err),
      stack:   err instanceof Error ? err.stack ?? null : null,
    });
  });
}
