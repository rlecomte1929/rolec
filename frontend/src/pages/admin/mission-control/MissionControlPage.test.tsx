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
}));
vi.mock('../AdminLayout', () => ({
  AdminLayout: ({ children, headerRight }: { children: React.ReactNode; headerRight?: React.ReactNode }) => (
    <div>{headerRight}{children}</div>
  ),
}));

import { listWorkItems, syncWorkItems, patchWorkItem } from '../../../api/missionControl';
import { MissionControlPage } from './MissionControlPage';

const mockList = listWorkItems as unknown as ReturnType<typeof vi.fn>;
const mockSync = syncWorkItems as unknown as ReturnType<typeof vi.fn>;
const mockPatch = patchWorkItem as unknown as ReturnType<typeof vi.fn>;

afterEach(cleanup);
beforeEach(() => { mockList.mockReset(); mockSync.mockReset(); mockPatch.mockReset(); });

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
});
