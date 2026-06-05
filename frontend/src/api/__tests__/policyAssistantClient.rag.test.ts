/**
 * AIQ-833 / F2 — integration test for the client cutover.
 * Spies the axios instance to prove hrAPI/employeeAPI.postPolicyAssistantQuery
 * (a) POST to /api/policy-assistant/rag-query with { question }, and
 * (b) adapt the flat RAG response into the rich panel shape.
 * This exercises the real client.ts code path (criteria 1 & 7 at integration level).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

// client.ts transitively constructs the Supabase client at import time (needs
// VITE_SUPABASE_* env). Stub those modules so the real client.ts loads under test.
vi.mock('../supabase', () => ({ supabase: {} }));
vi.mock('../supabaseAuth', () => ({ signOutSupabase: vi.fn() }));

import api, { hrAPI, employeeAPI } from '../client';

const RAG_ANSWER = {
  answer_text: 'Your housing allowance is 2000 EUR/month [chunk:c1].',
  answer_kind: 'answer',
  cited_chunks: [
    { id: 'c1', source_type: 'matrix_benefit', source_ref: 'policy_config_benefits.b1', chunk_text: 'Housing cap 2000.' },
  ],
  audit_id: 'audit-123',
};

const RAG_REFUSAL = {
  answer_text: "I don't see this in your company's policy. Check with your HR team.",
  answer_kind: 'refusal_out_of_policy',
  cited_chunks: [],
  audit_id: 'audit-456',
};

afterEach(() => vi.restoreAllMocks());

describe('hrAPI.postPolicyAssistantQuery → RAG cutover', () => {
  it('posts { question } to /api/policy-assistant/rag-query and adapts an answer', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: RAG_ANSWER } as never);
    const res = await hrAPI.postPolicyAssistantQuery('pol-1', 'What is my housing allowance?', 'doc-9');

    expect(post).toHaveBeenCalledTimes(1);
    const [url, body] = post.mock.calls[0];
    expect(url).toBe('/api/policy-assistant/rag-query');
    expect(body).toEqual({ question: 'What is my housing allowance?' });

    expect(res.policy_id).toBe('pol-1');
    expect(res.document_id).toBe('doc-9');
    expect(res.request_id).toBe('audit-123');
    expect(res.answer.answer_type).toBe('status_summary');
    expect(res.answer.cited_chunks).toEqual(RAG_ANSWER.cited_chunks);
    expect(res.answer.evidence).toHaveLength(1);
    expect(res.answer.evidence[0].reference).toBe('policy_config_benefits.b1');
  });

  it('adapts a refusal into answer.refusal with the exact copy', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({ data: RAG_REFUSAL } as never);
    const res = await hrAPI.postPolicyAssistantQuery('pol-1', 'give me legal advice');
    expect(res.answer.answer_type).toBe('refusal');
    expect(res.answer.refusal?.refusal_text).toBe(
      "I don't see this in your company's policy. Check with your HR team."
    );
  });
});

describe('employeeAPI.postPolicyAssistantQuery → RAG cutover', () => {
  it('posts { question } to rag-query and carries assignment_id', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: RAG_ANSWER } as never);
    const res = await employeeAPI.postPolicyAssistantQuery('asg-7', 'Do I get relocation support?');
    const [url, body] = post.mock.calls[0];
    expect(url).toBe('/api/policy-assistant/rag-query');
    expect(body).toEqual({ question: 'Do I get relocation support?' });
    expect(res.assignment_id).toBe('asg-7');
    expect(res.answer.cited_chunks).toEqual(RAG_ANSWER.cited_chunks);
  });
});
