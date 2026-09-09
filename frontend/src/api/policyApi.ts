import type { NormalizedPolicyResponse, PolicyDocument, PolicyDocumentClause, CompanyPolicySummary } from '../features/policy/types';
import { logger } from '../lib/logger';
import { api } from './client';
import type {
  CompanyPolicyResult,
  PolicyDocumentsHealth,
  PolicyNormalizeResult,
} from './types';

// [AIQ-2090] `hrPolicyAPI` was REMOVED with the legacy /api/hr/policies endpoints it
// wrapped. Those had no ownership check on get/update/delete by id, so any HR user could
// read, overwrite or delete another company's policy given its id. Its only consumer,
// HrPolicyManagement.tsx, was not mounted — /hr/policy-management <Navigate>s to
// /hr/policy — and hr_policies holds 0 rows in production.
//
// The live policy stack is policyConfigAPI (/api/hr/policy-config/*), below.

/** Structured Compensation & Allowance matrix (policy_configs / versions / benefits). */
// [AIQ-1615] Shared in-flight guard: the Policy Builder "Publish" and the Published-policy
// tab "Publish draft" both POST /api/hr/policy-config/publish on the same config-matrix.
// Two clicks raced to a server 409 Conflict and a stuck "Publishing…" spinner. De-dupe so a
// concurrent publish shares the first request's promise instead of firing a competing one.
let _hrPublishInFlight: Promise<Record<string, unknown>> | null = null;

export const policyConfigMatrixAPI = {
  hrGet: async (companyId?: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>('/api/hr/policy-config', {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },
  hrPostDraft: async (companyId?: string): Promise<Record<string, unknown>> => {
    const response = await api.post<Record<string, unknown>>('/api/hr/policy-config/draft', {}, {
      params: companyId ? { companyId } : {},
      // Seeding/cloning a draft writes the full benefit matrix (~90 rows for a
      // multi-tier policy) — override the 12s default per the B13 convention.
      timeout: 120_000,
    });
    return response.data;
  },
  hrPutDraft: async (body: Record<string, unknown>, companyId?: string): Promise<Record<string, unknown>> => {
    const response = await api.put<Record<string, unknown>>('/api/hr/policy-config/draft', body, {
      params: companyId ? { companyId } : {},
      // Destructive replace of the whole matrix (~90 rows + audit rows) can
      // exceed the 12s default; override per the B13 convention.
      timeout: 120_000,
    });
    return response.data;
  },
  /**
   * AIQ-1415 — Natural-Language Policy Builder. Read-only: turns a free-text
   * policy description into a CANDIDATE config-matrix `categories` body for
   * confirm-before-save. Never persists — saving goes through hrPutDraft after
   * the HR user approves the preview. An LLM call can exceed the 12s default.
   */
  hrGenerate: async (text: string, companyId?: string): Promise<Record<string, unknown>> => {
    const response = await api.post<Record<string, unknown>>('/api/hr/policy-config/generate', { text }, {
      params: companyId ? { companyId } : {},
      timeout: 120_000,
    });
    return response.data;
  },
  hrPublish: async (body: Record<string, unknown> | undefined, companyId?: string): Promise<Record<string, unknown>> => {
    // [AIQ-1615] Concurrent publishes share one request (see _hrPublishInFlight) so the two
    // publish controls can't race to a 409.
    if (_hrPublishInFlight) return _hrPublishInFlight;
    _hrPublishInFlight = api
      .post<Record<string, unknown>>('/api/hr/policy-config/publish', body ?? {}, {
        params: companyId ? { companyId } : {},
        // Publish also rebuilds the RAG index (OpenAI embeddings over all chunks),
        // which can take well over 12s; override per the B13 convention.
        timeout: 120_000,
      })
      .then((response) => response.data)
      .finally(() => {
        _hrPublishInFlight = null;
      });
    return _hrPublishInFlight;
  },
  hrHistory: async (companyId?: string): Promise<{ versions: unknown[] }> => {
    const response = await api.get<{ versions: unknown[] }>('/api/hr/policy-config/history', {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },
  hrPublished: async (companyId?: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>('/api/hr/policy-config/published', {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },
  hrGetVersion: async (versionId: string, companyId?: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>(`/api/hr/policy-config/versions/${encodeURIComponent(versionId)}`, {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },
  /**
   * List admin-curated starter templates. Metadata only
   * — { templates: [{ key, label, description }] }.
   */
  hrListTemplates: async (): Promise<{ templates: Array<{ key: string; label: string; description: string }> }> => {
    const response = await api.get<{ templates: Array<{ key: string; label: string; description: string }> }>('/api/hr/policy-config/templates');
    return response.data;
  },
  /**
   * Apply a starter template to the company's draft. Body:
   *   { template_key, replace_existing_draft? }
   * On success returns the fresh working payload. On 409
   * ("draft_has_rows") the UI should offer to retry with
   * replace_existing_draft=true.
   */
  hrApplyTemplate: async (
    body: { template_key: string; replace_existing_draft?: boolean },
    companyId?: string
  ): Promise<Record<string, unknown>> => {
    const response = await api.post<Record<string, unknown>>('/api/hr/policy-config/draft/apply-template', body, {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },
  /**
   * Draft-vs-Live snapshot for the HR Policy "Draft vs Live" section.
   * Returns {live, draft, diff: {added, removed, changed, unchanged_count, summary}}.
   */
  hrDiff: async (companyId?: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>('/api/hr/policy-config/diff', {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },
  /**
   * Revert one benefit row of the current draft back to the live version.
   * Body: { benefit_key, targeting_signature }. Returns the refreshed diff.
   */
  hrRevertRow: async (
    body: { benefit_key: string; targeting_signature: string },
    companyId?: string
  ): Promise<Record<string, unknown>> => {
    const response = await api.post<Record<string, unknown>>('/api/hr/policy-config/draft/revert-row', body, {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },

  /**
   * Import an uploaded policy document's LLM-extracted benefits into the
   * company's config-matrix draft as `extracted_llm` rows (AIQ-873 bridge).
   * Body: { policy_id } — the policy_documents id returned by the upload flow.
   * Existing manual/template/extracted rows are never clobbered. Returns the
   * imported matrix keys, keys skipped as already-present, and extraction keys
   * that had no canonical mapping (for manual entry).
   */
  hrImportExtraction: async (
    body: { policy_id: string },
    companyId?: string
  ): Promise<{ imported: string[]; skipped_existing: string[]; unmapped: string[]; version_id: string }> => {
    const response = await api.post<{ imported: string[]; skipped_existing: string[]; unmapped: string[]; version_id: string }>(
      '/api/hr/policy-config/draft/import-extraction',
      body,
      {
        params: companyId ? { companyId } : {},
        // Merging the extracted matrix rewrites the draft row set; override the
        // 12s default per the B13 convention (same as hrPutDraft/hrPublish).
        timeout: 120_000,
      },
    );
    return response.data;
  },

  adminGet: async (companyId: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>('/api/admin/policy-config', { params: { companyId } });
    return response.data;
  },
  /**
   * POST /api/admin/policy-config/draft — ensures a company draft (idempotent if draft exists).
   * Backend clones from latest published when present, otherwise seeds canonical rows.
   * (Product names like “clone published” / “create empty” map to this single route today.)
   */
  adminPostDraft: async (companyId: string): Promise<Record<string, unknown>> => {
    const response = await api.post<Record<string, unknown>>('/api/admin/policy-config/draft', {}, { params: { companyId } });
    return response.data;
  },
  adminPutDraft: async (companyId: string, body: Record<string, unknown>): Promise<Record<string, unknown>> => {
    const response = await api.put<Record<string, unknown>>('/api/admin/policy-config/draft', body, { params: { companyId } });
    return response.data;
  },
  adminPublish: async (companyId: string, body?: Record<string, unknown>): Promise<Record<string, unknown>> => {
    const response = await api.post<Record<string, unknown>>('/api/admin/policy-config/publish', body ?? {}, { params: { companyId } });
    return response.data;
  },
  adminHistory: async (companyId: string): Promise<{ versions: unknown[] }> => {
    const response = await api.get<{ versions: unknown[] }>('/api/admin/policy-config/history', { params: { companyId } });
    return response.data;
  },
  adminPublished: async (companyId: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>('/api/admin/policy-config/published', { params: { companyId } });
    return response.data;
  },
  adminGetVersion: async (companyId: string, versionId: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>(`/api/admin/policy-config/versions/${encodeURIComponent(versionId)}`, {
      params: { companyId },
    });
    return response.data;
  },

  employeeGet: async (params?: {
    assignmentId?: string;
    caseId?: string;
    assignmentType?: string;
    familyStatus?: string;
  }): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>('/api/employee/policy-config', {
      params: {
        assignmentId: params?.assignmentId,
        caseId: params?.caseId,
        assignmentType: params?.assignmentType,
        familyStatus: params?.familyStatus,
      },
    });
    return response.data;
  },

  /** HR / Admin: compare provider monetary estimates to published normalized caps. */
  hrCompareProviderEstimates: async (
    body: {
      assignment_type?: string;
      family_status?: string;
      estimates: Array<{ benefit_key: string; amount: number; currency: string }>;
    },
    companyId?: string
  ): Promise<{ metadata?: Record<string, unknown>; results: unknown[] }> => {
    const response = await api.post<{ metadata?: Record<string, unknown>; results: unknown[] }>('/api/hr/policy-config/caps/compare', body, {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },
};

export const companyPolicyAPI = {
  list: async (params?: { company_id?: string }): Promise<{ policies: CompanyPolicySummary[] }> => {
    const response = await api.get<{ policies: CompanyPolicySummary[] }>('/api/company-policies', { params });
    return response.data;
  },
  getLatest: async (): Promise<CompanyPolicyResult> => {
    const response = await api.get<CompanyPolicyResult>('/api/company-policies/latest');
    return response.data;
  },
  getById: async (policyId: string): Promise<CompanyPolicyResult> => {
    const response = await api.get<CompanyPolicyResult>(`/api/company-policies/${policyId}`);
    return response.data;
  },
  getDownloadUrl: async (policyId: string): Promise<{ ok?: boolean; url?: string }> => {
    const response = await api.get<{ ok?: boolean; url?: string }>(`/api/company-policies/${policyId}/download-url`);
    return response.data;
  },
  upload: async (file: File, meta: { title: string; version?: string; effective_date?: string }): Promise<{ policy: unknown }> => {
    const form = new FormData();
    form.append('file', file);
    form.append('title', meta.title);
    if (meta.version) form.append('version', meta.version);
    if (meta.effective_date) form.append('effective_date', meta.effective_date);
    const response = await api.post<{ policy: unknown }>('/api/company-policies/upload', form, { timeout: 120_000 });
    return response.data;
  },
  extract: async (policyId: string): Promise<CompanyPolicyResult> => {
    const response = await api.post<CompanyPolicyResult>(`/api/policies/${policyId}/extract`, undefined, { timeout: 120_000 });
    return response.data;
  },
  saveBenefits: async (policyId: string, benefits: unknown[]): Promise<CompanyPolicyResult> => {
    const response = await api.put<CompanyPolicyResult>(`/api/company-policies/${policyId}/benefits`, { benefits });
    return response.data;
  },
  getNormalized: async (
    policyId: string,
    opts?: { detail?: 'full' | 'summary'; includeReadiness?: boolean }
  ): Promise<NormalizedPolicyResponse> => {
    const params: Record<string, string | boolean> = {};
    if (opts?.detail === 'summary') params.detail = 'summary';
    if (opts?.includeReadiness === false) params.include_readiness = 'false';
    const response = await api.get<NormalizedPolicyResponse>(`/api/company-policies/${policyId}/normalized`, {
      params: Object.keys(params).length ? params : undefined,
    });
    return response.data;
  },
  patchBenefitRule: async (
    policyId: string,
    benefitRuleId: string,
    body: {
      amount_value?: number;
      amount_unit?: string;
      currency?: string;
      frequency?: string;
      description?: string;
      review_status?: string;
      benefit_key?: string;
      metadata_json?: Record<string, unknown>;
    }
  ): Promise<{ benefit_rule: unknown }> => {
    const response = await api.patch<{ benefit_rule: unknown }>(`/api/company-policies/${policyId}/benefits/${benefitRuleId}`, body);
    return response.data;
  },
  /** HR override layer — does not change extracted Layer-2 rows; adjusts effective entitlements. */
  patchHrBenefitOverride: async (
    policyId: string,
    versionId: string,
    benefitRuleId: string,
    body: {
      service_visibility?: 'force_included' | 'force_excluded' | null;
      amount_value_override?: number | null;
      amount_unit_override?: string | null;
      currency_override?: string | null;
      duration_quantity_json?: { quantity?: number; unit?: string } | null;
      approval_required_override?: boolean | null;
      hr_notes?: string | null;
    }
  ): Promise<{ hr_override: unknown }> => {
    const response = await api.patch<{ hr_override: unknown }>(
      `/api/company-policies/${policyId}/versions/${versionId}/benefits/${benefitRuleId}/hr-override`,
      body
    );
    return response.data;
  },
  deleteHrBenefitOverride: async (
    policyId: string,
    versionId: string,
    benefitRuleId: string
  ): Promise<{ ok?: boolean }> => {
    const response = await api.delete<{ ok?: boolean }>(
      `/api/company-policies/${policyId}/versions/${versionId}/benefits/${benefitRuleId}/hr-override`
    );
    return response.data;
  },
  patchVersionStatus: async (
    policyId: string,
    versionId: string,
    body: { status: string }
  ): Promise<{ version: unknown }> => {
    const response = await api.patch<{ version: unknown }>(`/api/company-policies/${policyId}/versions/${versionId}/status`, body);
    return response.data;
  },
  /** Update latest version status - avoids version_id mismatch 404s */
  patchLatestVersionStatus: async (policyId: string, body: { status: string }): Promise<{ version: unknown }> => {
    const response = await api.patch<{ version: unknown }>(`/api/company-policies/${policyId}/versions/latest/status`, body);
    return response.data;
  },
  publishVersion: async (policyId: string, versionId: string): Promise<{ version: unknown }> => {
    const response = await api.post<{ version: unknown }>(`/api/company-policies/${policyId}/versions/${versionId}/publish`);
    return response.data;
  },
  /**
   * Archive a live (published) version. Employees stop seeing its benefits
   * immediately; the row stays queryable for audit history. HR can then
   * import a new document or start from a template, review, and publish
   * a fresh version.
   * Returns `{ version, already }`. When `already` is a non-null string
   * the version was not in "published" status — the call was a no-op.
   */
  unpublishVersion: async (
    policyId: string,
    versionId: string
  ): Promise<{ version: unknown; already: string | null }> => {
    const response = await api.post<{ version: unknown; already: string | null }>(`/api/company-policies/${policyId}/versions/${versionId}/unpublish`);
    return response.data;
  },
  /**
   * Canonical (document-normalized) policy diff for a company — sibling
   * of policyConfigMatrixAPI.hrDiff which covers the compensation
   * matrix. Auto-resolves the primary policy_id server-side; returns
   * has_policy=false when the company hasn't uploaded a canonical
   * policy yet (frontend renders a neutral empty state in that case).
   */
  hrCanonicalDiffForCompany: async (
    companyId?: string
  ): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>('/api/hr/canonical-policy/diff', {
      params: companyId ? { companyId } : {},
    });
    return response.data;
  },
  /** Publish latest version - avoids version_id mismatch 404s */
  publishLatestVersion: async (policyId: string): Promise<{ version: unknown }> => {
    const response = await api.post<{ version: unknown }>(`/api/company-policies/${policyId}/versions/latest/publish`);
    return response.data;
  },
  patchExclusion: async (
    policyId: string,
    exclId: string,
    body: { description?: string; review_status?: string }
  ): Promise<{ exclusion: unknown }> => {
    const response = await api.patch<{ exclusion: unknown }>(`/api/company-policies/${policyId}/exclusions/${exclId}`, body);
    return response.data;
  },
  patchCondition: async (
    policyId: string,
    condId: string,
    body: { condition_value_json?: Record<string, unknown>; review_status?: string }
  ): Promise<{ condition: unknown }> => {
    const response = await api.patch<{ condition: unknown }>(`/api/company-policies/${policyId}/conditions/${condId}`, body);
    return response.data;
  },
  /** Platform starter baseline (only when company has no policy yet). */
  initializeFromTemplate: async (body: {
    template_key: string;
    comparison_ready_structure?: boolean;
  }): Promise<{
    ok?: boolean;
    policy_id?: string;
    policy_version_id?: string;
    version_status?: string;
    benefit_rules_created?: number;
    message?: string;
  }> => {
    const response = await api.post<{ ok?: boolean; policy_id?: string; policy_version_id?: string; version_status?: string; benefit_rules_created?: number; message?: string }>('/api/hr/company-policy/initialize-from-template', body);
    return response.data;
  },
};

/** HR aggregate review payload (document + policy + draft + readiness). */
export const hrPolicyReviewAPI = {
  get: async (params: { document_id?: string; policy_id?: string }): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>('/api/hr/policy-review', { params });
    return response.data;
  },
};

/** Policy document intake: upload PDF/DOCX, classify before extraction */
export const policyDocumentsAPI = {
  health: async (): Promise<{
    supabase_url_present: boolean;
    service_role_present: boolean;
    bucket_name: string;
    bucket_access_ok: boolean;
    policy_documents_table_ok: boolean;
    policy_document_clauses_table_ok: boolean;
    policy_versions_table_ok: boolean;
    resolved_assignment_policies_table_ok: boolean;
  }> => {
    const response = await api.get<PolicyDocumentsHealth>('/api/hr/policy-documents/health');
    return response.data;
  },
  list: async (params?: { company_id?: string }): Promise<{ documents: PolicyDocument[] }> => {
    const response = await api.get<{ documents: PolicyDocument[] }>('/api/hr/policy-documents', { params });
    return response.data;
  },
  get: async (docId: string): Promise<{ document: PolicyDocument }> => {
    const response = await api.get<{ document: PolicyDocument }>(`/api/hr/policy-documents/${docId}`);
    return response.data;
  },
  upload: async (file: File, companyId?: string | null): Promise<{ ok: boolean; document: PolicyDocument; error_code?: string; message?: string; request_id?: string; processing_queued?: boolean }> => {
    // Backend expects field name "file". When admin is viewing a company's policy workspace, pass company_id so the doc is stored for that company.
    const form = new FormData();
    form.append('file', file);
    const params = companyId && companyId.trim() ? { company_id: companyId.trim() } : undefined;
    if (import.meta.env.DEV) {
      logger.info('policy upload selected file', {
        name: file?.name,
        size: file?.size,
        type: file?.type,
        isFile: file instanceof File,
        companyId: companyId ?? undefined,
      });
      logger.info('policy upload form keys', [...form.keys()]);
    }
    const response = await api.post<{ ok: boolean; document: PolicyDocument; error_code?: string; message?: string; request_id?: string; processing_queued?: boolean }>('/api/hr/policy-documents/upload', form, { params, timeout: 120_000 });
    return response.data;
  },
  reprocess: async (docId: string): Promise<{ document: PolicyDocument }> => {
    const response = await api.post<{ document: PolicyDocument }>(`/api/hr/policy-documents/${docId}/reprocess`, undefined, { timeout: 120_000 });
    return response.data;
  },
  listClauses: async (docId: string, clauseType?: string): Promise<{ clauses: PolicyDocumentClause[] }> => {
    const params = clauseType ? { clause_type: clauseType } : {};
    const response = await api.get<{ clauses: PolicyDocumentClause[] }>(`/api/hr/policy-documents/${docId}/clauses`, { params });
    return response.data;
  },
  getClause: async (docId: string, clauseId: string): Promise<{ clause: PolicyDocumentClause }> => {
    const response = await api.get<{ clause: PolicyDocumentClause }>(`/api/hr/policy-documents/${docId}/clauses/${clauseId}`);
    return response.data;
  },
  patchClause: async (
    docId: string,
    clauseId: string,
    body: { clause_type?: string; title?: string; hr_override_notes?: string }
  ): Promise<{ clause: PolicyDocumentClause }> => {
    const response = await api.patch<{ clause: PolicyDocumentClause }>(
      `/api/hr/policy-documents/${docId}/clauses/${clauseId}`,
      body
    );
    return response.data;
  },
  normalize: async (
    docId: string
  ): Promise<{
    ok?: boolean;
    normalized?: boolean;
    publishable?: boolean;
    published?: boolean;
    outcome?: string;
    /** Stable semantic code for success path (draft-only, published, publish blocked). */
    normalization_result_code?: string;
    readiness_status?: string;
    readiness_issues?: Array<Record<string, unknown>>;
    publish_block_code?: string;
    publish_block_detail?: string;
    comparison_readiness_code?: string;
    rule_candidates_summary?: {
      benefit_rules?: number;
      exclusions?: number;
      evidence_requirements?: number;
      conditions?: number;
      draft_rule_candidates?: number;
    };
    policy_id: string;
    policy_version_id: string;
    summary: unknown;
    version?: Record<string, unknown>;
    input_repairs?: Array<Record<string, string>>;
    policy_readiness?: {
      normalization_readiness?: { status?: string; issues?: Array<Record<string, unknown>> };
      publish_readiness?: { status?: string; issues?: Array<Record<string, unknown>> };
      comparison_readiness?: { status?: string; issues?: Array<Record<string, unknown>> };
    };
    normalization_draft?: Record<string, unknown> | null;
  }> => {
    const response = await api.post<PolicyNormalizeResult>(`/api/hr/policy-documents/${docId}/normalize`, undefined, { timeout: 120_000 });
    return response.data;
  },
  bulkDelete: async (documentIds: string[]): Promise<{ ok: boolean; deleted: number; skipped?: Array<{ id: string; reason: string }> }> => {
    const response = await api.post<{ ok: boolean; deleted: number; skipped?: Array<{ id: string; reason: string }> }>('/api/hr/policy-documents/bulk-delete', { document_ids: documentIds });
    return response.data;
  },
};
