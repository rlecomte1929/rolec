/**
 * Tests for PolicyAssistantPage (P5-3)
 *
 * Covers:
 *  - Scope label rendered
 *  - 8 question tiles rendered initially
 *  - Clicking a tile submits immediately (no extra typing required)
 *  - Tiles hidden after first submit
 *  - Response card shown with question + answer text
 *  - "Discuss with HR" escalation href contains question + response
 *  - Evidence section rendered when present
 *  - "New question" button restores tiles
 *  - Free-text input + submit button
 *  - Enter key submits (Shift+Enter does not)
 *  - Error banner shown on API failure
 *  - No-assignment guard state
 *  - Helper functions: buildEscalationHref, answerToPlainText
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import {
  PolicyAssistantPage,
  QuestionTileGrid,
  ResponseCard,
  buildEscalationHref,
  answerToPlainText,
  SCOPE_LABEL,
  QUESTION_TILES,
  ESCALATION_SUBJECT_PREFIX,
  type AssistantTurn,
} from '../PolicyAssistantPage';
import type { PolicyAssistantAnswer } from '../../../types/policyAssistant';

// ---------------------------------------------------------------------------
// Mock employeeAPI
// ---------------------------------------------------------------------------

const postPolicyAssistantQuery = vi.fn();

vi.mock('../../../api/client', () => ({
  employeeAPI: {
    postPolicyAssistantQuery: (...args: unknown[]) => postPolicyAssistantQuery(...args),
  },
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeAnswer(overrides: Partial<PolicyAssistantAnswer> = {}): PolicyAssistantAnswer {
  return {
    answer_type: 'entitlement_summary',
    canonical_topic: 'housing',
    answer_text: 'Your housing allowance is USD 5,000 per month.',
    policy_status: 'published',
    comparison_readiness: 'comparison_ready',
    evidence: [
      {
        kind: 'benefit_rule',
        label: 'Housing policy §3.1',
        excerpt: 'Housing allowance capped at USD 5,000/month.',
      },
    ],
    conditions: [],
    approval_required: false,
    follow_up_options: [],
    refusal: null,
    role_scope: 'employee',
    detected_intent: null,
    ...overrides,
  };
}

function makeTurn(overrides: Partial<AssistantTurn> = {}): AssistantTurn {
  return {
    id: 'pa-test-1',
    question: 'What is my housing allowance?',
    answer: makeAnswer(),
    ...overrides,
  };
}

function mockApiSuccess(answer?: PolicyAssistantAnswer) {
  postPolicyAssistantQuery.mockResolvedValue({
    ok: true,
    assignment_id: 'assign-1',
    answer: answer ?? makeAnswer(),
  });
}

function mockApiError(message = 'Server error') {
  postPolicyAssistantQuery.mockRejectedValue(new Error(message));
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// buildEscalationHref
// ---------------------------------------------------------------------------

describe('buildEscalationHref', () => {
  it('returns a mailto: href', () => {
    const href = buildEscalationHref('My question?', 'The answer.');
    expect(href).toMatch(/^mailto:/);
  });

  it('encodes the subject prefix', () => {
    const href = buildEscalationHref('Q', 'A');
    const subject = encodeURIComponent(ESCALATION_SUBJECT_PREFIX);
    expect(href).toContain(`subject=${subject}`);
  });

  it('encodes question text in the body', () => {
    const href = buildEscalationHref('What is my housing allowance?', 'USD 5000.');
    expect(href).toContain(encodeURIComponent('What is my housing allowance?'));
  });

  it('encodes response text in the body', () => {
    const href = buildEscalationHref('Q?', 'USD 5000 per month.');
    expect(href).toContain(encodeURIComponent('USD 5000 per month.'));
  });

  it('uses empty to: field so client resolves HR contact', () => {
    const href = buildEscalationHref('Q', 'A');
    // mailto: with no recipient — starts with "mailto:?" or "mailto:?subject"
    expect(href).toMatch(/^mailto:\?/);
  });
});

// ---------------------------------------------------------------------------
// answerToPlainText
// ---------------------------------------------------------------------------

describe('answerToPlainText', () => {
  it('returns answer_text when present', () => {
    const answer = makeAnswer({ answer_text: 'This is the answer.' });
    expect(answerToPlainText(answer)).toBe('This is the answer.');
  });

  it('falls back to refusal_text when answer_text is empty', () => {
    const answer = makeAnswer({
      answer_text: '',
      refusal: {
        refusal_code: 'TOPIC_REJECTED',
        refusal_text: 'Out of scope.',
        supported_examples: [],
      },
    });
    expect(answerToPlainText(answer)).toBe('Out of scope.');
  });

  it('falls back to default message when both are absent', () => {
    const answer = makeAnswer({ answer_text: '', refusal: null });
    expect(answerToPlainText(answer)).toBe('No answer text available.');
  });

  it('trims whitespace', () => {
    const answer = makeAnswer({ answer_text: '  trimmed  ' });
    expect(answerToPlainText(answer)).toBe('trimmed');
  });
});

// ---------------------------------------------------------------------------
// QuestionTileGrid
// ---------------------------------------------------------------------------

describe('QuestionTileGrid', () => {
  it('renders all provided tiles', () => {
    const onTileClick = vi.fn();
    render(
      <QuestionTileGrid tiles={QUESTION_TILES} disabled={false} onTileClick={onTileClick} />,
    );
    const tiles = screen.getAllByTestId('question-tile');
    expect(tiles).toHaveLength(QUESTION_TILES.length);
  });

  it('shows tile text', () => {
    const onTileClick = vi.fn();
    render(
      <QuestionTileGrid tiles={['First tile', 'Second tile']} disabled={false} onTileClick={onTileClick} />,
    );
    expect(screen.getByText('First tile')).toBeInTheDocument();
    expect(screen.getByText('Second tile')).toBeInTheDocument();
  });

  it('calls onTileClick with the correct question when clicked', () => {
    const onTileClick = vi.fn();
    render(
      <QuestionTileGrid tiles={QUESTION_TILES} disabled={false} onTileClick={onTileClick} />,
    );
    fireEvent.click(screen.getAllByTestId('question-tile')[0]);
    expect(onTileClick).toHaveBeenCalledWith(QUESTION_TILES[0]);
  });

  it('disables all tile buttons when disabled=true', () => {
    const onTileClick = vi.fn();
    render(
      <QuestionTileGrid tiles={QUESTION_TILES} disabled={true} onTileClick={onTileClick} />,
    );
    const tiles = screen.getAllByTestId('question-tile');
    for (const tile of tiles) {
      expect(tile).toBeDisabled();
    }
  });

  it('has accessible role="group" label', () => {
    render(
      <QuestionTileGrid tiles={QUESTION_TILES} disabled={false} onTileClick={vi.fn()} />,
    );
    expect(screen.getByRole('group', { name: /suggested policy questions/i })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// ResponseCard
// ---------------------------------------------------------------------------

describe('ResponseCard', () => {
  it('renders the question', () => {
    render(<ResponseCard turn={makeTurn()} />);
    expect(screen.getByText('What is my housing allowance?')).toBeInTheDocument();
  });

  it('renders the answer text', () => {
    render(<ResponseCard turn={makeTurn()} />);
    expect(screen.getByText('Your housing allowance is USD 5,000 per month.')).toBeInTheDocument();
  });

  it('renders evidence label and excerpt', () => {
    render(<ResponseCard turn={makeTurn()} />);
    expect(screen.getByText('Housing policy §3.1')).toBeInTheDocument();
    expect(screen.getByText('Housing allowance capped at USD 5,000/month.')).toBeInTheDocument();
  });

  it('does not render evidence section when evidence is empty', () => {
    render(<ResponseCard turn={makeTurn({ answer: makeAnswer({ evidence: [] }) })} />);
    expect(screen.queryByText('Where this comes from')).not.toBeInTheDocument();
  });

  it('renders escalation button with correct href', () => {
    const turn = makeTurn();
    render(<ResponseCard turn={turn} />);
    const btn = screen.getByTestId('escalation-button');
    expect(btn).toBeInTheDocument();
    const href = btn.getAttribute('href') ?? '';
    expect(href).toMatch(/^mailto:/);
    expect(href).toContain(encodeURIComponent(turn.question));
    expect(href).toContain(encodeURIComponent(turn.answer.answer_text));
  });

  it('escalation button label is "Discuss with HR"', () => {
    render(<ResponseCard turn={makeTurn()} />);
    expect(screen.getByTestId('escalation-button')).toHaveAttribute(
      'aria-label',
      'Discuss this with HR',
    );
  });

  it('uses refusal text in escalation href when answer_text is empty', () => {
    const turn = makeTurn({
      answer: makeAnswer({
        answer_text: '',
        refusal: { refusal_code: 'TOPIC_REJECTED', refusal_text: 'Cannot answer.', supported_examples: [] },
      }),
    });
    render(<ResponseCard turn={turn} />);
    const href = screen.getByTestId('escalation-button').getAttribute('href') ?? '';
    expect(href).toContain(encodeURIComponent('Cannot answer.'));
  });
});

// ---------------------------------------------------------------------------
// PolicyAssistantPage — rendering
// ---------------------------------------------------------------------------

describe('PolicyAssistantPage — render', () => {
  it('renders the page container', () => {
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    expect(screen.getByTestId('policy-assistant-page')).toBeInTheDocument();
  });

  it('renders the scope label', () => {
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    expect(screen.getByTestId('scope-label')).toHaveTextContent(SCOPE_LABEL);
  });

  it('renders question tiles on initial load', () => {
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    expect(screen.getByTestId('question-tile-grid')).toBeInTheDocument();
    expect(screen.getAllByTestId('question-tile')).toHaveLength(QUESTION_TILES.length);
  });

  it('renders the text input and submit button', () => {
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    expect(screen.getByTestId('question-input')).toBeInTheDocument();
    expect(screen.getByTestId('submit-button')).toBeInTheDocument();
  });

  it('submit button disabled when input is empty', () => {
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    expect(screen.getByTestId('submit-button')).toBeDisabled();
  });

  it('shows no-assignment guard when assignmentId is null', () => {
    render(<PolicyAssistantPage assignmentId={null} />);
    expect(screen.queryByTestId('question-tile-grid')).not.toBeInTheDocument();
    expect(screen.getByText(/link an active assignment/i)).toBeInTheDocument();
  });

  it('shows no-assignment guard when assignmentId is undefined', () => {
    render(<PolicyAssistantPage assignmentId={undefined} />);
    expect(screen.queryByTestId('question-tile-grid')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// PolicyAssistantPage — tile click submits immediately
// ---------------------------------------------------------------------------

describe('PolicyAssistantPage — tile click', () => {
  it('clicking a tile calls postPolicyAssistantQuery with that tile text', async () => {
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    fireEvent.click(screen.getAllByTestId('question-tile')[0]);

    await waitFor(() => {
      expect(postPolicyAssistantQuery).toHaveBeenCalledWith('assign-1', QUESTION_TILES[0]);
    });
  });

  it('hides tiles after tile click submit', async () => {
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    fireEvent.click(screen.getAllByTestId('question-tile')[0]);

    await waitFor(() => {
      expect(screen.queryByTestId('question-tile-grid')).not.toBeInTheDocument();
    });
  });

  it('shows response card after tile click', async () => {
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    fireEvent.click(screen.getAllByTestId('question-tile')[2]);

    await waitFor(() => {
      expect(screen.getByTestId('response-card')).toBeInTheDocument();
    });
    expect(screen.getByText(QUESTION_TILES[2])).toBeInTheDocument();
  });

  it('shows "New question" button after first tile submit', async () => {
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    fireEvent.click(screen.getAllByTestId('question-tile')[0]);

    await waitFor(() => {
      expect(screen.getByTestId('new-question-button')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// PolicyAssistantPage — text input submit
// ---------------------------------------------------------------------------

describe('PolicyAssistantPage — text input', () => {
  it('typing enables the submit button', () => {
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    fireEvent.change(screen.getByTestId('question-input'), {
      target: { value: 'What is my housing allowance?' },
    });
    expect(screen.getByTestId('submit-button')).not.toBeDisabled();
  });

  it('clicking submit calls postPolicyAssistantQuery with typed text', async () => {
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    fireEvent.change(screen.getByTestId('question-input'), {
      target: { value: 'My custom question?' },
    });
    fireEvent.click(screen.getByTestId('submit-button'));

    await waitFor(() => {
      expect(postPolicyAssistantQuery).toHaveBeenCalledWith('assign-1', 'My custom question?');
    });
  });

  it('Enter key submits the query', async () => {
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    const input = screen.getByTestId('question-input');
    fireEvent.change(input, { target: { value: 'Enter key test?' } });
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: false });

    await waitFor(() => {
      expect(postPolicyAssistantQuery).toHaveBeenCalledWith('assign-1', 'Enter key test?');
    });
  });

  it('Shift+Enter does NOT submit', async () => {
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    const input = screen.getByTestId('question-input');
    fireEvent.change(input, { target: { value: 'Shift enter test?' } });
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true });

    // Not submitted
    expect(postPolicyAssistantQuery).not.toHaveBeenCalled();
  });

  it('clears input after successful submit', async () => {
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    const input = screen.getByTestId('question-input');
    fireEvent.change(input, { target: { value: 'My question?' } });
    fireEvent.click(screen.getByTestId('submit-button'));

    await waitFor(() => {
      expect(input).toHaveValue('');
    });
  });
});

// ---------------------------------------------------------------------------
// PolicyAssistantPage — HR escalation on response card
// ---------------------------------------------------------------------------

describe('PolicyAssistantPage — HR escalation', () => {
  it('escalation button href contains the submitted question', async () => {
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    const question = QUESTION_TILES[0];
    fireEvent.click(screen.getAllByTestId('question-tile')[0]);

    await waitFor(() => {
      expect(screen.getByTestId('escalation-button')).toBeInTheDocument();
    });

    const href = screen.getByTestId('escalation-button').getAttribute('href') ?? '';
    expect(href).toContain(encodeURIComponent(question));
  });

  it('escalation button href contains answer text from API response', async () => {
    const answer = makeAnswer({ answer_text: 'USD 5000 per month.' });
    mockApiSuccess(answer);
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    fireEvent.click(screen.getAllByTestId('question-tile')[0]);

    await waitFor(() => {
      expect(screen.getByTestId('escalation-button')).toBeInTheDocument();
    });

    const href = screen.getByTestId('escalation-button').getAttribute('href') ?? '';
    expect(href).toContain(encodeURIComponent('USD 5000 per month.'));
  });
});

// ---------------------------------------------------------------------------
// PolicyAssistantPage — New question restores tiles
// ---------------------------------------------------------------------------

describe('PolicyAssistantPage — New question', () => {
  it('clicking "New question" restores the question tile grid', async () => {
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    // Submit to hide tiles
    fireEvent.click(screen.getAllByTestId('question-tile')[0]);
    await waitFor(() => expect(screen.queryByTestId('question-tile-grid')).not.toBeInTheDocument());

    // Restore tiles
    fireEvent.click(screen.getByTestId('new-question-button'));
    expect(screen.getByTestId('question-tile-grid')).toBeInTheDocument();
  });

  it('"New question" hides the "New question" button itself', async () => {
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    fireEvent.click(screen.getAllByTestId('question-tile')[0]);
    await waitFor(() => expect(screen.getByTestId('new-question-button')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('new-question-button'));
    expect(screen.queryByTestId('new-question-button')).not.toBeInTheDocument();
  });

  it('"New question" clears the text input', async () => {
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    const input = screen.getByTestId('question-input');
    fireEvent.change(input, { target: { value: 'Some text' } });

    fireEvent.click(screen.getAllByTestId('question-tile')[0]);
    await waitFor(() => expect(screen.getByTestId('new-question-button')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('new-question-button'));
    expect(input).toHaveValue('');
  });

  it('prior response cards are still visible after "New question"', async () => {
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    fireEvent.click(screen.getAllByTestId('question-tile')[0]);
    await waitFor(() => expect(screen.getByTestId('response-card')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('new-question-button'));
    expect(screen.getByTestId('response-card')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// PolicyAssistantPage — Error handling
// ---------------------------------------------------------------------------

describe('PolicyAssistantPage — errors', () => {
  it('shows error banner on API failure', async () => {
    mockApiError("Couldn't reach the server.");
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    fireEvent.change(screen.getByTestId('question-input'), {
      target: { value: 'My question?' },
    });
    fireEvent.click(screen.getByTestId('submit-button'));

    await waitFor(() => {
      expect(screen.getByTestId('error-message')).toBeInTheDocument();
    });
  });

  it('shows API detail string in error banner', async () => {
    const axiosError = {
      response: { data: { detail: 'Policy engine unavailable.' } },
      message: 'Request failed',
    };
    postPolicyAssistantQuery.mockRejectedValue(axiosError);
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    fireEvent.change(screen.getByTestId('question-input'), {
      target: { value: 'My question?' },
    });
    fireEvent.click(screen.getByTestId('submit-button'));

    await waitFor(() => {
      expect(screen.getByTestId('error-message')).toHaveTextContent(
        'Policy engine unavailable.',
      );
    });
  });

  it('clears error on successful next submission', async () => {
    // First call fails
    postPolicyAssistantQuery.mockRejectedValueOnce(new Error('oops'));
    // Second call succeeds
    postPolicyAssistantQuery.mockResolvedValueOnce({
      ok: true,
      assignment_id: 'assign-1',
      answer: makeAnswer(),
    });

    render(<PolicyAssistantPage assignmentId="assign-1" />);
    const input = screen.getByTestId('question-input');

    fireEvent.change(input, { target: { value: 'First?' } });
    fireEvent.click(screen.getByTestId('submit-button'));
    await waitFor(() => expect(screen.getByTestId('error-message')).toBeInTheDocument());

    fireEvent.change(input, { target: { value: 'Second?' } });
    fireEvent.click(screen.getByTestId('submit-button'));
    await waitFor(() => expect(screen.queryByTestId('error-message')).not.toBeInTheDocument());
  });

  it('does not add a turn on API failure', async () => {
    mockApiError('oops');
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    fireEvent.change(screen.getByTestId('question-input'), { target: { value: 'Q?' } });
    fireEvent.click(screen.getByTestId('submit-button'));

    await waitFor(() => expect(screen.getByTestId('error-message')).toBeInTheDocument());
    expect(screen.queryByTestId('response-card')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// PolicyAssistantPage — multiple turns
// ---------------------------------------------------------------------------

describe('PolicyAssistantPage — multiple turns', () => {
  it('stacks multiple response cards (most recent first)', async () => {
    postPolicyAssistantQuery
      .mockResolvedValueOnce({ ok: true, assignment_id: 'a', answer: makeAnswer({ answer_text: 'Answer 1' }) })
      .mockResolvedValueOnce({ ok: true, assignment_id: 'a', answer: makeAnswer({ answer_text: 'Answer 2' }) });

    render(<PolicyAssistantPage assignmentId="assign-1" />);

    // First question via tile
    fireEvent.click(screen.getAllByTestId('question-tile')[0]);
    await waitFor(() => expect(screen.getAllByTestId('response-card')).toHaveLength(1));

    // Second question via text input (tiles hidden; use text + submit)
    const input = screen.getByTestId('question-input');
    fireEvent.change(input, { target: { value: 'Second question?' } });
    fireEvent.click(screen.getByTestId('submit-button'));

    await waitFor(() => expect(screen.getAllByTestId('response-card')).toHaveLength(2));
  });
});
