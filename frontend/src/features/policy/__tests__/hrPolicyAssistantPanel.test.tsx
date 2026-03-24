import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { HrPolicyAssistantPanel } from '../HrPolicyAssistantPanel';
import {
  HR_POLICY_ASSISTANT_SUBTITLE,
  HR_POLICY_ASSISTANT_TITLE,
  HR_POLICY_ASSISTANT_SUGGESTIONS,
} from '../hrPolicyAssistantCopy';
import type { PolicyAssistantAnswer } from '../../../types/policyAssistant';

const postPolicyAssistantQuery = vi.fn();

vi.mock('../../../api/client', () => ({
  hrAPI: {
    postPolicyAssistantQuery: (...args: unknown[]) => postPolicyAssistantQuery(...args),
  },
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
    expect(screen.getByText(/same policy review data/i)).toBeInTheDocument();
  });

  it('shows no-policy guidance when policy id missing', () => {
    render(<HrPolicyAssistantPanel policyId={null} />);
    expect(screen.getByText(/select or create a company policy/i)).toBeInTheDocument();
  });

  it('applies a suggestion chip to the textarea', () => {
    render(<HrPolicyAssistantPanel policyId="pol-1" />);
    fireEvent.click(screen.getByRole('button', { name: HR_POLICY_ASSISTANT_SUGGESTIONS[0] }));
    expect(screen.getByPlaceholderText(/employees see for shipment/i)).toHaveValue(HR_POLICY_ASSISTANT_SUGGESTIONS[0]);
  });

  it('submits and shows policy scope, draft/published hint, and source reference', async () => {
    postPolicyAssistantQuery.mockResolvedValue({
      ok: true,
      policy_id: 'pol-1',
      document_id: null,
      answer: baseAnswer(),
    });
    render(<HrPolicyAssistantPanel policyId="pol-1" documentId={null} />);
    fireEvent.change(screen.getByPlaceholderText(/employees see for shipment/i), {
      target: { value: 'What changes if I publish?' },
    });
    fireEvent.click(screen.getByRole('button', { name: /get answer/i }));
    await waitFor(() =>
      expect(postPolicyAssistantQuery).toHaveBeenCalledWith('pol-1', 'What changes if I publish?', undefined)
    );
    const region = await screen.findByRole('region', { name: /HR policy assistant result/i });
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
    render(<HrPolicyAssistantPanel policyId="pol-1" documentId="doc-9" />);
    fireEvent.change(screen.getByPlaceholderText(/employees see for shipment/i), {
      target: { value: 'Test' },
    });
    fireEvent.click(screen.getByRole('button', { name: /get answer/i }));
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
    render(<HrPolicyAssistantPanel policyId="pol-1" />);
    fireEvent.change(screen.getByPlaceholderText(/employees see for shipment/i), {
      target: { value: 'Why informational?' },
    });
    fireEvent.click(screen.getByRole('button', { name: /get answer/i }));
    const region = await screen.findByRole('region', { name: /HR policy assistant result/i });
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
          refusal_text: 'That is outside this assistant’s scope.',
          supported_examples: ['What do employees see for temporary housing?'],
        },
        role_scope: 'hr',
      },
    });
    render(<HrPolicyAssistantPanel policyId="pol-1" />);
    fireEvent.change(screen.getByPlaceholderText(/employees see for shipment/i), {
      target: { value: 'How should we beat competitors on benefits?' },
    });
    fireEvent.click(screen.getByRole('button', { name: /get answer/i }));
    await waitFor(() => expect(screen.getByText(/not answered/i)).toBeInTheDocument());
    expect(screen.getByText(/in-scope examples/i)).toBeInTheDocument();
    expect(screen.getByText('What do employees see for temporary housing?')).toBeInTheDocument();
  });
});
