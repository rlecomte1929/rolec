/**
 * Lazy PostHog load — the SDK must not enter the static graph. These tests
 * assert the GDPR contract: no import / no init / no capture until consent is
 * granted (or a test-drive session starts replay).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { waitFor } from '@testing-library/react';
import {
  initAnalytics,
  grantAnalyticsConsent,
  revokeAnalyticsConsent,
  getAnalyticsConsent,
  track,
  emitMarketingEvent,
  ensureTestDriveReplay,
  resetAnalyticsForTests,
} from './analytics';

const { posthogImported, mockPosthog } = vi.hoisted(() => ({
  posthogImported: vi.fn(),
  mockPosthog: {
    init: vi.fn(),
    opt_in_capturing: vi.fn(),
    opt_out_capturing: vi.fn(),
    capture: vi.fn(),
    register: vi.fn(),
    identify: vi.fn(),
    startSessionRecording: vi.fn(),
    get_distinct_id: vi.fn(() => 'dist-1'),
  },
}));

vi.mock('posthog-js', () => {
  posthogImported();
  return { default: mockPosthog };
});

vi.mock('./config/env', () => ({
  env: {
    posthogKey: 'phc_test_key',
    posthogHost: 'https://eu.i.posthog.com',
    apiUrl: 'http://localhost:8000',
  },
}));

vi.mock('./api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  invalidateApiCache: vi.fn(),
}));

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

describe('analytics lazy posthog-js', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'localStorage', { value: localStorageShim, configurable: true });
    Object.defineProperty(globalThis, 'localStorage', { value: localStorageShim, configurable: true });
    store.clear();
    resetAnalyticsForTests();
    vi.clearAllMocks();
  });
  afterEach(() => {
    store.clear();
    resetAnalyticsForTests();
  });

  it('does not import posthog-js when consent is undecided', async () => {
    initAnalytics();
    track('page_view');
    emitMarketingEvent('cta_click');
    await Promise.resolve();
    expect(posthogImported).not.toHaveBeenCalled();
    expect(mockPosthog.init).not.toHaveBeenCalled();
    expect(mockPosthog.capture).not.toHaveBeenCalled();
  });

  it('does not import posthog-js when consent is denied', async () => {
    store.set(CONSENT_KEY, 'denied');
    initAnalytics();
    await Promise.resolve();
    expect(posthogImported).not.toHaveBeenCalled();
    expect(mockPosthog.init).not.toHaveBeenCalled();
  });

  it('inits PostHog when grantAnalyticsConsent runs', async () => {
    grantAnalyticsConsent();
    expect(getAnalyticsConsent()).toBe('granted');
    await waitFor(() => expect(mockPosthog.init).toHaveBeenCalled());
    expect(posthogImported).toHaveBeenCalled();
    expect(mockPosthog.init).toHaveBeenCalledWith(
      'phc_test_key',
      expect.objectContaining({
        api_host: 'https://eu.i.posthog.com',
        opt_out_capturing_by_default: false,
        property_denylist: expect.arrayContaining(['email', 'iban', 'password']),
      }),
    );
    const opts = mockPosthog.init.mock.calls[0][1] as { property_denylist: string[] };
    expect(opts.property_denylist).not.toContain('token');
    expect(mockPosthog.opt_in_capturing).toHaveBeenCalled();
  });

  it('inits on load for a returning visitor who already granted', async () => {
    store.set(CONSENT_KEY, 'granted');
    expect(getAnalyticsConsent()).toBe('granted');
    initAnalytics();
    await waitFor(() => expect(mockPosthog.init).toHaveBeenCalled());
  });

  it('revokeAnalyticsConsent does not throw when the SDK never loaded', async () => {
    expect(() => revokeAnalyticsConsent()).not.toThrow();
    expect(getAnalyticsConsent()).toBe('denied');
    expect(posthogImported).not.toHaveBeenCalled();
    expect(mockPosthog.opt_out_capturing).not.toHaveBeenCalled();
  });

  it('opts out after revoke once the SDK is live', async () => {
    grantAnalyticsConsent();
    await waitFor(() => expect(mockPosthog.init).toHaveBeenCalled());
    revokeAnalyticsConsent();
    expect(mockPosthog.opt_out_capturing).toHaveBeenCalled();
  });

  it('does not load posthog-js for ensureTestDriveReplay without a session', async () => {
    ensureTestDriveReplay();
    await Promise.resolve();
    await Promise.resolve();
    expect(posthogImported).not.toHaveBeenCalled();
  });

  it('loads posthog-js and starts replay for a test-drive session', async () => {
    store.set('relopass_test_drive', JSON.stringify({
      session_id: 's-td',
      campaign: 'qa',
      corridor_id: 'FR_NO',
    }));
    ensureTestDriveReplay();
    await waitFor(() => expect(mockPosthog.startSessionRecording).toHaveBeenCalled());
    expect(mockPosthog.opt_in_capturing).toHaveBeenCalled();
    expect(mockPosthog.identify).toHaveBeenCalledWith(
      's-td',
      expect.objectContaining({ test_drive_session_id: 's-td' }),
    );
  });
});
