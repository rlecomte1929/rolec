/** Shapes from GET /api/employee/assignments/overview (snake_case keys from API). */
import { getCountryName } from '../utils/countries';
export type EmployeeOverviewCompany = {
  id?: string | null;
  name?: string | null;
};

export type EmployeeOverviewDestination = {
  label?: string | null;
  host_country?: string | null;
  home_country?: string | null;
  // Optional cities (migration 20260529150000). Null until HR sets.
  host_city?: string | null;
  home_city?: string | null;
};

export type EmployeeLinkedOverviewRow = {
  assignment_id: string;
  case_id?: string | null;
  company?: EmployeeOverviewCompany;
  destination?: EmployeeOverviewDestination;
  status?: string;
  created_at?: string | null;
  updated_at?: string | null;
  current_stage?: string | null;
  relocation_case_status?: string | null;
  // Intake wizard progress (per-assignment step counter). 0 means
  // the wizard has never been opened. Backed by Postgres migration
  // 20260529130000_case_assignments_intake_progress.sql.
  intake_step?: number | null;
  intake_total_steps?: number | null;
  intake_updated_at?: string | null;
};

export type EmployeePendingClaimInfo = {
  state?: string;
  requires_explicit_claim?: boolean;
  extra_verification_required?: boolean;
};

export type EmployeePendingOverviewRow = {
  assignment_id: string;
  case_id?: string | null;
  company?: EmployeeOverviewCompany;
  destination?: EmployeeOverviewDestination;
  created_at?: string | null;
  claim?: EmployeePendingClaimInfo;
};

/**
 * Human-readable destination for an assignment row. Prefers the API-provided
 * `label`, then composes "city, country" from the host fields, and finally
 * falls back to "Not set yet" so an unset destination reads as deliberate
 * rather than a system placeholder ("Destination TBD"). (AIQ-977)
 */
export function formatDestinationLabel(dest?: EmployeeOverviewDestination | null): string {
  const label = dest?.label?.trim();
  if (label) return label;
  const city = dest?.host_city?.trim();
  // M-03 (AIQ-1261): resolve ISO codes to full names ("AE" → "United Arab
  // Emirates"); getCountryName passes already-full names and unknowns through.
  const country = getCountryName(dest?.host_country);
  if (city && country) return `${city}, ${country}`;
  if (country) return country;
  if (city) return city;
  return 'Not set yet';
}

/**
 * Corridor label "Origin → Destination" for an assignment row (EMP-1). Used to
 * title a case picker by the MOVE rather than the (constant) company name, so
 * multiple cases under one employer are distinguishable at a glance. Falls back
 * to the destination label alone when no origin is known, and to "Not set yet"
 * when neither is. Country-level for a clean, scannable corridor.
 */
export function formatCorridorLabel(dest?: EmployeeOverviewDestination | null): string {
  const origin = getCountryName(dest?.home_country) || dest?.home_city?.trim() || '';
  const destination = formatDestinationLabel(dest);
  if (!origin || destination === 'Not set yet') return destination;
  // E2: guard against a double origin when the destination label is itself already
  // a corridor (e.g. dest.label = "France → Germany") or already starts with the
  // origin — otherwise we render "France → France → Germany".
  if (destination.includes('→') || destination === origin || destination.startsWith(`${origin} `)) {
    return destination;
  }
  return `${origin} → ${destination}`;
}

/**
 * Short, stable per-case reference (last 8 chars of the case/assignment id,
 * upper-cased) used to distinguish otherwise-identical rows — e.g. multiple
 * cases that share a company and have no destination set yet. (AIQ-977)
 */
export function formatCaseReference(row: { case_id?: string | null; assignment_id?: string | null }): string {
  const id = (row.case_id || row.assignment_id || '').trim();
  return id ? id.slice(-8).toUpperCase() : '';
}
