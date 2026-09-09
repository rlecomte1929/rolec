import type { ThreadSummariesResult } from './types';
import { API_BASE_URL, api } from './client';

// Admin HR Prospect Pipeline API (admin only)
export type ProspectSeedItem = {
  company_name: string;
  company_domain?: string;
  company_linkedin_url?: string;
  notes?: string;
};

export type ProspectRow = {
  id: string;
  company_name: string;
  company_domain: string | null;
  company_linkedin_url: string | null;
  icp_score: number | null;
  qualification_band: string | null;
  suggested_contact_title: string | null;
  suggested_hook: string | null;
  status: string;
  web_search_used: boolean;
  batch_id: string | null;
  enrichment_error: string | null;
  enriched?: Record<string, unknown> | null;
  raw_input?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  enriched_at: string | null;
  reviewed_at: string | null;
  reviewed_by: string | null;
};

export const adminProspectsAPI = {
  list: async (params?: {
    status?: string;
    band?: string;
    batch_id?: string;
    min_score?: number;
    limit?: number;
    offset?: number;
  }) =>
    api
      .get('/api/admin/prospects', { params: params || {} })
      .then((r) => r.data as { total: number; limit: number; offset: number; prospects: ProspectRow[] }),
  get: async (prospectId: string) =>
    api.get(`/api/admin/prospects/${prospectId}`).then((r) => r.data as ProspectRow),
  ingestBatch: async (payload: { prospects: ProspectSeedItem[]; enable_web_search: boolean }) =>
    api
      .post('/api/admin/prospects/batch', payload)
      .then(
        (r) =>
          r.data as {
            batch_id: string;
            queued: number;
            skipped_duplicates: number;
            duplicate_domains: string[];
            enable_web_search: boolean;
            estimated_web_search_cost_usd: number;
          },
      ),
  remove: async (prospectId: string) =>
    api.delete(`/api/admin/prospects/${prospectId}`).then((r) => r.data as { deleted: string }),
  triage: async (prospectId: string, decision: 'approved' | 'maybe' | 'rejected') =>
    api
      .post(`/api/admin/prospects/${prospectId}/triage`, { decision })
      .then((r) => r.data as ProspectRow),
  // Track B: convert an approved prospect into a live tenant (company + HR seat + welcome).
  onboard: async (
    prospectId: string,
    payload: { hr_email: string; hr_name?: string; reason?: string; send_welcome?: boolean },
  ): Promise<{ ok: boolean; company_id?: string; company_name?: string; hr_email?: string; invite_sent?: boolean; already_onboarded?: boolean }> =>
    api
      .post<{ ok: boolean; company_id?: string; company_name?: string; hr_email?: string; invite_sent?: boolean; already_onboarded?: boolean }>(
        `/api/admin/prospects/${prospectId}/onboard`, payload,
      )
      .then((r) => r.data),
  reenrich: async (prospectId: string, enableWebSearch: boolean) =>
    api
      .post(`/api/admin/prospects/${prospectId}/reenrich`, { enable_web_search: enableWebSearch })
      .then((r) => r.data as ProspectRow),
  reenrichFailed: async (enableWebSearch: boolean) =>
    api
      .post('/api/admin/prospects/reenrich-failed', { enable_web_search: enableWebSearch })
      .then(
        (r) =>
          r.data as {
            reenriched: number;
            enable_web_search: boolean;
            estimated_web_search_cost_usd: number;
          },
      ),
  costEstimate: async (prospectCount: number) =>
    api
      .get('/api/admin/prospects/cost-estimate', { params: { prospect_count: prospectCount } })
      .then(
        (r) =>
          r.data as {
            prospect_count: number;
            tavily_cost_per_query_usd: number;
            estimated_web_search_cost_usd: number;
            notes: string;
          },
      ),
  exportCsvUrl: (status: string = 'approved') =>
    `${API_BASE_URL}/api/admin/prospects/export.csv?status=${encodeURIComponent(status)}`,
};

// Admin Leads API (admin only) — audos-P1
export interface LeadRow {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  company_domain: string | null;
  source: string;
  status: string;
  tags: string[];
  message: string | null;
  utm_source: string | null;
  utm_campaign: string | null;
  created_at: string;
  updated_at: string;
  matched_prospect: boolean;
}

export interface LeadStats {
  total: number;
  new_this_week: number;
  by_status: Record<string, number>;
}

export const adminLeadsAPI = {
  list: async (params?: { status?: string; search?: string; limit?: number }) =>
    api
      .get('/api/admin/leads', { params: params || {} })
      .then((r) => r.data as { total: number; leads: LeadRow[] }),
  get: async (id: string) =>
    api.get(`/api/admin/leads/${id}`).then((r) => r.data as LeadRow),
  patch: async (id: string, patch: { status?: string; tags?: string[] }) =>
    api.patch(`/api/admin/leads/${id}`, patch).then((r) => r.data as LeadRow),
  stats: async () => api.get('/api/admin/leads/stats').then((r) => r.data as LeadStats),
};

export const leadCaptureAPI = {
  submit: async (payload: {
    email: string; first_name?: string; last_name?: string;
    company_domain?: string; message?: string; source: string;
    utm_source?: string; utm_campaign?: string;
  }) =>
    api.post('/api/public/lead-capture', payload).then((r) => r.data as { id: string; matched_prospect: boolean }),
};

// Admin Resources CMS API
export const adminResourcesAPI = {
  getCounts: async (): Promise<Record<string, number>> => api.get<Record<string, number>>('/api/admin/resources/counts').then((r) => r.data),
  listResources: async (params?: {
    country_code?: string;
    city?: string;
    category_id?: string;
    status?: string;
    audience?: string;
    featured?: boolean;
    family_friendly?: boolean;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: unknown[]; total: number }> => api.get<{ items: unknown[]; total: number }>('/api/admin/resources', { params }).then((r) => r.data),
  getResource: async (id: string) => api.get<unknown>(`/api/admin/resources/${id}`).then((r) => r.data),
  createResource: async (payload: Record<string, unknown>) =>
    api.post<unknown>('/api/admin/resources', payload).then((r) => r.data),
  updateResource: async (id: string, payload: Record<string, unknown>) =>
    api.put<unknown>(`/api/admin/resources/${id}`, payload).then((r) => r.data),
  submitForReview: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/${id}/submit-for-review`).then((r) => r.data),
  approveResource: async (id: string, notes?: string) =>
    api.post<unknown>(`/api/admin/resources/${id}/approve`, { notes }).then((r) => r.data),
  publishResource: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/${id}/publish`).then((r) => r.data),
  unpublishResource: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/${id}/unpublish`).then((r) => r.data),
  archiveResource: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/${id}/archive`).then((r) => r.data),
  restoreResource: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/${id}/restore`).then((r) => r.data),
  // [AIQ-1333] Soft-delete a draft/archived resource (server enforces the status guard).
  deleteResource: async (id: string) =>
    api.delete<{ ok: boolean; id: string }>(`/api/admin/resources/${id}`).then((r) => r.data),
  getResourceAudit: async (id: string, limit?: number) =>
    api.get<unknown>(`/api/admin/resources/${id}/audit`, { params: { limit } }).then((r) => r.data),
  getGlobalAuditLog: async (params?: { entity_type?: string; limit?: number; offset?: number }) =>
    api.get<unknown>('/api/admin/resources/audit-log', { params }).then((r) => r.data),
  listEvents: async (params?: {
    country_code?: string;
    city?: string;
    event_type?: string;
    status?: string;
    family_friendly?: boolean;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: unknown[]; total: number }> => api.get<{ items: unknown[]; total: number }>('/api/admin/resources/events', { params }).then((r) => r.data),
  getEvent: async (id: string) => api.get<unknown>(`/api/admin/resources/events/${id}`).then((r) => r.data),
  createEvent: async (payload: Record<string, unknown>) =>
    api.post<unknown>('/api/admin/resources/events', payload).then((r) => r.data),
  updateEvent: async (id: string, payload: Record<string, unknown>) =>
    api.put<unknown>(`/api/admin/resources/events/${id}`, payload).then((r) => r.data),
  publishEvent: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/events/${id}/publish`).then((r) => r.data),
  archiveEvent: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/events/${id}/archive`).then((r) => r.data),
  submitEventForReview: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/events/${id}/submit-for-review`).then((r) => r.data),
  approveEvent: async (id: string, notes?: string) =>
    api.post<unknown>(`/api/admin/resources/events/${id}/approve`, { notes }).then((r) => r.data),
  unpublishEvent: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/events/${id}/unpublish`).then((r) => r.data),
  restoreEvent: async (id: string) =>
    api.post<unknown>(`/api/admin/resources/events/${id}/restore`).then((r) => r.data),
  getEventAudit: async (id: string, limit?: number) =>
    api.get<unknown>(`/api/admin/resources/events/${id}/audit`, { params: { limit } }).then((r) => r.data),
  listCategories: async (): Promise<{ categories: unknown[] }> => api.get<{ categories: unknown[] }>('/api/admin/resources/taxonomy/categories').then((r) => r.data),
  createCategory: async (payload: Record<string, unknown>) =>
    api.post<unknown>('/api/admin/resources/taxonomy/categories', payload).then((r) => r.data),
  updateCategory: async (id: string, payload: Record<string, unknown>) =>
    api.put<unknown>(`/api/admin/resources/taxonomy/categories/${id}`, payload).then((r) => r.data),
  deactivateCategory: async (id: string) =>
    api.delete<unknown>(`/api/admin/resources/taxonomy/categories/${id}`).then((r) => r.data),
  listTags: async (tag_group?: string): Promise<{ tags: unknown[] }> =>
    api.get<{ tags: unknown[] }>('/api/admin/resources/taxonomy/tags', { params: { tag_group } }).then((r) => r.data),
  createTag: async (payload: Record<string, unknown>) =>
    api.post<unknown>('/api/admin/resources/taxonomy/tags', payload).then((r) => r.data),
  updateTag: async (id: string, payload: Record<string, unknown>) =>
    api.put<unknown>(`/api/admin/resources/taxonomy/tags/${id}`, payload).then((r) => r.data),
  listSources: async (): Promise<{ sources: unknown[] }> => api.get<{ sources: unknown[] }>('/api/admin/resources/taxonomy/sources').then((r) => r.data),
  createSource: async (payload: Record<string, unknown>) =>
    api.post<unknown>('/api/admin/resources/taxonomy/sources', payload).then((r) => r.data),
  updateSource: async (id: string, payload: Record<string, unknown>) =>
    api.put<unknown>(`/api/admin/resources/taxonomy/sources/${id}`, payload).then((r) => r.data),
};

// [P1-2] Admin Form Templates API — catalog of official government forms.
// Backend: backend/app/routers/admin_form_templates.py
export interface FormTemplate {
  id: string;
  code: string;
  name: string;
  country: string;
  authority_code: string | null;
  authority_name: string | null;
  category: string | null;
  original_pdf_url: string | null;
  version: string;
  fields: Array<Record<string, unknown>>;
  trigger_rules: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type FormTemplateCreate = Omit<FormTemplate, 'id' | 'created_at' | 'updated_at'> & {
  // All optional except code/name/country — backend supplies defaults.
  authority_code?: string | null;
  authority_name?: string | null;
  category?: string | null;
  original_pdf_url?: string | null;
  version?: string;
  fields?: Array<Record<string, unknown>>;
  trigger_rules?: Record<string, unknown>;
};

export type FormTemplateUpdate = Partial<Omit<FormTemplate, 'id' | 'created_at' | 'updated_at'>>;

export const adminFormTemplatesAPI = {
  list: async (params?: {
    country?: string;
    category?: string;
    code?: string;
    limit?: number;
    offset?: number;
  }): Promise<FormTemplate[]> =>
    api.get<FormTemplate[]>('/api/admin/form-templates', { params }).then((r) => r.data),

  get: async (id: string): Promise<FormTemplate> =>
    api.get<FormTemplate>(`/api/admin/form-templates/${id}`).then((r) => r.data),

  create: async (payload: FormTemplateCreate): Promise<FormTemplate> =>
    api.post<FormTemplate>('/api/admin/form-templates', payload).then((r) => r.data),

  /**
   * PATCH — two modes:
   *  - In-place: omit `version` (or pass the current value) → row is mutated.
   *  - Version bump: pass a NEW `version` → a new row is inserted carrying the
   *    merged values; the old row is preserved so historical case_forms keep
   *    pointing at it. The returned row is the new one.
   */
  update: async (id: string, payload: FormTemplateUpdate): Promise<FormTemplate> =>
    api.patch<FormTemplate>(`/api/admin/form-templates/${id}`, payload).then((r) => r.data),
};

// Admin Staging Review API (admin-only)
export const adminStagingAPI = {
  getDashboard: () => api.get<unknown>('/api/admin/staging/dashboard').then((r) => r.data),
  listResourceCandidates: (params?: {
    status?: string;
    country_code?: string;
    city_name?: string;
    category_key?: string;
    resource_type?: string;
    trust_tier?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: unknown[]; total: number }> => api.get<{ items: unknown[]; total: number }>('/api/admin/staging/resources', { params }).then((r) => r.data),
  getResourceCandidate: (id: string) =>
    api.get<unknown>(`/api/admin/staging/resources/${id}`).then((r) => r.data),
  getResourceCandidateMatches: (id: string) =>
    api.get<unknown>(`/api/admin/staging/resources/${id}/matches`).then((r) => r.data),
  approveResourceAsNew: (id: string, reason?: string) =>
    api.post<unknown>(`/api/admin/staging/resources/${id}/approve-new`, { reason }).then((r) => r.data),
  mergeResource: (
    id: string,
    payload: {
      target_resource_id: string;
      merge_mode?: string;
      fields_to_merge?: string[];
      reason?: string;
    }
  ) => api.post<unknown>(`/api/admin/staging/resources/${id}/merge`, payload).then((r) => r.data),
  rejectResource: (id: string, reason?: string) =>
    api.post<unknown>(`/api/admin/staging/resources/${id}/reject`, { reason }).then((r) => r.data),
  markResourceDuplicate: (
    id: string,
    payload: {
      duplicate_of_candidate_id?: string;
      duplicate_of_live_resource_id?: string;
      reason?: string;
    }
  ) => api.post<unknown>(`/api/admin/staging/resources/${id}/mark-duplicate`, payload).then((r) => r.data),
  ignoreResource: (id: string, reason?: string) =>
    api.post<unknown>(`/api/admin/staging/resources/${id}/ignore`, { reason }).then((r) => r.data),
  restoreResourceToReview: (id: string) =>
    api.post<unknown>(`/api/admin/staging/resources/${id}/restore-review`).then((r) => r.data),
  listEventCandidates: (params?: {
    status?: string;
    country_code?: string;
    city_name?: string;
    event_type?: string;
    trust_tier?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: unknown[]; total: number }> => api.get<{ items: unknown[]; total: number }>('/api/admin/staging/events', { params }).then((r) => r.data),
  getEventCandidate: (id: string) =>
    api.get<unknown>(`/api/admin/staging/events/${id}`).then((r) => r.data),
  getEventCandidateMatches: (id: string) =>
    api.get<unknown>(`/api/admin/staging/events/${id}/matches`).then((r) => r.data),
  approveEventAsNew: (id: string, reason?: string) =>
    api.post<unknown>(`/api/admin/staging/events/${id}/approve-new`, { reason }).then((r) => r.data),
  mergeEvent: (
    id: string,
    payload: {
      target_event_id: string;
      merge_mode?: string;
      fields_to_merge?: string[];
      reason?: string;
    }
  ) => api.post<unknown>(`/api/admin/staging/events/${id}/merge`, payload).then((r) => r.data),
  rejectEvent: (id: string, reason?: string) =>
    api.post<unknown>(`/api/admin/staging/events/${id}/reject`, { reason }).then((r) => r.data),
  markEventDuplicate: (
    id: string,
    payload: {
      duplicate_of_candidate_id?: string;
      duplicate_of_live_event_id?: string;
      reason?: string;
    }
  ) => api.post<unknown>(`/api/admin/staging/events/${id}/mark-duplicate`, payload).then((r) => r.data),
  ignoreEvent: (id: string, reason?: string) =>
    api.post<unknown>(`/api/admin/staging/events/${id}/ignore`, { reason }).then((r) => r.data),
  restoreEventToReview: (id: string) =>
    api.post<unknown>(`/api/admin/staging/events/${id}/restore-review`).then((r) => r.data),
};

// Admin Freshness & Crawl API (admin-only)
export const adminFreshnessAPI = {
  getOverview: () => api.get<unknown>('/api/admin/freshness/overview').then((r) => r.data),
  getCountries: () => api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/freshness/countries').then((r) => r.data),
  getCities: (params?: { country_code?: string }) =>
    api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/freshness/cities', { params }).then((r) => r.data),
  getSources: () => api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/freshness/sources').then((r) => r.data),
  getSourcePages: () => api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/freshness/source-pages').then((r) => r.data),
  refreshFreshness: () => api.post<unknown>('/api/admin/freshness/refresh').then((r) => r.data),
  listSchedules: (params?: { is_active?: boolean; limit?: number }) =>
    api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/crawl/schedules', { params }).then((r) => r.data),
  getDueSchedules: () => api.get<unknown>('/api/admin/crawl/schedules/due').then((r) => r.data),
  getSchedule: (id: string) => api.get<unknown>(`/api/admin/crawl/schedules/${id}`).then((r) => r.data),
  createSchedule: (payload: Record<string, unknown>) =>
    api.post<unknown>('/api/admin/crawl/schedules', payload).then((r) => r.data),
  updateSchedule: (id: string, payload: Record<string, unknown>) =>
    api.put<unknown>(`/api/admin/crawl/schedules/${id}`, payload).then((r) => r.data),
  pauseSchedule: (id: string) => api.post<unknown>(`/api/admin/crawl/schedules/${id}/pause`).then((r) => r.data),
  resumeSchedule: (id: string) => api.post<unknown>(`/api/admin/crawl/schedules/${id}/resume`).then((r) => r.data),
  triggerSchedule: (id: string) => api.post<unknown>(`/api/admin/crawl/schedules/${id}/trigger`).then((r) => r.data),
  processDueSchedules: () => api.post<unknown>('/api/admin/crawl/process-due').then((r) => r.data),
  triggerCrawl: (payload: { source_name?: string; country_code?: string; city_name?: string; content_domain?: string }) =>
    api.post<unknown>('/api/admin/crawl/trigger', payload).then((r) => r.data),
  listJobRuns: (params?: { schedule_id?: string; status?: string; limit?: number; offset?: number }) =>
    api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/crawl/job-runs', { params }).then((r) => r.data),
  getJobRun: (id: string) => api.get<unknown>(`/api/admin/crawl/job-runs/${id}`).then((r) => r.data),
  listDocumentChanges: (params?: {
    job_run_id?: string;
    source_name?: string;
    change_type?: string;
    since?: string;
    limit?: number;
    offset?: number;
  }) => api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/changes/documents', { params }).then((r) => r.data),
  getDocumentChange: (id: string) => api.get<unknown>(`/api/admin/changes/documents/${id}`).then((r) => r.data),
  getStaleResources: (params?: { country_code?: string; city_name?: string; limit?: number }) =>
    api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/changes/live-stale-resources', { params }).then((r) => r.data),
  getStaleEvents: (params?: { country_code?: string; city_name?: string; limit?: number }) =>
    api.get<{ items: Record<string, unknown>[]; total?: number }>('/api/admin/changes/live-stale-events', { params }).then((r) => r.data),
};

// P2-02d — admin material-change review queue (approve before users are notified).
export const sourceChangeReviewAPI = {
  listPending: (params?: { limit?: number; offset?: number }) =>
    api.get<{ items: unknown[]; total?: number }>('/api/admin/source-change-reviews', { params }).then((r) => r.data),
  approve: (id: string) =>
    api.post<unknown>(`/api/admin/source-change-reviews/${id}/approve`).then((r) => r.data),
  reject: (id: string, note?: string) =>
    api.post<unknown>(`/api/admin/source-change-reviews/${id}/reject`, { note }).then((r) => r.data),
};

// Admin Review Queue API (admin-only)
export const adminReviewQueueAPI = {
  list: (params?: {
    status?: string;
    priority_band?: string;
    assignee_id?: string;
    country_code?: string;
    city_name?: string;
    queue_item_type?: string;
    overdue_only?: boolean;
    unassigned_only?: boolean;
    search?: string;
    limit?: number;
    offset?: number;
    sort?: 'priority' | 'created' | 'due' | 'age';
  }) => api.get<{ items: unknown[]; total?: number }>('/api/admin/review-queue', { params }).then((r) => r.data),
  getStats: () => api.get<unknown>('/api/admin/review-queue/stats').then((r) => r.data),
  getAssignees: (limit?: number) =>
    api.get<unknown>('/api/admin/review-queue/assignees', { params: { limit } }).then((r) => r.data),
  getItem: (id: string) => api.get<unknown>(`/api/admin/review-queue/${id}`).then((r) => r.data),
  getActivity: (id: string, limit?: number) =>
    api.get<unknown>(`/api/admin/review-queue/${id}/activity`, { params: { limit } }).then((r) => r.data),
  assign: (id: string, assigneeUserId: string) =>
    api.post<unknown>(`/api/admin/review-queue/${id}/assign`, { assignee_user_id: assigneeUserId }).then((r) => r.data),
  claim: (id: string) => api.post<unknown>(`/api/admin/review-queue/${id}/claim`).then((r) => r.data),
  unassign: (id: string) => api.post<unknown>(`/api/admin/review-queue/${id}/unassign`).then((r) => r.data),
  setStatus: (id: string, status: string, note?: string) =>
    api.post<unknown>(`/api/admin/review-queue/${id}/status`, { status, note }).then((r) => r.data),
  defer: (id: string, dueAt?: string, note?: string) =>
    api.post<unknown>(`/api/admin/review-queue/${id}/defer`, { due_at: dueAt, note }).then((r) => r.data),
  resolve: (id: string, resolutionSummary?: string) =>
    api.post<unknown>(`/api/admin/review-queue/${id}/resolve`, { resolution_summary: resolutionSummary }).then((r) => r.data),
  reopen: (id: string, note?: string) =>
    api.post<unknown>(`/api/admin/review-queue/${id}/reopen`, { note }).then((r) => r.data),
  updateNotes: (id: string, notes: string) =>
    api.patch<unknown>(`/api/admin/review-queue/${id}/notes`, { notes }).then((r) => r.data),
  bulkAssign: (itemIds: string[], assigneeUserId: string) =>
    api.post<unknown>('/api/admin/review-queue/bulk-assign', { item_ids: itemIds, assignee_user_id: assigneeUserId }).then((r) => r.data),
  bulkStatus: (itemIds: string[], status: string, note?: string) =>
    api.post<unknown>('/api/admin/review-queue/bulk-status', { item_ids: itemIds, status, note }).then((r) => r.data),
  backfill: () => api.post<unknown>('/api/admin/review-queue/backfill').then((r) => r.data),
};

// Admin Ops Notifications API (admin-only)
export const adminNotificationsAPI = {
  list: (params?: {
    status?: string;
    severity?: string;
    notification_type?: string;
    country_code?: string;
    escalation_only?: boolean;
    open_only?: boolean;
    limit?: number;
    offset?: number;
  }) => api.get<{ items: unknown[]; total?: number }>('/api/admin/notifications', { params }).then((r) => r.data),
  getStats: () => api.get<unknown>('/api/admin/notifications/stats').then((r) => r.data),
  getFeed: (params?: { limit?: number; critical_first?: boolean }) =>
    api.get<unknown>('/api/admin/notifications/feed', { params }).then((r) => r.data),
  getOne: (id: string) => api.get<unknown>(`/api/admin/notifications/${id}`).then((r) => r.data),
  getEvents: (id: string, limit?: number) =>
    api.get<unknown>(`/api/admin/notifications/${id}/events`, { params: { limit } }).then((r) => r.data),
  acknowledge: (id: string) => api.post<unknown>(`/api/admin/notifications/${id}/acknowledge`).then((r) => r.data),
  resolve: (id: string, reason?: string) =>
    api.post<unknown>(`/api/admin/notifications/${id}/resolve`, null, { params: { reason } }).then((r) => r.data),
  suppress: (id: string, until?: string) =>
    api.post<unknown>(`/api/admin/notifications/${id}/suppress`, null, { params: { until } }).then((r) => r.data),
  reopen: (id: string, reason?: string) =>
    api.post<unknown>(`/api/admin/notifications/${id}/reopen`, null, { params: { reason } }).then((r) => r.data),
  recompute: () => api.post<unknown>('/api/admin/notifications/recompute').then((r) => r.data),
  sync: () => api.post<unknown>('/api/admin/notifications/sync').then((r) => r.data),
};

// Admin Ops Analytics API (admin-only)
export interface WorkflowFunnelStage {
  stage: string;
  label: string;
  count: number;
  /** null for the first stage (no previous to convert from). */
  conversion_from_prev_pct: number | null;
  conversion_from_start_pct: number;
}
export interface WorkflowFunnelResponse {
  period_days: number;
  since: string;
  stages: WorkflowFunnelStage[];
}
export interface AssistantTopicRow {
  topic: string;
  asked: number;
  supported: number;
  unsupported: number;
  refusal: number;
  support_rate_pct: number;
  refusal_rate_pct: number;
}
export interface AssistantTopicsResponse {
  period_days: number;
  since: string;
  overall: {
    asked: number;
    supported: number;
    unsupported: number;
    refusal: number;
    support_rate_pct: number;
    refusal_rate_pct: number;
  };
  topics: AssistantTopicRow[];
}

export const adminOpsAnalyticsAPI = {
  getSlaOverview: (params?: { country_code?: string; days?: number }) =>
    api.get<unknown>('/api/admin/ops/sla/overview', { params }).then((r) => r.data),
  getWorkflowOverview: (params?: { country_code?: string; days?: number }) =>
    // The aggregate event counts are nested under `events` (alongside period_days/rates).
    api.get<{ events?: { case_created?: number; rfq_created?: number; recommendations_generated?: number; quote_received?: number } }>(
      '/api/admin/workflow/overview',
      { params },
    ).then((r) => r.data),
  getQueueBacklog: (params?: { country_code?: string }) =>
    api.get<unknown>('/api/admin/ops/queue/backlog', { params }).then((r) => r.data),
  getQueueBreaches: (params?: { country_code?: string; limit?: number }) =>
    api.get<unknown>('/api/admin/ops/queue/breaches', { params }).then((r) => r.data),
  getReviewerWorkload: () => api.get<unknown>('/api/admin/ops/reviewers/workload').then((r) => r.data),
  getDestinations: () => api.get<unknown>('/api/admin/ops/destinations').then((r) => r.data),
  /** Top destinations selected by users across all relocation cases (request-driven, not ops backlog). */
  getTopDestinationsByRequest: (params?: { limit?: number }) =>
    api.get<unknown>('/api/admin/ops/destinations/requests', { params }).then((r) => r.data),
  getNotificationMetrics: (params?: { days?: number }) =>
    api.get<unknown>('/api/admin/ops/notifications', { params }).then((r) => r.data),
  getBottlenecks: () => api.get<unknown>('/api/admin/ops/bottlenecks').then((r) => r.data),
  /** AIQ-1439: workflow conversion funnel (per-stage counts + conversion %). */
  getWorkflowFunnel: (params?: { days?: number }) =>
    api.get<WorkflowFunnelResponse>('/api/admin/workflow/funnel', { params }).then((r) => r.data),
  /** AIQ-1438: policy-assistant questions ranked by canonical topic. */
  getAssistantTopics: (params?: { days?: number; limit?: number }) =>
    api.get<AssistantTopicsResponse>('/api/admin/workflow/assistant-topics', { params }).then((r) => r.data),
};

// Admin Marketing Analytics API (admin-only, pre-signup acquisition funnel)
export interface MarketingFunnel {
  period_days: number;
  events: { landing_page_view: number; landing_cta_click: number; lead_captured: number };
  rates: { cta_rate_pct: number; capture_rate_pct: number };
  daily: { date: string; landing_page_view: number; landing_cta_click: number; lead_captured: number }[];
}

export const adminMarketingAnalyticsAPI = {
  funnel: async (days = 30) =>
    api.get('/api/admin/marketing-analytics/funnel', { params: { days } }).then((r) => r.data as MarketingFunnel),
};

// Admin Collaboration API (admin-only, internal threads)
export const adminCollaborationAPI = {
  getThread: (targetType: string, targetId: string) =>
    api.get<unknown>('/api/admin/collaboration/threads/by-target', { params: { target_type: targetType, target_id: targetId } }).then((r) => r.data),
  getOrCreateThread: (targetType: string, targetId: string, title?: string) =>
    api.post<unknown>('/api/admin/collaboration/threads/by-target', null, {
      params: { target_type: targetType, target_id: targetId, title: title || undefined },
    }).then((r) => r.data),
  getSummary: (targetType: string, targetId: string) =>
    api.get<ThreadSummariesResult>('/api/admin/collaboration/threads/summary', { params: { target_type: targetType, target_id: targetId } }).then((r) => r.data),
  getSummariesBatch: (targets: { target_type: string; target_id: string }[]) =>
    api.post<ThreadSummariesResult>('/api/admin/collaboration/threads/summaries', { targets }).then((r) => r.data),
  getThreadById: (threadId: string) =>
    api.get<unknown>(`/api/admin/collaboration/threads/${threadId}`).then((r) => r.data),
  getComments: (threadId: string) =>
    api.get<unknown>(`/api/admin/collaboration/threads/${threadId}/comments`).then((r) => r.data),
  createComment: (threadId: string, body: string, parentCommentId?: string) =>
    api.post<unknown>(`/api/admin/collaboration/threads/${threadId}/comments`, { body, parent_comment_id: parentCommentId }).then((r) => r.data),
  editComment: (commentId: string, body: string) =>
    api.patch<unknown>(`/api/admin/collaboration/comments/${commentId}`, { body }).then((r) => r.data),
  deleteComment: (commentId: string) =>
    api.delete<unknown>(`/api/admin/collaboration/comments/${commentId}`).then((r) => r.data),
  resolveThread: (threadId: string, note?: string) =>
    api.post<unknown>(`/api/admin/collaboration/threads/${threadId}/resolve`, null, { params: { note } }).then((r) => r.data),
  reopenThread: (threadId: string) =>
    api.post<unknown>(`/api/admin/collaboration/threads/${threadId}/reopen`).then((r) => r.data),
  closeThread: (threadId: string) =>
    api.post<unknown>(`/api/admin/collaboration/threads/${threadId}/close`).then((r) => r.data),
  markRead: (threadId: string, lastCommentId?: string) =>
    api.post<unknown>(`/api/admin/collaboration/threads/${threadId}/read`, null, { params: { last_comment_id: lastCommentId } }).then((r) => r.data),
  getUnreadCount: () =>
    api.get<unknown>('/api/admin/collaboration/notifications/unread-count').then((r) => r.data),
};
