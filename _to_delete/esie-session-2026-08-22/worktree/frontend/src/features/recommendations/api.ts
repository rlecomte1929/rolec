import api from '../../api/client';
import type { RecommendationResponse, CategoryInfo } from './types';

const BASE = '/api/recommendations';

// AIQ-1856: the batch endpoint legitimately runs several seconds — it fans out one
// engine run per selected category, then applies HR curation. In production it was
// measured at 11.9s for a 4-category case, and the 12s axios default aborted it 77ms
// before the 200 landed: the work completed server-side, the employee saw "cannot
// reach server" (a status-0 failed request with no response). Ceiling it well above
// the real cost — the page already asks the user to keep it open while it works.
const RECOMMEND_BATCH_TIMEOUT = 60_000;

export interface ProviderRatingResult {
  ok: boolean;
  supplier_id: string;
  average_rating: number | null;
  review_count: number;
}

/**
 * CATALOG-3 — submit an employee's 1-5 rating for a provider on a case.
 * Idempotent server-side per (employee, supplier, case).
 */
export async function rateProvider(
  supplierId: string,
  payload: { caseId: string; score: number; comment?: string },
): Promise<ProviderRatingResult> {
  const res = await api.post<ProviderRatingResult>(`/api/employee/providers/${encodeURIComponent(supplierId)}/rating`, {
    case_id: payload.caseId,
    score: payload.score,
    comment: payload.comment,
  });
  return res.data;
}

export const recommendationsEngineAPI = {
  listCategories: async (): Promise<{ categories: CategoryInfo[] }> => {
    const res = await api.get<{ categories: CategoryInfo[] }>(`${BASE}/categories`);
    return res.data;
  },

  getSchema: async (category: string): Promise<Record<string, unknown>> => {
    const res = await api.get<Record<string, unknown>>(`${BASE}/${category}/schema`);
    return res.data;
  },

  recommend: async (
    category: string,
    criteria: Record<string, unknown>,
    topN = 10
  ): Promise<RecommendationResponse> => {
    const res = await api.post<RecommendationResponse>(`${BASE}/${category}`, {
      criteria,
      top_n: topN,
    });
    return res.data;
  },

  /** Batch recommendations for selected services. Backend builds criteria from assignment, case, saved answers, and policy.
   *  `shortlistedAreaIds` (living_areas item_ids the employee shortlisted) re-ranks housing
   *  agencies to favour those serving the shortlisted neighbourhoods — a boost, never a filter. */
  recommendBatch: async (
    assignmentId: string,
    selectedServices?: string[],
    shortlistedAreaIds?: string[]
  ): Promise<{ results: Record<string, RecommendationResponse> }> => {
    const res = await api.post<{ results: Record<string, RecommendationResponse> }>(
      `${BASE}/batch`,
      {
        assignment_id: assignmentId,
        selected_services: selectedServices ?? undefined,
        shortlisted_area_ids: shortlistedAreaIds && shortlistedAreaIds.length ? shortlistedAreaIds : undefined,
      },
      { timeout: RECOMMEND_BATCH_TIMEOUT },
    );
    return res.data;
  },
};
