/**
 * FeedbackWidget — routes submissions through the backend (POST /api/feedback) instead of a
 * direct Supabase insert (which fails for ReloPass-session users), attaches diagnostics,
 * supports screenshot capture + markup (AIQ-1480), and lists the caller's reports ("My reports").
 * The productFeedback API is mocked.
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
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
beforeEach(() => { mockSubmit.mockReset(); mockGetReports.mockReset(); });

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

  it('[AIQ-1480] "Screenshot" reveals full-page / region capture options', () => {
    render(<FeedbackWidget userId="u1" />);
    openAndType('needs a shot');
    fireEvent.click(screen.getByRole('button', { name: /^screenshot$/i }));
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

// ── R2: My reports view ───────────────────────────────────────────────────────

const MOCK_REPORTS = [
  { report_id: 'BUG-260630-1111', category: 'bug', message_excerpt: 'Button is broken', status: 'new', severity: 'low', area: 'ui', dispatch_status: null, created_at: new Date().toISOString() },
  { report_id: 'IDR-260630-2222', category: 'idea', message_excerpt: 'Add dark mode', status: 'triaged', severity: null, area: null, dispatch_status: null, created_at: new Date().toISOString() },
  { report_id: 'BUG-260630-3333', category: 'bug', message_excerpt: 'Login fails', status: 'dispatched', severity: 'high', area: 'auth', dispatch_status: 'dispatched', created_at: new Date().toISOString() },
  { report_id: 'OTH-260630-4444', category: 'other', message_excerpt: 'General question', status: 'resolved', severity: null, area: null, dispatch_status: null, created_at: new Date().toISOString() },
  { report_id: 'BUG-260630-5555', category: 'bug', message_excerpt: 'Null status report', status: null, severity: null, area: null, dispatch_status: null, created_at: new Date().toISOString() },
];

describe('FeedbackWidget — My reports (R2)', () => {
  it('renders reports with correct status badge labels', async () => {
    mockGetReports.mockResolvedValue({ reports: MOCK_REPORTS });
    render(<FeedbackWidget userId="u1" />);
    openMyReports();
    await waitFor(() => expect(mockGetReports).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('BUG-260630-1111')).toBeInTheDocument();
    expect(screen.getByText('new')).toBeInTheDocument();
    expect(screen.getByText('triaged')).toBeInTheDocument();
    expect(screen.getByText('dispatched')).toBeInTheDocument();
    expect(screen.getByText('resolved')).toBeInTheDocument();
    expect(screen.getByText('submitted')).toBeInTheDocument(); // null status → 'submitted'
  });

  it('shows "No reports yet" for an empty list', async () => {
    mockGetReports.mockResolvedValue({ reports: [] });
    render(<FeedbackWidget userId="u1" />);
    openMyReports();
    await waitFor(() => expect(screen.getByText(/no reports yet/i)).toBeInTheDocument());
  });

  it('shows an error message when getMyReports rejects', async () => {
    mockGetReports.mockRejectedValue(new Error('Network error'));
    render(<FeedbackWidget userId="u1" />);
    openMyReports();
    await waitFor(() => expect(screen.getByText(/could not load/i)).toBeInTheDocument());
  });

  it('renders severity and area chips when present', async () => {
    mockGetReports.mockResolvedValue({ reports: MOCK_REPORTS });
    render(<FeedbackWidget userId="u1" />);
    openMyReports();
    await waitFor(() => expect(mockGetReports).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('low')).toBeInTheDocument();
    expect(screen.getByText('high')).toBeInTheDocument();
    expect(screen.getByText('auth')).toBeInTheDocument();
  });
});
