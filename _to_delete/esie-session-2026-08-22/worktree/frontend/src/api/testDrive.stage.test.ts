import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock the network client (also keeps the test off client.ts's supabase import chain).
vi.mock('./client', () => ({ apiPost: vi.fn(), API_BASE_URL: '' }));

import { apiPost } from './client';
import { emitTestDriveStage } from './testDrive';

const mockPost = apiPost as unknown as ReturnType<typeof vi.fn>;

// jsdom has no localStorage — shim a Map-backed one (known vitest trap).
function shimLocalStorage() {
  const store = new Map<string, string>();
  const ls = {
    getItem: (k: string) => (store.has(k) ? (store.get(k) as string) : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
    key: (i: number) => Array.from(store.keys())[i] ?? null,
    get length() {
      return store.size;
    },
  };
  Object.defineProperty(window, 'localStorage', { value: ls, configurable: true, writable: true });
}

beforeEach(() => {
  shimLocalStorage();
  mockPost.mockReset();
  mockPost.mockResolvedValue({ ok: true });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('emitTestDriveStage (TD-FIX-4)', () => {
  it('records the stage for an active test-drive session', async () => {
    window.localStorage.setItem(
      'relopass_test_drive',
      JSON.stringify({ session_id: 'sess-9', corridor_id: 'GB_US', tester_segment: 'prospect', campaign: 'insead-2026' }),
    );
    emitTestDriveStage('roadmap-reached');
    await Promise.resolve();

    expect(mockPost).toHaveBeenCalledTimes(1);
    const [path, body] = mockPost.mock.calls[0];
    expect(path).toBe('/api/test-drive/event');
    expect(body).toMatchObject({
      event_type: 'roadmap-reached',
      session_id: 'sess-9',
      corridor_id: 'GB_US',
      tester_segment: 'prospect',
    });
  });

  it('is a no-op when there is no active test-drive session (real users)', async () => {
    emitTestDriveStage('intake-start');
    await Promise.resolve();
    expect(mockPost).not.toHaveBeenCalled();
  });
});
