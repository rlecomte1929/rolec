import type { AiStep } from '../features/admin/specialist-review/RoadmapStepDiff';
import type { ReasonCode, ReviewDecision } from '../features/admin/specialist-review/reasonCodes';
import type {
  DossierQuestionsResponse,
  DossierSearchSuggestionsResponse,
  DossierSource,
} from '../types';
import { api } from './client';
import type { CountryResourcesResult, GuidanceGenerateResult } from './types';

export const resourcesAPI = {
  /** Legacy: uses /api/resources/country (rkg_resources). Kept for backward compatibility. */
  getCountryResources: async (
    assignmentId: string,
    filters?: Record<string, string | number | boolean | null>
  ): Promise<{
    profile: Record<string, unknown>;
    context?: Record<string, unknown>;
    hints: { priorities: string[]; recommendations: string[] };
    sections: Array<{ key: string; title: string; content: unknown }>;
    events?: unknown[];
    recommended?: unknown[];
    filters_applied: Record<string, unknown>;
  }> => {
    const params: Record<string, string> = { assignment_id: assignmentId };
    if (filters && Object.keys(filters).length) {
      params.filters = JSON.stringify(filters);
    }
    const response = await api.get<CountryResourcesResult>('/api/resources/country', { params });
    return response.data;
  },

  /** New: composite page data from published views. Use assignmentId or caseId (backend resolves both). */
  getPage: async (
    assignmentOrCaseId: string,
    filters?: Record<string, string | number | boolean | null>
  ): Promise<import('../types').ResourcesPagePayload> => {
    const params: Record<string, string> = { assignment_id: assignmentOrCaseId };
    if (filters && Object.keys(filters).length) {
      params.filters = JSON.stringify(filters);
    }
    const response = await api.get<import('../types').ResourcesPagePayload>('/api/resources/page', { params });
    return response.data;
  },

  getContext: async (assignmentOrCaseId: string): Promise<import('../types').ResourceContext> => {
    const response = await api.get<import('../types').ResourceContext>('/api/resources/context', {
      params: { assignment_id: assignmentOrCaseId },
    });
    return response.data;
  },

  /**
   * Returns the catalog destination allowlist — every (city, country) pair the
   * platform supports for AI scraping. Used by HrResourcesPreview to build a
   * live dropdown instead of a hardcoded 12-country list (B14 fix).
   */
  getDestinations: async (): Promise<Array<{ city: string; country: string }>> => {
    const response = await api.get<Array<{ city: string; country: string }>>('/api/hr/resources/destinations');
    return Array.isArray(response.data) ? response.data : [];
  },

  /** HR-only preview: same payload shape as getPage, but driven by an explicit
   *  destination + persona instead of a real assignment. */
  getHrPreviewPage: async (
    params: {
      countryCode: string;
      countryName?: string | null;
      city?: string | null;
      familyType?: 'single' | 'couple' | 'family';
      relocationType?: 'short_term' | 'long_term' | 'permanent';
      hasChildren?: boolean | null;
    },
    filters?: Record<string, string | number | boolean | null>
  ): Promise<import('../types').ResourcesPagePayload> => {
    const q: Record<string, string> = { country_code: params.countryCode };
    if (params.countryName) q.country_name = params.countryName;
    if (params.city) q.city = params.city;
    if (params.familyType) q.family_type = params.familyType;
    if (params.relocationType) q.relocation_type = params.relocationType;
    if (params.hasChildren != null) q.has_children = String(params.hasChildren);
    if (filters && Object.keys(filters).length) q.filters = JSON.stringify(filters);
    const response = await api.get<import('../types').ResourcesPagePayload>('/api/hr/resources/page', { params: q });
    return response.data;
  },

  /**
   * AIQ-1581: LLM-generated "things to do" suggestions for a destination city.
   * City + country are non-personal. The backend is fail-soft (empty list on
   * generation failure), so this never throws for a missing feed.
   */
  getCityActivities: async (
    city: string,
    country: string
  ): Promise<import('../types').CityActivity[]> => {
    const response = await api.get<import('../types').CityActivitiesResponse>(
      '/api/resources/city-activities',
      { params: { city, country } }
    );
    return Array.isArray(response.data?.activities) ? response.data.activities : [];
  },

  getResources: async (
    assignmentOrCaseId: string,
    filters?: Record<string, string | number | boolean | null>,
    page = 1,
    limit = 50
  ): Promise<{ resources: Record<string, unknown>[] }> => {
    const params: Record<string, string | number> = {
      assignment_id: assignmentOrCaseId,
      page,
      limit,
    };
    if (filters && Object.keys(filters).length) {
      params.filters = JSON.stringify(filters);
    }
    const response = await api.get<{ resources: Record<string, unknown>[] }>('/api/resources', { params });
    return response.data;
  },

  getEvents: async (
    assignmentOrCaseId: string,
    filters?: Record<string, string | number | boolean | null>,
    page = 1,
    limit = 50
  ): Promise<{ events: import('../types').PublicEvent[] }> => {
    const params: Record<string, string | number> = {
      assignment_id: assignmentOrCaseId,
      page,
      limit,
    };
    if (filters && Object.keys(filters).length) {
      params.filters = JSON.stringify(filters);
    }
    const response = await api.get<{ events: import('../types').PublicEvent[] }>('/api/resources/events', { params });
    return response.data;
  },

  getRecommended: async (
    assignmentOrCaseId: string,
    limit = 10
  ): Promise<import('../types').RecommendationGroup> => {
    const response = await api.get<import('../types').RecommendationGroup>('/api/resources/recommended', {
      params: { assignment_id: assignmentOrCaseId, limit },
    });
    return response.data;
  },
};

export const dossierAPI = {
  getQuestions: async (caseId: string): Promise<DossierQuestionsResponse> => {
    const response = await api.get<DossierQuestionsResponse>('/api/dossier/questions', { params: { case_id: caseId } });
    return response.data;
  },
  saveAnswers: async (payload: { case_id: string; answers: Array<{ question_id?: string | null; case_question_id?: string | null; answer: unknown }> }): Promise<{ ok: boolean }> => {
    const response = await api.post<{ ok: boolean }>('/api/dossier/answers', payload);
    return response.data;
  },
  searchSuggestions: async (caseId: string): Promise<DossierSearchSuggestionsResponse> => {
    const response = await api.post<DossierSearchSuggestionsResponse>('/api/dossier/search-suggestions', { case_id: caseId });
    return response.data;
  },
  addCaseQuestion: async (payload: { case_id: string; question_text: string; answer_type: string; options?: string[] | null; is_mandatory?: boolean; sources?: DossierSource[] }): Promise<unknown> => {
    const response = await api.post<unknown>('/api/dossier/case-questions', payload);
    return response.data;
  },
};

export const guidanceAPI = {
  generate: async (caseId: string, mode?: 'demo' | 'strict'): Promise<{
    guidance_pack_id: string;
    guidance_mode?: 'demo' | 'strict';
    pack_hash?: string;
    rule_set?: unknown[];
    plan: unknown;
    checklist: unknown;
    markdown: string;
    sources: Array<{ doc_id: string; title?: string; url: string; publisher?: string }>;
    not_covered: string[];
    coverage?: unknown;
  }> => {
    const response = await api.post<GuidanceGenerateResult>('/api/guidance/generate', { case_id: caseId, mode });
    return response.data;
  },
  getLatest: async (caseId: string): Promise<unknown> => {
    const response = await api.get<unknown>('/api/guidance/latest', { params: { case_id: caseId } });
    return response.data;
  },
  explain: async (caseId: string): Promise<unknown> => {
    const response = await api.get<unknown>('/api/guidance/explain', { params: { case_id: caseId } });
    return response.data;
  },
};

// ── Specialist review API (AIQ-633) ───────────────────────────────────────────

export interface SpecialistReviewSubmitItem {
  step_id: string;
  decision: ReviewDecision;
  reason_code?: ReasonCode;
  original_step: AiStep;
  edited_step?: AiStep;
}

export const specialistReviewAPI = {
  getRoadmap: async (caseId: string): Promise<{ case_id: string; steps: AiStep[] }> => {
    const res = await api.get<{ case_id: string; steps: AiStep[] }>(`/api/internal/specialist-review/${caseId}`);
    return res.data;
  },
  submit: async (
    caseId: string,
    body: { decision: 'approved' | 'rejected'; notes?: string; items: SpecialistReviewSubmitItem[] },
  ): Promise<{ released_to_user: boolean; regeneration_requested: boolean }> => {
    const res = await api.post<{ released_to_user: boolean; regeneration_requested: boolean }>(`/api/internal/specialist-review/submit`, { case_id: caseId, ...body });
    return res.data;
  },
};
