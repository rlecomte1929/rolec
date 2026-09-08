/**
 * The one-line caption under the HR cockpit's Path tile.
 *
 * [AIQ-1902] It used to read "No permit mapping for this destination yet." whenever
 * `destinationPermitLabel` came up empty. That dictionary covers ten destinations, and
 * Ireland is not among them — so a case with fourteen published, approved requirements
 * was told there was no mapping for it. The catalog is the better answer wherever it has
 * one; the indicative permit label stays the headline wherever that exists.
 *
 * Kept in its own module for the same reason `hrAssignmentPermit.ts` is: it can then be
 * unit-tested without pulling in the page's api/supabase import chain, which throws in
 * jsdom.
 *
 * `requirementCount` is 0 while the dossier is loading and 0 if it failed. Both fall
 * through to the old copy, which is the safe direction — this caption must never be the
 * thing that tells HR a destination is unmapped OR that it is handled.
 */
export function pathTileSubtitle(input: {
  permitLabel: string | null;
  requirementCount: number;
  /** Empty only when neither intake nor the canonical case row knows the destination. */
  destination: string;
}): string {
  const { permitLabel, requirementCount, destination } = input;
  if (permitLabel) return 'Indicative — confirm with the relevant authority.';
  if (requirementCount > 0) {
    const noun = requirementCount === 1 ? 'requirement' : 'requirements';
    return `${requirementCount} ${noun} for this destination — see below.`;
  }
  if (destination) return 'No permit mapping for this destination yet.';
  return 'Awaiting destination from intake.';
}
