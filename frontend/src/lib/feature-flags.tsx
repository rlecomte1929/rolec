/**
 * feature-flags.ts — ReloPass A/B test feature flag library (PRODUCT-6B)
 * ─────────────────────────────────────────────────────────────────────────────
 * Exports:
 *   getVariant(flagName, userId)  — async; fetches live flags, resolves variant
 *   FeatureFlagProvider           — React provider; fetches + resolves on mount
 *   useVariant(flagName)          — hook; reads resolved variant from context
 *
 * Design principles:
 *   - Deterministic: same userId + flagName always produces the same variant
 *     (SHA-256 via Web Crypto API, bucket 0–99 against traffic_split)
 *   - Safe: always returns 'control' on any error, missing flag, or disabled flag
 *   - Secure: EDGE_CONFIG token never reaches the browser — reads go via the
 *     get-feature-flags Supabase Edge Function
 * ─────────────────────────────────────────────────────────────────────────────
 */

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { useLocation } from 'react-router-dom';
import { getAuthItem } from '../utils/demo';
// Imported dynamically, not statically — see api/demoBooking.ts. FeatureFlagProvider
// wraps the whole router (App.tsx), so a static import here is the single biggest
// reason @supabase/supabase-js lands in the eager graph and gets preloaded on
// marketing pages. api/supabase.ts is unchanged: same module, same singleton.

// ─── Types ────────────────────────────────────────────────────────────────────

export interface FeatureFlag {
  enabled: boolean;
  variants: string[];
  traffic_split: number[]; // must sum to 100; index matches variants[]
  description?: string;
}

/** Map of flagName → resolved variant string (e.g. 'control' | 'variant_a') */
export type ResolvedVariants = Record<string, string>;

// ─── Deterministic hash ───────────────────────────────────────────────────────

/**
 * Returns a stable bucket 0–99 for (userId, flagName) using SHA-256.
 * Uses the Web Crypto API so it works in both browser and Deno runtimes.
 * Same inputs always produce the same bucket — no randomness at runtime.
 */
async function hashUserBucket(userId: string, flagName: string): Promise<number> {
  const data = new TextEncoder().encode(`${userId}:${flagName}`);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const view = new DataView(hashBuffer);
  // Take first 4 bytes as an unsigned 32-bit int, then mod 100
  const uint32 = view.getUint32(0);
  return uint32 % 100;
}

// ─── Variant resolution ───────────────────────────────────────────────────────

/**
 * Resolve which variant a specific user gets for a flag.
 * Falls back to 'control' when:
 *   - flag.enabled is false
 *   - traffic_split is malformed or doesn't reach the user's bucket
 */
async function resolveVariant(
  flagName: string,
  userId: string,
  flag: FeatureFlag,
): Promise<string> {
  if (!flag.enabled) return 'control';
  if (!flag.variants.length || !flag.traffic_split.length) return 'control';

  const bucket = await hashUserBucket(userId, flagName);
  let cumulative = 0;
  for (let i = 0; i < flag.traffic_split.length; i++) {
    cumulative += flag.traffic_split[i] ?? 0;
    if (bucket < cumulative) return flag.variants[i] ?? 'control';
  }
  return 'control';
}

/** True when any auth artefact exists locally — ReloPass token or a Supabase session. */
function hasAnySession(): boolean {
  try {
    if (getAuthItem('relopass_token')) return true;
    for (let i = 0; i < localStorage.length; i += 1) {
      const k = localStorage.key(i);
      if (k && k.startsWith('sb-') && k.endsWith('-auth-token')) return true;
    }
  } catch {
    // Private mode / storage disabled — treat as anonymous rather than throwing.
  }
  return false;
}

// ─── Flag fetcher (internal) ──────────────────────────────────────────────────

async function fetchAllFlags(): Promise<Record<string, FeatureFlag>> {
  const { supabase } = await import('../api/supabase');
  const invokeResult = await supabase.functions.invoke('get-feature-flags');
  const data = invokeResult.data as { flags?: Record<string, FeatureFlag> } | null;
  const error: unknown = invokeResult.error;
  if (error || !data?.flags) return {};
  return data.flags;
}

// ─── getVariant (public, non-hook) ────────────────────────────────────────────

/**
 * Fetch live flags and resolve a single variant for the given user.
 * Suitable for use outside React components (e.g. analytics pre-routing).
 * Always returns 'control' on any network or parse error.
 *
 * @example
 *   const variant = await getVariant('onboarding_flow_v2', userId);
 *   // → 'control' | 'variant_a'
 */
export async function getVariant(
  flagName: string,
  userId: string,
): Promise<string> {
  try {
    const flags = await fetchAllFlags();
    const flag = flags[flagName];
    if (!flag) return 'control';
    return await resolveVariant(flagName, userId, flag);
  } catch {
    return 'control';
  }
}

// ─── React context ────────────────────────────────────────────────────────────

const FeatureFlagContext = createContext<ResolvedVariants>({});

// ─── FeatureFlagProvider ──────────────────────────────────────────────────────

/**
 * FeatureFlagProvider
 *
 * Place once near the root of your component tree (inside your router is fine).
 * Automatically reads the current Supabase session to get the userId.
 * On mount (and whenever the auth state changes) it:
 *   1. Fetches all flag configs from the get-feature-flags edge function
 *   2. Resolves every variant for the current user via deterministic hash
 *   3. Makes results available to all descendants via useVariant()
 *
 * All children render immediately with an empty variants map ({}) and
 * update without unmounting once the async resolution completes — no
 * layout shift, no hydration mismatch.
 */
export function FeatureFlagProvider({ children }: { children: ReactNode }) {
  const [variants, setVariants] = useState<ResolvedVariants>({});

  async function loadVariants(userId: string | null) {
    if (!userId) {
      setVariants({});
      return;
    }
    try {
      const flags = await fetchAllFlags();
      const resolved: ResolvedVariants = {};
      await Promise.all(
        Object.entries(flags).map(async ([name, flag]) => {
          resolved[name] = await resolveVariant(name, userId, flag);
        }),
      );
      setVariants(resolved);
    } catch {
      // Leave variants as {} → useVariant() returns 'control' for everything
    }
  }

  // Do not touch Supabase at all for an anonymous visitor. loadVariants already returns
  // early without a userId, but the getSession() call that resolves that userId is itself
  // what pulls the 57 kB SDK chunk over the wire — on marketing pages, for people who have
  // never signed in. Vite's __vitePreload injects a modulepreload link when the dynamic
  // import runs, so moving the import off the eager graph was not enough on its own; the
  // request has to not happen. e2e/bundle.spec.ts holds this.
  //
  // `armed` gates that. It starts true for anyone who already has a session, so a signed-in
  // user's behaviour is byte-for-byte what it was: one setup, one subscription, at mount.
  const [armed, setArmed] = useState(hasAnySession);

  // Sign-in navigates client-side (useAuth -> safeNavigate), so the provider never
  // remounts and the effect below would otherwise stay parked for the whole session.
  // Re-check the cheap localStorage predicate on each navigation to catch that transition.
  // This only ever flips false -> true; sign-out does a full document load.
  const { pathname } = useLocation();
  useEffect(() => {
    if (!armed && hasAnySession()) setArmed(true);
  }, [pathname, armed]);

  useEffect(() => {
    if (!armed) {
      setVariants({});
      return;
    }

    // Load variants for the current session immediately. Use getSession()
    // (local read, no network) rather than getUser() (network → auth/v1/user):
    // ReloPass-token users have no Supabase GoTrue session, so getUser() 403s on
    // every page and floods the console. getSession() returns the session (with
    // its user) when one exists and null otherwise — falling back to the
    // ReloPass identity exactly as before, but without the network probe.
    // Both branches below resolve the SAME identity on a normal page load, and
    // supabase-js fires INITIAL_SESSION on subscribe — so this used to invoke the
    // get-feature-flags Edge Function 2-3x per load for one user. Track the identity we
    // last loaded for and skip a repeat; a genuine sign-in/sign-out changes it and still
    // re-resolves.
    let lastLoadedUserId: string | null | undefined;
    const loadOnce = (userId: string | null) => {
      if (lastLoadedUserId === userId) return;
      lastLoadedUserId = userId;
      void loadVariants(userId);
    };

    // The client now arrives asynchronously, so the subscription may not exist yet when
    // React runs cleanup (a fast unmount, or StrictMode's double-invoke in dev). Track
    // both the handle and a cancelled flag: whichever happens first, we neither leak a
    // subscription nor call unsubscribe on undefined.
    let cancelled = false;
    let subscription: { unsubscribe: () => void } | undefined;

    void (async () => {
      const { supabase } = await import('../api/supabase');
      if (cancelled) return;

      void supabase.auth.getSession().then(({ data: { session } }) => {
        if (cancelled) return;
        loadOnce(session?.user?.id ?? getAuthItem('relopass_email') ?? null);
      });

      // Re-resolve whenever the user signs in or out
      const listener = supabase.auth.onAuthStateChange((_event, session) => {
        if (cancelled) return;
        loadOnce(session?.user?.id ?? getAuthItem('relopass_email') ?? null);
      });
      // Unmounted while the import was in flight — tear down immediately.
      if (cancelled) listener.data.subscription.unsubscribe();
      else subscription = listener.data.subscription;
    })();

    return () => {
      cancelled = true;
      subscription?.unsubscribe();
    };
  }, [armed]);

  return (
    <FeatureFlagContext.Provider value={variants}>
      {children}
    </FeatureFlagContext.Provider>
  );
}

// ─── useVariant ───────────────────────────────────────────────────────────────

/**
 * Read the resolved variant for a flag in any React component.
 * Returns 'control' when:
 *   - The flag is disabled
 *   - The flag name is not in Edge Config
 *   - Edge Config was unreachable at load time
 *   - The component is rendered outside <FeatureFlagProvider>
 *   - The async resolution hasn't completed yet
 *
 * @example
 *   function OnboardingFlow() {
 *     const variant = useVariant('onboarding_flow_v2');
 *     return variant === 'variant_a' ? <NewFlow /> : <LegacyFlow />;
 *   }
 */
export function useVariant(flagName: string): string {
  const variants = useContext(FeatureFlagContext);
  return variants[flagName] ?? 'control';
}
