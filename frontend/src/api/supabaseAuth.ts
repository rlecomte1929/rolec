/**
 * Phase 1: Supabase sign-in after backend login.
 * Establishes Supabase session so tokens auto-refresh for feedback/review/RPC.
 */

import { supabase } from './supabase';

/**
 * Sign in to Supabase with email/password.
 * Call after backend login succeeds so Supabase session exists and auto-refreshes.
 * Non-blocking: if user doesn't exist in Supabase, we still allow app use (backend login worked).
 */
export async function signInSupabase(email: string, password: string): Promise<{ ok: boolean; error?: string }> {
  const e = (email || '').trim();
  if (!e || !password) return { ok: false, error: 'Email and password required' };
  try {
    const { data, error } = await supabase.auth.signInWithPassword({ email: e, password });
    if (error) {
      if (import.meta.env.DEV) {
        console.warn('[Supabase sign-in]', error.message, '(Backend login succeeded; Supabase features may need VITE_SUPABASE_ACCESS_TOKEN fallback)');
      }
      return { ok: false, error: error.message };
    }
    if (import.meta.env.DEV && data?.session) {
      console.debug('[Supabase sign-in] Session established; tokens will auto-refresh');
    }
    return { ok: true };
  } catch (err: any) {
    if (import.meta.env.DEV) {
      console.warn('[Supabase sign-in]', err?.message);
    }
    return { ok: false, error: err?.message };
  }
}

/**
 * Sign out from Supabase. Call on logout to clear Supabase session.
 */
export async function signOutSupabase(): Promise<void> {
  try {
    await supabase.auth.signOut();
  } catch (err) {
    if (import.meta.env.DEV) {
      console.warn('[Supabase sign-out]', err);
    }
  }
}
