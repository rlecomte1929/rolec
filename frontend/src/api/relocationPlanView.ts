import type { RelocationPlanViewResponseDTO } from '../types/relocationPlanView';
import { apiGet } from './client';

export type FetchRelocationPlanViewOptions = {
  /** Optional lens; must match the authenticated user. */
  role?: 'employee' | 'hr';
  debug?: boolean;
};

// In-flight request dedup. The employee Roadmap mounts several independent
// consumers (timeline, task tracker, canonical tasks, page-data hook) that each
// fetch this view on mount — ~7 identical GETs per page load. Share the promise
// only WHILE it is in flight (keyed by the exact request path), so concurrent
// mounts collapse to a single network request. It is cleared as soon as the
// request settles, so a genuine later refetch (e.g. the timeline's refresh after
// roadmap generation) still hits the network fresh — no result staleness.
const _inflight = new Map<string, Promise<RelocationPlanViewResponseDTO>>();

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

  const existing = _inflight.get(path);
  if (existing) return existing;

  const promise = apiGet<RelocationPlanViewResponseDTO>(path);
  _inflight.set(path, promise);
  // Clear once settled (success or failure) so retries/refetches aren't cached.
  void promise.finally(() => {
    if (_inflight.get(path) === promise) _inflight.delete(path);
  });
  return promise;
}
