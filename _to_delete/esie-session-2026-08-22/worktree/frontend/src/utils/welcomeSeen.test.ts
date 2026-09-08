import { describe, it, expect, beforeEach } from 'vitest';
import { hasSeenWelcome, markWelcomeSeen, seedWelcomeSeenFromLogin } from './welcomeSeen';

// jsdom in this config doesn't expose localStorage — install a Map-backed shim on
// globalThis (=== window) so the bare `localStorage` the module uses resolves.
function installStore() {
  const store = new Map<string, string>();
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, String(v)),
      removeItem: (k: string) => void store.delete(k),
      clear: () => store.clear(),
    },
  });
}

function installBlockedStore() {
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem: () => {
        throw new Error('blocked');
      },
      setItem: () => {
        throw new Error('blocked');
      },
      removeItem: () => {},
      clear: () => {},
    },
  });
}

describe('welcomeSeen', () => {
  beforeEach(() => {
    installStore();
  });

  it('marks and reads back the flag, scoped per user', () => {
    expect(hasSeenWelcome('u1')).toBe(false);
    markWelcomeSeen('u1');
    expect(hasSeenWelcome('u1')).toBe(true);
    // a different user is unaffected
    expect(hasSeenWelcome('u2')).toBe(false);
  });

  it('treats blocked storage as already-seen (never traps the user) and never throws', () => {
    installBlockedStore();
    expect(hasSeenWelcome('u1')).toBe(true);
    expect(() => markWelcomeSeen('u1')).not.toThrow();
  });
});

// AIQ-1701 — the dismissal is owned server-side (profiles.welcome_seen_at) and
// mirrored here at login, so it survives a change of browser or device.
describe('seedWelcomeSeenFromLogin', () => {
  beforeEach(() => {
    installStore();
  });

  it('seeds a fresh browser when the server says the user already dismissed it', () => {
    // THE BUG: this browser has never seen the flag (new device / incognito), but the
    // user dismissed the welcome elsewhere. Before AIQ-1701 they were re-onboarded.
    expect(hasSeenWelcome('u1')).toBe(false);
    seedWelcomeSeenFromLogin('u1', true);
    expect(hasSeenWelcome('u1')).toBe(true);
  });

  it('leaves a genuinely new user unseeded, so they still get the welcome once', () => {
    seedWelcomeSeenFromLogin('u1', false);
    expect(hasSeenWelcome('u1')).toBe(false);
  });

  it('never CLEARS an existing flag when the server reports false', () => {
    // A legacy account with no profiles row reports false. Clearing here would
    // re-onboard someone on the very login that was meant to stop doing that.
    markWelcomeSeen('u1');
    seedWelcomeSeenFromLogin('u1', false);
    seedWelcomeSeenFromLogin('u1', null);
    seedWelcomeSeenFromLogin('u1', undefined);
    expect(hasSeenWelcome('u1')).toBe(true);
  });

  it('ignores a missing user id and never throws on blocked storage', () => {
    seedWelcomeSeenFromLogin('', true);
    expect(hasSeenWelcome('u1')).toBe(false);
    installBlockedStore();
    expect(() => seedWelcomeSeenFromLogin('u1', true)).not.toThrow();
  });
});
