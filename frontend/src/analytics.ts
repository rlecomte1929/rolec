import posthog from 'posthog-js';
import { env } from './config/env';
import { getTestDriveSession } from './api/testDrive';

let enabled = false;
let replayStarted = false;

export function initAnalytics(): void {
  const key = env.posthogKey;
  if (!key) return;

  const host = env.posthogHost;
  posthog.init(key, {
    api_host: host,
    capture_pageview: true,
    persistence: 'localStorage+cookie',
    autocapture: false,
    // TD-M2 (AIQ-1560): the SDK stays loaded for product/marketing analytics, but
    // session RECORDING is OFF by default so real HR/employee/admin users are never
    // recorded. Recording is started ONLY inside a test-drive session (see
    // ensureTestDriveReplay). maskAllInputs redacts every input value (the tester's
    // survey name/email, plus any password/token) in the replays we do capture.
    disable_session_recording: true,
    session_recording: { maskAllInputs: true },
  });
  enabled = true;
}

/**
 * TD-M2 (AIQ-1560): start session replay ONLY when the current browser is running a
 * test drive (getTestDriveSession reads the localStorage slice stashed at provision —
 * null for every real user). Idempotent: starts once per browser session. Tags the
 * recording with the test_sessions session_id (as the PostHog distinct_id + a
 * super-property) so an /admin/test-drive row can deep-link to the replay. No-op when
 * PostHog is disabled (no key) or there is no test-drive session — so it never records
 * a normal HR/employee/admin page.
 */
export function ensureTestDriveReplay(): void {
  if (!enabled || replayStarted) return;
  const slice = getTestDriveSession();
  if (!slice?.session_id) return; // not a test-drive session — never record
  try {
    posthog.identify(slice.session_id, {
      test_drive_session_id: slice.session_id,
      test_drive_campaign: slice.campaign,
      test_drive_corridor: slice.corridor_id,
    });
    posthog.register({ test_drive_session_id: slice.session_id });
    posthog.startSessionRecording();
    replayStarted = true;
  } catch {
    /* replay is best-effort — never surface to the tester */
  }
}

export function track(event: string, properties?: Record<string, unknown>): void {
  if (!enabled) return;
  posthog.capture(event, properties);
}

/**
 * Register super-properties that ride along on every subsequent event in the
 * session (persisted by PostHog). Used to split events by A/B arm — e.g. the
 * resolved `hr_inference_onboarding` variant so PR-A's HR onboarding events
 * (AIQ-1223b) can be segmented by arm. No-op without an analytics key.
 */
export function registerSuperProperties(properties: Record<string, unknown>): void {
  if (!enabled) return;
  posthog.register(properties);
}

/** Emit a marketing funnel event to BOTH PostHog and the server-side
 *  analytics_events sink (which the admin marketing dashboard reads). */
export function emitMarketingEvent(event: string, properties?: Record<string, unknown>): void {
  track(event, properties);
  try {
    const base = env.apiUrl;
    void fetch(`${base}/api/public/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event, properties: properties || {} }),
      keepalive: true,
    }).catch(() => {});
  } catch {
    /* best-effort */
  }
}

/** Read utm_source / utm_campaign from the current URL. */
export function readUtm(): { utm_source?: string; utm_campaign?: string } {
  const usp = new URLSearchParams(window.location.search);
  return {
    utm_source: usp.get('utm_source') || undefined,
    utm_campaign: usp.get('utm_campaign') || undefined,
  };
}
