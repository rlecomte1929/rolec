/**
 * pets.ts — AIQ-160-C
 *
 * API client for the pets CRUD endpoints created in AIQ-160-A.
 * Endpoints: GET/POST /api/cases/{caseId}/pets
 *            PATCH/DELETE /api/cases/{caseId}/pets/{petId}
 *
 * Used when a caseId is available (e.g. case editing context or post-submission).
 * The intake wizard (EmployeeIntakePage) stores pet data in local state and
 * will call these functions at submission time once the case is created.
 */

import { apiGet, apiPost, apiPatch, apiDelete } from './client';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface PetVaccination {
  name: string;
  date: string;    // ISO date string
  expiry: string;  // ISO date string
}

export interface PetDTO {
  id: string;
  case_id: string;
  name: string | null;
  species: string;
  breed: string | null;
  microchip_number: string | null;
  date_of_birth: string | null;   // ISO date
  passport_number: string | null;
  health_cert_expiry: string | null;  // ISO date
  vaccinations: PetVaccination[];
  vet_name: string | null;
  vet_phone: string | null;
  vet_country: string | null;  // ISO 3166-1 alpha-2
  created_at: string | null;
  updated_at: string | null;
}

export interface PetCreate {
  species: string;                    // required
  name?: string | null;
  breed?: string | null;
  microchip_number?: string | null;
  date_of_birth?: string | null;
  passport_number?: string | null;
  health_cert_expiry?: string | null;
  vaccinations?: PetVaccination[];
  vet_name?: string | null;
  vet_phone?: string | null;
  vet_country?: string | null;
}

export type PetUpdate = Partial<PetCreate>;

// ─── API functions ────────────────────────────────────────────────────────────

/**
 * List all pets for a case.
 * Returns empty array on any error (non-fatal).
 */
export async function listPets(caseId: string): Promise<PetDTO[]> {
  try {
    return await apiGet<PetDTO[]>(`/api/cases/${caseId}/pets`);
  } catch {
    return [];
  }
}

/**
 * Create a new pet for a case.
 * Returns the created PetDTO (status 201).
 */
export async function createPet(caseId: string, pet: PetCreate): Promise<PetDTO> {
  return apiPost<PetDTO>(`/api/cases/${caseId}/pets`, pet);
}

/**
 * Update an existing pet.
 * Returns the updated PetDTO.
 */
export async function updatePet(caseId: string, petId: string, pet: PetUpdate): Promise<PetDTO> {
  return apiPatch<PetDTO>(`/api/cases/${caseId}/pets/${petId}`, pet);
}

/**
 * Delete a pet.
 * Returns void (status 204).
 */
export async function deletePet(caseId: string, petId: string): Promise<void> {
  return apiDelete(`/api/cases/${caseId}/pets/${petId}`);
}
