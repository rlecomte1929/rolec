/**
 * Test-Drive provisioning API client (TD-3 / AIQ-1421).
 *
 * Wraps the public POST /api/test-drive/provision endpoint (TD-2, #1311). The
 * endpoint is unauthenticated; `apiPost` omits the Authorization header when no
 * session token is present, so a public visitor calls it fine.
 */
import { apiPost } from './client';

// TD-SEG (ICP instrumentation): the two optional one-tap segmentation answers captured
// on the /test-drive start form. Values mirror the backend Pydantic patterns and the DB
// CHECK constraints (20260929000000_test_drive_tester_segmentation.sql) exactly.
export type TestDriveCompanySize = '<50' | '50-500' | '500-2000' | '2000+';
export type TestDriveOwnsRelocation = 'run_it' | 'touch_it' | 'not_my_area';

export interface ProvisionInput {
  first_name: string;
  // TD-M0 (AIQ-1556, corrected): the tester's real contact, captured at the start so a
  // tester who consents is reachable even if they drop out. OPTIONAL — the relocation
  // data is synthetic, so nothing here forces real PII; omitted when left blank.
  tester_email?: string;
  corridor_id?: string;
  // TD-FIX-2 (AIQ-1503): optional — omitted for the single-link flow (segment is
  // captured later via the survey's one-tap self-ID), set only for explicit ?segment=.
  tester_segment?: 'internal' | 'prospect';
  invite_token?: string;
  campaign?: string;
  // TD-SEG: optional one-tap segmentation — omitted entirely when the tester skips the
  // tap (stored NULL server-side, on the same test_sessions row as the survey linkage).
  company_size?: TestDriveCompanySize;
  owns_relocation?: TestDriveOwnsRelocation;
}

export interface TestDriveCredential {
  username: string;
  email: string;
  password: string;
  role: 'HR' | 'EMPLOYEE';
}

interface ProvisionResponse {
  session_id: string;
  corridor_id: string;
  campaign: string;
  hr: TestDriveCredential;
  employee: TestDriveCredential;
}

export interface ProvisionSuccess {
  ok: true;
  sessionId: string;
  corridorId: string;
  campaign: string;
  hr: TestDriveCredential;
  employee: TestDriveCredential;
}

export interface ProvisionFailure {
  ok: false;
  error: string;
}

export type ProvisionResult = ProvisionSuccess | ProvisionFailure;

export async function provisionTestDrive(input: ProvisionInput): Promise<ProvisionResult> {
  try {
    const data = await apiPost<ProvisionResponse>('/api/test-drive/provision', input);
    return {
      ok: true,
      sessionId: data.session_id,
      corridorId: data.corridor_id,
      campaign: data.campaign,
      hr: data.hr,
      employee: data.employee,
    };
  } catch (err) {
    const status = (err as { status?: number })?.status;
    const detail = (err as { detail?: unknown })?.detail;
    // Default to a safe generic message. We never surface err.message here: on a 422
    // it is the stringified Pydantic error array, which must not leak to the page.
    let error = 'Something went wrong. Please try again.';
    if (status === 404) {
      error = 'This test drive isn’t open right now. Check with whoever sent you the link.';
    } else if (status === 403) {
      error = 'This invite link is invalid or has expired.';
    } else if (status === 422) {
      error = 'Please check your details and try again.';
    } else if (typeof detail === 'string' && detail) {
      error = detail;
    }
    return { ok: false, error };
  }
}

// ── TD-5 (AIQ-1423): completion survey ────────────────────────────────────────

export interface SurveyInput {
  session_id?: string;
  campaign?: string;
  corridor_id?: string;
  tester_segment?: 'internal' | 'prospect';
  tester_name?: string;
  tester_email?: string;
  tester_company_role?: string;
  tester_sector?: string;
  q1_overall?: number;
  q2_friction?: string;
  q3_problem_fit?: 'yes' | 'somewhat' | 'no';
  q3_why?: string;
  // TD-EEA (INSEAD cohort): permit relevance — EEA free movement vs Employment Permit.
  permit_relevance?: 'yes' | 'not_yet' | 'no';
  q4_change?: string;
  // TD-M4 (AIQ-1559): trust / intent-to-use.
  trust_intent?: 'yes' | 'maybe' | 'no';
  trust_intent_why?: string;
  testimonial?: string;
  testimonial_consent?: boolean;
  pilot_interest?: 'yes' | 'maybe' | 'no';
  pilot_note?: string;
  referral_name?: string;
  referral_company_role?: string;
  referral_contact?: string;
  referral_consent?: boolean;
}

export interface SurveySuccess {
  ok: true;
  responseId: string;
}

export type SurveyResult = SurveySuccess | ProvisionFailure;

export async function submitSurvey(input: SurveyInput): Promise<SurveyResult> {
  try {
    const data = await apiPost<{ ok: boolean; response_id: string }>(
      '/api/test-drive/survey',
      input,
    );
    return { ok: true, responseId: data.response_id };
  } catch (err) {
    const status = (err as { status?: number })?.status;
    let error =
      err instanceof Error ? err.message : 'Something went wrong. Please try again.';
    if (status === 404) {
      error = 'This survey isn’t open right now.';
    }
    return { ok: false, error };
  }
}

// ── TD-FIX-1 (AIQ-1502): record completion ────────────────────────────────────

/**
 * Mark a test session complete via POST /api/test-drive/complete. Best-effort: the
 * caller awaits this before routing to the survey, but a failure must never trap the
 * tester on the page — mirrors `recordTestDriveEvent`, so it always resolves.
 */
export async function completeTestDrive(sessionId: string): Promise<void> {
  try {
    await apiPost<{ ok: boolean }>('/api/test-drive/complete', { session_id: sessionId });
  } catch {
    /* completion telemetry is best-effort — log-and-continue, never block the tester */
  }
}

// ── TD-8 (AIQ-1426): funnel-event recorder (best-effort) ──────────────────────

export interface TestDriveEventInput {
  event_type: string;
  session_id?: string;
  campaign?: string;
  corridor_id?: string;
  tester_segment?: 'internal' | 'prospect';
  invite_token?: string;
  metadata?: Record<string, string | number | boolean>;
}

export async function recordTestDriveEvent(input: TestDriveEventInput): Promise<void> {
  try {
    await apiPost<{ ok: boolean }>('/api/test-drive/event', input);
  } catch {
    /* funnel telemetry is best-effort — never surface to the user */
  }
}

// ── TD-FIX-4 (AIQ-1505): mid-journey stage events ─────────────────────────────
/** localStorage slice stashed by TestDrivePage at provision (same key it uses). */
const TEST_DRIVE_LS_KEY = 'relopass_test_drive';

export type TestDriveStage =
  | 'hr-handoff'
  | 'intake-start'
  | 'intake-completed'
  | 'roadmap-reached'
  | 'vendor-selected';

export type TestDriveSlice = {
  session_id?: string;
  corridor_id?: string;
  tester_segment?: string;
  campaign?: string;
};

/**
 * The active test-drive session stashed by TestDrivePage at provision, or null.
 * Returns null for every real user — this is the app's only client-side signal that
 * the current browser is running a test drive. Browser-local and therefore NOT a
 * security control: it gates UI affordances only (TD-FIX-7 suppresses the intake's
 * "unlock" escape hatch with it). The corridor itself is enforced server-side.
 */
export function getTestDriveSession(): TestDriveSlice | null {
  try {
    const raw = localStorage.getItem(TEST_DRIVE_LS_KEY);
    const slice = raw ? (JSON.parse(raw) as TestDriveSlice) : null;
    return slice?.session_id ? slice : null;
  } catch {
    return null;
  }
}

/**
 * Emit a mid-journey funnel event for the active test-drive session, if any. The tester
 * runs the HR + employee journeys logged in as the seeded @probe.test accounts in the
 * same browser where /test-drive stashed the session, so the session_id is in localStorage.
 * No-op (and never throws) when there is no active test-drive session — i.e. for real
 * users this does nothing. Fire-and-forget; best-effort via recordTestDriveEvent.
 */
export function emitTestDriveStage(stage: TestDriveStage): void {
  const slice = getTestDriveSession();
  if (!slice?.session_id) return; // not a test-drive session — no-op for real users
  void recordTestDriveEvent({
    event_type: stage,
    session_id: slice.session_id,
    corridor_id: slice.corridor_id,
    tester_segment:
      slice.tester_segment === 'internal' || slice.tester_segment === 'prospect'
        ? slice.tester_segment
        : undefined,
    campaign: slice.campaign,
  });
}

// ── TD-M1 (AIQ-1557): dropout / friction capture ──────────────────────────────
/**
 * Record a `friction` funnel event for the active test-drive session — the stage the
 * tester stalled on or left, plus a one-tap reason and optional free text. No-op (and
 * never throws) for real users (no test-drive session). metadata is short scalar strings
 * only, matching the backend record_event filter. Never sent to an LLM.
 */
export function emitTestDriveFriction(stage: string, reason: string, text?: string): void {
  const slice = getTestDriveSession();
  if (!slice?.session_id) return; // not a test-drive session — no-op for real users
  const metadata: Record<string, string> = {
    stage: (stage || 'unknown').slice(0, 64),
    reason: (reason || 'other').slice(0, 40),
  };
  const t = (text || '').trim();
  if (t) metadata.text = t.slice(0, 200);
  void recordTestDriveEvent({
    event_type: 'friction',
    session_id: slice.session_id,
    corridor_id: slice.corridor_id,
    tester_segment:
      slice.tester_segment === 'internal' || slice.tester_segment === 'prospect'
        ? slice.tester_segment
        : undefined,
    campaign: slice.campaign,
    metadata,
  });
}
