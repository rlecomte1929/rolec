/**
 * platform-v2 · s9g Companies · adapter
 *
 * Translates the real backend's `AdminCompany` shape (from
 * `frontend/src/types.ts:767`) into the V2 component's `CompanyV2` shape
 * (modelled on `frontend/public/design-preview/platform-s9g-companies.jsx`).
 *
 * Endpoints:
 *   List   →  GET /api/admin/companies            (adminAPI.listCompanies)
 *   Detail →  GET /api/admin/companies/{id}        (adminAPI.getCompanyDetail)
 *
 * Stub only — `toV2Shape` is implemented in step 3 of the per-screen recipe.
 */

import type { AdminCompany } from '../../../types';

// ── V2 shape (what the component consumes) ──────────────────────────────────

/** Tone bucket used by the V2 component to colour the company logo chip. */
export type CompanyV2Tone = 'a' | 'b' | 'c' | 'd' | 'e' | 'f';

/** Status as exposed to V2 — narrowed string union. */
export type CompanyV2Status = 'active' | 'inactive' | 'archived';

/** Plan tier as exposed to V2 — narrowed string union. */
export type CompanyV2PlanTier = 'low' | 'medium' | 'premium';

export interface CompanyV2 {
  id: string;
  name: string;
  /** Backend-provided where present; falls back to `name` in the adapter. */
  legal_name: string;
  /** Backend has no `industry` column today; the adapter returns `null`. */
  industry: string | null;
  /** Backend has no `website` column today; the adapter returns `null`. */
  website: string | null;
  /** Backend has no `hq_city` column today; the adapter returns `null`. */
  hq_city: string | null;

  country: string | null;
  size_band: string | null;
  address: string | null;
  phone: string | null;

  status: CompanyV2Status;
  plan_tier: CompanyV2PlanTier;

  hr_users_count: number;
  hr_seat_limit: number | null;
  employee_count: number;
  employee_seat_limit: number | null;
  assignments_count: number;

  primary_contact_name: string | null;
  hr_contact: string | null;
  support_email: string | null;

  created_at: string;
  updated_at: string | null;

  /** Deterministic colour bucket derived from `id`; purely visual. */
  tone: CompanyV2Tone;

  /** True when the company exists in users/cases but not in `companies`. */
  has_registry_issue: boolean;
  /** Count of rows referencing an unknown company id; > 0 means orphan rows. */
  orphan_row_count: number;
}

// ── Adapter (stub) ──────────────────────────────────────────────────────────

/**
 * Convert one real-backend `AdminCompany` into the V2 shape.
 * Pure function — no side effects, no network, no React.
 *
 * Implementation lands in step 3 of the recipe.
 */
export function toV2Shape(_real: AdminCompany): CompanyV2 {
  throw new Error('toV2Shape: not implemented yet (step 3 of per-screen recipe)');
}

/** Convert the whole list response in one call. */
export function listToV2Shape(_companies: AdminCompany[]): CompanyV2[] {
  throw new Error('listToV2Shape: not implemented yet (step 3 of per-screen recipe)');
}
