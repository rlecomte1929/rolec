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
  corridor_id: string;
  tester_segment: 'internal' | 'prospect';
  invite_token: string;
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
    let error =
      err instanceof Error ? err.message : 'Something went wrong. Please try again.';
    if (status === 404) {
      error = 'This test drive isn’t open right now. Check with whoever sent you the link.';
    } else if (status === 403) {
      error = 'This invite link is invalid or has expired.';
    } else if (typeof detail === 'string' && detail) {
      error = detail;
    }
    return { ok: false, error };
  }
}
