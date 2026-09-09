/**
 * [AIQ-1850] Vetting queue — filters, multi-select batch approval, and
 * summary counts. Pure helpers are unit-tested directly; the batch-approve
 * wiring is exercised through a mocked suppliersAPI.
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  AdminVettingQueue,
  filterCapabilities,
  distinctCounts,
  type PendingCapability,
} from '../AdminVettingQueue';
import { suppliersAPI } from '../../../api/client';

vi.mock('../AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  suppliersAPI: {
    listPendingCapabilities: vi.fn(),
    approveCapability: vi.fn().mockResolvedValue({}),
    rejectCapability: vi.fn().mockResolvedValue({}),
  },
}));

vi.mock('../../../navigation/routes', () => ({
  buildRoute: () => '/admin/suppliers/x',
}));

const ROWS: PendingCapability[] = [
  { supplier_id: 's1', supplier_name: 'Acme Movers', capability_id: 'c1', service_category: 'movers', country_code: 'NO' },
  { supplier_id: 's1', supplier_name: 'Acme Movers', capability_id: 'c2', service_category: 'banks', country_code: 'NO' },
  { supplier_id: 's2', supplier_name: 'Berlin Bank', capability_id: 'c3', service_category: 'banks', country_code: 'DE' },
  { supplier_id: 's3', supplier_name: 'Nordic Insure', capability_id: 'c4', service_category: 'insurance', country_code: null },
];

describe('filterCapabilities', () => {
  it('returns everything when no filter is set', () => {
    expect(filterCapabilities(ROWS, { country: '', service: '', name: '' })).toHaveLength(4);
  });

  it('filters by country', () => {
    const out = filterCapabilities(ROWS, { country: 'NO', service: '', name: '' });
    expect(out.map((r) => r.capability_id)).toEqual(['c1', 'c2']);
  });

  it('filters by service category', () => {
    const out = filterCapabilities(ROWS, { country: '', service: 'banks', name: '' });
    expect(out.map((r) => r.capability_id)).toEqual(['c2', 'c3']);
  });

  it('filters by name (case-insensitive substring)', () => {
    const out = filterCapabilities(ROWS, { country: '', service: '', name: 'acme' });
    expect(out.map((r) => r.capability_id)).toEqual(['c1', 'c2']);
  });

  it('combines filters with AND', () => {
    const out = filterCapabilities(ROWS, { country: 'NO', service: 'banks', name: 'acme' });
    expect(out.map((r) => r.capability_id)).toEqual(['c2']);
  });
});

describe('distinctCounts', () => {
  it('counts distinct companies by supplier_id and countries by country_code', () => {
    // 3 suppliers (s1 twice), 2 countries (NO, DE) — null country is ignored.
    expect(distinctCounts(ROWS)).toEqual({ companies: 3, countries: 2 });
  });

  it('reflects the filtered subset', () => {
    const filtered = filterCapabilities(ROWS, { country: 'NO', service: '', name: '' });
    expect(distinctCounts(filtered)).toEqual({ companies: 1, countries: 1 });
  });
});

describe('AdminVettingQueue — batch approval', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (suppliersAPI.approveCapability as ReturnType<typeof vi.fn>).mockResolvedValue({});
    (suppliersAPI.listPendingCapabilities as ReturnType<typeof vi.fn>).mockResolvedValue({
      capabilities: ROWS,
    });
  });
  afterEach(() => cleanup());

  it('approves every selected row via Select all → Approve selected', async () => {
    render(<AdminVettingQueue />);
    await screen.findAllByText('Acme Movers');

    fireEvent.click(screen.getByLabelText('Select all'));
    fireEvent.click(screen.getByRole('button', { name: /Approve selected \(4\)/ }));

    await waitFor(() => {
      expect(suppliersAPI.approveCapability).toHaveBeenCalledTimes(4);
    });
    expect(suppliersAPI.approveCapability).toHaveBeenCalledWith('s1', 'c1');
    expect(suppliersAPI.approveCapability).toHaveBeenCalledWith('s2', 'c3');
  });

  it('batch-approves only the rows left after filtering', async () => {
    render(<AdminVettingQueue />);
    await screen.findAllByText('Acme Movers');

    // Filter to Norway (ISO NO → c1, c2), then select all + approve.
    fireEvent.click(screen.getByRole('button', { name: 'All countries' }));
    fireEvent.click(screen.getByRole('option', { name: 'Norway' }));
    fireEvent.click(screen.getByLabelText('Select all'));
    fireEvent.click(screen.getByRole('button', { name: /Approve selected \(2\)/ }));

    await waitFor(() => {
      expect(suppliersAPI.approveCapability).toHaveBeenCalledTimes(2);
    });
    expect(suppliersAPI.approveCapability).toHaveBeenCalledWith('s1', 'c1');
    expect(suppliersAPI.approveCapability).toHaveBeenCalledWith('s1', 'c2');
  });
});
