import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getCaseProviders } from '../hrCoordination';

/**
 * AIQ-862 regression guard. hr-coordination calls (providers list + task
 * assign/update/cancel) previously read the token from `hr_token`, a
 * localStorage key that is never written anywhere in the app — so every
 * request went out as `Authorization: Bearer null` and the backend returned
 * 401. They must use `relopass_token` (the key login writes and the shared
 * axios client reads).
 */

// The project's jsdom env does not shim localStorage (see ChangelogBell.test) —
// install a deterministic in-memory stub.
function installLocalStorageStub() {
  const store: Record<string, string> = {};
  const storage: Storage = {
    get length() {
      return Object.keys(store).length;
    },
    clear: () => {
      for (const k of Object.keys(store)) delete store[k];
    },
    getItem: (k: string) => (k in store ? store[k] : null),
    key: (i: number) => Object.keys(store)[i] ?? null,
    removeItem: (k: string) => {
      delete store[k];
    },
    setItem: (k: string, v: string) => {
      store[k] = String(v);
    },
  };
  Object.defineProperty(window, 'localStorage', {
    value: storage,
    configurable: true,
    writable: true,
  });
}

function mockOkFetch() {
  const fetchMock = vi
    .fn()
    .mockResolvedValue(
      new Response(JSON.stringify({ providers: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function authHeaderFrom(fetchMock: ReturnType<typeof vi.fn>): string {
  const init = fetchMock.mock.calls[0][1] as RequestInit;
  return (init.headers as Record<string, string>).Authorization;
}

describe('hrCoordination auth header (AIQ-862)', () => {
  beforeEach(() => {
    installLocalStorageStub();
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sends the relopass_token as the Bearer credential', async () => {
    window.localStorage.setItem('relopass_token', 'tok-abc123');
    const fetchMock = mockOkFetch();

    await getCaseProviders('case-1');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(authHeaderFrom(fetchMock)).toBe('Bearer tok-abc123');
  });

  it('does NOT read the unused hr_token key', async () => {
    // Both keys present, different values — proves we read relopass_token.
    window.localStorage.setItem('hr_token', 'WRONG-stale-token');
    window.localStorage.setItem('relopass_token', 'tok-correct');
    const fetchMock = mockOkFetch();

    await getCaseProviders('case-1');

    expect(authHeaderFrom(fetchMock)).toBe('Bearer tok-correct');
    expect(authHeaderFrom(fetchMock)).not.toContain('WRONG-stale-token');
  });

  it('never emits the literal "Bearer null" when no token is stored', async () => {
    const fetchMock = mockOkFetch();

    await getCaseProviders('case-1');

    // Empty string, not the string "null" — the old bug.
    expect(authHeaderFrom(fetchMock)).toBe('Bearer ');
  });
});
