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

    renderPanel(null);

    await waitFor(() => expect(screen.getByText('NestFinders Europe')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: /assign to case/i })).not.toBeInTheDocument();
    // The heading must not promise an action the panel cannot perform.
    expect(screen.getByText(/browse the approved vendor directory/i)).toBeInTheDocument();
  });

  it('assigns the vendor to the given case and confirms it', async () => {
    mocked(hrAPI.getVendors).mockResolvedValue({ vendors: [VENDOR] });
    mocked(hrAPI.getVendorCorridors).mockResolvedValue({ corridors: [] });
    mocked(hrAPI.assignVendorToCase).mockResolvedValue({
      shortlist_id: 'row-1',
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

  it('surfaces a failed assign instead of silently doing nothing', async () => {
    mocked(hrAPI.getVendors).mockResolvedValue({ vendors: [VENDOR] });
    mocked(hrAPI.getVendorCorridors).mockResolvedValue({ corridors: [] });
    mocked(hrAPI.assignVendorToCase).mockRejectedValue(new Error('500'));

    renderPanel('case-abc');

    fireEvent.click(await screen.findByRole('button', { name: /assign to case/i }));

    await waitFor(() =>
      expect(screen.getByText(/could not assign that vendor/i)).toBeInTheDocument(),
    );
  });
});
