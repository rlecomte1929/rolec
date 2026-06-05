import { describe, expect, it } from 'vitest';
import {
  ragResponseToAnswer,
  ragResponseToEmployeeResponse,
  ragResponseToHrResponse,
  type RagQueryResponse,
} from '../policyAssistantRagAdapter';

const CITED = [
  { id: 'c1', source_type: 'matrix_benefit', source_ref: 'policy_config_benefits.b1', chunk_text: 'Housing cap is 2000 EUR/mo.' },
];

const ANSWER: RagQueryResponse = {
  answer_text: 'Your housing allowance is 2000 EUR/month [chunk:c1].',
  answer_kind: 'answer',
  cited_chunks: CITED,
  model: 'claude',
  cost_usd: 0.0001,
  audit_id: 'audit-123',
};

const REFUSAL: RagQueryResponse = {
  answer_text: "I don't see this in your company's policy. Check with your HR team.",
  answer_kind: 'refusal_out_of_policy',
  cited_chunks: [],
  audit_id: 'audit-456',
};

describe('ragResponseToAnswer — grounded answer', () => {
  it('passes cited_chunks through for inline citation rendering', () => {
    const a = ragResponseToAnswer(ANSWER, 'hr');
    expect(a.answer_type).toBe('status_summary');
    expect(a.answer_text).toContain('[chunk:c1]');
    expect(a.cited_chunks).toEqual(CITED);
    expect(a.refusal).toBeNull();
    expect(a.role_scope).toBe('hr');
  });

  it('derives the Source reference evidence list from cited chunks', () => {
    const a = ragResponseToAnswer(ANSWER, 'employee');
    expect(a.evidence).toHaveLength(1);
    expect(a.evidence[0]).toMatchObject({
      label: 'policy_config_benefits.b1',
      reference: 'policy_config_benefits.b1', // deep-link scroll target
      excerpt: 'Housing cap is 2000 EUR/mo.',
      policy_source_type: 'matrix_benefit',
    });
  });
});

describe('ragResponseToAnswer — refusal', () => {
  it('maps the refusal copy into answer.refusal and flags answer_type refusal', () => {
    const a = ragResponseToAnswer(REFUSAL, 'hr');
    expect(a.answer_type).toBe('refusal');
    expect(a.refusal?.refusal_text).toBe(
      "I don't see this in your company's policy. Check with your HR team."
    );
    expect(a.refusal?.refusal_code).toBe('refusal_out_of_policy');
    expect(a.answer_text).toBe('');
    expect(a.evidence).toEqual([]);
    expect(a.cited_chunks).toEqual([]);
  });

  it('handles validation-failed refusals the same way', () => {
    const a = ragResponseToAnswer({ ...REFUSAL, answer_kind: 'refusal_validation_failed' }, 'employee');
    expect(a.answer_type).toBe('refusal');
    expect(a.refusal?.refusal_code).toBe('refusal_validation_failed');
  });
});

describe('response wrappers preserve the legacy shape', () => {
  it('HR wrapper carries policy_id, document_id, request_id=audit_id', () => {
    const r = ragResponseToHrResponse(ANSWER, 'pol-1', 'doc-9');
    expect(r).toMatchObject({ ok: true, policy_id: 'pol-1', document_id: 'doc-9', request_id: 'audit-123' });
    expect(r.answer.answer_type).toBe('status_summary');
  });

  it('HR wrapper defaults document_id to null when omitted', () => {
    expect(ragResponseToHrResponse(ANSWER, 'pol-1').document_id).toBeNull();
  });

  it('employee wrapper carries assignment_id + request_id', () => {
    const r = ragResponseToEmployeeResponse(ANSWER, 'asg-7');
    expect(r).toMatchObject({ ok: true, assignment_id: 'asg-7', request_id: 'audit-123' });
  });

  it('tolerates a missing audit_id (request_id → null)', () => {
    const r = ragResponseToEmployeeResponse({ ...ANSWER, audit_id: null }, 'asg-7');
    expect(r.request_id).toBeNull();
  });
});
