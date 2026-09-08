/**
 * Subset of the canonical RelocationCase shape used by the case list view.
 *
 * The full type lives in frontend/src/types/relopass-api-contracts.ts and is
 * the contract owned by the existing relopass.com surface. Rather than reach
 * across the app boundary at runtime, we re-declare the subset we need.
 * Keep this file narrow: only the fields the list view consumes.
 *
 * If new columns are added to the dashboard, mirror the field here AND verify
 * the backend SELECT * returns it (the API returns the raw row from
 * relocation_cases, so any column on that table is implicitly available).
 */

export type CaseStatus =
  | 'draft'
  | 'in_progress'
  | 'on_hold'
  | 'completed'
  | 'cancelled'
  // The relocation_cases.status column is free-form text; tolerate unknown
  // values rather than crashing the table.
  | (string & {});

export interface CaseRow {
  id: string;
  company_id: string;
  employee_id: string;
  hr_owner_id: string | null;
  origin_country_code: string | null;
  dest_country_code: string | null;
  /** Generated stored column: ISO-2 ORIGIN + "_" + ISO-2 DEST (e.g. "IN_DE"). */
  corridor: string | null;
  status: CaseStatus;
  stage: string | null;
  target_start_date: string | null;
  actual_start_date: string | null;
  target_close_date: string | null;
  actual_close_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  /**
   * Optional join-augmented fields. The current backend SELECT * doesn't
   * supply these, but the brief calls them out as columns the list view
   * should expose. We surface them in the UI when present and fall back
   * gracefully when not — a follow-up backend task will populate them.
   */
  employee_name?: string;
  open_contradictions_count?: number;
}

export interface CasesListResponse {
  cases: CaseRow[];
}

/** Display filter shape used by the list view (lifted to CasesPage). */
export interface CasesFilterState {
  /** Free-text employee search — matched against employee_name client-side, debounced. */
  search: string;
  /** Multi-select; empty array = no filter. */
  statuses: CaseStatus[];
  /** Multi-select; empty array = no filter. Corridor codes like "IN_DE". */
  corridors: string[];
}

export const EMPTY_FILTERS: CasesFilterState = {
  search: '',
  statuses: [],
  corridors: [],
};
