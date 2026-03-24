import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { EmployeePolicyAssistantPanel } from '../EmployeePolicyAssistantPanel';
import {
  EMPLOYEE_POLICY_ASSISTANT_DISCLAIMER,
  EMPLOYEE_POLICY_ASSISTANT_DISCLAIMER_SECONDARY,
  EMPLOYEE_POLICY_ASSISTANT_EMPTY_HINT,
  EMPLOYEE_POLICY_ASSISTANT_ERROR_TITLE,
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

const lsStore: Record<string, string> = {};

beforeEach(() => {
  for (const k of Object.keys(lsStore)) delete lsStore[k];
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => (Object.prototype.hasOwnProperty.call(lsStore, k) ? lsStore[k] : null),
    setItem: (k: string, v: string) => {
      lsStore[k] = String(v);
    },
    removeItem: (k: string) => {
      delete lsStore[k];
    },
    clear: () => {
      for (const k of Object.keys(lsStore)) delete lsStore[k];
    },
    key: (i: number) => Object.keys(lsStore)[i] ?? null,
    get length() {
      return Object.keys(lsStore).length;
    },
  } as Storage);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe('EmployeePolicyAssistantPanel', () => {
  it('shows title, subtitle, and disclaimer when assignment is present', () => {
    render(<EmployeePolicyAssistantPanel assignmentId="asg-1" />);
    expect(screen.getByText(EMPLOYEE_POLICY_ASSISTANT_TITLE)).toBeInTheDocument();
    expect(screen.getByText(EMPLOYEE_POLICY_ASSISTANT_SUBTITLE)).toBeInTheDocument();
    expect(screen.getByText(EMPLOYEE_POLICY_ASSISTANT_DISCLAIMER)).toBeInTheDocument();
    expect(screen.getByText(EMPLOYEE_POLICY_ASSISTANT_DISCLAIMER_SECONDARY)).toBeInTheDocument();
  });

  it('shows no-assignment copy when assignment id missing', () => {
    render(<EmployeePolicyAssistantPanel assignmentId={null} />);
    expect(screen.getByText(/link an active assignment/i)).toBeInTheDocument();
  });

  it('shows loading placeholder when parent is loading and id not yet known', () => {
    render(<EmployeePolicyAssistantPanel assignmentId={null} assignmentLoading />);
    expect(screen.getByText(/loading assignment for policy context/i)).toBeInTheDocument();
  });

  it('fills suggestion into textarea when chip clicked', async () => {
    render(<EmployeePolicyAssistantPanel assignmentId="asg-1" />);
    fireEvent.click(screen.getByRole('button', { name: EMPLOYEE_POLICY_ASSISTANT_SUGGESTIONS[0] }));
    const ta = screen.getByPlaceholderText(/shipment allowance/i);
    expect(ta).toHaveValue(EMPLOYEE_POLICY_ASSISTANT_SUGGESTIONS[0]);
    await waitFor(() => expect(ta).toHaveFocus());
  });

  it('shows inline hint when Get answer is clicked with an empty question', () => {
    render(<EmployeePolicyAssistantPanel assignmentId="asg-1" />);
    fireEvent.click(screen.getByRole('button', { name: /get answer/i }));
    expect(screen.getByText(EMPLOYEE_POLICY_ASSISTANT_EMPTY_HINT)).toBeInTheDocument();
    expect(postPolicyAssistantQuery).not.toHaveBeenCalled();
  });

  it('shows response region label and empty placeholder before first answer', () => {
    render(<EmployeePolicyAssistantPanel assignmentId="asg-1" />);
    expect(screen.getByRole('region', { name: /published policy answer/i })).toBeInTheDocument();
    expect(screen.getByText(/answers from your policy/i)).toBeInTheDocument();
    expect(screen.getByText(/no answers yet/i)).toBeInTheDocument();
  });

  it('shows Checking published policy while the request is in flight', async () => {
    postPolicyAssistantQuery.mockImplementation(() => new Promise(() => undefined));
    render(<EmployeePolicyAssistantPanel assignmentId="asg-1" />);
    fireEvent.change(screen.getByPlaceholderText(/shipment allowance/i), {
      target: { value: 'Test question' },
    });
    fireEvent.click(screen.getByRole('button', { name: /get answer/i }));
    expect(await screen.findByText(/checking published policy/i)).toBeInTheDocument();
  });

  it('submits question and renders answer card with status and source', async () => {
    postPolicyAssistantQuery.mockResolvedValue({
      ok: true,
      assignment_id: 'asg-1',
      request_id: 'r1',
      answer: entitlementAnswer(),
    });
    render(<EmployeePolicyAssistantPanel assignmentId="asg-1" />);
    fireEvent.change(screen.getByPlaceholderText(/shipment allowance/i), {
      target: { value: 'Is temporary housing included?' },
    });
    fireEvent.click(screen.getByRole('button', { name: /get answer/i }));
    await waitFor(() => expect(postPolicyAssistantQuery).toHaveBeenCalledWith('asg-1', 'Is temporary housing included?'));
    await waitFor(() => {
      expect(screen.getByText(/included \(published policy\)/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/where this comes from/i)).toBeInTheDocument();
    expect(screen.getAllByText(/published benefit rule/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/related policy questions/i)).toBeInTheDocument();
    expect(screen.getByText(/home leave cap/i)).toBeInTheDocument();
  });

  it('sideSheet variant opens anchored panel with intro copy', async () => {
    render(<EmployeePolicyAssistantPanel assignmentId="asg-1" variant="sideSheet" />);
    fireEvent.click(screen.getByRole('button', { name: EMPLOYEE_POLICY_ASSISTANT_TITLE }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getAllByText(EMPLOYEE_POLICY_ASSISTANT_SUBTITLE).length).toBeGreaterThan(0);
    fireEvent.click(within(dialog).getByRole('button', { name: 'Close' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
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
    fireEvent.change(screen.getByPlaceholderText(/shipment allowance/i), {
      target: { value: 'Negotiate my salary' },
    });
    fireEvent.click(screen.getByRole('button', { name: /get answer/i }));
    await waitFor(() => expect(screen.getByText(/no policy answer/i)).toBeInTheDocument());
    expect(screen.getByText(/policy questions you can ask/i)).toBeInTheDocument();
    expect(screen.getByText('What is my housing cap?')).toBeInTheDocument();
  });

  it('shows friendly error when API returns generic policy assistant failed', async () => {
    postPolicyAssistantQuery.mockRejectedValue({
      response: { data: { detail: 'Policy assistant failed' } },
    });
    render(<EmployeePolicyAssistantPanel assignmentId="asg-1" />);
    fireEvent.change(screen.getByPlaceholderText(/shipment allowance/i), {
      target: { value: 'Test question' },
    });
    fireEvent.click(screen.getByRole('button', { name: /get answer/i }));
    await waitFor(() => {
      expect(screen.getByText(EMPLOYEE_POLICY_ASSISTANT_ERROR_TITLE)).toBeInTheDocument();
    });
  });

  it('restores saved Q&A from localStorage for this assignment', () => {
    const stored = [
      {
        id: 'saved-1',
        question: 'Previously saved question?',
        answer: entitlementAnswer({ answer_text: '**Saved** answer.' }),
      },
    ];
    globalThis.localStorage.setItem('relopass_employee_policy_assistant_v1:asg-1', JSON.stringify(stored));
    render(<EmployeePolicyAssistantPanel assignmentId="asg-1" />);
    expect(screen.getByText('Previously saved question?')).toBeInTheDocument();
    const card = screen.getByRole('article', { name: /policy q&a/i });
    expect(within(card).getByText('Saved')).toBeInTheDocument();
  });
});
