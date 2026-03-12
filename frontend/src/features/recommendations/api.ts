import api from '../../api/client';
import type { RecommendationResponse, CategoryInfo } from './types';

const BASE = '/api/recommendations';

export const recommendationsEngineAPI = {
  listCategories: async (): Promise<{ categories: CategoryInfo[] }> => {
    const res = await api.get(`${BASE}/categories`);
    return res.data;
  },

  getSchema: async (category: string): Promise<Record<string, unknown>> => {
    const res = await api.get(`${BASE}/${category}/schema`);
    return res.data;
  },

  recommend: async (
    category: string,
    criteria: Record<string, unknown>,
    topN = 10
  ): Promise<RecommendationResponse> => {
    const res = await api.post(`${BASE}/${category}`, {
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
    const res = await api.post(`${BASE}/batch`, {
      assignment_id: assignmentId,
      selected_services: selectedServices ?? undefined,
    });
    return res.data;
  },
};
