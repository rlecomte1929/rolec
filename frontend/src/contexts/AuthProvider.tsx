/**
 * AuthProvider.tsx — ReloPass authentication context
 * ─────────────────────────────────────────────────────────────────────────────
 * Provides:
 *   AuthContext  — { user, loading, signIn, signOut }
 *   AuthProvider — wraps the app; listens to Supabase auth changes
 *   useAuth()    — hook to consume the context
 *
 * Behaviour:
 *   - Renders a full-screen LoadingSpinner while the initial session is resolving.
 *   - On successful auth: fetches /profiles/:id and sets user state.
 *   - On unauthenticated access to protected content: dispatches 'rp:auth-required'
 *     custom event so any listener (router guard, modal) can react.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import { supabase, onAuthChange, signIn as supabaseSignIn, signOut as supabaseSignOut } from '../lib/supabase';
import type { PlanTier, UserRole } from '../types/relopass-api-contracts';
import { LoadingSpinner } from '../features/platform-v2/shared/index';
import { initRelopassAnalytics, resetRelopassAnalytics, trackEvent } from '../lib/analytics';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  plan_tier: PlanTier;
  avatar_url: string | null;
}

interface AuthContextValue {
  /** Authenticated user, or null when signed out */
  user: AuthUser | null;
  /** True while the initial session check is in flight */
  loading: boolean;
  /** Sign in with email + password. Throws on failure. */
  signIn: (email: string, password: string) => Promise<void>;
  /** Sign out the current user. */
  signOut: () => Promise<void>;
}

// ─── Context ──────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

// ─── Profile fetcher ──────────────────────────────────────────────────────────

async function fetchProfile(userId: string): Promise<AuthUser | null> {
  const { data, error } = await supabase
    .from('profiles')
    .select('id, email, full_name, role, plan_tier, avatar_url')
    .eq('id', userId)
    .single();

  if (error || !data) return null;

  return {
    id: data.id as string,
    email: data.email as string,
    name: data.full_name as string,
    role: data.role as UserRole,
    plan_tier: data.plan_tier as PlanTier,
    avatar_url: (data.avatar_url as string | null) ?? null,
  };
}

// ─── Provider ─────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // On mount: resolve existing session once, then subscribe to changes
  useEffect(() => {
    let cancelled = false;

    // Resolve initial session
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (cancelled) return;

      if (session?.user) {
        const profile = await fetchProfile(session.user.id);
        if (!cancelled) {
          if (profile) {
            await initRelopassAnalytics({ userId: profile.id, companyId: null });
          }
          setUser(profile);
        }
      }

      setLoading(false);
    });

    // Subscribe to subsequent auth state changes
    const unsubscribe = onAuthChange(async supabaseUser => {
      if (cancelled) return;

      if (supabaseUser) {
        const profile = await fetchProfile(supabaseUser.id);
        if (profile) {
          await initRelopassAnalytics({ userId: profile.id, companyId: null });
          trackEvent('user_signed_in');
        }
        setUser(profile);
      } else {
        resetRelopassAnalytics();
        setUser(null);
      }
    });

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    await supabaseSignIn(email, password);
    // onAuthChange will handle setting user state after sign-in
  }, []);

  const signOut = useCallback(async () => {
    trackEvent('user_signed_out');
    await supabaseSignOut();
    // onAuthChange will handle clearing user state after sign-out
  }, []);

  // Show a full-screen spinner while the initial auth state resolves
  if (loading) {
    return (
      <div
        style={{
          position: 'fixed',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--surface)',
          zIndex: 9999,
        }}
      >
        <LoadingSpinner size={32} centered label="Loading session…" />
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

// ─── Auth-required event dispatcher ──────────────────────────────────────────

/**
 * Dispatch the 'rp:auth-required' custom event.
 * Call this from route guards or data-fetching hooks when an unauthenticated
 * user attempts to access a protected resource.
 *
 * @example
 *   if (!user) dispatchAuthRequired();
 */
export function dispatchAuthRequired(): void {
  window.dispatchEvent(new CustomEvent('rp:auth-required'));
}
