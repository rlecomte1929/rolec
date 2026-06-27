import api from '../../api/client';
import type { RecommendationResponse, CategoryInfo } from './types';

const BASE = '/api/recommendations';

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

  /** Batch recommendations for selected services. Backend builds criteria from assignment, case, saved answers, and policy. */
  recommendBatch: async (
    assignmentId: string,
    selectedServices?: string[]
  ): Promise<{ results: Record<string, RecommendationResponse> }> => {
    const res = await api.post<{ results: Record<string, RecommendationResponse> }>(`${BASE}/batch`, {
      assignment_id: assignmentId,
      selected_services: selectedServices ?? undefined,
    });
    return res.data;
  },
};
