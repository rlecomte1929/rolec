import { describe, it, expect } from 'vitest';
import { env } from './env';

/**
 * [AIQ-1491] The passkey flag is a safety gate, not a preference.
 *
 * Passkeys need the WebAuthn toggle enabled on the Supabase project; auth-js is
 * explicit that without `auth.experimental.passkey: true` "all methods throw".
 * While that toggle is off, a rendered passkey button is a dead end — and the
 * one shipped here sent users to a *second* dead end in Settings. So the flag
 * must default OFF, and it must only be on for the literal string 'true'.
 *
 * vitest runs with the VITE_* vars unset (MODE='test'), which is exactly the
 * "operator forgot to set it" case we care about.
 */
describe('env.enablePasskeys', () => {
  it('is OFF when VITE_ENABLE_PASSKEYS is unset', () => {
    expect(import.meta.env.VITE_ENABLE_PASSKEYS).toBeUndefined();
    expect(env.enablePasskeys).toBe(false);
  });

  it('is a boolean, so `env.enablePasskeys && <UI/>` cannot leak a string into the tree', () => {
    expect(typeof env.enablePasskeys).toBe('boolean');
  });
});
