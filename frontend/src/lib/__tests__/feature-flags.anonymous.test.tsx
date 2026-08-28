import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { useEffect } from 'react';

// sdkLoaded fires when the Supabase chunk is first pulled in. The module registry caches
// it, so the factory runs at most once across the file — it can prove the SDK was never
// imported, but not that a later mount imported it again. onAuthStateChange is the
// per-mount signal, so the re-arm assertions use that.
const { sdkLoaded, onAuthStateChange } = vi.hoisted(() => ({
  sdkLoaded: vi.fn(),
  onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
}));

vi.mock('../../api/supabase', () => {
  sdkLoaded();
  return {
    supabase: {
      auth: {
        getSession: vi.fn(async () => ({ data: { session: null } })),
        onAuthStateChange,
      },
    },
  };
});

import { FeatureFlagProvider } from '../feature-flags';

// jsdom in this repo ships no localStorage — back it with a Map.
function installLocalStorage() {
  const store = new Map<string, string>();
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, String(v)),
      removeItem: (k: string) => void store.delete(k),
      clear: () => store.clear(),
      key: (i: number) => Array.from(store.keys())[i] ?? null,
      get length() {
        return store.size;
      },
    },
  });
}

/** Signs in (writes the token) and then client-side navigates, exactly as useAuth does. */
function SignInThenNavigate() {
  const navigate = useNavigate();
  useEffect(() => {
    window.localStorage.setItem('relopass_token', 'tok-123');
    navigate('/hr/dashboard');
  }, [navigate]);
  return null;
}

describe('FeatureFlagProvider · anonymous visitors do not load the auth SDK', () => {
  beforeEach(() => {
    installLocalStorage();
    sdkLoaded.mockClear();
    onAuthStateChange.mockClear();
  });

  it('never imports Supabase for a visitor with no session', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <FeatureFlagProvider>
          <div>marketing</div>
        </FeatureFlagProvider>
      </MemoryRouter>,
    );
    // Give any pending microtask-driven import a chance to run before asserting absence.
    await new Promise((r) => setTimeout(r, 20));
    expect(sdkLoaded).not.toHaveBeenCalled();
    expect(onAuthStateChange).not.toHaveBeenCalled();
  });

  it('imports Supabase at mount when a session already exists', async () => {
    window.localStorage.setItem('relopass_token', 'tok-123');
    render(
      <MemoryRouter initialEntries={['/hr/dashboard']}>
        <FeatureFlagProvider>
          <div>app</div>
        </FeatureFlagProvider>
      </MemoryRouter>,
    );
    await waitFor(() => expect(onAuthStateChange).toHaveBeenCalled());
  });

  // The regression this guards: sign-in navigates client-side, so the provider does not
  // remount. Without the re-arm the effect stays parked and flags never resolve for the
  // whole session.
  it('arms after a client-side sign-in, with no remount', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <FeatureFlagProvider>
          <Routes>
            <Route path="/" element={<SignInThenNavigate />} />
            <Route path="/hr/dashboard" element={<div>dashboard</div>} />
          </Routes>
        </FeatureFlagProvider>
      </MemoryRouter>,
    );
    await waitFor(() => expect(onAuthStateChange).toHaveBeenCalled());
  });
});
