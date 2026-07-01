/**
 * Mission Control P1 — the demands console renders triaged demands, surfaces the
 * store-not-ready state, syncs, and updates status. API + AdminLayout mocked (keeps
 * the admin shell + supabase client out of jsdom).
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../../../api/missionControl', () => ({
  listWorkItems: vi.fn(),
  syncWorkItems: vi.fn(),
  retriageWorkItem: vi.fn(),
  patchWorkItem: vi.fn(),
  dispatchWorkItem: vi.fn(),
  planWorkItem: vi.fn(),
  approvePlan: vi.fn(),
}));
vi.mock('../AdminLayout', () => ({
  AdminLayout: ({ children, headerRight }: { children: React.ReactNode; headerRight?: React.ReactNode }) => (
    <div>{headerRight}{children}</div>
  ),
}));

import { listWorkItems, syncWorkItems, patchWorkItem, dispatchWorkItem, planWorkItem, approvePlan } from '../../../api/missionControl';
import { MissionControlPage } from './MissionControlPage';

const mockList = listWorkItems as unknown as ReturnType<typeof vi.fn>;
const mockSync = syncWorkItems as unknown as ReturnType<typeof vi.fn>;
const mockPatch = patchWorkItem as unknown as ReturnType<typeof vi.fn>;
const mockDispatch = dispatchWorkItem as unknown as ReturnType<typeof vi.fn>;
const mockPlan = planWorkItem as unknown as ReturnType<typeof vi.fn>;
const mockApprove = approvePlan as unknown as ReturnType<typeof vi.fn>;

afterEach(cleanup);
beforeEach(() => {
  mockList.mockReset(); mockSync.mockReset(); mockPatch.mockReset();
  mockDispatch.mockReset(); mockPlan.mockReset(); mockApprove.mockReset();
});

describe('MissionControlPage', () => {
  it('renders triaged demands from the API', async () => {
    mockList.mockResolvedValue({
      table_ready: true,
      items: [{ id: '1', source: 'feedback', kind: 'bug', title: 'Save crashes', body: '500 error', status: 'triaged', priority: 'P1', auto_fixable: false, triage_json: { rationale: 'bug/P1/medium' } }],
    });
    render(<MissionControlPage />);
    expect(await screen.findByText('Save crashes')).toBeInTheDocument();
    expect(screen.getByText('P1')).toBeInTheDocument();
    expect(screen.getByText('bug')).toBeInTheDocument();
  });

  it('shows the store-not-ready notice when the table is not applied', async () => {
    mockList.mockResolvedValue({ table_ready: false, items: [] });
    render(<MissionControlPage />);
    expect(await screen.findByTestId('store-not-ready')).toBeInTheDocument();
  });

  it('Sync demands calls the API', async () => {
    mockList.mockResolvedValue({ table_ready: true, items: [] });
    mockSync.mockResolvedValue({ ok: true, inserted: 2 });
    render(<MissionControlPage />);
    await screen.findByTestId('empty');
    fireEvent.click(screen.getByRole('button', { name: /sync demands/i }));
    await waitFor(() => expect(mockSync).toHaveBeenCalled());
  });

  it('changing a demand status calls patchWorkItem', async () => {
    mockList.mockResolvedValue({
      table_ready: true,
      items: [{ id: '1', source: 'feedback', kind: 'bug', title: 'X', status: 'triaged', priority: 'P2', auto_fixable: false }],
    });
    mockPatch.mockResolvedValue({ ok: true });
    render(<MissionControlPage />);
    await screen.findByText('X');
    fireEvent.change(screen.getByLabelText('Status for X'), { target: { value: 'done' } });
    await waitFor(() => expect(mockPatch).toHaveBeenCalledWith('1', { status: 'done' }));
  });

  it('shows Execute only for agent-eligible demands and dispatches on confirm', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    mockList.mockResolvedValue({
      table_ready: true,
      items: [
        { id: 'a', source: 'feedback', kind: 'bug', title: 'Typo fix', status: 'triaged', priority: 'P3', auto_fixable: true, triage_json: { blocked: false } },
        { id: 'b', source: 'feedback', kind: 'bug', title: 'Auth bug', status: 'triaged', priority: 'P1', auto_fixable: false },
      ],
    });
    mockDispatch.mockResolvedValue({ ok: true, run_id: 'r1', pr_url: 'https://github.com/o/r/pull/3' });
    render(<MissionControlPage />);
    await screen.findByText('Typo fix');
    const buttons = screen.getAllByRole('button', { name: /execute/i });
    expect(buttons).toHaveLength(1); // only the agent-eligible demand
    fireEvent.click(buttons[0]);
    await waitFor(() => expect(mockDispatch).toHaveBeenCalledWith('a'));
    confirmSpy.mockRestore();
  });

  it('does not dispatch when the confirm is cancelled', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    mockList.mockResolvedValue({
      table_ready: true,
      items: [{ id: 'a', source: 'feedback', kind: 'bug', title: 'Typo', status: 'triaged', priority: 'P3', auto_fixable: true, triage_json: { blocked: false } }],
    });
    render(<MissionControlPage />);
    await screen.findByText('Typo');
    fireEvent.click(screen.getByRole('button', { name: /execute/i }));
    expect(mockDispatch).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('Plan button drafts a plan', async () => {
    mockList.mockResolvedValue({
      table_ready: true,
      items: [{ id: '1', source: 'feedback', kind: 'bug', title: 'Crash', status: 'triaged', priority: 'P1', auto_fixable: false }],
    });
    mockPlan.mockResolvedValue({ ok: true, plan: { summary: 's', risk: 'low', approved: false } });
    render(<MissionControlPage />);
    await screen.findByText('Crash');
    fireEvent.click(screen.getByRole('button', { name: 'Plan' }));
    await waitFor(() => expect(mockPlan).toHaveBeenCalledWith('1'));
  });

  it('renders an existing plan and approves it', async () => {
    mockList.mockResolvedValue({
      table_ready: true,
      items: [{
        id: '1', source: 'feedback', kind: 'bug', title: 'Crash', status: 'planned', priority: 'P1', auto_fixable: false,
        plan_json: { summary: 'Rename the handler', affected_files: ['a.ts'], risk: 'medium', approved: false },
      }],
    });
    mockApprove.mockResolvedValue({ ok: true, approved: true });
    render(<MissionControlPage />);
    expect(await screen.findByTestId('plan')).toBeInTheDocument();
    expect(screen.getByText(/Rename the handler/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /approve plan/i }));
    await waitFor(() => expect(mockApprove).toHaveBeenCalledWith('1'));
  });
});
