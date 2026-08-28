/**
 * Phase 1: Supabase sign-in after backend login.
 * Establishes Supabase session so tokens auto-refresh for feedback/review/RPC.
 */

import { logger } from '../lib/logger';
// Imported dynamically, not statically — see api/demoBooking.ts for the full reason.
// api/supabase.ts is unchanged, so this resolves to the same module-scope singleton.

/**
 * Sign in to Supabase with email/password.
 * Call after backend login succeeds so Supabase session exists and auto-refreshes.
 * Non-blocking: if user doesn't exist in Supabase, we still allow app use (backend login worked).
 */
/** ~10s is the observed LockManager deadlock; 15s leaves headroom for a slow-but-real login. */
const SIGN_IN_TIMEOUT_MS = 15_000;

/** Reject rather than hang forever. The timer is cleared either way so it never leaks. */
async function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      promise,
      new Promise<never>((_, reject) => {
        timer = setTimeout(
          () => reject(new Error(`Supabase sign-in did not settle within ${ms}ms`)),
          ms,
        );
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export async function signInSupabase(email: string, password: string): Promise<{ ok: boolean; error?: string }> {
  const e = (email || '').trim();
  if (!e || !password) return { ok: false, error: 'Email and password required' };
  try {
    const { supabase } = await import('./supabase');
    // Bounded, because a hang here is otherwise INVISIBLE. useAuth fires this
    // fire-and-forget AFTER the post-login redirect, trackAuthPerf is disabled in
    // production, and client.ts's 12s axios timeout covers /api/* only — not the direct
    // call to *.supabase.co. If two GoTrue clients ever end up sharing the
    // sb-*-auth-token key they deadlock the Navigator LockManager and this never settles:
    // login LOOKS fine, then token refresh and realtime silently never work. Failing
    // loudly after 15s turns that into something a person can see.
    const { data, error } = await withTimeout(
      supabase.auth.signInWithPassword({ email: e, password }),
      SIGN_IN_TIMEOUT_MS,
    );
    if (error) {
      if (import.meta.env.DEV) {
        logger.warn('[Supabase sign-in]', error.message, '(Backend login succeeded; Supabase features may need VITE_SUPABASE_ACCESS_TOKEN fallback)');
      }
      return { ok: false, error: error.message };
    }
    if (import.meta.env.DEV && data?.session) {
      logger.debug('[Supabase sign-in] Session established; tokens will auto-refresh');
    }
    return { ok: true };
  } catch (err) {
    const msg = err instanceof Error ? err.message : undefined;
    // Deliberately NOT DEV-gated: the timeout above is the one signal that a LockManager
    // deadlock has happened, and gating it to DEV is why such a failure would go unseen
    // in production.
    logger.warn('[Supabase sign-in]', msg);
    return { ok: false, error: msg };
  }
}

/**
 * Sign out from Supabase. Call on logout to clear Supabase session.
 */
export async function signOutSupabase(): Promise<void> {
  try {
    const { supabase } = await import('./supabase');
    await supabase.auth.signOut();
  } catch (err) {
    if (import.meta.env.DEV) {
      logger.warn('[Supabase sign-out]', err);
    }
  }
}
