import { describe, it, expect, beforeEach } from 'vitest';
import { hasSeenWelcome, markWelcomeSeen } from './welcomeSeen';

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
