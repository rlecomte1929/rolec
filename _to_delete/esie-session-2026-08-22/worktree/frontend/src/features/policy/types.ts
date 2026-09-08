/**
 * Shared types for the document-normalized HR policy subsystem (company_policies +
 * policy_documents), as opposed to the policy_config compensation matrix
 * (see policy-config/types.ts — a different subsystem; do not conflate).
 *
 * These mirror the shapes the HR policy-review surfaces actually read off the
 * API; introduced to drain the @typescript-eslint/no-unsafe-* backlog by typing
 * the API boundary instead of consuming `any` (LINT-3 / API-typing).
 */

/** Open-ended per-rule JSON blob — read via the dynamic meta() helper, so it stays loose. */
export type BenefitRuleMeta = Record<string, unknown>;

export interface NormalizedBenefitRule {
  id?: string;
  benefit_category?: string | null;
  benefit_key?: string | null;
  amount_value?: number | string | null;
  amount_unit?: string | null;
  currency?: string | null;
  description?: string | null;
  confidence?: number | null;
  auto_generated?: boolean | null;
  metadata_json?: BenefitRuleMeta | null;
}

export interface NormalizedExclusion {
  id: string;
  benefit_key?: string | null;
  description?: string | null;
  raw_text?: string | null;
}

export interface NormalizedEvidenceRequirement {
  id: string;
  evidence_items_json?: unknown[] | null;
}

export interface PolicySourceLink {
  object_type?: string;
  object_id?: string;
  clause_id?: string;
  source_page_start?: number | null;
  source_page_end?: number | null;
}

export interface PolicyVersionSummary {
  id?: string;
  version_number?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
  status?: string | null;
  source_policy_document_id?: string | null;
}

export interface NormalizedPolicySummary {
  id?: string;
  title?: string | null;
  status?: string | null;
}

export interface PolicyReadinessTier {
  status?: string;
  issues?: Array<{ code?: string; message?: string; field?: string }>;
}

/** Return shape of companyPolicyAPI.getNormalized. */
export interface NormalizedPolicyResponse {
  policy: NormalizedPolicySummary;
  version: PolicyVersionSummary;
  benefit_rules: NormalizedBenefitRule[];
  exclusions: NormalizedExclusion[];
  evidence_requirements: NormalizedEvidenceRequirement[];
  conditions: unknown[];
  assignment_applicability: unknown[];
  family_applicability: unknown[];
  source_links: PolicySourceLink[];
  published_version?: PolicyVersionSummary;
  published_comparison_readiness?: {
    comparison_ready?: boolean;
    comparison_blockers?: string[];
  };
  policy_readiness?: {
    normalization_readiness?: PolicyReadinessTier;
    publish_readiness?: PolicyReadinessTier;
    comparison_readiness?: PolicyReadinessTier;
  };
  normalization_draft?: Record<string, unknown> | null;
  detail?: string;
  // Tolerated by the loose resolvers (resolveHrPolicyWorkspaceState etc.) that take
  // Record<string, unknown>; the explicit fields above still type-check.
  [key: string]: unknown;
}

export interface PolicyDocumentClause {
  id: string;
  section_label?: string | null;
  section_path?: string | null;
  confidence?: number | null;
  clause_type?: string | null;
  source_page_start?: number | null;
  source_page_end?: number | null;
  title?: string | null;
  raw_text?: string | null;
  normalized_hint_json?: Record<string, unknown> | null;
  hr_override_notes?: string | null;
}

export interface PolicyDocument {
  id: string;
  processing_status?: string | null;
  /**
   * Assistant-import pipeline status: extracting_text → classified (or failed).
   * Read alongside `processing_status` (which reaches `normalized` once LLM
   * value-extraction persists benefits) to know when an upload is ready to import.
   */
  assistant_import_status?: string | null;
  filename?: string | null;
  detected_document_type?: string | null;
  detected_policy_scope?: string | null;
  uploaded_at?: string | null;
  extraction_error?: string | null;
  extracted_metadata?: Record<string, unknown> | null;
  raw_text?: string | null;
}

export interface CompanyPolicySummary {
  id: string;
  title?: string | null;
}
