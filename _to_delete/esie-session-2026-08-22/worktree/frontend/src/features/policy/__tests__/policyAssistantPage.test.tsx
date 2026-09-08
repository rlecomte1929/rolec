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

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
// Query helpers (semantic-first)
// ---------------------------------------------------------------------------

/** The suggested-question tiles are buttons inside the role="group" grid. */
function tileButtons() {
  return within(
    screen.getByRole('group', { name: /suggested policy questions/i }),
  ).getAllByRole('button');
}

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

// jsdom does not implement scrollIntoView; with user-event the component's
// auto-scroll-to-latest-response actually fires, so stub it to avoid an
// unhandled "scrollIntoView is not a function" error in the coverage run.
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

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
    const tiles = screen.getAllByRole('button');
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

  it('calls onTileClick with the correct question when clicked', async () => {
    const user = userEvent.setup();
    const onTileClick = vi.fn();
    render(
      <QuestionTileGrid tiles={QUESTION_TILES} disabled={false} onTileClick={onTileClick} />,
    );
    await user.click(screen.getAllByRole('button')[0]);
    expect(onTileClick).toHaveBeenCalledWith(QUESTION_TILES[0]);
  });

  it('disables all tile buttons when disabled=true', () => {
    const onTileClick = vi.fn();
    render(
      <QuestionTileGrid tiles={QUESTION_TILES} disabled={true} onTileClick={onTileClick} />,
    );
    const tiles = screen.getAllByRole('button');
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
    const btn = screen.getByRole('link', { name: 'Discuss this with HR' });
    expect(btn).toBeInTheDocument();
    const href = btn.getAttribute('href') ?? '';
    expect(href).toMatch(/^mailto:/);
    expect(href).toContain(encodeURIComponent(turn.question));
    expect(href).toContain(encodeURIComponent(turn.answer.answer_text));
  });

  it('escalation button label is "Discuss with HR"', () => {
    render(<ResponseCard turn={makeTurn()} />);
    expect(screen.getByRole('link')).toHaveAttribute('aria-label', 'Discuss this with HR');
  });

  it('uses refusal text in escalation href when answer_text is empty', () => {
    const turn = makeTurn({
      answer: makeAnswer({
        answer_text: '',
        refusal: { refusal_code: 'TOPIC_REJECTED', refusal_text: 'Cannot answer.', supported_examples: [] },
      }),
    });
    render(<ResponseCard turn={turn} />);
    const href = screen.getByRole('link', { name: 'Discuss this with HR' }).getAttribute('href') ?? '';
    expect(href).toContain(encodeURIComponent('Cannot answer.'));
  });
});

// ---------------------------------------------------------------------------
// PolicyAssistantPage — rendering
// ---------------------------------------------------------------------------

describe('PolicyAssistantPage — render', () => {
  it('renders the page container', () => {
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    expect(screen.getByRole('heading', { name: 'Policy Assistant' })).toBeInTheDocument();
  });

  it('renders the scope label', () => {
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    expect(screen.getByText(SCOPE_LABEL)).toBeInTheDocument();
  });

  it('renders question tiles on initial load', () => {
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    expect(screen.getByRole('group', { name: /suggested policy questions/i })).toBeInTheDocument();
    expect(tileButtons()).toHaveLength(QUESTION_TILES.length);
  });

  it('renders the text input and submit button', () => {
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    expect(screen.getByLabelText('Policy question')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ask' })).toBeInTheDocument();
  });

  it('submit button disabled when input is empty', () => {
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled();
  });

  it('shows no-assignment guard when assignmentId is null', () => {
    render(<PolicyAssistantPage assignmentId={null} />);
    expect(screen.queryByRole('group', { name: /suggested policy questions/i })).not.toBeInTheDocument();
    expect(screen.getByText(/link an active assignment/i)).toBeInTheDocument();
  });

  it('shows no-assignment guard when assignmentId is undefined', () => {
    render(<PolicyAssistantPage assignmentId={undefined} />);
    expect(screen.queryByRole('group', { name: /suggested policy questions/i })).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// PolicyAssistantPage — tile click submits immediately
// ---------------------------------------------------------------------------

describe('PolicyAssistantPage — tile click', () => {
  it('clicking a tile calls postPolicyAssistantQuery with that tile text', async () => {
    const user = userEvent.setup();
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    await user.click(tileButtons()[0]);

    await waitFor(() => {
      expect(postPolicyAssistantQuery).toHaveBeenCalledWith('assign-1', QUESTION_TILES[0]);
    });
  });

  it('hides tiles after tile click submit', async () => {
    const user = userEvent.setup();
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    await user.click(tileButtons()[0]);

    await waitFor(() => {
      expect(screen.queryByRole('group', { name: /suggested policy questions/i })).not.toBeInTheDocument();
    });
  });

  it('shows response card after tile click', async () => {
    const user = userEvent.setup();
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    await user.click(tileButtons()[2]);

    expect(await screen.findByRole('article')).toBeInTheDocument();
    expect(screen.getByText(QUESTION_TILES[2])).toBeInTheDocument();
  });

  it('shows "New question" button after first tile submit', async () => {
    const user = userEvent.setup();
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    await user.click(tileButtons()[0]);

    expect(await screen.findByRole('button', { name: 'New question' })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// PolicyAssistantPage — text input submit
// ---------------------------------------------------------------------------

describe('PolicyAssistantPage — text input', () => {
  it('typing enables the submit button', async () => {
    const user = userEvent.setup();
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    await user.type(screen.getByLabelText('Policy question'), 'What is my housing allowance?');
    expect(screen.getByRole('button', { name: 'Ask' })).not.toBeDisabled();
  });

  it('clicking submit calls postPolicyAssistantQuery with typed text', async () => {
    const user = userEvent.setup();
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    await user.type(screen.getByLabelText('Policy question'), 'My custom question?');
    await user.click(screen.getByRole('button', { name: 'Ask' }));

    await waitFor(() => {
      expect(postPolicyAssistantQuery).toHaveBeenCalledWith('assign-1', 'My custom question?');
    });
  });

  it('Enter key submits the query', async () => {
    const user = userEvent.setup();
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    const input = screen.getByLabelText('Policy question');
    await user.type(input, 'Enter key test?{Enter}');

    await waitFor(() => {
      expect(postPolicyAssistantQuery).toHaveBeenCalledWith('assign-1', 'Enter key test?');
    });
  });

  it('Shift+Enter does NOT submit', async () => {
    const user = userEvent.setup();
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    const input = screen.getByLabelText('Policy question');
    await user.type(input, 'Shift enter test?');
    await user.keyboard('{Shift>}{Enter}{/Shift}');

    // Not submitted
    expect(postPolicyAssistantQuery).not.toHaveBeenCalled();
  });

  it('clears input after successful submit', async () => {
    const user = userEvent.setup();
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    const input = screen.getByLabelText('Policy question');
    await user.type(input, 'My question?');
    await user.click(screen.getByRole('button', { name: 'Ask' }));

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
    const user = userEvent.setup();
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    const question = QUESTION_TILES[0];
    await user.click(tileButtons()[0]);

    const link = await screen.findByRole('link', { name: 'Discuss this with HR' });

    const href = link.getAttribute('href') ?? '';
    expect(href).toContain(encodeURIComponent(question));
  });

  it('escalation button href contains answer text from API response', async () => {
    const user = userEvent.setup();
    const answer = makeAnswer({ answer_text: 'USD 5000 per month.' });
    mockApiSuccess(answer);
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    await user.click(tileButtons()[0]);

    const link = await screen.findByRole('link', { name: 'Discuss this with HR' });

    const href = link.getAttribute('href') ?? '';
    expect(href).toContain(encodeURIComponent('USD 5000 per month.'));
  });
});

// ---------------------------------------------------------------------------
// PolicyAssistantPage — New question restores tiles
// ---------------------------------------------------------------------------

describe('PolicyAssistantPage — New question', () => {
  it('clicking "New question" restores the question tile grid', async () => {
    const user = userEvent.setup();
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    // Submit to hide tiles
    await user.click(tileButtons()[0]);
    await waitFor(() =>
      expect(screen.queryByRole('group', { name: /suggested policy questions/i })).not.toBeInTheDocument(),
    );

    // Restore tiles
    await user.click(screen.getByRole('button', { name: 'New question' }));
    expect(screen.getByRole('group', { name: /suggested policy questions/i })).toBeInTheDocument();
  });

  it('"New question" hides the "New question" button itself', async () => {
    const user = userEvent.setup();
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    await user.click(tileButtons()[0]);
    await screen.findByRole('button', { name: 'New question' });

    await user.click(screen.getByRole('button', { name: 'New question' }));
    expect(screen.queryByRole('button', { name: 'New question' })).not.toBeInTheDocument();
  });

  it('"New question" clears the text input', async () => {
    const user = userEvent.setup();
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);
    const input = screen.getByLabelText('Policy question');
    await user.type(input, 'Some text');

    await user.click(tileButtons()[0]);
    await screen.findByRole('button', { name: 'New question' });

    await user.click(screen.getByRole('button', { name: 'New question' }));
    expect(input).toHaveValue('');
  });

  it('prior response cards are still visible after "New question"', async () => {
    const user = userEvent.setup();
    mockApiSuccess();
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    await user.click(tileButtons()[0]);
    await screen.findByRole('article');

    await user.click(screen.getByRole('button', { name: 'New question' }));
    expect(screen.getByRole('article')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// PolicyAssistantPage — Error handling
// ---------------------------------------------------------------------------

describe('PolicyAssistantPage — errors', () => {
  it('shows error banner on API failure', async () => {
    const user = userEvent.setup();
    mockApiError("Couldn't reach the server.");
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    await user.type(screen.getByLabelText('Policy question'), 'My question?');
    await user.click(screen.getByRole('button', { name: 'Ask' }));

    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });

  it('shows API detail string in error banner', async () => {
    const user = userEvent.setup();
    const axiosError = {
      response: { data: { detail: 'Policy engine unavailable.' } },
      message: 'Request failed',
    };
    postPolicyAssistantQuery.mockRejectedValue(axiosError);
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    await user.type(screen.getByLabelText('Policy question'), 'My question?');
    await user.click(screen.getByRole('button', { name: 'Ask' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Policy engine unavailable.');
  });

  it('clears error on successful next submission', async () => {
    const user = userEvent.setup();
    // First call fails
    postPolicyAssistantQuery.mockRejectedValueOnce(new Error('oops'));
    // Second call succeeds
    postPolicyAssistantQuery.mockResolvedValueOnce({
      ok: true,
      assignment_id: 'assign-1',
      answer: makeAnswer(),
    });

    render(<PolicyAssistantPage assignmentId="assign-1" />);
    const input = screen.getByLabelText('Policy question');

    await user.type(input, 'First?');
    await user.click(screen.getByRole('button', { name: 'Ask' }));
    expect(await screen.findByRole('alert')).toBeInTheDocument();

    await user.clear(input);
    await user.type(input, 'Second?');
    await user.click(screen.getByRole('button', { name: 'Ask' }));
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  });

  it('does not add a turn on API failure', async () => {
    const user = userEvent.setup();
    mockApiError('oops');
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    await user.type(screen.getByLabelText('Policy question'), 'Q?');
    await user.click(screen.getByRole('button', { name: 'Ask' }));

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.queryByRole('article')).not.toBeInTheDocument();
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

    const user = userEvent.setup();
    render(<PolicyAssistantPage assignmentId="assign-1" />);

    // First question via tile
    await user.click(tileButtons()[0]);
    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(1));

    // Second question via text input (tiles hidden; use text + submit)
    const input = screen.getByLabelText('Policy question');
    await user.type(input, 'Second question?');
    await user.click(screen.getByRole('button', { name: 'Ask' }));

    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(2));
  });
});
