import posthog from 'posthog-js';
import { env } from './config/env';
// NOTE: getTestDriveSession is imported LAZILY inside ensureTestDriveReplay (not
// at module top). It lives in ./api/testDrive, which imports ./api/client →
// ./api/supabase — a chain that throws "supabaseUrl is required" at import time
// when VITE_ env is unset (the jsdom/vitest trap). Keeping that import out of the
// static graph means `track()` / analyticsEvents can be imported by any component
// without dragging supabase into its module graph and breaking that component's
// unit tests. Runtime behaviour is unchanged (replay is best-effort, idempotent).

let enabled = false;
let replayStarted = false;

/** localStorage key holding the visitor's analytics consent decision. */
const CONSENT_KEY = 'relopass_analytics_consent';

/**
 * Read the stored analytics consent decision. `null` = the visitor has not yet
 * chosen (the ConsentBanner is shown until they do).
 */
export function getAnalyticsConsent(): 'granted' | 'denied' | null {
  if (typeof window === 'undefined') return null;
  try {
    const val = window.localStorage.getItem(CONSENT_KEY);
    return val === 'granted' || val === 'denied' ? val : null;
  } catch {
    return null; // localStorage unavailable (private mode / SSR) — treat as undecided
  }
}

/** Grant consent: persist and start capturing. Called by the ConsentBanner. */
export function grantAnalyticsConsent(): void {
  try {
    window.localStorage.setItem(CONSENT_KEY, 'granted');
  } catch {
    /* best-effort */
  }
  if (enabled) posthog.opt_in_capturing();
}

/** Revoke consent: persist and stop capturing (also stops any active replay). */
export function revokeAnalyticsConsent(): void {
  try {
    window.localStorage.setItem(CONSENT_KEY, 'denied');
  } catch {
    /* best-effort */
  }
  if (enabled) posthog.opt_out_capturing();
}

// Property keys that must never reach PostHog even if a caller passes them by
// mistake. Belt-and-suspenders on top of the typed analyticsEvents.ts wrappers.
const PII_KEYS = [
  'password', 'token', 'secret', 'passport_number', 'passport_no',
  'salary', 'salary_exact', 'date_of_birth', 'dob', 'ssn', 'tax_id',
  'bank_account', 'iban', 'email', 'full_name', 'display_name', 'name',
];

export function initAnalytics(): void {
  const key = env.posthogKey;
  if (!key) return;

  const host = env.posthogHost;
  posthog.init(key, {
    api_host: host,
    capture_pageview: true,
    persistence: 'localStorage+cookie',
    autocapture: false,
    // GDPR: opt OUT of all capturing (events + cookies) until the visitor grants
    // consent via the ConsentBanner. A returning visitor who already granted stays
    // opted in. Test-drive sessions opt themselves in (see ensureTestDriveReplay) —
    // testers consent as part of the provisioning flow.
    opt_out_capturing_by_default: getAnalyticsConsent() !== 'granted',
    // Strip any PII that slips into event properties before it leaves the browser.
    sanitize_properties: (props) => {
      if (!props) return props;
      const clean: Record<string, unknown> = { ...props };
      for (const k of PII_KEYS) {
        if (k in clean) delete clean[k];
      }
      return clean;
    },
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
  // Lazy-load testDrive (and its api/client chain) only when we actually need it —
  // see the import note at the top of this file. Fire-and-forget: replay start is
  // best-effort and already idempotent via `replayStarted`.
  void import('./api/testDrive').then(({ getTestDriveSession }) => {
    if (replayStarted) return;
    const slice = getTestDriveSession();
    if (!slice?.session_id) return; // not a test-drive session — never record
    try {
      // Testers consent to recording as part of the test-drive provisioning flow, so
      // opt this synthetic session in explicitly (real users stay opted out until they
      // Accept in the ConsentBanner). Without this, opt_out_capturing_by_default would
      // suppress the replay we intentionally capture here.
      posthog.opt_in_capturing();
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
  });
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
