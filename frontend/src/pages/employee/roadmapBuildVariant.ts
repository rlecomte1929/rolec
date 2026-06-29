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
): RoadmapBuildVariant {
  if (!windowElapsed) return 'generating';
  return hasError ? 'failed' : 'empty';
}
