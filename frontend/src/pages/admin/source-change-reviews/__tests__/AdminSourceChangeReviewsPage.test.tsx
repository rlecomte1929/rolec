import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
// eslint-disable-next-line import/order
import { AdminSourceChangeReviewsPage } from '../AdminSourceChangeReviewsPage';

vi.mock('../../../../api/client', () => ({
  sourceChangeReviewAPI: {
    listPending: vi.fn().mockResolvedValue({
      items: [
        {
          id: 'rev-1',
          rule_version_id: 'rv-1',
          source_name: 'Cantonal migration office',
          source_url: 'https://example.org/permits',
          old_excerpt: 'The fee is CHF 100.',
          new_excerpt: 'The fee is CHF 140.',
          changed_sections: [{ kind: 'added', category: 'fee', text: 'The fee is CHF 140.' }],
          created_at: '2026-06-06T00:00:00Z',
        },
        {
          id: 'rev-2',
          rule_version_id: 'rv-2',
          source_name: 'Tax authority',
          old_excerpt: 'within 14 days',
          new_excerpt: 'within 8 days',
          changed_sections: [{ kind: 'added', category: 'date', text: 'within 8 days' }],
        },
      ],
      count: 2,
    }),
    approve: vi.fn().mockResolvedValue({ status: 'approved', notified_case_ids: ['case-A', 'case-B'] }),
    reject: vi.fn().mockResolvedValue({ status: 'rejected' }),
  },
}));

import { sourceChangeReviewAPI } from '../../../../api/client';

const renderPage = () =>
  render(
    <MemoryRouter>
      <AdminSourceChangeReviewsPage />
    </MemoryRouter>,
  );

describe('AdminSourceChangeReviewsPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('lists pending material changes with their diff', async () => {
    renderPage();
    await waitFor(() => expect(sourceChangeReviewAPI.listPending).toHaveBeenCalled());
    expect(await screen.findByText('Cantonal migration office')).toBeInTheDocument();
    expect(screen.getByText('Tax authority')).toBeInTheDocument();
    expect(screen.getByText('The fee is CHF 100.')).toBeInTheDocument();
    expect(screen.getByText('The fee is CHF 140.')).toBeInTheDocument();
  });

  it('approves a change, notifies cases, and removes it from the queue', async () => {
    renderPage();
    await screen.findByText('Cantonal migration office');

    fireEvent.click(screen.getAllByRole('button', { name: /approve & notify/i })[0]);

    await waitFor(() => expect(sourceChangeReviewAPI.approve).toHaveBeenCalledWith('rev-1'));
    expect(await screen.findByText(/notified 2 active cases/i)).toBeInTheDocument();
    // The approved item is gone; the other remains.
    await waitFor(() =>
      expect(screen.queryByText('Cantonal migration office')).not.toBeInTheDocument(),
    );
    expect(screen.getByText('Tax authority')).toBeInTheDocument();
  });

  it('rejects a change without notifying anyone', async () => {
    renderPage();
    await screen.findByText('Tax authority');

    fireEvent.click(screen.getAllByRole('button', { name: /reject/i })[1]);

    await waitFor(() => expect(sourceChangeReviewAPI.reject).toHaveBeenCalledWith('rev-2'));
    expect(sourceChangeReviewAPI.approve).not.toHaveBeenCalled();
    expect(await screen.findByText(/no users notified/i)).toBeInTheDocument();
  });

  it('shows an empty state when nothing is pending', async () => {
    (sourceChangeReviewAPI.listPending as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      items: [],
      count: 0,
    });
    renderPage();
    expect(await screen.findByText(/no pending material changes/i)).toBeInTheDocument();
  });
});
