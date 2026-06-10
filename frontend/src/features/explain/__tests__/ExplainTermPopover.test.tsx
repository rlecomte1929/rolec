/** I-6 — ExplainTermPopover. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

// client.ts builds the Supabase client at import time — stub those modules.
vi.mock('../../../api/supabase', () => ({ supabase: {} }));
vi.mock('../../../api/supabaseAuth', () => ({ signOutSupabase: vi.fn() }));

import { employeeAPI } from '../../../api/client';
import { ExplainTermPopover } from '../ExplainTermPopover';
import type { TextSelection } from '../../../hooks/useTextSelection';

const selection: TextSelection = {
  text: 'apostille',
  rect: { left: 10, bottom: 20, top: 5, right: 50, width: 40, height: 15 } as DOMRect,
};

afterEach(() => vi.restoreAllMocks());

describe('ExplainTermPopover', () => {
  it('calls the answer endpoint with the selected term and shows the explanation', async () => {
    const spy = vi.spyOn(employeeAPI, 'postPolicyAssistantQuery').mockResolvedValue({
      ok: true,
      assignment_id: 'c1',
      answer: {
        answer_text: 'An apostille certifies a document for international use.',
        cited_chunks: [{ id: 'x', source_type: 'matrix_benefit', source_ref: 'r', chunk_text: 't' }],
      },
    } as never);

    render(<ExplainTermPopover selection={selection} assignmentId="c1" onClose={() => {}} />);
    fireEvent.click(screen.getByText(/Explain this term/i));

    expect(await screen.findByText(/An apostille certifies/)).toBeTruthy();
    expect(await screen.findByText(/Grounded in 1 policy citation/)).toBeTruthy();
    expect(spy).toHaveBeenCalledTimes(1);
    expect(String(spy.mock.calls[0][1])).toContain('apostille');
  });

  it('shows an error state when the call fails', async () => {
    vi.spyOn(employeeAPI, 'postPolicyAssistantQuery').mockRejectedValue(new Error('boom'));
    render(<ExplainTermPopover selection={selection} assignmentId="c1" onClose={() => {}} />);
    fireEvent.click(screen.getByText(/Explain this term/i));
    expect(await screen.findByRole('alert')).toBeTruthy();
  });

  it('renders the selected term and a close control', () => {
    const onClose = vi.fn();
    render(<ExplainTermPopover selection={selection} assignmentId="c1" onClose={onClose} />);
    expect(screen.getByText(/apostille/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText('Close'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
