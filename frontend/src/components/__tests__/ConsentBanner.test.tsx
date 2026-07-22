/**
 * GDPR consent gate — the user-facing contract that governs whether analytics
 * (PostHog events + cookies) is allowed to run. Analytics is opt-OUT by default
 * (see initAnalytics `opt_out_capturing_by_default`); this banner is the only
 * opt-in surface. These assertions guard the parts that must never regress:
 *   • a first-time visitor is asked (banner shows, no stored decision)
 *   • Accept / Decline persist the decision and dismiss the banner
 *   • a returning visitor who already decided is never asked again
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { ConsentBanner } from '../ConsentBanner';
import { getAnalyticsConsent } from '../../analytics';

// Sever the analytics → api/testDrive → api/client → api/supabase import chain
// (api/supabase throws "supabaseUrl is required" at import when VITE_ env is
// unset — the known jsdom import trap). We don't exercise any client call here.
vi.mock('../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  invalidateApiCache: vi.fn(),
}));

// posthog-js is a passthrough here — opt in/out is a no-op until initAnalytics
// runs with a key (never in tests). We assert the persisted-decision contract,
// which is what actually gates capturing on the next SDK load.
vi.mock('posthog-js', () => ({
  default: { opt_in_capturing: vi.fn(), opt_out_capturing: vi.fn() },
}));

// jsdom ships no localStorage under the default vitest runner — shim a
// Map-backed one so the consent helpers persist for real in the test.
const store = new Map<string, string>();
const localStorageShim = {
  getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
  setItem: (k: string, v: string) => void store.set(k, String(v)),
  removeItem: (k: string) => void store.delete(k),
  clear: () => store.clear(),
  key: (i: number) => Array.from(store.keys())[i] ?? null,
  get length() {
    return store.size;
  },
};

const CONSENT_KEY = 'relopass_analytics_consent';

function renderBanner() {
  return render(
    <MemoryRouter>
      <ConsentBanner />
    </MemoryRouter>,
  );
}

describe('ConsentBanner', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'localStorage', { value: localStorageShim, configurable: true });
    store.clear();
  });
  afterEach(() => store.clear());

  it('shows for a visitor with no stored decision', () => {
    expect(getAnalyticsConsent()).toBeNull();
    renderBanner();
    expect(screen.getByRole('dialog', { name: /analytics consent/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /accept analytics/i })).toBeInTheDocument();
  });

  it('Accept persists "granted" and dismisses the banner', () => {
    renderBanner();
    fireEvent.click(screen.getByRole('button', { name: /accept analytics/i }));
    expect(store.get(CONSENT_KEY)).toBe('granted');
    expect(getAnalyticsConsent()).toBe('granted');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('Decline persists "denied" and dismisses the banner', () => {
    renderBanner();
    fireEvent.click(screen.getByRole('button', { name: /decline/i }));
    expect(store.get(CONSENT_KEY)).toBe('denied');
    expect(getAnalyticsConsent()).toBe('denied');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('does not show once a decision exists (granted or denied)', () => {
    store.set(CONSENT_KEY, 'granted');
    const { unmount } = renderBanner();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    unmount();

    store.set(CONSENT_KEY, 'denied');
    renderBanner();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  // AIQ-1660: the band is suppressed for the admin profile only. A first-time
  // ADMIN visitor (no stored decision, so it would otherwise show) sees nothing.
  it('is hidden for the admin profile even with no stored decision', () => {
    expect(getAnalyticsConsent()).toBeNull();
    store.set('relopass_role', 'ADMIN');
    renderBanner();
    expect(screen.queryByRole('dialog', { name: /analytics consent/i })).not.toBeInTheDocument();
  });

  it('still shows for a non-admin (HR) first-time visitor', () => {
    store.set('relopass_role', 'HR');
    renderBanner();
    expect(screen.getByRole('dialog', { name: /analytics consent/i })).toBeInTheDocument();
  });

  // AIQ-1678: the banner mounts ONCE at the app root and never remounts, so it must
  // re-evaluate admin status when the role is set AFTER first mount (the same-page-load
  // login case). Regression for the stale `useMemo(..., [])` that cached the pre-login
  // 'false' forever. Here the banner stays mounted; the role is written after mount, then a
  // navigation (as happens on login redirect) must make it hide.
  it('hides once the user becomes admin after mount, without remounting', () => {
    function Nav() {
      const navigate = useNavigate();
      return <button onClick={() => navigate('/admin')}>go admin</button>;
    }
    // First mount with no role → a first-time visitor sees the band.
    render(
      <MemoryRouter initialEntries={['/login']}>
        <ConsentBanner />
        <Nav />
      </MemoryRouter>,
    );
    expect(screen.getByRole('dialog', { name: /analytics consent/i })).toBeInTheDocument();

    // Log in as admin (role written) and navigate — the same still-mounted banner must hide.
    store.set('relopass_role', 'ADMIN');
    fireEvent.click(screen.getByRole('button', { name: /go admin/i }));
    expect(screen.queryByRole('dialog', { name: /analytics consent/i })).not.toBeInTheDocument();
  });
});
