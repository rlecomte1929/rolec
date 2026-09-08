/**
 * Is the roadmap being held back by HR review?
 *
 * A one-line predicate, extracted so it can be tested — because the obvious way to write
 * it is wrong. `roadmap_released` is OPTIONAL and the backend FAILS OPEN (no review row →
 * released; lookup error → released), so `undefined` means RELEASED.
 *
 *   WRONG:  !plan.roadmap_released          // undefined -> held -> roadmap disappears
 *   RIGHT:  plan.roadmap_released === false // only an explicit withhold holds it
 *
 * The wrong version hides the roadmap from every employee whose case has no review row —
 * every one of the 47 live cases the day this ships. An employee must never lose a plan
 * they already had because a gate was undefined.
 */
export function isRoadmapHeldForHrReview(
  plan: { roadmap_released?: boolean } | null | undefined,
): boolean {
  return plan?.roadmap_released === false;
}
