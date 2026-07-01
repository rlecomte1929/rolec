/**
 * AIQ-833 / F2 — adapt the constrained RAG engine response
 * (POST /api/policy-assistant/rag-query) into the rich PolicyAssistantAnswer
 * shape the HR + employee panels already render.
 *
 * The RAG engine returns a flat payload; the panels consume the legacy
 * deterministic-engine shape `{ ok, request_id, answer: { ... } }`. Mapping at
 * the client boundary keeps every component, type, and existing test unchanged
 * while users get grounded, cited, refusal-capable answers.
 */
import type {
  EmployeePolicyAssistantQueryResponse,
  HrPolicyAssistantQueryResponse,
  PolicyAssistantAnswer,
  PolicyAssistantCitedChunk,
  PolicyAssistantEvidenceItem,
} from '../types/policyAssistant';

/** Answer-grounding classes the RAG engine emits (policy_assistant_rag_engine.py). */
export type RagAnswerKind =
  | 'answer'
  | 'refusal_out_of_policy'
  | 'refusal_validation_failed';

/** Flat response shape of POST /api/policy-assistant/rag-query. */
export interface RagQueryResponse {
  answer_text: string;
  answer_kind: RagAnswerKind;
  cited_chunks?: PolicyAssistantCitedChunk[] | null;
  model?: string | null;
  cost_usd?: number | null;
  audit_id?: string | null;
  /** Primary key of the policy_assistant_traces row. Used by the end-user
   *  helpfulness control (POST /api/policy-assistant/helpfulness). */
  trace_session_id?: string | null;
}

/**
 * Derive the "Source reference" evidence list from the cited chunks. The RAG
 * `cited_chunks` shape already matches PolicyAssistantCitedChunk; `source_ref`
 * doubles as the deep-link target the evidence renderer scrolls to.
 */
function citedChunksToEvidence(
  chunks: PolicyAssistantCitedChunk[]
): PolicyAssistantEvidenceItem[] {
  return chunks.map((c) => ({
    kind: c.source_type,
    label: c.source_ref,
    reference: c.source_ref,
    excerpt: c.chunk_text,
    source: null,
    section_ref: null,
    policy_source_type: c.source_type,
  }));
}

/** Map a flat RAG payload to a PolicyAssistantAnswer for the given role. */
export function ragResponseToAnswer(
  rag: RagQueryResponse,
  roleScope: 'hr' | 'employee'
): PolicyAssistantAnswer {
  const isRefusal = rag.answer_kind !== 'answer';
  const citedChunks = rag.cited_chunks ?? [];

  if (isRefusal) {
    return {
      answer_type: 'refusal',
      answer_text: '',
      policy_status: 'unknown',
      comparison_readiness: 'not_applicable',
      evidence: [],
      conditions: [],
      approval_required: false,
      follow_up_options: [],
      refusal: {
        refusal_code: rag.answer_kind,
        refusal_text: rag.answer_text,
        supported_examples: [],
      },
      role_scope: roleScope,
      canonical_topic: null,
      detected_intent: null,
      cited_chunks: [],
      trace_session_id: rag.trace_session_id ?? null,
    };
  }

  return {
    // 'status_summary' renders as the neutral "Policy information" badge — the
    // RAG engine produces a grounded narrative, not a structured entitlement
    // determination, so we deliberately avoid the "Included"/"Excluded" verdict.
    answer_type: 'status_summary',
    answer_text: rag.answer_text,
    policy_status: 'published',
    comparison_readiness: 'not_applicable',
    evidence: citedChunksToEvidence(citedChunks),
    conditions: [],
    approval_required: false,
    follow_up_options: [],
    refusal: null,
    role_scope: roleScope,
    canonical_topic: null,
    detected_intent: null,
    cited_chunks: citedChunks,
    trace_session_id: rag.trace_session_id ?? null,
  };
}

export function ragResponseToHrResponse(
  rag: RagQueryResponse,
  policyId: string,
  documentId?: string | null
): HrPolicyAssistantQueryResponse {
  return {
    ok: true,
    policy_id: policyId,
    document_id: documentId ?? null,
    request_id: rag.audit_id ?? null,
    answer: ragResponseToAnswer(rag, 'hr'),
  };
}

export function ragResponseToEmployeeResponse(
  rag: RagQueryResponse,
  assignmentId: string
): EmployeePolicyAssistantQueryResponse {
  return {
    ok: true,
    assignment_id: assignmentId,
    request_id: rag.audit_id ?? null,
    trace_session_id: rag.trace_session_id ?? null,
    answer: ragResponseToAnswer(rag, 'employee'),
  };
}
