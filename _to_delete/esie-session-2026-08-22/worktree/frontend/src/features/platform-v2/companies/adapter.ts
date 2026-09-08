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

// ── Adapter ─────────────────────────────────────────────────────────────────

const VALID_STATUS = new Set<CompanyV2Status>(['active', 'inactive', 'archived']);
const VALID_PLAN = new Set<CompanyV2PlanTier>(['low', 'medium', 'premium']);
const TONES: readonly CompanyV2Tone[] = ['a', 'b', 'c', 'd', 'e', 'f'];

/**
 * Deterministic 6-bucket hash of a string id. Same id always maps to the same
 * tone, so the logo chip colour stays stable across re-renders and across
 * different users viewing the same row. Uses djb2-style accumulation.
 */
function toneForId(id: string): CompanyV2Tone {
  let hash = 5381;
  for (let i = 0; i < id.length; i++) {
    hash = ((hash << 5) + hash + id.charCodeAt(i)) | 0;
  }
  // Bring into [0, TONES.length)
  const bucket = Math.abs(hash) % TONES.length;
  return TONES[bucket]!;
}

function narrowStatus(raw: AdminCompany['status']): CompanyV2Status {
  const s = (raw ?? 'active').toString().toLowerCase();
  return VALID_STATUS.has(s as CompanyV2Status) ? (s as CompanyV2Status) : 'active';
}

function narrowPlan(raw: AdminCompany['plan_tier']): CompanyV2PlanTier {
  const p = (raw ?? 'low').toString().toLowerCase();
  return VALID_PLAN.has(p as CompanyV2PlanTier) ? (p as CompanyV2PlanTier) : 'low';
}

/**
 * Convert one real-backend `AdminCompany` into the V2 shape.
 * Pure function — no side effects, no network, no React.
 */
export function toV2Shape(real: AdminCompany): CompanyV2 {
  return {
    id: real.id,
    name: real.name,
    legal_name: real.name, // backend has no separate legal_name yet
    industry: null,
    website: null,
    hq_city: null,

    country: real.country ?? null,
    size_band: real.size_band ?? null,
    address: real.address ?? null,
    phone: real.phone ?? null,

    status: narrowStatus(real.status),
    plan_tier: narrowPlan(real.plan_tier),

    hr_users_count: real.hr_users_count ?? 0,
    hr_seat_limit: real.hr_seat_limit ?? null,
    employee_count: real.employee_count ?? 0,
    employee_seat_limit: real.employee_seat_limit ?? null,
    assignments_count: real.assignments_count ?? 0,

    primary_contact_name: real.primary_contact_name ?? null,
    hr_contact: real.hr_contact ?? null,
    support_email: real.support_email ?? null,

    created_at: real.created_at,
    updated_at: real.updated_at ?? null,

    tone: toneForId(real.id),

    has_registry_issue: Boolean(real.missing_from_registry),
    orphan_row_count: real.missing_from_companies_table ?? 0,
  };
}

/** Convert the whole list response in one call. */
export function listToV2Shape(companies: AdminCompany[]): CompanyV2[] {
  return companies.map(toV2Shape);
}
