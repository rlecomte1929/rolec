/**
 * FeedbackWidget — routes submissions through the backend (POST /api/feedback)
 * instead of a direct Supabase insert (which failed for ReloPass-session users).
 * API module is mocked (avoids importing api/client → api/supabase jsdom trap).
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../api/productFeedback', () => ({ submitProductFeedback: vi.fn() }));

import { submitProductFeedback } from '../api/productFeedback';
import { FeedbackWidget } from './FeedbackWidget';

const mockSubmit = submitProductFeedback as unknown as ReturnType<typeof vi.fn>;

afterEach(cleanup);
beforeEach(() => mockSubmit.mockReset());

function openAndType(text: string) {
  fireEvent.click(screen.getByLabelText('Give feedback'));
  const box = screen.getByRole('textbox');
  fireEvent.change(box, { target: { value: text } });
  return box;
}

describe('FeedbackWidget', () => {
  it('submits via the backend API and shows success', async () => {
    mockSubmit.mockResolvedValue({ ok: true, report_id: 'BUG-x' });
    render(<FeedbackWidget userId="u1" />);
    openAndType('ÇVX');
    fireEvent.click(screen.getByRole('button', { name: /send/i }));
    await waitFor(() => expect(mockSubmit).toHaveBeenCalledTimes(1));
    const arg = mockSubmit.mock.calls[0][0];
    expect(arg.category).toBe('bug');
    expect(arg.message).toBe('ÇVX');
    expect(typeof arg.page_url).toBe('string');
    await waitFor(() => expect(screen.getByText(/received/i)).toBeInTheDocument());
  });

  it('does not submit an empty message', () => {
    render(<FeedbackWidget userId="u1" />);
    fireEvent.click(screen.getByLabelText('Give feedback'));
    fireEvent.click(screen.getByRole('button', { name: /send/i }));
    expect(mockSubmit).not.toHaveBeenCalled();
  });
});
