import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AdminResearchRequestsPage } from '../AdminResearchRequestsPage';
import * as api from '../../../api/researchRequests';

vi.mock('../AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock('../../../api/researchRequests', () => ({
  listResearchRequests: vi.fn(),
  resolveResearchRequest: vi.fn(),
  completeResearchRequest: vi.fn(),
}));

const sample = [
  {
    id: 'rr-1', corridor: 'US→JP', status: 'pending', purpose: 'employment',
    estimated_cost: 500, actual_cost: null, created_at: '2026-06-29T00:00:00Z',
  },
];

describe('AdminResearchRequestsPage', () => {
  beforeEach(() => {
    (api.listResearchRequests as ReturnType<typeof vi.fn>).mockResolvedValue(sample);
    (api.resolveResearchRequest as ReturnType<typeof vi.fn>).mockResolvedValue({ ...sample[0], status: 'in_progress' });
  });

  it('lists research requests from the API', async () => {
    render(<AdminResearchRequestsPage />);
    await waitFor(() => expect(api.listResearchRequests).toHaveBeenCalled());
    expect(await screen.findByText('US→JP')).toBeTruthy();
  });

  it('approves a pending request', async () => {
    render(<AdminResearchRequestsPage />);
    fireEvent.click(await screen.findByText('Approve'));
    await waitFor(() => expect(api.resolveResearchRequest).toHaveBeenCalledWith('rr-1', 'approved'));
  });
});
