/**
 * AIQ-1894 — bulk approve/reject on the admin catalog queue. Verifies the wiring
 * of the shared useRowSelection + BulkActionBar into AdminCatalogQueuePage:
 * selecting pending rows and firing a bulk action applies it to every selected id,
 * and the per-row action still works. AdminLayout/DiscoverSection and the API are
 * mocked so only the ticket-list + bulk logic is under test.
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock('../DiscoverSection', () => ({ DiscoverSection: () => null }));
vi.mock('../../../api/adminCatalog', () => ({
  listAdminDestinationRequests: vi.fn(),
  listAllowlist: vi.fn(),
  listDemandGaps: vi.fn(),
  listIntakeCorridors: vi.fn(),
  resolveDestinationRequest: vi.fn(),
  addAllowlistEntry: vi.fn(),
  fillDemandGap: vi.fn(),
}));

import {
  listAdminDestinationRequests,
  listAllowlist,
  listDemandGaps,
  listIntakeCorridors,
  resolveDestinationRequest,
} from '../../../api/adminCatalog';
import { AdminCatalogQueuePage } from '../AdminCatalogQueuePage';

const asMock = (fn: unknown) => fn as ReturnType<typeof vi.fn>;

function ticket(id: string, over: Record<string, unknown> = {}) {
  return {
    id,
    city: `City${id}`,
    country: 'France',
    category: 'movers',
    status: 'pending',
    created_at: '2026-08-01T00:00:00Z',
    requested_by: 'user1234',
    company_id: 'comp1234',
    notes: null,
    resolved_at: null,
    resolved_by: null,
    ...over,
  };
}

beforeEach(() => {
  asMock(listAllowlist).mockResolvedValue([]);
  asMock(listDemandGaps).mockResolvedValue([]);
  asMock(listIntakeCorridors).mockResolvedValue([]);
  asMock(listAdminDestinationRequests).mockResolvedValue([ticket('1'), ticket('2')]);
  asMock(resolveDestinationRequest).mockImplementation(
    async (id: string, status: string) => ticket(id, { status }),
  );
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('AdminCatalogQueuePage bulk actions (AIQ-1894)', () => {
  it('bulk-approves every selected pending request in one action', async () => {
    render(<AdminCatalogQueuePage />);
    await screen.findByText(/City1, France/);

    fireEvent.click(screen.getByLabelText(/select all pending/i));
    fireEvent.click(
      screen.getByRole('button', { name: /approve & allowlist \(2\)/i }),
    );

    await waitFor(() =>
      expect(asMock(resolveDestinationRequest)).toHaveBeenCalledTimes(2),
    );
    expect(asMock(resolveDestinationRequest)).toHaveBeenCalledWith('1', 'approved');
    expect(asMock(resolveDestinationRequest)).toHaveBeenCalledWith('2', 'approved');
  });

  it('still supports the per-row action', async () => {
    render(<AdminCatalogQueuePage />);
    await screen.findByText(/City1, France/);

    // Per-row "Reject" (no count); the bulk button is "Reject (2)".
    const rowReject = screen.getAllByRole('button', { name: /^reject$/i })[0];
    fireEvent.click(rowReject);

    await waitFor(() =>
      expect(asMock(resolveDestinationRequest)).toHaveBeenCalledWith('1', 'rejected'),
    );
  });
});
