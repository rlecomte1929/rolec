/**
 * diagnostics.ts — collect a scrubbed client-side diagnostics snapshot for a bug report.
 *
 * Attached to feedback submissions as `client_context` and rendered in the admin
 * "Feedback & Work" Diagnostics panel so a triager can see, without asking the reporter:
 * the page/route, the function that failed (from the error-tracking fingerprint), the
 * recent failed API requests (+ X-Request-ID correlation id → backend request log), the
 * navigation breadcrumb trail, the viewport, and the app build version.
 *
 * Every free-text field is PII-scrubbed BEFORE it leaves the browser (GDPR posture — the
 * report is read by admins and persisted). Buffers are already bounded (last ~5) upstream.
 */
import { getPosthogDistinctId, getPosthogSessionId, getPosthogReplayUrl } from '../analytics';
import { getRecentFailedRequests, type FailedRequest } from '../api/requestLog';
import { getCurrentInteractionId } from '../perf/perf';
import {
  getBreadcrumbs,
  getRecentErrors,
  scrubPii,
  redactUrl,
  type RecentError,
} from './errorTracking';

// Injected at build time by vite `define` (see vite.config.ts). Guarded with `typeof`
// below so it degrades to 'unknown' under vitest where the define does not run.
declare const __APP_VERSION__: string;

export interface ClientContext {
  route: string;
  appVersion: string;
  viewport: string;
  userAgent: string;
  interactionId: string | null;
  breadcrumbs: { type: string; message: string; timestamp: string }[];
  recentErrors: RecentError[];
  recentFailedRequests: FailedRequest[];
  /** PostHog person distinct id — links the report to the reporter's PostHog activity. */
  posthog_id: string | null;
  /** PostHog session id — identifies the session replay captured for this bug report. */
  posthog_session_id: string | null;
  /** Direct URL to the session replay, when recording was active + the SDK exposes it. */
  posthog_replay_url: string | null;
}

/** Best-effort, never throws — diagnostics must never block a feedback submit. */
export function collectDiagnostics(): ClientContext {
  const safe = <T>(fn: () => T, fallback: T): T => {
    try {
      return fn();
    } catch {
      return fallback;
    }
  };
  return {
    route: safe(() => redactUrl(window.location.pathname), ''),
    appVersion: safe(
      () => (typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : 'unknown'),
      'unknown',
    ),
    viewport: safe(() => `${window.innerWidth}x${window.innerHeight}`, ''),
    userAgent: safe(() => navigator.userAgent.slice(0, 300), ''),
    interactionId: safe(() => getCurrentInteractionId(), null),
    breadcrumbs: safe(() => getBreadcrumbs(), []), // getBreadcrumbs already scrubs messages
    recentErrors: safe(() => getRecentErrors(), []), // already scrubbed at capture time
    recentFailedRequests: safe(
      () => getRecentFailedRequests().map((r) => ({ ...r, path: scrubPii(r.path) })),
      [],
    ),
    // PostHog identity from the module instance (window.posthog is unreliable — the
    // app imports posthog as a module and never assigns it to window).
    posthog_id: safe(() => getPosthogDistinctId(), null),
    posthog_session_id: safe(() => getPosthogSessionId(), null),
    posthog_replay_url: safe(() => getPosthogReplayUrl(), null),
  };
}
