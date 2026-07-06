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
  getFeedbackScreenshot: vi.fn().mockResolvedValue(null),
  saveDispatchContext: vi.fn().mockResolvedValue(undefined),
  dispatchPreview: vi.fn(),
  dispatchCreate: vi.fn(),
  dismissFeedback: vi.fn().mockResolvedValue(undefined),
  deleteFeedback: vi.fn().mockResolvedValue(undefined),
}));
import * as feedbackApi from '../../api/adminFeedback';
import { FeedbackTab } from './FeedbackTab';

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

// ── BR-3: dispatch + badges ────────────────────────────────────────────────

const MOCK_DISPATCH_ITEMS: UnifiedFeedbackItem[] = [
  {
    id: 'low-risk-1',
    stream: 'product',
    source_ref: null,
    text: 'Minor UI glitch',
    verdict: 'minor',
    user_id: 'u-3',
    company_id: null,
    created_at: new Date().toISOString(),
    status: 'new',
    owner: null,
    resolution: null,
    severity: 'low',
    area: 'ui',
    dispatch_status: null,
  },
  {
    id: 'high-risk-1',
    stream: 'product',
    source_ref: null,
    text: 'Critical auth bypass',
    verdict: 'bug',
    user_id: 'u-4',
    company_id: null,
    created_at: new Date().toISOString(),
    status: 'new',
    owner: null,
    resolution: null,
    severity: 'critical',
    area: 'auth',
    dispatch_status: null,
  },
  {
    id: 'isolation-risk-1',
    stream: 'product',
    source_ref: null,
    text: 'Tenant data leak',
    verdict: 'bug',
    user_id: 'u-5',
    company_id: null,
    created_at: new Date().toISOString(),
    status: 'new',
    owner: null,
    resolution: null,
    severity: 'high',
    area: 'isolation',
    dispatch_status: null,
  },
  {
    id: 'already-dispatched-1',
    stream: 'product',
    source_ref: null,
    text: 'Already handled',
    verdict: null,
    user_id: null,
    company_id: null,
    created_at: new Date().toISOString(),
    status: 'acted_on',
    owner: null,
    resolution: null,
    severity: 'low',
    area: 'ui',
    dispatch_status: 'dispatched',
  },
];

describe('FeedbackTab — dispatch + badges (BR-3)', () => {
  function renderTab() {
    return render(
      <MemoryRouter>
        <FeedbackTab />
      </MemoryRouter>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(feedbackApi.listFeedback).mockResolvedValue(MOCK_DISPATCH_ITEMS);
    vi.mocked(feedbackApi.triageFeedback).mockResolvedValue(undefined);
  });

  it('renders severity badges for each row that has severity', async () => {
    renderTab();
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    // 3 rows have severity set; 'low' appears twice (low-risk-1 and already-dispatched-1)
    const lowBadges = screen.getAllByText('low');
    expect(lowBadges.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('critical')).toBeTruthy();
    expect(screen.getByText('high')).toBeTruthy();
  });

  it('renders area badges for each row that has area', async () => {
    renderTab();
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    const uiBadges = screen.getAllByText('ui');
    expect(uiBadges.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('auth')).toBeTruthy();
    expect(screen.getByText('isolation')).toBeTruthy();
  });

  it('clicking a row opens the dispatch panel with the required context field (no separate button)', async () => {
    renderTab();
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    // There is no compact "Dispatch" button anymore — the row itself opens the panel.
    expect(screen.queryByRole('button', { name: /^dispatch$/i })).toBeNull();
    fireEvent.click(screen.getByText('Minor UI glitch'));
    expect(feedbackApi.dispatchPreview).not.toHaveBeenCalled();
    expect(await screen.findByPlaceholderText(/detail an engineer needs/i)).toBeTruthy();
  });

  it('drafts a task from context, then creates the Notion task and shows the link', async () => {
    vi.mocked(feedbackApi.dispatchPreview).mockResolvedValue({
      title: 'Fix roadmap', strategic_objective: 'g', execution_prompt: 'p', expected_output: 'o',
      validation_criteria: 'v', priority: 'P1', complexity: 'Medium',
      task_type: 'Backend Implementation', layer: 'API', product_area: 'Core Product', status: 'Ready for AI',
    });
    vi.mocked(feedbackApi.dispatchCreate).mockResolvedValue({
      dispatched: true, url: 'https://notion.so/task-1', dispatch_ref: 'https://notion.so/task-1',
    });
    renderTab();
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    fireEvent.click(screen.getByText('Minor UI glitch'));

    const ctx = await screen.findByPlaceholderText(/detail an engineer needs/i);
    fireEvent.change(ctx, { target: { value: 'repro: open /journey, spinner forever' } });
    fireEvent.click(screen.getByRole('button', { name: /draft task with ai/i }));
    await waitFor(() => expect(feedbackApi.dispatchPreview).toHaveBeenCalled());

    const createBtn = await screen.findByRole('button', { name: /create task in notion/i });
    fireEvent.click(createBtn);
    await waitFor(() => expect(feedbackApi.dispatchCreate).toHaveBeenCalled());
    const links = await screen.findAllByRole('link', { name: /notion/i });
    expect(links.length).toBeGreaterThan(0);
  });

  it('dismiss hides the row; delete asks to confirm then removes it', async () => {
    renderTab();
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    fireEvent.click(screen.getByText('Minor UI glitch'));

    // Dismiss
    fireEvent.click(await screen.findByRole('button', { name: /dismiss \(hide\)/i }));
    await waitFor(() => expect(feedbackApi.dismissFeedback).toHaveBeenCalledWith('product', 'low-risk-1', true));

    // Delete (product) → confirm gate → confirm
    fireEvent.click(screen.getByText('Critical auth bypass')); // high-risk-1 (product)
    fireEvent.click(await screen.findByRole('button', { name: /^delete$/i }));
    fireEvent.click(await screen.findByRole('button', { name: /yes, delete/i }));
    await waitFor(() => expect(feedbackApi.deleteFeedback).toHaveBeenCalledWith('high-risk-1'));
  });
});

// ── D2: Dispatched view ────────────────────────────────────────────────────

const DISPATCHED_VIEW_ITEMS: UnifiedFeedbackItem[] = [
  {
    id: 'disp-001',
    stream: 'product',
    source_ref: 'report-xyz',
    text: 'Crash on submit',
    verdict: 'bug',
    user_id: 'u-10',
    company_id: null,
    created_at: new Date(Date.now() - 3_600_000).toISOString(),
    status: 'acted_on',
    owner: null,
    resolution: null,
    severity: 'high',
    area: 'auth',
    dispatch_status: 'dispatched',
    dispatch_ref: 'DR-789',
  },
  {
    id: 'disp-002',
    stream: 'ai_answers',
    source_ref: 'trace-abc',
    text: 'Wrong answer given',
    verdict: 'bug',
    user_id: 'u-11',
    company_id: null,
    created_at: new Date(Date.now() - 7_200_000).toISOString(),
    status: 'new',
    owner: null,
    resolution: null,
    severity: 'critical',
    area: 'isolation',
    dispatch_status: 'dispatched',
    dispatch_ref: 'DR-790',
  },
];

describe('FeedbackTab — Dispatched view (D2)', () => {
  function renderTab() {
    return render(
      <MemoryRouter>
        <FeedbackTab />
      </MemoryRouter>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(feedbackApi.listFeedback).mockResolvedValue(DISPATCHED_VIEW_ITEMS);
    vi.mocked(feedbackApi.triageFeedback).mockResolvedValue(undefined);
  });

  it('has a "Dispatched" tab in the stream tab bar', async () => {
    renderTab();
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    expect(screen.getByRole('button', { name: /^Dispatched$/i })).toBeTruthy();
  });

  it('clicking Dispatched tab calls listFeedback with { dispatched: true }', async () => {
    renderTab();
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    vi.mocked(feedbackApi.listFeedback).mockClear();
    fireEvent.click(screen.getByRole('button', { name: /^Dispatched$/i }));
    await waitFor(() =>
      expect(feedbackApi.listFeedback).toHaveBeenCalledWith({ dispatched: true })
    );
  });

  it('renders dispatch_ref and severity/area badges for dispatched rows', async () => {
    renderTab();
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    vi.mocked(feedbackApi.listFeedback).mockResolvedValue(DISPATCHED_VIEW_ITEMS);
    fireEvent.click(screen.getByRole('button', { name: /^Dispatched$/i }));
    await waitFor(() =>
      expect(feedbackApi.listFeedback).toHaveBeenCalledWith({ dispatched: true })
    );
    expect(screen.getByText('DR-789')).toBeTruthy();
    expect(screen.getByText('DR-790')).toBeTruthy();
    expect(screen.getByText('high')).toBeTruthy();
    expect(screen.getByText('critical')).toBeTruthy();
    expect(screen.getByText('auth')).toBeTruthy();
    expect(screen.getByText('isolation')).toBeTruthy();
  });

  it('shows "No dispatched tickets" when dispatched list is empty', async () => {
    vi.mocked(feedbackApi.listFeedback).mockResolvedValue([]);
    renderTab();
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    fireEvent.click(screen.getByRole('button', { name: /^Dispatched$/i }));
    await waitFor(() =>
      expect(feedbackApi.listFeedback).toHaveBeenCalledWith({ dispatched: true })
    );
    expect(screen.getByText(/No dispatched tickets/i)).toBeTruthy();
  });

  it('switching to a stream tab after Dispatched calls listFeedback with stream param', async () => {
    renderTab();
    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    fireEvent.click(screen.getByRole('button', { name: /^Dispatched$/i }));
    await waitFor(() =>
      expect(feedbackApi.listFeedback).toHaveBeenCalledWith({ dispatched: true })
    );
    vi.mocked(feedbackApi.listFeedback).mockClear();
    // Click the Product stream tab (first occurrence = the tab bar button)
    fireEvent.click(screen.getAllByRole('button', { name: /^Product$/i })[0]);
    await waitFor(() =>
      expect(feedbackApi.listFeedback).toHaveBeenCalledWith({ stream: 'product' })
    );
  });
});
