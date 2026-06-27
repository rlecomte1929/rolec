/**
 * Shared response/payload types for the API client (`api/client.ts`, `api/rpc.ts`).
 *
 * Convention (Epic B / client.ts typing): prefer an existing domain type in
 * `features/<domain>/types.ts` or `types/relopass-api-contracts.ts` when one matches.
 * Add a type here only when the shape is shared across multiple client methods and
 * has no existing home. One domain per slice; keep it minimal.
 */

/**
 * Error body returned by the FastAPI backend (`{ detail }`) and Supabase REST
 * (`{ message }` / `{ error }`). All fields optional — error bodies vary by source.
 */
export type ApiErrorBody = {
  detail?: string;
  message?: string;
  error?: string;
};

/**
 * Raw company-policy record + its benefit rules, as returned by the company-policy
 * CRUD endpoints (getLatest/getById/extract/saveBenefits). The entities are opaque to
 * the client — consumers cast `policy`/`benefits` to their own view types. Returned
 * shape is shared across those methods, so it lives here (Epic B decision 3).
 */
export type CompanyPolicyResult = {
  policy: unknown;
  benefits: unknown[];
  company_name?: string;
};

/** /api/services/context — services-flow context banner payload. */
export type ServiceContextResult = {
  assignment_id: string;
  case_id: string;
  case_context: { destCity?: string; destCountry?: string; originCity?: string; originCountry?: string };
  target_start_date?: string | null;
  services: Array<{ service_key: string; selected: boolean | number; [k: string]: unknown }>;
  answers: Array<{ service_key: string; answers: Record<string, unknown> }>;
  questions: unknown[];
  selected_services: string[];
};

/** /api/resources/country — legacy country-resources payload (rkg_resources). */
export type CountryResourcesResult = {
  profile: Record<string, unknown>;
  context?: Record<string, unknown>;
  hints: { priorities: string[]; recommendations: string[] };
  sections: Array<{ key: string; title: string; content: unknown }>;
  events?: unknown[];
  recommended?: unknown[];
  filters_applied: Record<string, unknown>;
};

/** /api/guidance/generate — generated guidance pack. */
export type GuidanceGenerateResult = {
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
};

/** /api/admin/collaboration/threads/summary|summaries — per-target comment summaries. */
export type ThreadSummariesResult = {
  summaries?: Record<string, { comment_count: number; last_comment_at?: string; status?: string; is_unread?: boolean }>;
};

/** /api/hr/policy-documents/health — storage + table health probe. */
export type PolicyDocumentsHealth = {
  supabase_url_present: boolean;
  service_role_present: boolean;
  bucket_name: string;
  bucket_access_ok: boolean;
  policy_documents_table_ok: boolean;
  policy_document_clauses_table_ok: boolean;
  policy_versions_table_ok: boolean;
  resolved_assignment_policies_table_ok: boolean;
};

/** /api/hr/policy-documents/{id}/normalize — normalization outcome + readiness. */
export type PolicyNormalizeResult = {
  ok?: boolean;
  normalized?: boolean;
  publishable?: boolean;
  published?: boolean;
  outcome?: string;
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
};
