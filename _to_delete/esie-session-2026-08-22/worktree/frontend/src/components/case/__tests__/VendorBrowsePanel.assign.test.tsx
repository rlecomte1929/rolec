/**
 * AIQ-1896 — the browse → assign half of the vendor journey.
 *
 * Before this, public.case_vendor_shortlist had no writer at all: HR could open
 * the directory but nothing could attach a vendor to a case. These tests pin the
 * two behaviours that make the loop real — the action exists only when there is a
 * case to assign into, and a click actually calls the write endpoint with that
 * case's id.
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { hrAPI } from '../../../api/client';
import { VendorBrowsePanel } from '../VendorBrowsePanel';

vi.mock('../../../api/client', () => ({
  hrAPI: {
    getVendors: vi.fn(),
    getVendorCorridors: vi.fn(),
    assignVendorToCase: vi.fn(),
    // [AIQ-2024] The panel now asks the server which vendors are already on the
    // case, instead of only remembering clicks made this session.
    getCaseVendors: vi.fn(),
  },
}));

const mocked = <T,>(fn: T) => fn as T & ReturnType<typeof vi.fn>;

const VENDOR = {
  id: 'vendor-uuid-1',
  name: 'NestFinders Europe',
  service_categories: ['housing_search'],
  corridors: ['ES-IE'],
  contact_email: 'hello@nestfinders.example',
  is_approved: true,
};

const ASSIGNED_ROW = {
  shortlist_id: 'row-1',
  vendor_id: 'vendor-uuid-1',   // matches VENDOR.id
  category: 'housing',
  status: 'Assigned',
  contact_name: null,
  contact_email: null,
  vendor_name: 'NestFinders Europe',
  vendor_website: null,
};

function renderPanel(caseId?: string | null) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <VendorBrowsePanel isOpen onClose={() => {}} caseId={caseId} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('VendorBrowsePanel — assign to case', () => {
  it('offers no assign action without a caseId (read-only browse)', async () => {
    mocked(hrAPI.getVendors).mockResolvedValue({ vendors: [VENDOR] });
    mocked(hrAPI.getVendorCorridors).mockResolvedValue({ corridors: [] });
    mocked(hrAPI.getCaseVendors).mockResolvedValue([]);

    renderPanel(null);

    await waitFor(() => expect(screen.getByText('NestFinders Europe')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /assign to case/i })).not.toBeInTheDocument();
    // The heading must not promise an action the panel cannot perform.
    expect(screen.getByText(/browse the approved vendor directory/i)).toBeInTheDocument();
  });

  it('assigns the vendor to the given case and confirms it', async () => {
    mocked(hrAPI.getVendors).mockResolvedValue({ vendors: [VENDOR] });
    mocked(hrAPI.getVendorCorridors).mockResolvedValue({ corridors: [] });
    // [AIQ-2024] The badge is server truth now, not local state: empty on open,
    // then carrying the row once the assign has been refetched. That is precisely
    // the behaviour worth having — it survives a reload.
    mocked(hrAPI.getCaseVendors)
      .mockResolvedValueOnce([])
      .mockResolvedValue([ASSIGNED_ROW]);
    mocked(hrAPI.assignVendorToCase).mockResolvedValue({
      shortlist_id: 'row-1',
      vendor_id: 'vendor-uuid-1',
      category: 'housing',
      status: 'Assigned',
      contact_name: null,
      contact_email: null,
      vendor_name: 'NestFinders Europe',
      vendor_website: null,
    });

    renderPanel('case-abc');

    const button = await screen.findByRole('button', { name: /assign to case/i });
    fireEvent.click(button);

    await waitFor(() =>
      expect(hrAPI.assignVendorToCase).toHaveBeenCalledWith('case-abc', {
        vendor_id: 'vendor-uuid-1',
      }),
    );
    // The row flips to a confirmed state rather than staying an idle button.
    await waitFor(() => expect(screen.getByText(/✓ Assigned/)).toBeInTheDocument());
  });

  it('shows an already-assigned vendor as assigned on OPEN, without a click', async () => {
    // [AIQ-2024] THE point of the change. Before it, the panel only knew about
    // assignments made in the current session, so re-opening it offered an idle
    // "Assign to case" button for a vendor already attached to the case.
    mocked(hrAPI.getVendors).mockResolvedValue({ vendors: [VENDOR] });
    mocked(hrAPI.getVendorCorridors).mockResolvedValue({ corridors: [] });
    mocked(hrAPI.getCaseVendors).mockResolvedValue([ASSIGNED_ROW]);

    renderPanel('case-abc');

    await waitFor(() => expect(screen.getByText(/✓ Assigned/)).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /assign to case/i })).not.toBeInTheDocument();
    expect(hrAPI.assignVendorToCase).not.toHaveBeenCalled();
  });

  it('matches on vendor id, not on display name', async () => {
    // Two vendors can share a name; the id is what identifies the row.
    mocked(hrAPI.getVendors).mockResolvedValue({ vendors: [VENDOR] });
    mocked(hrAPI.getVendorCorridors).mockResolvedValue({ corridors: [] });
    mocked(hrAPI.getCaseVendors).mockResolvedValue([
      {
        shortlist_id: 'row-9',
        vendor_id: 'a-different-vendor',
        category: 'housing',
        status: 'Assigned',
        contact_name: null,
        contact_email: null,
        vendor_name: 'NestFinders Europe',  // same NAME as the browsed vendor
        vendor_website: null,
      },
    ]);

    renderPanel('case-abc');

    // Same name, different id -> still offered, because it is not the same vendor.
    await screen.findByRole('button', { name: /assign to case/i });
  });

  it('surfaces a failed assign instead of silently doing nothing', async () => {
    mocked(hrAPI.getVendors).mockResolvedValue({ vendors: [VENDOR] });
    mocked(hrAPI.getVendorCorridors).mockResolvedValue({ corridors: [] });
    mocked(hrAPI.getCaseVendors).mockResolvedValue([]);
    mocked(hrAPI.assignVendorToCase).mockRejectedValue(new Error('500'));

    renderPanel('case-abc');

    fireEvent.click(await screen.findByRole('button', { name: /assign to case/i }));

    await waitFor(() =>
      expect(screen.getByText(/could not assign that vendor/i)).toBeInTheDocument(),
    );
  });
});
