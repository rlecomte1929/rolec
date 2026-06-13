/**
 * Pet-relocation corridor availability (AIQ-1001).
 *
 * There is no backend per-corridor service-availability system yet, so this
 * frontend config is the single source of truth for "is pet relocation offered
 * for this origin→destination corridor?". Pet relocation is broadly available,
 * so the default is AVAILABLE; only corridors explicitly listed as unsupported
 * return false. This is the seam a real backend corridor-availability check
 * replaces later — callers depend only on isPetRelocationAvailableForCorridor.
 */

/** Corridor key format: `${ORIGIN_ISO2}-${DEST_ISO2}`, uppercased. */
function corridorKey(originCountry?: string | null, destCountry?: string | null): string {
  return `${(originCountry || '').trim().toUpperCase()}-${(destCountry || '').trim().toUpperCase()}`;
}

/**
 * Corridors where pet relocation is NOT offered. Empty by default — pet
 * relocation is broadly available. Add `${ORIGIN}-${DEST}` entries here (or
 * swap this module for a backend lookup) to mark a corridor unsupported.
 */
export const PET_RELOCATION_UNSUPPORTED_CORRIDORS: ReadonlySet<string> = new Set<string>([]);

/**
 * Whether pet relocation is available for the employee's corridor.
 *
 * - Destination unknown → cannot determine, default to available (never block
 *   the employee on missing data).
 * - Corridor present in the unsupported set → not available.
 * - Otherwise → available.
 *
 * `unsupported` is injectable for testing; production uses the module default.
 */
export function isPetRelocationAvailableForCorridor(
  originCountry?: string | null,
  destCountry?: string | null,
  unsupported: ReadonlySet<string> = PET_RELOCATION_UNSUPPORTED_CORRIDORS,
): boolean {
  if (!destCountry || !destCountry.trim()) return true;
  return !unsupported.has(corridorKey(originCountry, destCountry));
}
