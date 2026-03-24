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
}

export interface EmployeePolicyAssistantQueryResponse {
  ok: boolean;
  assignment_id: string;
  request_id?: string | null;
  answer: PolicyAssistantAnswer;
}

export interface HrPolicyAssistantQueryResponse {
  ok: boolean;
  policy_id: string;
  document_id?: string | null;
  request_id?: string | null;
  answer: PolicyAssistantAnswer;
}
