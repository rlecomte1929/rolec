/**
 * supabase.ts — ReloPass Supabase client singleton + auth helpers
 * ─────────────────────────────────────────────────────────────────────────────
 * Exports:
 *   supabase          — singleton SupabaseClient
 *   getCurrentUser()  — returns cached profile (id, email, role, plan_tier) | null
 *   signIn()          — email/password sign-in
 *   signUp()          — new account creation
 *   signOut()         — clears session
 *   onAuthChange()    — wraps supabase.auth.onAuthStateChange
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { type User } from '@supabase/supabase-js';
import type { PlanTier, UserRole } from '../types/relopass-api-contracts';
import { supabase } from '../api/supabase';

// ─── Client ──────────────────────────────────────────────────────────────────

// Re-export the single app-wide Supabase client (defined in ../api/supabase).
// Existing `import { supabase } from '../lib/supabase'` call sites keep working
// without instantiating a second GoTrueClient (which deadlocks the LockManager).
export { supabase };

// ─── Profile cache ────────────────────────────────────────────────────────────

export interface UserProfile {
  id: string;
  email: string;
  role: UserRole;
  plan_tier: PlanTier;
}

let _profileCache: UserProfile | null = null;

/** Invalidate the in-memory profile cache (e.g. on sign-out). */
function clearProfileCache(): void {
  _profileCache = null;
}

// ─── getCurrentUser ───────────────────────────────────────────────────────────

/**
 * Returns the currently authenticated user's profile (id, email, role, plan_tier).
 * Reads from the `profiles` table on first call; result is cached in module scope.
 * Returns null if the user is not authenticated or the profile cannot be loaded.
 */
export async function getCurrentUser(): Promise<UserProfile | null> {
  if (_profileCache) return _profileCache;

  const {
    data: { user },
    error: sessionError,
  } = await supabase.auth.getUser();

  if (sessionError || !user) return null;

  const { data: profile, error: profileError } = await supabase
    .from('profiles')
    .select('id, email, role, plan_tier')
    .eq('id', user.id)
    .single();

  if (profileError || !profile) return null;

  _profileCache = {
    id: profile.id as string,
    email: profile.email as string,
    role: profile.role as UserRole,
    plan_tier: profile.plan_tier as PlanTier,
  };

  return _profileCache;
}

// ─── signIn ───────────────────────────────────────────────────────────────────

export interface SignInResult {
  access_token: string;
  user_id: string;
  role: UserRole;
}

/**
 * Sign in with email and password.
 * Throws if credentials are invalid or Supabase returns an error.
 */
export async function signIn(email: string, password: string): Promise<SignInResult> {
  clearProfileCache();

  const { data, error } = await supabase.auth.signInWithPassword({ email, password });

  if (error || !data.session || !data.user) {
    throw new Error(error?.message ?? 'Sign-in failed.');
  }

  // Fetch role from profiles
  const { data: profile, error: profileError } = await supabase
    .from('profiles')
    .select('role')
    .eq('id', data.user.id)
    .single();

  if (profileError || !profile) {
    throw new Error('Signed in but profile could not be loaded.');
  }

  return {
    access_token: data.session.access_token,
    user_id: data.user.id,
    role: profile.role as UserRole,
  };
}

// ─── signUp ───────────────────────────────────────────────────────────────────

export interface SignUpOptions {
  full_name?: string;
  company_slug?: string;
  invite_token?: string;
}

export interface SignUpResult {
  user_id: string;
}

/**
 * Create a new account.
 * Metadata (full_name, company_slug, invite_token) is passed as user metadata
 * so that server-side triggers can create the profile row.
 * Throws if registration fails.
 */
export async function signUp(
  email: string,
  password: string,
  opts: SignUpOptions = {}
): Promise<SignUpResult> {
  clearProfileCache();

  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: {
        full_name: opts.full_name ?? '',
        company_slug: opts.company_slug ?? null,
        invite_token: opts.invite_token ?? null,
      },
    },
  });

  if (error || !data.user) {
    throw new Error(error?.message ?? 'Sign-up failed.');
  }

  return { user_id: data.user.id };
}

// ─── signOut ──────────────────────────────────────────────────────────────────

/** Sign out and clear the profile cache. */
export async function signOut(): Promise<void> {
  clearProfileCache();
  const { error } = await supabase.auth.signOut();
  if (error) throw new Error(error.message);
}

// ─── onAuthChange ─────────────────────────────────────────────────────────────

type AuthChangeCallback = (user: User | null) => void;

/**
 * Subscribe to authentication state changes.
 * Returns an unsubscribe function — call it in useEffect cleanup.
 *
 * @example
 *   const unsub = onAuthChange(user => setUser(user));
 *   return () => unsub();
 */
export function onAuthChange(callback: AuthChangeCallback): () => void {
  const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
    if (!session) clearProfileCache();
    callback(session?.user ?? null);
  });

  return () => subscription.unsubscribe();
}
