/**
 * Policy assistant API contracts — employee and HR endpoints share the same `answer` shape.
 */

export type PolicyAssistantAnswerType =
  | 'entitlement_summary'
  | 'comparison_summary'
  | 'status_summary'
  | 'draft_published_summary'
  | 'clarification_needed'
  | 'refusal';

export type PolicyAssistantComparisonReadiness =
  | 'comparison_ready'
  | 'informational_only'
  | 'external_reference_partial'
  | 'review_required'
  | 'deterministic_non_budget'
  | 'not_applicable';

export type PolicyAssistantPolicyStatus =
  | 'published'
  | 'draft'
  | 'draft_and_published'
  | 'no_policy_bound'
  | 'unknown';

export interface PolicyAssistantEvidenceItem {
  kind: string;
  label?: string | null;
  reference?: string | null;
  excerpt?: string | null;
  source?: string | null;
  section_ref?: string | null;
  policy_source_type?: string | null;
}

export interface PolicyAssistantConditionItem {
  text: string;
  kind?: string | null;
}

export interface PolicyAssistantFollowUpOption {
  intent: string;
  label: string;
  query_hint?: string | null;
}

export interface PolicyAssistantRefusal {
  refusal_code: string;
  refusal_text: string;
  supported_examples: string[];
}

/**
 * Source chunk cited inline in `answer_text` via `[chunk:<id>]`. Returned
 * by the RAG engine (Sprint A/B/C). Optional on PolicyAssistantAnswer so
 * legacy engine outputs (which don't produce chunk citations) still type-
 * check; renderers that want clickable chips check for this and fall
 * back to plain text when absent.
 */
export interface PolicyAssistantCitedChunk {
  id: string;
  /** e.g. "matrix_benefit", "matrix_override" */
  source_type: string;
  /** e.g. "policy_config_benefits.b1" — used to scroll to the matching DOM row. */
  source_ref: string;
  /** Full chunk text — shown in the chip's tooltip / expanded preview. */
  chunk_text: string;
}

export interface PolicyAssistantAnswer {
  answer_type: PolicyAssistantAnswerType;
  canonical_topic?: string | null;
  answer_text: string;
  policy_status: PolicyAssistantPolicyStatus;
  comparison_readiness: PolicyAssistantComparisonReadiness;
  evidence: PolicyAssistantEvidenceItem[];
  conditions: PolicyAssistantConditionItem[];
  approval_required: boolean;
  follow_up_options: PolicyAssistantFollowUpOption[];
  refusal?: PolicyAssistantRefusal | null;
  role_scope: string;
  detected_intent?: string | null;
  /** RAG engine output — present when the answer was grounded in
   *  retrieved chunks. Renderers turn `[chunk:<id>]` tokens in
   *  `answer_text` into clickable chips that look these up. */
  cited_chunks?: PolicyAssistantCitedChunk[];
  /** Trace row id for the end-user helpfulness vote control (👍/👎).
   *  Populated by the RAG engine; absent on legacy deterministic answers. */
  trace_session_id?: string | null;
}

export interface EmployeePolicyAssistantQueryResponse {
  ok: boolean;
  assignment_id: string;
  request_id?: string | null;
  /** Trace row id for the end-user helpfulness vote control. */
  trace_session_id?: string | null;
  answer: PolicyAssistantAnswer;
}

export interface HrPolicyAssistantQueryResponse {
  ok: boolean;
  policy_id: string;
  document_id?: string | null;
  request_id?: string | null;
  answer: PolicyAssistantAnswer;
}
