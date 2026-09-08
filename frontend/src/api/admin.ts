import type { CountryListDTO, CountryProfileDTO } from '../types';
import { apiGet, apiPost } from './client';

const adminHeaders = () => ({
  'X-Role': localStorage.getItem('demo_role') || 'user',
});

export async function listCountries(): Promise<CountryListDTO> {
  return apiGet('/api/admin/countries', { headers: adminHeaders() });
}

export async function getCountryProfile(countryCode: string): Promise<CountryProfileDTO> {
  return apiGet(`/api/admin/countries/${countryCode}`, { headers: adminHeaders() });
}

export async function rerunCountryResearch(
  countryCode: string,
  opts?: { purpose?: string }
): Promise<{ jobId: string }> {
  return apiPost(`/api/admin/countries/${countryCode}/research/rerun`, opts, { headers: adminHeaders() });
}

/** How well-sourced a requirement is. A badge — it does not decide what is served. */
// 'verified' is the value production stores; 'expert_verified' is the value the backend
// constants use. Both are listed until they are normalised.
export type VerificationStatus = 'representative' | 'corpus_grounded' | 'expert_verified' | 'verified';
/** Whether a requirement is served. Only 'approved' reaches employees or the public endpoint. */
export type ReviewStatus = 'pending' | 'approved' | 'rejected';

/**
 * One resolved citation. `url` is nullable on purpose: `citations_json` holds `source_records`
 * ids and some of them dangle, so the backend surfaces the broken reference rather than
 * dropping it — the reviewer is the one person who has to see it before publishing.
 */
export interface AdminCitation {
  id: string;
  url?: string | null;
  title: string;
  publisherDomain?: string | null;
}

export interface AdminRequirementReview {
  id: string;
  purpose: string;
  pillar: string;
  title: string;
  description: string;
  severity: string;
  owner: string;
  verificationStatus?: VerificationStatus | null;
  reviewStatus: ReviewStatus;
  reviewedBy?: string | null;
  reviewedAt?: string | null;
  /** null ⇒ applies to every nationality class — which is how a visa track reaches a free mover. */
  appliesToNationalityClasses?: string[] | null;
  appliesToAssignmentTypes?: string[] | null;
  citations: AdminCitation[];
  lastVerifiedAt?: string | null;
}

export interface AdminRequirementList {
  countryCode: string;
  pendingCount: number;
  items: AdminRequirementReview[];
}

/** Includes unapproved rows — the whole point of the review surface. */
export async function listCountryRequirements(countryCode: string): Promise<AdminRequirementList> {
  return apiGet(`/api/admin/countries/${countryCode}/requirements`, { headers: adminHeaders() });
}

/** Publish or withhold one requirement. Approving is what makes it readable. */
export async function reviewCountryRequirement(
  countryCode: string,
  requirementId: string,
  status: Exclude<ReviewStatus, 'pending'>
): Promise<AdminRequirementReview> {
  return apiPost(
    `/api/admin/countries/${countryCode}/requirements/${requirementId}/review`,
    { status },
    { headers: adminHeaders() }
  );
}

/** Publish or withhold many requirements in one request. */
export async function reviewCountryRequirementsBatch(
  countryCode: string,
  ids: string[],
  status: Exclude<ReviewStatus, 'pending'>
): Promise<{ items: AdminRequirementReview[] }> {
  return apiPost(
    `/api/admin/countries/${countryCode}/requirements/review-batch`,
    { ids, status },
    { headers: adminHeaders() }
  );
}
