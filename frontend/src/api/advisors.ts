/**
 * GAP 4: Immigration advisor matching — POST /api/advisors/match
 *                                        GET  /api/advisors/{id}
 *
 * Returns immigration advisors matched to a relocation corridor.
 * Sort order: company preferred → platform preferred → by rating desc.
 * Used by the advisor card on the Discovery screen and the Roadmap sidebar.
 */
import { apiGet, apiPost } from './client';

export interface AdvisorProfile {
  id: string;
  name: string;
  firm: string;
  title: string | null;
  specialisms: string[];
  languages: string[];
  rating: number | null;
  rating_count: number;
  verified: boolean;
  preferred_partner: boolean;
  /** True if this advisor is a preferred choice for the employee's company */
  preferred_for_company: boolean;
  contact_url: string | null;
  response_sla: string | null;
  logo_initials: string;
}

export interface AdvisorMatchRequest {
  origin_country?: string;
  destination_country?: string;
  purpose?: string;
  case_id?: string;
}

export interface AdvisorMatchResponse {
  origin_country: string | null;
  destination_country: string | null;
  advisors: AdvisorProfile[];
  total: number;
}

/**
 * GAP 4: Match immigration advisors for a relocation corridor.
 */
export async function matchAdvisors(
  params: AdvisorMatchRequest,
): Promise<AdvisorMatchResponse> {
  return apiPost<AdvisorMatchResponse>('/api/advisors/match', params);
}

/**
 * GAP 4: Fetch a single advisor profile by ID.
 */
export async function getAdvisor(advisorId: string): Promise<AdvisorProfile> {
  return apiGet<AdvisorProfile>(`/api/advisors/${advisorId}`);
}
