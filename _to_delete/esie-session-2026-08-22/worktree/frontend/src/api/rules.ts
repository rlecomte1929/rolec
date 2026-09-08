/**
 * GAP 6: Pet restriction rules — GET /api/rules/pet-restrictions
 *
 * Centralises country-level pet entry rules previously hardcoded in the S1n prototype.
 * Used by the pet profile step and the pre-move checklist.
 */
import { apiGet } from './client';

export interface PetRestrictions {
  destination_code: string;
  /** Present if loaded from DB; null for hardcoded fallback entries */
  destination_name?: string | null;
  quarantine_days: number | null;
  quarantine_required: boolean;
  /** Import/entry permit required at destination */
  import_permit_required: boolean;
  /** Accepted by EU Pet Passport scheme */
  eu_pet_passport_accepted?: boolean;
  microchip_required: boolean;
  rabies_vaccination_required?: boolean;
  rabies_titre_test_required: boolean;
  restricted_breeds: string[];
  estimated_cost_range?: string | null;
  notes: string | null;
}

export interface BreedCheckResult {
  destination_code: string;
  breed: string;
  /** True if breed is restricted or banned at destination */
  is_restricted: boolean;
  restriction_note: string | null;
}

/**
 * GAP 6: Fetch pet entry restrictions for a destination country.
 * @param destinationCode ISO 3166-1 alpha-2 country code (e.g. "GB", "AU")
 */
export async function getPetRestrictions(
  destinationCode: string,
): Promise<PetRestrictions> {
  return apiGet<PetRestrictions>(
    `/api/rules/pet-restrictions?destination_code=${encodeURIComponent(destinationCode)}`,
  );
}

/**
 * GAP 6: Check whether a specific breed is restricted at the destination.
 */
export async function checkBreedRestriction(
  destinationCode: string,
  breed: string,
): Promise<BreedCheckResult> {
  return apiGet<BreedCheckResult>(
    `/api/rules/pet-restrictions/breed-check?destination_code=${encodeURIComponent(destinationCode)}&breed=${encodeURIComponent(breed)}`,
  );
}
