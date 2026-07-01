/**
 * AnswerFeedback — end-user 👍/👎 helpfulness control on policy-assistant answers.
 *
 * Mocks api/policyHelpfulness directly (no axios / supabase involved).
 * Pattern mirrors ImmigrationAnswerPanel.test.tsx.
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

expect.extend(matchers);

vi.mock('../../../api/policyHelpfulness', () => ({
  submitHelpfulness: vi.fn(),
}));

import { submitHelpfulness } from '../../../api/policyHelpfulness';
import { AnswerFeedback } from '../AnswerFeedback';

const mockSubmit = submitHelpfulness as unknown as ReturnType<typeof vi.fn>;

afterEach(cleanup);
// Block statement prevents the spy from being returned (and registered as a vitest cleanup hook)
beforeEach(() => { mockSubmit.mockReset(); });

describe('AnswerFeedback', () => {
  it('renders nothing when traceSessionId is null', () => {
    const { container } = render(<AnswerFeedback traceSessionId={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when traceSessionId is undefined', () => {
    const { container } = render(<AnswerFeedback traceSessionId={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it('shows thumbs buttons when traceSessionId is present', () => {
    render(<AnswerFeedback traceSessionId="trace-abc" />);
    expect(screen.getByRole('button', { name: 'Helpful' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Not helpful' })).toBeInTheDocument();
    expect(screen.getByText(/was this helpful/i)).toBeInTheDocument();
  });

  it('calls submitHelpfulness with helpful=true on 👍 and shows thanks', async () => {
    mockSubmit.mockResolvedValue(undefined);
    render(<AnswerFeedback traceSessionId="trace-abc" />);
    fireEvent.click(screen.getByRole('button', { name: 'Helpful' }));
    await waitFor(() =>
      expect(mockSubmit).toHaveBeenCalledWith('trace-abc', true, undefined),
    );
    await waitFor(() =>
      expect(screen.getByText(/thanks.*feedback recorded/i)).toBeInTheDocument(),
    );
  });

  it('calls submitHelpfulness with helpful=false on 👎 and shows thanks', async () => {
    mockSubmit.mockResolvedValue(undefined);
    render(<AnswerFeedback traceSessionId="trace-abc" />);
    fireEvent.click(screen.getByRole('button', { name: 'Not helpful' }));
    await waitFor(() =>
      expect(mockSubmit).toHaveBeenCalledWith('trace-abc', false, undefined),
    );
    await waitFor(() =>
      expect(screen.getByText(/thanks.*feedback recorded/i)).toBeInTheDocument(),
    );
  });

  it('hides thumbs buttons after successful submission', async () => {
    mockSubmit.mockResolvedValue(undefined);
    render(<AnswerFeedback traceSessionId="trace-abc" />);
    fireEvent.click(screen.getByRole('button', { name: 'Helpful' }));
    await waitFor(() => expect(mockSubmit).toHaveBeenCalled());
    // After submission the thumbs are gone (replaced by thanks message)
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Helpful' })).not.toBeInTheDocument(),
    );
  });

  it('shows an error message on API failure', async () => {
    // Synchronous throw avoids the unhandled-rejection timing issue in jsdom/vitest:
    // a throw inside an async fn with try/catch is caught before it becomes a
    // globally-detectable unhandled promise rejection.
    mockSubmit.mockImplementation(() => { throw new Error('network error'); });
    render(<AnswerFeedback traceSessionId="trace-abc" />);
    fireEvent.click(screen.getByRole('button', { name: 'Helpful' }));
    await waitFor(() =>
      expect(screen.getByText(/couldn.*t save/i)).toBeInTheDocument(),
    );
    // Buttons remain so the user can retry
    expect(screen.getByRole('button', { name: 'Helpful' })).toBeInTheDocument();
  });
});
