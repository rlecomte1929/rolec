/**
 * Per-case Services-flow state API client.
 *
 * Returns null on 404 so callers can treat "no saved state" as a soft signal
 * instead of an error. Other failures (network, 5xx, oversize 413) bubble up.
 *
 * The backend route is POST (not PUT) so it can ride the existing apiPost
 * helper without expanding api/client.ts; semantically it's still upsert
 * keyed by case_id.
 */

import { apiGet, apiPost } from './client';

export interface ServicesStateRead {
  case_id: string;
  organization_id: string;
  state: Record<string, unknown>;
  updated_at: string;
  updated_by_user_id: string | null;
}

export async function getServicesState(caseId: string): Promise<ServicesStateRead | null> {
  try {
    return await apiGet<ServicesStateRead>(
      `/api/cases/${encodeURIComponent(caseId)}/services-state`,
    );
  } catch (err: unknown) {
    const e = err as { status?: number; statusCode?: number };
    if (e?.status === 404 || e?.statusCode === 404) return null;
    if (err instanceof Error && /\b404\b/.test(err.message)) return null;
    throw err;
  }
}

export function saveServicesState(
  caseId: string,
  state: Record<string, unknown>,
): Promise<ServicesStateRead> {
  return apiPost<ServicesStateRead>(
    `/api/cases/${encodeURIComponent(caseId)}/services-state`,
    { state },
  );
}
