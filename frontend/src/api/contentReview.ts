import { apiGet, apiPatch, apiPost } from './client';

/**
 * [AIQ-1821] The content review queue — requirement facts with their evidence.
 *
 * One typed file per domain (the requirementFacts.ts shape), not another entry in the 187 KB
 * client.ts.
 */

/**
 * How much we can say about a fact's quote WITHOUT a human.
 *
 * The distinction between `translated` and `unverified` is load-bearing: France's 97 pending
 * facts are English renderings of French pages, so a verbatim match is impossible by
 * construction. Showing those as "unverified" would put 97 sound facts in the suspect pile.
 */
export type EvidenceStatus = 'verified' | 'translated' | 'unverified' | 'no_source' | 'no_quote';

export interface ReviewFact {
  id: string;
  fact_text: string;
  fact_type: string;
  evidence_quote: string | null;
  source_url: string;
  confidence: string;
  status: string;
  evidence_status: EvidenceStatus;
  /** The quote surrounded by source text. Empty unless evidence_status === 'verified'. */
  evidence_context: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string | null;
  destination_country: string;
  topic_key: string;
  domain_area: string;
  source_last_verified: string | null;
}

export interface ReviewPage {
  items: ReviewFact[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReviewSummary {
  by_destination: Record<string, Record<string, number>>;
  totals: Record<string, number>;
  pending_evidence: Partial<Record<'verified' | 'unverified' | 'unchecked', number>>;
  pending: number;
}

export interface ListParams {
  status?: string;
  destination?: string;
  evidence?: 'verified' | 'unverified' | 'unchecked';
  q?: string;
  limit?: number;
  offset?: number;
}

export const listReviewFacts = (params: ListParams = {}): Promise<ReviewPage> => {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v));
  });
  return apiGet<ReviewPage>(`/api/admin/content-review/facts?${qs.toString()}`);
};

export const getReviewSummary = (): Promise<ReviewSummary> =>
  apiGet<ReviewSummary>('/api/admin/content-review/summary');

/** Bulk approve/reject. `notes` is required by the server when rejecting. */
export const decideFacts = (
  factIds: string[],
  action: 'approve' | 'reject',
  notes?: string,
): Promise<{ ok: boolean; count: number; status: string }> =>
  apiPost('/api/admin/content-review/decide', { fact_ids: factIds, action, notes });

/** Correct a fact's wording — the verdict approve/reject cannot express. */
export const editFact = (
  id: string,
  factText: string,
  notes?: string,
  extras?: { evidenceQuote?: string; approve?: boolean },
): Promise<{ ok: boolean; fact_text: string; previous_fact_text: string }> =>
  apiPatch(`/api/admin/content-review/facts/${encodeURIComponent(id)}`, {
    fact_text: factText,
    notes,
    ...(extras?.evidenceQuote !== undefined ? { evidence_quote: extras.evidenceQuote } : {}),
    ...(extras?.approve !== undefined ? { approve: extras.approve } : {}),
  });
