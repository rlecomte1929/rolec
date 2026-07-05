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

/** Fetch the live auth-page globe config. No auth token required. */
export async function getAuthPageConfig(): Promise<AuthPageConfig> {
  return apiGet<AuthPageConfig>('/api/public/auth-page-config');
}

/** Save the auth-page globe config. Admin only. */
export async function updateAuthPageConfig(config: AuthPageConfig): Promise<AuthPageConfig> {
  return apiPut<AuthPageConfig>('/api/admin/auth-page-config', config);
}
