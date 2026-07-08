/**
 * FeedbackWidget — routes submissions through the backend (POST /api/feedback) instead of a
 * direct Supabase insert (which fails for ReloPass-session users), attaches diagnostics, and
 * supports screenshot capture + markup (AIQ-1480). The productFeedback API is mocked.
 *
 * NOTE: this widget was reverted on main (#1400/#1404), which also dropped the "My reports"
 * tab. Those tests were removed here to match the shipped component; restoring that tab is
 * tracked as a SEPARATE regression (filed from AIQ-1480 handoff), not part of this task.
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../api/productFeedback', () => ({
  submitProductFeedback: vi.fn(),
}));

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
  it('submits via the backend API (with diagnostics) and shows success', async () => {
    mockSubmit.mockResolvedValue({ ok: true, report_id: 'BUG-x' });
    render(<FeedbackWidget userId="u1" />);
    openAndType('ÇVX');
    fireEvent.click(screen.getByRole('button', { name: /send/i }));
    await waitFor(() => expect(mockSubmit).toHaveBeenCalledTimes(1));
    const arg = mockSubmit.mock.calls[0][0];
    expect(arg.category).toBe('bug');
    expect(arg.message).toBe('ÇVX');
    expect(typeof arg.page_url).toBe('string');
    expect(arg.client_context).toBeTruthy(); // diagnostics attached (restored from the revert)
    await waitFor(() => expect(screen.getByText(/received/i)).toBeInTheDocument());
  });

  it('does not submit an empty message', () => {
    render(<FeedbackWidget userId="u1" />);
    fireEvent.click(screen.getByLabelText('Give feedback'));
    fireEvent.click(screen.getByRole('button', { name: /send/i }));
    expect(mockSubmit).not.toHaveBeenCalled();
  });

  it('success shows the generated report_id reference', async () => {
    mockSubmit.mockResolvedValue({ ok: true, report_id: 'BUG-x' });
    render(<FeedbackWidget userId="u1" />);
    openAndType('Something broke');
    fireEvent.click(screen.getByRole('button', { name: /send/i }));
    await waitFor(() => expect(screen.getByText(/reference/i)).toBeInTheDocument());
    expect(screen.getByText(/BUG-\d{6}-/)).toBeInTheDocument();
  });

  it('[AIQ-1480] "Attach Screenshot" reveals full-page / region capture options', () => {
    render(<FeedbackWidget userId="u1" />);
    openAndType('needs a shot');
    fireEvent.click(screen.getByRole('button', { name: /attach screenshot/i }));
    expect(screen.getByRole('button', { name: /full page/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /select region/i })).toBeInTheDocument();
  });

  it('[AIQ-1480] shows the storage-capacity notice after a submit that stored a screenshot', async () => {
    mockSubmit.mockResolvedValue({
      ok: true, report_id: 'BUG-x',
      screenshot_storage: { used_mb: 12, budget_mb: 500, remaining_mb: 488 },
    });
    render(<FeedbackWidget userId="u1" />);
    openAndType('with shot');
    fireEvent.click(screen.getByRole('button', { name: /send/i }));
    const note = await screen.findByText(/image storage/i);
    expect(note.textContent).toContain('488 MB');
    expect(note.textContent).toContain('500 MB');
  });
});
