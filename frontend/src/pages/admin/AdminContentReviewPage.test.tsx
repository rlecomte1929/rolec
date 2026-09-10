/**
 * [AIQ-1821] The content review queue page.
 *
 * The assertions that matter are about honesty, not markup: the evidence must be on screen, a
 * translated source must not be labelled unsupported, a rejection must carry a reason, and a
 * failed load must never render as an empty (i.e. "all reviewed") queue.
 */
import React from 'react';
import { render, screen, waitFor, cleanup, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock('../../api/contentReview', () => ({
  listReviewFacts: vi.fn(),
  getReviewSummary: vi.fn(),
  decideFacts: vi.fn(),
  editFact: vi.fn(),
}));

import { AdminContentReviewPage } from './AdminContentReviewPage';
import {
  decideFacts,
  editFact,
  getReviewSummary,
  listReviewFacts,
} from '../../api/contentReview';

const mk = (over: Record<string, unknown> = {}) => ({
  id: 'f1',
  fact_text: 'You cannot apply for a D number.',
  fact_type: 'eligibility',
  evidence_quote: 'You cannot apply for a D number.',
  source_url: 'https://www.skatteetaten.no/en/d-number/',
  confidence: 'high',
  status: 'pending',
  evidence_status: 'verified',
  evidence_context:
    'Who can receive a D number? You cannot apply for a D number. An enterprise can request one.',
  reviewed_by: null,
  reviewed_at: null,
  created_at: null,
  destination_country: 'NO',
  topic_key: 'no.d_number',
  domain_area: 'registration',
  source_last_verified: '2026-08-12',
  ...over,
});

const page = (items: unknown[]) => ({ items, total: items.length, limit: 25, offset: 0 });

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/admin/content-review']}>
      <AdminContentReviewPage />
    </MemoryRouter>,
  );

beforeEach(() => {
  vi.mocked(getReviewSummary).mockResolvedValue({
    by_destination: { NO: { pending: 51 } },
    totals: { pending: 686 },
    pending_evidence: { verified: 192, unverified: 391, unchecked: 96 },
    pending: 686,
  } as never);
  vi.mocked(listReviewFacts).mockResolvedValue(page([mk()]) as never);
});
afterEach(cleanup);

describe('evidence is on screen', () => {
  it('shows the quote highlighted inside its source context', async () => {
    renderPage();
    // The fact text legitimately appears twice — as the claim, and inside the quoted context.
    expect(await screen.findByTestId('fact-text')).toHaveTextContent('You cannot apply for a D number.');
    // The surrounding sentence must be present, or a condition reads as an obligation.
    expect(screen.getByText(/An enterprise can request one/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /open source/i })).toHaveAttribute(
      'href',
      'https://www.skatteetaten.no/en/d-number/',
    );
  });

  it('labels a translated source as inapplicable, not unsupported', async () => {
    // France's 97 facts are English renderings of French pages. Calling those "unsupported"
    // would bury the ones that genuinely need reading.
    vi.mocked(listReviewFacts).mockResolvedValue(
      page([mk({ evidence_status: 'translated', evidence_context: '' })]) as never,
    );
    renderPage();
    expect(await screen.findByText('Translated')).toBeInTheDocument();
    expect(screen.getByText(/says nothing about whether the fact is right/i)).toBeInTheDocument();
  });

  it('marks a genuine miss as needing a read', async () => {
    vi.mocked(listReviewFacts).mockResolvedValue(
      page([mk({ evidence_status: 'unverified', evidence_context: '' })]) as never,
    );
    renderPage();
    expect(await screen.findByText('Not found in source')).toBeInTheDocument();
  });
});

describe('decisions', () => {
  it('bulk-approves the selection', async () => {
    vi.mocked(decideFacts).mockResolvedValue({ ok: true, count: 1, status: 'approved' } as never);
    renderPage();
    await screen.findByTestId('fact-text');
    fireEvent.click(screen.getByLabelText(/^Select You cannot apply/));
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    await waitFor(() =>
      expect(decideFacts).toHaveBeenCalledWith(['f1'], 'approve', undefined),
    );
  });

  it('will not let you reject without a reason', async () => {
    renderPage();
    await screen.findByTestId('fact-text');
    fireEvent.click(screen.getByLabelText(/^Select You cannot apply/));
    expect(screen.getByRole('button', { name: 'Reject' })).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/reason/i), {
      target: { value: 'Fee is invented; not on the page.' },
    });
    expect(screen.getByRole('button', { name: 'Reject' })).toBeEnabled();
  });

  it('corrects wording rather than binning an overstated fact', async () => {
    vi.mocked(editFact).mockResolvedValue({
      ok: true, fact_text: 'x', previous_fact_text: 'y',
    } as never);
    renderPage();
    await screen.findByTestId('fact-text');
    fireEvent.click(screen.getByRole('button', { name: /correct the wording/i }));
    const box = screen.getByLabelText(/corrected fact text/i);
    fireEvent.change(box, { target: { value: 'You cannot apply for a D number yourself.' } });
    fireEvent.click(screen.getByRole('button', { name: /save correction/i }));
    await waitFor(() =>
      expect(editFact).toHaveBeenCalledWith('f1', 'You cannot apply for a D number yourself.'),
    );
  });
});

describe('a failed load never reads as an empty queue', () => {
  it('shows an error with a retry, not "nothing matches"', async () => {
    vi.mocked(listReviewFacts).mockRejectedValue(new Error('boom'));
    renderPage();
    const err = await screen.findByTestId('content-review-error');
    expect(err).toHaveTextContent(/does not mean the queue is empty/i);
    expect(screen.queryByText(/nothing matches/i)).not.toBeInTheDocument();
  });

  it('distinguishes a genuinely empty result', async () => {
    vi.mocked(listReviewFacts).mockResolvedValue(page([]) as never);
    renderPage();
    expect(await screen.findByText(/nothing matches these filters/i)).toBeInTheDocument();
    expect(screen.queryByTestId('content-review-error')).not.toBeInTheDocument();
  });
});

describe('destination labels (BUG-260910-E623)', () => {
  it('shows full country names in the destination filter and fact rows', async () => {
    renderPage();
    const destFilter = await screen.findByLabelText('Destination');
    expect(destFilter).toHaveTextContent('Norway');
    expect(destFilter).not.toHaveTextContent('NO');
    expect(await screen.findByTestId('fact-text')).toBeInTheDocument();
    expect(screen.getByText(/Norway · eligibility/)).toBeInTheDocument();
  });
});
