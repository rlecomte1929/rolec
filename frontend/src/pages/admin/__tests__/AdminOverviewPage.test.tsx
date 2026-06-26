import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
}));

vi.mock('../../../api/client', () => ({
  adminAPI: {
    listCompanies: vi.fn(),
    listHrUsers: vi.fn(),
    listEmployees: vi.fn(),
    listAssignments: vi.fn(),
  },
  adminReviewQueueAPI: { getStats: vi.fn() },
  suppliersAPI: { list: vi.fn() },
}));

import { adminAPI, adminReviewQueueAPI, suppliersAPI } from '../../../api/client';
import { AdminOverviewPage } from '../AdminOverviewPage';

const mocked = <T,>(fn: T) => fn as T & ReturnType<typeof vi.fn>;

const storage = new Map<string, string>();
vi.stubGlobal('localStorage', {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => storage.delete(key),
  clear: () => storage.clear(),
});

const renderPage = () =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <AdminOverviewPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

describe('AdminOverviewPage metrics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('relopass_role', 'ADMIN');
  });

  afterEach(() => {
    cleanup();
    localStorage.clear();
  });

  it('renders API-backed totals from the same sources as destination views', async () => {
    mocked(adminAPI.listCompanies).mockResolvedValue({ companies: [{}, {}] });
    mocked(adminAPI.listHrUsers).mockResolvedValue({ hr_users: [{}, {}, {}] });
    mocked(adminAPI.listEmployees).mockResolvedValue({ employees: [{}, {}, {}, {}] });
    mocked(adminAPI.listAssignments).mockResolvedValue({ assignments: [{}, {}, {}, {}, {}] });
    mocked(adminReviewQueueAPI.getStats).mockResolvedValue({ open_items_count: 6, unassigned_count: 2 });
    mocked(suppliersAPI.list).mockResolvedValue({ suppliers: Array.from({ length: 8 }, () => ({})) });

    renderPage();

    await waitFor(() => expect(within(screen.getByTestId('metric-tenants')).getByText('2')).toBeInTheDocument());
    expect(within(screen.getByTestId('metric-assignments')).getByText('5')).toBeInTheDocument();
    expect(within(screen.getByTestId('metric-review-open')).getByText('6')).toBeInTheDocument();
    expect(within(screen.getByTestId('module-companies')).getByText('3')).toBeInTheDocument();
    expect(within(screen.getByTestId('module-companies')).getByText('4')).toBeInTheDocument();
    expect(within(screen.getByTestId('module-suppliers')).getAllByText('8')).toHaveLength(2);
    expect(screen.queryByText('7')).not.toBeInTheDocument();
  });

  it('preserves real zeroes instead of substituting demo counts', async () => {
    mocked(adminAPI.listCompanies).mockResolvedValue({ companies: [] });
    mocked(adminAPI.listHrUsers).mockResolvedValue({ hr_users: [] });
    mocked(adminAPI.listEmployees).mockResolvedValue({ employees: [] });
    mocked(adminAPI.listAssignments).mockResolvedValue({ assignments: [] });
    mocked(adminReviewQueueAPI.getStats).mockResolvedValue({ open_items_count: 0, unassigned_count: 0 });
    mocked(suppliersAPI.list).mockResolvedValue({ suppliers: [] });

    renderPage();

    await waitFor(() => expect(within(screen.getByTestId('metric-tenants')).getByText('0')).toBeInTheDocument());
    expect(within(screen.getByTestId('metric-assignments')).getByText('0')).toBeInTheDocument();
    expect(within(screen.getByTestId('metric-review-open')).getByText('0')).toBeInTheDocument();
    expect(within(screen.getByTestId('module-suppliers')).getAllByText('0')).toHaveLength(2);
    expect(screen.queryByText('1204')).not.toBeInTheDocument();
    expect(screen.queryByText('168')).not.toBeInTheDocument();
    expect(screen.queryByText('42')).not.toBeInTheDocument();
    expect(screen.queryByText('38')).not.toBeInTheDocument();
    expect(screen.queryByText('7')).not.toBeInTheDocument();
  });

  it('shows unavailable for failed sources and never renders fabricated fallback counts', async () => {
    const failure = new Error('offline');
    mocked(adminAPI.listCompanies).mockRejectedValue(failure);
    mocked(adminAPI.listHrUsers).mockRejectedValue(failure);
    mocked(adminAPI.listEmployees).mockRejectedValue(failure);
    mocked(adminAPI.listAssignments).mockRejectedValue(failure);
    mocked(adminReviewQueueAPI.getStats).mockRejectedValue(failure);
    mocked(suppliersAPI.list).mockRejectedValue(failure);

    renderPage();

    await waitFor(() =>
      expect(within(screen.getByTestId('metric-tenants')).getByText('Unavailable')).toBeInTheDocument(),
    );
    expect(within(screen.getByTestId('metric-assignments')).getByText('Unavailable')).toBeInTheDocument();
    expect(within(screen.getByTestId('metric-review-open')).getByText('Unavailable')).toBeInTheDocument();
    expect(within(screen.getByTestId('module-companies')).getAllByText('Unavailable')).toHaveLength(5);
    expect(screen.queryByText('42')).not.toBeInTheDocument();
    expect(screen.queryByText('38')).not.toBeInTheDocument();
    expect(screen.queryByText('1204')).not.toBeInTheDocument();
    expect(screen.queryByText('168')).not.toBeInTheDocument();
    expect(screen.queryByText('7')).not.toBeInTheDocument();
  });
});
