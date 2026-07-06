/**
 * AIQ-1414 Phase 4 — CoordinatorChatPanel: turn→bubble flatten, load, self-hide on
 * 404, and send→reply. The coordinator API is mocked so no network/supabase import runs.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

const getSession = vi.fn();
const respond = vi.fn();
vi.mock('../../api/coordinator', () => ({
  coordinatorAPI: {
    getSession: (...a: unknown[]) => getSession(...a),
    respond: (...a: unknown[]) => respond(...a),
  },
}));

import { CoordinatorChatPanel, flattenTurns } from './CoordinatorChatPanel';

afterEach(() => {
  cleanup();
  getSession.mockReset();
  respond.mockReset();
});

describe('flattenTurns', () => {
  it('splits each turn pair into a user + assistant message', () => {
    expect(
      flattenTurns([
        { user: 'hi', assistant: 'hello' },
        { user: 'q', assistant: 'a' },
      ]),
    ).toEqual([
      { role: 'user', content: 'hi' },
      { role: 'assistant', content: 'hello' },
      { role: 'user', content: 'q' },
      { role: 'assistant', content: 'a' },
    ]);
  });

  it('skips empty halves and tolerates undefined', () => {
    expect(flattenTurns(undefined)).toEqual([]);
    expect(flattenTurns([{ user: 'only', assistant: '' }])).toEqual([
      { role: 'user', content: 'only' },
    ]);
  });
});

describe('CoordinatorChatPanel', () => {
  it('renders persisted turns from the session', async () => {
    getSession.mockResolvedValue({
      case_id: 'c1',
      rolling_summary: '',
      recent_turns: [{ user: 'status?', assistant: 'On track.' }],
      model: 'x',
      status: 'active',
    });
    render(<CoordinatorChatPanel caseId="c1" />);
    expect(await screen.findByText('status?')).toBeInTheDocument();
    expect(screen.getByText('On track.')).toBeInTheDocument();
  });

  it('self-hides when the feature is unavailable (404)', async () => {
    getSession.mockRejectedValue({ status: 404 });
    const { container } = render(<CoordinatorChatPanel caseId="c1" />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it('sends a message and appends the coordinator reply', async () => {
    getSession.mockResolvedValue({
      case_id: 'c1',
      rolling_summary: '',
      recent_turns: [],
      model: 'x',
      status: 'active',
    });
    respond.mockResolvedValue({ answer: 'Book biometrics.', model: 'x', case_id: 'c1' });
    render(<CoordinatorChatPanel caseId="c1" />);
    await screen.findByPlaceholderText('Ask the coordinator…');
    const box = screen.getByLabelText('Message text');
    fireEvent.change(box, { target: { value: 'next step?' } });
    fireEvent.keyDown(box, { key: 'Enter' });
    expect(await screen.findByText('next step?')).toBeInTheDocument();
    expect(await screen.findByText('Book biometrics.')).toBeInTheDocument();
    expect(respond).toHaveBeenCalledWith('c1', 'next step?');
  });
});
