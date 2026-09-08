import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import { HrPolicyAssistantPanel } from '../HrPolicyAssistantPanel';
import {
  HR_POLICY_ASSISTANT_SUBTITLE,
  HR_POLICY_ASSISTANT_TITLE,
  HR_POLICY_ASSISTANT_SUGGESTIONS,
  HR_POLICY_ASSISTANT_TRUST_PILL,
} from '../hrPolicyAssistantCopy';
import type { PolicyAssistantAnswer } from '../../../types/policyAssistant';
import { ragResponseToHrResponse } from '../../../api/policyAssistantRagAdapter';

const postPolicyAssistantQuery = vi.fn();

vi.mock('../../../api/client', () => ({
  hrAPI: {
    postPolicyAssistantQuery: (...args: unknown[]) => postPolicyAssistantQuery(...args),
  },
  // Sprint 1 analytics beacons go through apiPost — stub here so the
  // mocked module exposes the symbol; calls are fire-and-forget.
  apiPost: vi.fn().mockResolvedValue({ ok: true }),
}));

// Avoid the jsdom supabase-import trap — policyHelpfulness → client (axios) → supabase.
vi.mock('../../../api/policyHelpfulness', () => ({
  submitHelpfulness: vi.fn().mockResolvedValue(undefined),
}));

function baseAnswer(overrides: Partial<PolicyAssistantAnswer> = {}): PolicyAssistantAnswer {
  return {
    answer_type: 'draft_published_summary',
    canonical_topic: null,
    answer_text: 'The **draft** is not live for employees until published.',
    policy_status: 'draft_and_published',
    comparison_readiness: 'not_applicable',
    evidence: [
      {
        kind: 'published_version',
        label: 'Published version (employees)',
        excerpt: null,
        source: 'published_matrix',
        policy_source_type: 'published_version',
      },
    ],
    conditions: [],
    approval_required: false,
    follow_up_options: [],
    refusal: null,
    role_scope: 'hr',
    detected_intent: 'draft_vs_published_question',
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('HrPolicyAssistantPanel', () => {
  it('shows framing when a policy is selected', () => {
    render(<HrPolicyAssistantPanel policyId="pol-1" />);
    expect(screen.getByText(HR_POLICY_ASSISTANT_TITLE)).toBeInTheDocument();
    expect(screen.getByText(HR_POLICY_ASSISTANT_SUBTITLE)).toBeInTheDocument();
    // Slice 3 replaced the SCOPE_NOTE paragraph with a trust-signal pill.
    expect(screen.getByText(HR_POLICY_ASSISTANT_TRUST_PILL)).toBeInTheDocument();
  });

  it('shows no-policy guidance when there is no live policy', () => {
    // No document policyId AND not flagged queryable → genuinely no live
    // policy. The empty-state now points at publishing (matrix or document),
    // not only at uploading a document.
    render(<HrPolicyAssistantPanel policyId={null} hasQueryablePolicy={false} />);
    expect(screen.getByText(/publish a policy/i)).toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText(/employees see for shipment/i)
    ).not.toBeInTheDocument();
  });

  it('opens the ask box for a matrix-published policy (no document policyId)', () => {
    // Company-scoped RAG: a live matrix policy has no document `policyId`
    // but is fully answerable. The input must render.
    render(<HrPolicyAssistantPanel policyId={null} hasQueryablePolicy={true} />);
    expect(screen.getByPlaceholderText(/employees see for shipment/i)).toBeInTheDocument();
    expect(screen.queryByText(/publish a policy/i)).not.toBeInTheDocument();
  });

  it('submits a matrix-policy question with an empty policy id (backend is company-scoped)', async () => {
    postPolicyAssistantQuery.mockResolvedValue({
      ok: true,
      policy_id: null,
      document_id: null,
      answer: baseAnswer(),
    });
    const user = userEvent.setup();
    render(<HrPolicyAssistantPanel policyId={null} hasQueryablePolicy={true} />);
    await user.type(
      screen.getByPlaceholderText(/employees see for shipment/i),
      'What relocation benefits do we offer?'
    );
    await user.click(screen.getByRole('button', { name: /^ask$/i }));
    await waitFor(() =>
      expect(postPolicyAssistantQuery).toHaveBeenCalledWith('', 'What relocation benefits do we offer?', undefined)
    );
  });

  it('legacy: still gates on policyId when hasQueryablePolicy is not supplied', () => {
    render(<HrPolicyAssistantPanel policyId={null} />);
    expect(screen.getByText(/publish a policy/i)).toBeInTheDocument();
  });

  it('applies a suggestion chip to the textarea', async () => {
    const user = userEvent.setup();
    render(<HrPolicyAssistantPanel policyId="pol-1" />);
    await user.click(screen.getByRole('button', { name: HR_POLICY_ASSISTANT_SUGGESTIONS[0] }));
    expect(screen.getByPlaceholderText(/employees see for shipment/i)).toHaveValue(HR_POLICY_ASSISTANT_SUGGESTIONS[0]);
  });

  it('submits and shows policy scope, draft/published hint, and source reference', async () => {
    postPolicyAssistantQuery.mockResolvedValue({
      ok: true,
      policy_id: 'pol-1',
      document_id: null,
      answer: baseAnswer(),
    });
    const user = userEvent.setup();
    render(<HrPolicyAssistantPanel policyId="pol-1" documentId={null} />);
    await user.type(
      screen.getByPlaceholderText(/employees see for shipment/i),
      'What changes if I publish?'
    );
    await user.click(screen.getByRole('button', { name: /^ask$/i }));
    await waitFor(() =>
      expect(postPolicyAssistantQuery).toHaveBeenCalledWith('pol-1', 'What changes if I publish?', undefined)
    );
    const region = await screen.findByRole('region', { name: /HR policy answer/i });
    expect(within(region).getByText(/policy data scope/i)).toBeInTheDocument();
    expect(within(region).getByText('Draft vs published:')).toBeInTheDocument();
    expect(within(region).getByText(/source reference/i)).toBeInTheDocument();
    expect(within(region).getByText(/published version \(employees\)/i)).toBeInTheDocument();
  });

  it('passes document_id when provided', async () => {
    postPolicyAssistantQuery.mockResolvedValue({
      ok: true,
      policy_id: 'pol-1',
      document_id: 'doc-9',
      answer: baseAnswer(),
    });
    const user = userEvent.setup();
    render(<HrPolicyAssistantPanel policyId="pol-1" documentId="doc-9" />);
    await user.type(screen.getByPlaceholderText(/employees see for shipment/i), 'Test');
    await user.click(screen.getByRole('button', { name: /^ask$/i }));
    await waitFor(() => expect(postPolicyAssistantQuery).toHaveBeenCalledWith('pol-1', 'Test', 'doc-9'));
  });

  it('shows comparison readiness line when applicable', async () => {
    postPolicyAssistantQuery.mockResolvedValue({
      ok: true,
      policy_id: 'pol-1',
      answer: baseAnswer({
        answer_type: 'comparison_summary',
        answer_text: 'Topic is not fully comparison-ready.',
        comparison_readiness: 'informational_only',
        evidence: [],
      }),
    });
    const user = userEvent.setup();
    render(<HrPolicyAssistantPanel policyId="pol-1" />);
    await user.type(screen.getByPlaceholderText(/employees see for shipment/i), 'Why informational?');
    await user.click(screen.getByRole('button', { name: /^ask$/i }));
    const region = await screen.findByRole('region', { name: /HR policy answer/i });
    expect(within(region).getByText('Comparison readiness:')).toBeInTheDocument();
    expect(within(region).getByText('informational only', { exact: false })).toBeInTheDocument();
  });

  it('renders refusal with in-scope examples', async () => {
    postPolicyAssistantQuery.mockResolvedValue({
      ok: true,
      policy_id: 'pol-1',
      answer: {
        answer_type: 'refusal',
        canonical_topic: null,
        answer_text: '',
        policy_status: 'unknown',
        comparison_readiness: 'not_applicable',
        evidence: [],
        conditions: [],
        approval_required: false,
        follow_up_options: [],
        refusal: {
          refusal_code: 'out_of_scope_general',
          refusal_text: 'That is outside this policy Q&A scope.',
          supported_examples: ['What do employees see for temporary housing?'],
        },
        role_scope: 'hr',
      },
    });
    const user = userEvent.setup();
    render(<HrPolicyAssistantPanel policyId="pol-1" />);
    await user.type(
      screen.getByPlaceholderText(/employees see for shipment/i),
      'How should we beat competitors on benefits?'
    );
    await user.click(screen.getByRole('button', { name: /^ask$/i }));
    expect(await screen.findByText(/no policy answer/i)).toBeInTheDocument();
    expect(screen.getByText(/within-policy examples/i)).toBeInTheDocument();
    expect(screen.getByText('What do employees see for temporary housing?')).toBeInTheDocument();
  });

  // ── AIQ-833 / F2: end-to-end render through the REAL RAG adapter ──────────
  // Feeds the actual flat RAG payload through ragResponseToHrResponse and
  // renders it in the real panel — the deterministic stand-in for the browser
  // smoke (criteria 2, 4, 6).

  it('RAG cutover: a grounded answer renders inline citation + Source reference', async () => {
    postPolicyAssistantQuery.mockResolvedValue(
      ragResponseToHrResponse(
        {
          answer_text: 'Housing allowance is 2000 EUR/month [chunk:c1].',
          answer_kind: 'answer',
          cited_chunks: [
            {
              id: 'c1',
              source_type: 'matrix_benefit',
              source_ref: 'policy_config_benefits.b1',
              chunk_text: 'Housing cap is 2000 EUR per month.',
            },
          ],
          audit_id: 'audit-1',
        },
        'pol-1'
      )
    );
    const user = userEvent.setup();
    render(<HrPolicyAssistantPanel policyId="pol-1" />);
    await user.type(
      screen.getByPlaceholderText(/employees see for shipment/i),
      'What is the housing allowance?'
    );
    await user.click(screen.getByRole('button', { name: /^ask$/i }));
    const region = await screen.findByRole('region', { name: /HR policy answer/i });
    expect(within(region).getByText(/housing allowance is 2000 eur\/month/i)).toBeInTheDocument();
    // Citation chip derived from the [chunk:c1] token + cited_chunks lookup.
    expect(within(region).getByTestId('policy-evidence-citation')).toBeInTheDocument();
    // Source reference section populated from cited_chunks via the adapter.
    expect(within(region).getByText(/source reference/i)).toBeInTheDocument();
    expect(within(region).getByText(/housing cap is 2000 eur per month/i)).toBeInTheDocument();
  });

  it('RAG cutover: a refusal renders the exact engine copy', async () => {
    postPolicyAssistantQuery.mockResolvedValue(
      ragResponseToHrResponse(
        {
          answer_text: "I don't see this in your company's policy. Check with your HR team.",
          answer_kind: 'refusal_out_of_policy',
          cited_chunks: [],
          audit_id: 'audit-2',
        },
        'pol-1'
      )
    );
    const user = userEvent.setup();
    render(<HrPolicyAssistantPanel policyId="pol-1" />);
    await user.type(screen.getByPlaceholderText(/employees see for shipment/i), 'give me legal advice');
    await user.click(screen.getByRole('button', { name: /^ask$/i }));
    expect(await screen.findByText(/i don't see this in your company's policy\. check with your hr team\./i)).toBeInTheDocument();
    expect(screen.getByText(/no policy answer/i)).toBeInTheDocument();
  });

  it('renders AnswerFeedback thumbs when answer has trace_session_id', async () => {
    postPolicyAssistantQuery.mockResolvedValue({
      ok: true,
      policy_id: 'pol-1',
      document_id: null,
      answer: baseAnswer({ trace_session_id: 'trace-hr-1' }),
    });
    const user = userEvent.setup();
    render(<HrPolicyAssistantPanel policyId="pol-1" />);
    await user.type(screen.getByPlaceholderText(/employees see for shipment/i), 'Housing allowance?');
    await user.click(screen.getByRole('button', { name: /^ask$/i }));
    expect(await screen.findByTestId('answer-feedback')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Helpful' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Not helpful' })).toBeInTheDocument();
  });

  it('does not render AnswerFeedback when answer has no trace_session_id', async () => {
    postPolicyAssistantQuery.mockResolvedValue({
      ok: true,
      policy_id: 'pol-1',
      document_id: null,
      answer: baseAnswer({ trace_session_id: null }),
    });
    const user = userEvent.setup();
    render(<HrPolicyAssistantPanel policyId="pol-1" />);
    await user.type(screen.getByPlaceholderText(/employees see for shipment/i), 'Housing allowance?');
    await user.click(screen.getByRole('button', { name: /^ask$/i }));
    await screen.findByRole('region', { name: /HR policy answer/i });
    expect(screen.queryByTestId('answer-feedback')).not.toBeInTheDocument();
  });
});
