import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { EmployeePolicyAssistantPanel } from '../EmployeePolicyAssistantPanel';
import {
  EMPLOYEE_POLICY_ASSISTANT_SUBTITLE,
  EMPLOYEE_POLICY_ASSISTANT_TITLE,
  EMPLOYEE_POLICY_ASSISTANT_SUGGESTIONS,
} from '../employeePolicyAssistantCopy';
import type { PolicyAssistantAnswer } from '../../../types/policyAssistant';

const postPolicyAssistantQuery = vi.fn();

vi.mock('../../../api/client', () => ({
  employeeAPI: {
    postPolicyAssistantQuery: (...args: unknown[]) => postPolicyAssistantQuery(...args),
  },
}));

function entitlementAnswer(overrides: Partial<PolicyAssistantAnswer> = {}): PolicyAssistantAnswer {
  return {
    answer_type: 'entitlement_summary',
    canonical_topic: 'temporary_housing',
    answer_text: 'For your case, **Temporary Housing** is **included** up to **5000 USD**.',
    policy_status: 'published',
    comparison_readiness: 'comparison_ready',
    evidence: [
      {
        kind: 'benefit_rule',
        label: 'Published benefit rule',
        excerpt: 'Temporary housing up to USD 5000.',
        source: 'published_matrix',
        policy_source_type: 'published_benefit_rule',
      },
    ],
    conditions: [],
    approval_required: false,
    follow_up_options: [{ intent: 'policy_entitlement_question', label: 'Home leave cap', query_hint: null }],
    refusal: null,
    role_scope: 'employee',
    detected_intent: 'policy_entitlement_question',
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('EmployeePolicyAssistantPanel', () => {
  it('shows title, subtitle, and scope note when assignment is present', () => {
    render(<EmployeePolicyAssistantPanel assignmentId="asg-1" />);
    expect(screen.getByText(EMPLOYEE_POLICY_ASSISTANT_TITLE)).toBeInTheDocument();
    expect(screen.getByText(EMPLOYEE_POLICY_ASSISTANT_SUBTITLE)).toBeInTheDocument();
    expect(screen.getByText(/published assignment policy/i)).toBeInTheDocument();
  });

  it('shows no-assignment copy when assignment id missing', () => {
    render(<EmployeePolicyAssistantPanel assignmentId={null} />);
    expect(screen.getByText(/active assignment/i)).toBeInTheDocument();
  });

  it('shows loading placeholder when parent is loading and id not yet known', () => {
    render(<EmployeePolicyAssistantPanel assignmentId={null} assignmentLoading />);
    expect(screen.getByText(/loading your assignment/i)).toBeInTheDocument();
  });

  it('fills suggestion into textarea when chip clicked', () => {
    render(<EmployeePolicyAssistantPanel assignmentId="asg-1" />);
    fireEvent.click(screen.getByRole('button', { name: EMPLOYEE_POLICY_ASSISTANT_SUGGESTIONS[0] }));
    const ta = screen.getByPlaceholderText(/household goods/i);
    expect(ta).toHaveValue(EMPLOYEE_POLICY_ASSISTANT_SUGGESTIONS[0]);
  });

  it('submits question and renders answer card with status and source', async () => {
    postPolicyAssistantQuery.mockResolvedValue({
      ok: true,
      assignment_id: 'asg-1',
      request_id: 'r1',
      answer: entitlementAnswer(),
    });
    render(<EmployeePolicyAssistantPanel assignmentId="asg-1" />);
    fireEvent.change(screen.getByPlaceholderText(/household goods/i), {
      target: { value: 'Is temporary housing included?' },
    });
    fireEvent.click(screen.getByRole('button', { name: /get answer/i }));
    await waitFor(() => expect(postPolicyAssistantQuery).toHaveBeenCalledWith('asg-1', 'Is temporary housing included?'));
    await waitFor(() => {
      expect(screen.getByText(/included \(per published policy data\)/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/source reference/i)).toBeInTheDocument();
    expect(screen.getByText(/published benefit rule/i)).toBeInTheDocument();
    expect(screen.getByText(/related questions/i)).toBeInTheDocument();
    expect(screen.getByText(/home leave cap/i)).toBeInTheDocument();
  });

  it('renders refusal card with supported examples', async () => {
    postPolicyAssistantQuery.mockResolvedValue({
      ok: true,
      assignment_id: 'asg-1',
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
          refusal_code: 'out_of_scope_negotiation',
          refusal_text: 'I can only answer **policy** questions.',
          supported_examples: ['What is my housing cap?'],
        },
        role_scope: 'employee',
        detected_intent: 'unsupported_question',
      },
    });
    render(<EmployeePolicyAssistantPanel assignmentId="asg-1" />);
    fireEvent.change(screen.getByPlaceholderText(/household goods/i), {
      target: { value: 'Negotiate my salary' },
    });
    fireEvent.click(screen.getByRole('button', { name: /get answer/i }));
    await waitFor(() => expect(screen.getByText(/not answered/i)).toBeInTheDocument());
    expect(screen.getByText(/try asking/i)).toBeInTheDocument();
    expect(screen.getByText('What is my housing cap?')).toBeInTheDocument();
  });
});
