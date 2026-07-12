/**
 * Test-Drive provisioning API client (TD-3 / AIQ-1421).
 *
 * Wraps the public POST /api/test-drive/provision endpoint (TD-2, #1311). The
 * endpoint is unauthenticated; `apiPost` omits the Authorization header when no
 * session token is present, so a public visitor calls it fine.
 */
import { apiPost } from './client';

export interface ProvisionInput {
  first_name: string;
  corridor_id?: string;
  tester_segment: 'internal' | 'prospect';
  invite_token?: string;
  campaign?: string;
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
  q4_change?: string;
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
