/**
 * Edge Config feature flags — frontend client (PRODUCT-6A)
 * ─────────────────────────────────────────────────────────────────────────────
 * Reads runtime feature flags from the `get-feature-flags` Supabase Edge
 * Function, which proxies Vercel Edge Config safely server-side.
 *
 * WHY A PROXY?
 *   Vercel Edge Config requires a bearer token. Exposing that token in the
 *   browser bundle would allow anyone to read or (with a write token) mutate
 *   flags. The Edge Function holds the token in Supabase Vault; the browser
 *   only calls the public function endpoint.
 *
 * USAGE
 *   // Once at app start (e.g. in main.tsx or a top-level React context):
 *   const flags = await getFeatureFlags();
 *
 *   // Per-component:
 *   import { useFeatureFlag } from '../api/edgeConfig';
 *   const isV2 = useFeatureFlag('onboarding_flow_v2');
 *
 * FLAG NAMING CONVENTION
 *   <feature_area>_<description>_<version>   e.g. onboarding_flow_v2
 *   - Lowercase snake_case
 *   - Suffix _v<N> when replacing an existing flow
 *   - traffic_split values must sum to 100
 *   - Reference doc: /config/feature-flags-reference.json
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useEffect, useState } from 'react';
import { logger } from '../lib/logger';
import { supabase } from './supabase';

export interface FeatureFlag {
  enabled: boolean;
  variants: string[];
  traffic_split: number[];
  description?: string;
}

export type FlagsMap = Record<string, FeatureFlag>;

/** In-memory cache — flags are fetched once per page load. */
let _cachedFlags: FlagsMap | null = null;
let _fetchPromise: Promise<FlagsMap> | null = null;

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL as string | undefined;

/** Safe defaults — every flag is off. Returned when the Edge Function is unreachable. */
const FLAG_DEFAULTS: FlagsMap = {
  onboarding_flow_v2: { enabled: false, variants: ['control', 'variant_a'], traffic_split: [100, 0] },
  hr_policy_assistant_v2: { enabled: false, variants: ['control', 'variant_a'], traffic_split: [100, 0] },
  employee_dashboard_v2: { enabled: false, variants: ['control', 'variant_a'], traffic_split: [100, 0] },
};

/**
 * Fetch the current feature flags from the Edge Function.
 * Results are cached for the lifetime of the page — flags don't change
 * mid-session (the server applies a 60 s CDN cache anyway).
 */
export async function getFeatureFlags(): Promise<FlagsMap> {
  if (_cachedFlags) return _cachedFlags;
  if (_fetchPromise) return _fetchPromise;

  _fetchPromise = (async (): Promise<FlagsMap> => {
    if (!SUPABASE_URL) {
      if (import.meta.env.DEV) {
        logger.warn('[EdgeConfig] VITE_SUPABASE_URL not set; using flag defaults.');
      }
      _cachedFlags = { ...FLAG_DEFAULTS };
      return _cachedFlags;
    }

    try {
      // Use the Supabase anon key so the Edge Function receives a valid JWT.
      const { data: { session } } = await supabase.auth.getSession();
      const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;
      const authHeader = session?.access_token
        ? `Bearer ${session.access_token}`
        : anonKey
          ? `Bearer ${anonKey}`
          : undefined;

      const headers: HeadersInit = { 'Content-Type': 'application/json' };
      if (authHeader) headers['Authorization'] = authHeader;
      if (anonKey) headers['apikey'] = anonKey;

      const res = await fetch(`${SUPABASE_URL}/functions/v1/get-feature-flags`, { headers });

      if (!res.ok) {
        if (import.meta.env.DEV) {
          logger.warn(`[EdgeConfig] Function returned ${res.status}; using defaults.`);
        }
        _cachedFlags = { ...FLAG_DEFAULTS };
        return _cachedFlags;
      }

      const json = await res.json() as { flags?: FlagsMap };
      _cachedFlags = { ...FLAG_DEFAULTS, ...(json.flags ?? {}) };
      return _cachedFlags;
    } catch (err) {
      if (import.meta.env.DEV) {
        logger.warn('[EdgeConfig] Failed to fetch flags:', err);
      }
      _cachedFlags = { ...FLAG_DEFAULTS };
      return _cachedFlags;
    }
  })();

  return _fetchPromise;
}

/**
 * Check whether a single flag is enabled.
 * Returns false if the flag is unknown (safe default).
 */
export async function isFlagEnabled(flagKey: string): Promise<boolean> {
  const flags = await getFeatureFlags();
  return flags[flagKey]?.enabled ?? false;
}

/**
 * React hook — returns whether a flag is enabled.
 * Resolves asynchronously; returns false while loading.
 *
 * @example
 *   const isV2 = useFeatureFlag('onboarding_flow_v2');
 */
export function useFeatureFlag(flagKey: string): boolean {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void isFlagEnabled(flagKey).then((val) => {
      if (!cancelled) setEnabled(val);
    });
    return () => { cancelled = true; };
  }, [flagKey]);

  return enabled;
}

/**
 * Invalidate the in-memory cache (useful in tests or after a forced refresh).
 */
export function invalidateFlagsCache(): void {
  _cachedFlags = null;
  _fetchPromise = null;
}
