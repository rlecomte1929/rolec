/**
 * AIQ-1377 — resolve the "roadmap not ready" screen variant.
 *
 * Within the bounded retry window (`windowElapsed === false`) a transient error
 * OR an empty plan both render as `generating` — the page keeps polling/retrying
 * and never dead-ends. Only once the window has elapsed do we resolve to a
 * terminal state: a still-erroring fetch → `failed` (shows "We couldn't load your
 * roadmap" + Try again), an empty plan → `empty`.
 */
export type RoadmapBuildVariant = 'generating' | 'empty' | 'failed';

export function resolveRoadmapBuildVariant(
  windowElapsed: boolean,
  hasError: boolean,
  errorStatus?: number | null,
): RoadmapBuildVariant {
  // A permission error will NEVER become a roadmap. Polling it for 60s while
  // showing "We're building your roadmap — you'll get an email the moment it's
  // ready, usually within 2 working days" promises something that cannot happen.
  // 401/403 are terminal on arrival; everything else keeps the bounded retry.
  if (hasError && (errorStatus === 401 || errorStatus === 403)) return 'failed';
  if (!windowElapsed) return 'generating';
  return hasError ? 'failed' : 'empty';
}
