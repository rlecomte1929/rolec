/**
 * Auth Page Config — GET /api/public/auth-page-config (no auth required)
 *                     PUT /api/admin/auth-page-config (admin only)
 *
 * Platform-wide (not per-company) visual-tuning config for the GlobeNetwork
 * canvas shown on the public, unauthenticated /auth page. Mirrors the style
 * of ./branding.ts, but unlike branding this is a single global row read
 * before login — the GET call never sends (or needs) an auth token.
 */
import { apiGet, apiPut } from './client';
import type { GlobeNetworkConfig } from '../components/auth/GlobeNetwork';

export type AuthPageConfig = GlobeNetworkConfig;

/**
 * Session memo. This is platform-global static config, and `useAuthPageConfig` calls it
 * from a mount effect — so every visit to /auth (or /login, or the admin design page)
 * paid a fresh round trip for a value that does not change between them. Caching the
 * PROMISE also collapses concurrent mounts into one request.
 *
 * `apiGet` deliberately does not go through client.ts's `cachedRequest`, so the memo
 * lives here rather than reaching across for a module-private helper.
 */
let authPageConfigPromise: Promise<AuthPageConfig> | null = null;

/** Fetch the live auth-page globe config. No auth token required. Memoised per session. */
export async function getAuthPageConfig(): Promise<AuthPageConfig> {
  if (!authPageConfigPromise) {
    authPageConfigPromise = apiGet<AuthPageConfig>('/api/public/auth-page-config').catch((err) => {
      // Never cache a failure — a transient blip must not pin the default config for the
      // rest of the session.
      authPageConfigPromise = null;
      throw err;
    });
  }
  return authPageConfigPromise;
}

/** Drop the memo so the next read is fresh — used after an admin save, and by tests. */
export function invalidateAuthPageConfig(): void {
  authPageConfigPromise = null;
}

/** Save the auth-page globe config. Admin only. */
export async function updateAuthPageConfig(config: AuthPageConfig): Promise<AuthPageConfig> {
  invalidateAuthPageConfig();
  return apiPut<AuthPageConfig>('/api/admin/auth-page-config', config);
}
