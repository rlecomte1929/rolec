import { apiGet } from './client';
import type { RelocationPlanViewResponseDTO } from '../types/relocationPlanView';

export type FetchRelocationPlanViewOptions = {
  /** Optional lens; must match the authenticated user. */
  role?: 'employee' | 'hr';
  debug?: boolean;
};

/**
 * GET /api/relocation-plans/{case_id}/view
 * `caseId` may be wizard case id or assignment id (backend resolves the same as timeline routes).
 */
export async function fetchRelocationPlanView(
  caseId: string,
  options?: FetchRelocationPlanViewOptions
): Promise<RelocationPlanViewResponseDTO> {
  const params = new URLSearchParams();
  if (options?.role) params.set('role', options.role);
  if (options?.debug) params.set('debug', 'true');
  const qs = params.toString();
  const path = `/api/relocation-plans/${encodeURIComponent(caseId)}/view${qs ? `?${qs}` : ''}`;
  return apiGet<RelocationPlanViewResponseDTO>(path);
}
