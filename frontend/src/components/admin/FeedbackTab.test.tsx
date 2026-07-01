/**
 * FeedbackTab — smoke tests for stream tabs and triage actions.
 * Mocks api/adminFeedback to avoid the jsdom supabase import trap.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import type { UnifiedFeedbackItem } from '../../api/adminFeedback';

vi.mock('../../api/adminFeedback', () => ({
  listFeedback: vi.fn(),
  triageFeedback: vi.fn(),
}));

import { FeedbackTab } from './FeedbackTab';
import * as feedbackApi from '../../api/adminFeedback';

const MOCK_ITEMS: UnifiedFeedbackItem[] = [
  {
    id: 'aaaa-1111',
    stream: 'product',
    source_ref: 'report-001',
    text: 'Button is broken',
    verdict: 'bug',
    user_id: 'u-1',
    company_id: null,
    created_at: new Date(Date.now() - 3_600_000).toISOString(),
    status: 'new',
    owner: null,
    resolution: null,
  },
  {
    id: 'bbbb-2222',
    stream: 'helpfulness',
    source_ref: 'trace-001',
    text: 'Great answer',
    verdict: 'thumbs_up',
    user_id: 'u-2',
    company_id: 'co-1',
    created_at: new Date(Date.now() - 7_200_000).toISOString(),
    status: null,
    owner: null,
    resolution: null,
  },
];

describe('FeedbackTab', () => {
  beforeEach(() => {
    vi.mocked(feedbackApi.listFeedback).mockResolvedValue(MOCK_ITEMS);
    vi.mocked(feedbackApi.triageFeedback).mockResolvedValue(undefined);
  });

  function renderTab() {
    return render(
      <MemoryRouter>
        <FeedbackTab />
      </MemoryRouter>
    );
  }

  it('renders stream tabs including Product, AI Answers and Helpfulness', async () => {
    renderTab();
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    expect(screen.getAllByText('Product').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Helpfulness').length).toBeGreaterThan(0);
    expect(screen.getAllByText('AI Answers').length).toBeGreaterThan(0);
  });

  it('shows rows from both streams by default', async () => {
    renderTab();
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    expect(screen.getByText('Button is broken')).toBeTruthy();
    expect(screen.getByText('Great answer')).toBeTruthy();
  });

  it('calls listFeedback with stream param when stream tab clicked', async () => {
    renderTab();
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    // Click the first occurrence (the tab button)
    fireEvent.click(screen.getAllByText('Helpfulness')[0]);
    await waitFor(() =>
      expect(feedbackApi.listFeedback).toHaveBeenCalledWith({ stream: 'helpfulness' })
    );
  });

  it('calls triageFeedback on status change', async () => {
    renderTab();
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    const selects = screen.getAllByRole('combobox');
    fireEvent.change(selects[0], { target: { value: 'reviewed' } });
    await waitFor(() =>
      expect(feedbackApi.triageFeedback).toHaveBeenCalledWith(
        'product',
        'aaaa-1111',
        { status: 'reviewed' }
      )
    );
  });
});
