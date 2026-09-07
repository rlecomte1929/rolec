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

// PII property keys stripped from every event before it leaves the browser, as a
// backstop for the untyped track()/emitMarketingEvent() paths (the typed wrappers
// in analyticsEvents.ts are the primary PII guarantee). Applied via posthog's
// native `property_denylist` — NOT a custom sanitize_properties.
//
// ⚠️ Never add 'token' (or other posthog-reserved keys) here: posthog-js carries
// the project api_key through the event payload under a colliding 'token' key, so
// denylisting it strips the api_key and every capture 401s with "event submitted
// without an api_key". (This was the AIQ-16xx client-capture outage.)
const PII_KEYS = [
  'password', 'passport_number', 'passport_no',
  'salary', 'salary_exact', 'date_of_birth', 'dob', 'ssn', 'tax_id',
  'bank_account', 'iban', 'email', 'full_name', 'display_name',
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
    // PII backstop via posthog's native denylist (safe — never strips the api_key).
    property_denylist: PII_KEYS,
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
  // Feedback join keys (never put message/screenshot here):
  //   feedback_widget_opened { route }
  //   feedback_submitted { report_id, category, route }
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

let bugReplayStarted = false;

/**
 * Start a session replay on demand for a bug report. Consent-gated — a visitor who
 * declined analytics is never recorded. Idempotent per browser session. Works even
 * though recording is disabled by default (startSessionRecording overrides the init
 * flag — same mechanism ensureTestDriveReplay relies on). Called when the Feedback
 * widget opens so the reporter's reproduction + annotation are captured; the session
 * id / replay url then ride along on the report via collectDiagnostics().
 */
export function startBugReportRecording(): void {
  if (!enabled || bugReplayStarted) return;
  if (getAnalyticsConsent() !== 'granted') return; // never record a user who declined
  try {
    posthog.opt_in_capturing();
    posthog.startSessionRecording();
    bugReplayStarted = true;
  } catch {
    /* best-effort — never surface to the reporter */
  }
}

// posthog-js exposes these on the module instance. get_distinct_id is typed; the
// session helpers vary by SDK version, so read them defensively.
type PosthogSessionApi = {
  get_session_id?: () => string;
  get_session_replay_url?: (opts?: { withTimestamp?: boolean }) => string;
};

/** Current PostHog person distinct id — reliable (module instance, not window.posthog). */
export function getPosthogDistinctId(): string | null {
  if (!enabled) return null;
  try {
    return posthog.get_distinct_id?.() ?? null;
  } catch {
    return null;
  }
}

/** Current PostHog session id — ties a bug report to its session replay. */
export function getPosthogSessionId(): string | null {
  if (!enabled) return null;
  try {
    const fn = (posthog as unknown as PosthogSessionApi).get_session_id;
    return fn ? fn.call(posthog) ?? null : null;
  } catch {
    return null;
  }
}

/** Direct URL to the current session's replay, when the SDK exposes it. */
export function getPosthogReplayUrl(): string | null {
  if (!enabled) return null;
  try {
    const fn = (posthog as unknown as PosthogSessionApi).get_session_replay_url;
    return fn ? fn.call(posthog, { withTimestamp: true }) ?? null : null;
  } catch {
    return null;
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
