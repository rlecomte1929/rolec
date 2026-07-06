import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the HTTP client so we exercise provisionTestDrive's error mapping in isolation
// (also keeps the test off client.ts's supabase import chain).
vi.mock('./client', () => ({ apiPost: vi.fn() }));

import { apiPost } from './client';
import { provisionTestDrive } from './testDrive';

const mockPost = apiPost as unknown as ReturnType<typeof vi.fn>;

/** Build an error shaped like the one buildApiError throws (status + detail + message). */
function apiError(status: number, detail: unknown, message: string) {
  return Object.assign(new Error(message), { status, detail });
}

beforeEach(() => vi.clearAllMocks());

describe('provisionTestDrive error mapping', () => {
  it('never leaks the raw Pydantic array on a 422 (the original bug)', async () => {
    // This is exactly what FastAPI returned for the empty invite_token: a JSON array
    // that buildApiError stringifies into err.message. It must not reach the user.
    const rawArray = [
      { type: 'string_too_short', loc: ['body', 'invite_token'], msg: 'String should have at least 1 character' },
    ];
    mockPost.mockRejectedValue(apiError(422, rawArray, JSON.stringify(rawArray)));

    const res = await provisionTestDrive({ first_name: 'Romain', tester_segment: 'prospect' });

    expect(res.ok).toBe(false);
    if (!res.ok) {
      expect(res.error).toBe('Please check your details and try again.');
      expect(res.error).not.toContain('string_too_short');
      expect(res.error).not.toContain('{');
    }
  });

  it('maps 404 to a friendly closed-test-drive message', async () => {
    mockPost.mockRejectedValue(apiError(404, 'Not found', 'Not found'));
    const res = await provisionTestDrive({ first_name: 'A', tester_segment: 'prospect' });
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.error).toMatch(/isn’t open right now/i);
  });

  it('maps 403 to a friendly invalid-invite message', async () => {
    mockPost.mockRejectedValue(apiError(403, 'Invalid or missing invite token', 'Invalid or missing invite token'));
    const res = await provisionTestDrive({ first_name: 'A', tester_segment: 'prospect' });
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.error).toMatch(/invite link is invalid/i);
  });

  it('returns success payload on a 200', async () => {
    mockPost.mockResolvedValue({
      session_id: 's1',
      corridor_id: 'FR_NO',
      campaign: 'insead-2026',
      hr: { username: 'HR-a-1', email: 'hr-a@probe.test', password: 'p1', role: 'HR' },
      employee: { username: 'EMP-a-1', email: 'emp-a@probe.test', password: 'p2', role: 'EMPLOYEE' },
    });
    const res = await provisionTestDrive({ first_name: 'A', tester_segment: 'prospect' });
    expect(res.ok).toBe(true);
    if (res.ok) expect(res.corridorId).toBe('FR_NO');
  });
});
