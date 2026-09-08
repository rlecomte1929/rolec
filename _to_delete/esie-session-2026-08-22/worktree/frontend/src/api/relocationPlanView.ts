import type { RelocationPlanViewResponseDTO } from '../types/relocationPlanView';
import { apiGet } from './client';

export type FetchRelocationPlanViewOptions = {
  /** Optional lens; must match the authenticated user. */
  role?: 'employee' | 'hr';
  debug?: boolean;
  /**
   * Skip the short dedup window and force a fresh network fetch. Used after
   * seeding default tasks, where we must read back the newly-created data rather
   * than a cached pre-seed view. The fresh result repopulates the window cache.
   */
  forceFresh?: boolean;
};

// Short-window request dedup. The employee Roadmap mounts several independent
// consumers (timeline, task tracker, canonical tasks, page-data hook) that each
// fetch this view within ~1–2s of each other, and a status poll repeats it — ~7
// identical GETs per page load. Share one request (in-flight OR just-resolved)
// across a brief window keyed by the exact request path, so the mount/poll burst
// collapses to a single network call. The window is intentionally short so a real
// refetch (the ~6s status poll, or the post-seed refetch below) still gets fresh
// data; failures are evicted immediately so retries proceed and errors never cache.
const DEDUP_WINDOW_MS = 2500;
const _window = new Map<string, { at: number; promise: Promise<RelocationPlanViewResponseDTO> }>();

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

  const now = Date.now();
  if (!options?.forceFresh) {
    const hit = _window.get(path);
    if (hit && now - hit.at < DEDUP_WINDOW_MS) return hit.promise;
  }

  const promise = apiGet<RelocationPlanViewResponseDTO>(path);
  _window.set(path, { at: now, promise });
  // Evict on failure so an error is never cached and a retry can proceed.
  void promise.catch(() => {
    if (_window.get(path)?.promise === promise) _window.delete(path);
  });
  return promise;
}
