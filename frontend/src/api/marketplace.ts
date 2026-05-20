/**
 * GAP 8: Marketplace / vendor catalogue — GET /api/employee/assignments/{id}/marketplace
 *
 * Returns a curated list of vetted vendors for a given assignment,
 * pre-sorted by: preferred+covered → covered only → preferred only → rest.
 * Used by S2b (Marketplace screen) and the provider cards in the employee journey.
 */
import { apiGet } from './client';

export interface MarketplaceVendor {
  id: string;
  name: string;
  service_category: string;
  logo_initials: string;
  rating: number | null;
  rating_count: number | null;
  price_display: string | null;
  sla_display: string | null;
  /** Vendor is a preferred partner for this company */
  preferred: boolean;
  /** Benefit is covered under the employee's policy */
  covered: boolean;
  /** Vendor is a ReloPass verified preferred partner (platform-wide) */
  preferred_partner: boolean;
  verified: boolean;
}

export interface MarketplaceResponse {
  assignment_id: string;
  vendors: MarketplaceVendor[];
  total: number;
}

/**
 * GAP 8: Fetch the vendor marketplace for a given assignment.
 * Vendors are pre-sorted: preferred+covered first, then covered, then preferred, then rest.
 */
export async function getAssignmentMarketplace(
  assignmentId: string,
): Promise<MarketplaceResponse> {
  return apiGet<MarketplaceResponse>(
    `/api/employee/assignments/${assignmentId}/marketplace`,
  );
}
