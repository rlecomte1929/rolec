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

vi.mock('../api/productFeedback', () => ({
  submitProductFeedback: vi.fn(),
  getMyReports: vi.fn(),
}));

import { submitProductFeedback, getMyReports } from '../api/productFeedback';
import { FeedbackWidget } from './FeedbackWidget';

const mockSubmit = submitProductFeedback as unknown as ReturnType<typeof vi.fn>;
const mockGetReports = getMyReports as unknown as ReturnType<typeof vi.fn>;

afterEach(cleanup);
beforeEach(() => {
  mockSubmit.mockReset();
  mockGetReports.mockReset();
});

function openAndType(text: string) {
  fireEvent.click(screen.getByLabelText('Give feedback'));
  const box = screen.getByRole('textbox');
  fireEvent.change(box, { target: { value: text } });
  return box;
}

function openMyReports() {
  fireEvent.click(screen.getByLabelText('Give feedback'));
  fireEvent.click(screen.getByRole('button', { name: /my reports/i }));
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

  it('success state shows the submitted report_id reference label', async () => {
    mockSubmit.mockResolvedValue({ ok: true, report_id: 'BUG-x' });
    render(<FeedbackWidget userId="u1" />);
    openAndType('Something broke');
    fireEvent.click(screen.getByRole('button', { name: /send/i }));
    // The widget generates the report_id client-side and shows it in the success state
    await waitFor(() =>
      expect(screen.getByText(/reference/i)).toBeInTheDocument()
    );
    // The generated ID follows the pattern BUG-YYMMDD-XXXX
    expect(screen.getByText(/BUG-\d{6}-/)).toBeInTheDocument();
  });
});

// ── R2: My reports view ───────────────────────────────────────────────────────

const MOCK_REPORTS = [
  {
    report_id: 'BUG-260630-1111',
    category: 'bug',
    message_excerpt: 'Button is broken',
    status: 'new',
    severity: 'low',
    area: 'ui',
    dispatch_status: null,
    created_at: new Date().toISOString(),
  },
  {
    report_id: 'IDR-260630-2222',
    category: 'idea',
    message_excerpt: 'Add dark mode',
    status: 'triaged',
    severity: null,
    area: null,
    dispatch_status: null,
    created_at: new Date().toISOString(),
  },
  {
    report_id: 'BUG-260630-3333',
    category: 'bug',
    message_excerpt: 'Login fails',
    status: 'dispatched',
    severity: 'high',
    area: 'auth',
    dispatch_status: 'dispatched',
    created_at: new Date().toISOString(),
  },
  {
    report_id: 'OTH-260630-4444',
    category: 'other',
    message_excerpt: 'General question',
    status: 'resolved',
    severity: null,
    area: null,
    dispatch_status: null,
    created_at: new Date().toISOString(),
  },
  {
    report_id: 'BUG-260630-5555',
    category: 'bug',
    message_excerpt: 'Null status report',
    status: null,
    severity: null,
    area: null,
    dispatch_status: null,
    created_at: new Date().toISOString(),
  },
];

describe('FeedbackWidget — My reports (R2)', () => {
  it('renders reports with correct status badge labels', async () => {
    mockGetReports.mockResolvedValue({ reports: MOCK_REPORTS });
    render(<FeedbackWidget userId="u1" />);
    openMyReports();
    await waitFor(() => expect(mockGetReports).toHaveBeenCalledTimes(1));
    // report IDs visible
    expect(await screen.findByText('BUG-260630-1111')).toBeInTheDocument();
    // status badge labels
    expect(screen.getByText('new')).toBeInTheDocument();
    expect(screen.getByText('triaged')).toBeInTheDocument();
    expect(screen.getByText('dispatched')).toBeInTheDocument();
    expect(screen.getByText('resolved')).toBeInTheDocument();
    // null status → "submitted"
    expect(screen.getByText('submitted')).toBeInTheDocument();
  });

  it('shows "No reports yet" for an empty reports list', async () => {
    mockGetReports.mockResolvedValue({ reports: [] });
    render(<FeedbackWidget userId="u1" />);
    openMyReports();
    await waitFor(() =>
      expect(screen.getByText(/no reports yet/i)).toBeInTheDocument()
    );
  });

  it('shows error message when getMyReports rejects', async () => {
    mockGetReports.mockRejectedValue(new Error('Network error'));
    render(<FeedbackWidget userId="u1" />);
    openMyReports();
    await waitFor(() =>
      expect(screen.getByText(/could not load/i)).toBeInTheDocument()
    );
  });

  it('renders severity and area chips when present', async () => {
    mockGetReports.mockResolvedValue({ reports: MOCK_REPORTS });
    render(<FeedbackWidget userId="u1" />);
    openMyReports();
    await waitFor(() => expect(mockGetReports).toHaveBeenCalledTimes(1));
    // severity chips
    expect(await screen.findByText('low')).toBeInTheDocument();
    expect(screen.getByText('high')).toBeInTheDocument();
    // area chip
    expect(screen.getByText('auth')).toBeInTheDocument();
  });
});
