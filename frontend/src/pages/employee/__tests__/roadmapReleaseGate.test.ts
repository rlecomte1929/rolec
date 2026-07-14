/**
 * The HR release gate, and the one way it can go catastrophically wrong.
 *
 * `roadmap_released` is OPTIONAL and the backend FAILS OPEN: no review row -> released,
 * lookup error -> released. So `undefined` means RELEASED. Writing the gate as
 * `!plan.roadmap_released` instead of `plan.roadmap_released === false` turns every
 * undefined into "held" and hides the roadmap from every employee whose case predates
 * the gate — 47 live cases on the day this ships.
 *
 * These tests exist to make that inversion impossible to land quietly.
 */
import { describe, it, expect } from 'vitest';
import { isRoadmapHeldForHrReview } from '../roadmapReleaseGate';

describe('isRoadmapHeldForHrReview', () => {
  it('holds the plan only when HR has actively withheld it', () => {
    expect(isRoadmapHeldForHrReview({ roadmap_released: false })).toBe(true);
  });

  it('releases when HR has approved', () => {
    expect(isRoadmapHeldForHrReview({ roadmap_released: true })).toBe(false);
  });

  // ── The fail-open cases. Each of these would break if the gate were `!released`. ──

  it('releases when the field is absent (case predates the gate)', () => {
    expect(isRoadmapHeldForHrReview({})).toBe(false);
  });

  it('releases when the field is explicitly undefined', () => {
    expect(isRoadmapHeldForHrReview({ roadmap_released: undefined })).toBe(false);
  });

  it('releases when there is no plan at all', () => {
    expect(isRoadmapHeldForHrReview(null)).toBe(false);
    expect(isRoadmapHeldForHrReview(undefined)).toBe(false);
  });
});
