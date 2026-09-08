/**
 * [AIQ-1092 / P4-03] Admin review API for LLM-extracted requirement facts.
 * Backend: backend/app/routers/requirement_facts.py (GET list + PATCH review).
 */
import { apiGet, apiPatch } from './client';

export type RequirementFactStatus = 'pending' | 'approved' | 'rejected';

export interface RequirementFactCandidate {
  id: string;
  created_at: string | null;
  source_url: string;
  corridor: string | null;
  requirement_type: string;
  fact_text: string;
  confidence_score: number | null;
  source_quote: string | null;
  extraction_method: string;
  status: RequirementFactStatus;
  reviewed_by: string | null;
  reviewed_at: string | null;
}

export const listRequirementFacts = (
  status: RequirementFactStatus = 'pending',
): Promise<RequirementFactCandidate[]> =>
  apiGet<RequirementFactCandidate[]>(
    `/api/admin/requirement-facts?status=${encodeURIComponent(status)}`,
  );

export const reviewRequirementFact = (
  id: string,
  status: 'approved' | 'rejected',
): Promise<RequirementFactCandidate> =>
  apiPatch<RequirementFactCandidate>(
    `/api/admin/requirement-facts/${encodeURIComponent(id)}`,
    { status },
  );
