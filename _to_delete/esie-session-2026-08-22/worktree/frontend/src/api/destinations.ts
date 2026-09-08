/**
 * AIQ-1656 — supported-destination catalogue + "request a new destination" flow,
 * usable from BOTH employee and HR surfaces.
 *
 * The catalogue (`catalog_destination_allowlist`) is deliberately small — a city not
 * in it is never a hard block. The intake/profile city inputs seed their suggestions
 * from it, still accept a typed value, and fire `requestDestination` so an admin can
 * validate the new city into the catalogue (controlled scaling).
 */
import { apiGet, apiPost } from './client';

export interface AllowlistedDestination {
  city: string;
  country: string;
  approved_by: string | null;
  approved_at: string;
  notes: string | null;
}

/** Employee-readable supported-destination catalogue (GET /api/employee/destinations). */
export const listEmployeeDestinations = (): Promise<AllowlistedDestination[]> =>
  apiGet('/api/employee/destinations');

export interface DestinationRequestTicket {
  id: string;
  city: string;
  country: string;
  status: string;
}

/**
 * Ask the ReloPass team to add a destination that isn't in the catalogue yet. Lands in
 * the admin/HR catalog-queue for validation. Backend dedupes a pending (city, country,
 * company) request, so calling this repeatedly for the same city is safe. Works for
 * employee AND HR (endpoint auth is require_hr_or_employee).
 */
export const requestDestination = (
  city: string,
  country: string,
  notes?: string,
): Promise<DestinationRequestTicket> =>
  apiPost('/api/employee/destination-request', { city, country, notes });
