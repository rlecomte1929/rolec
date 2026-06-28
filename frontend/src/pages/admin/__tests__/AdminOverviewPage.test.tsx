import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  adminAPI,
  adminReviewQueueAPI,
  suppliersAPI,
  adminOpsAnalyticsAPI,
  adminResourcesAPI,
  adminProspectsAPI,
} from '../../../api/client';
import { getRagEvalMetrics, type RagEvalDashboard } from '../../../api/ragEval';
import { AdminOverviewPage } from '../AdminOverviewPage';

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
  adminOpsAnalyticsAPI: { getSlaOverview: vi.fn(), getWorkflowOverview: vi.fn() },
  adminResourcesAPI: { getCounts: vi.fn() },
  adminProspectsAPI: { list: vi.fn() },
}));

vi.mock('../../../api/ragEval', () => ({ getRagEvalMetrics: vi.fn() }));

const mocked = <T,>(fn: T) => fn as T & ReturnType<typeof vi.fn>;

// Module-card sources (AIQ-1329). Helper keeps the three tests focused on the
// assertions that differ rather than re-stubbing five endpoints each time.
const stubModuleSources = (mode: 'values' | 'zeros' | 'reject') => {
  if (mode === 'reject') {
    const failure = new Error('offline');
    mocked(adminOpsAnalyticsAPI.getSlaOverview).mockRejectedValue(failure);
    mocked(adminOpsAnalyticsAPI.getWorkflowOverview).mockRejectedValue(failure);
    mocked(adminResourcesAPI.getCounts).mockRejectedValue(failure);
    mocked(adminProspectsAPI.list).mockRejectedValue(failure);
    mocked(getRagEvalMetrics).mockRejectedValue(failure);
    return;
  }
  const z = mode === 'zeros';
  mocked(adminOpsAnalyticsAPI.getSlaOverview).mockResolvedValue({ open_count: z ? 0 : 11, breached_count: z ? 0 : 12 });
  mocked(adminOpsAnalyticsAPI.getWorkflowOverview).mockResolvedValue({ events: { case_created: z ? 0 : 13, rfq_created: z ? 0 : 14 } });
  mocked(adminResourcesAPI.getCounts).mockResolvedValue({ resources_published: z ? 0 : 15, resources_draft: z ? 0 : 16 });
  mocked(adminProspectsAPI.list).mockResolvedValue({ total: z ? 0 : 17, limit: 1, offset: 0, prospects: [] });
  // The card only reads `.metrics[].alert.firing` and `.metrics.length`, so a
  // partial shape is sufficient — cast to the full dashboard type for the mock.
  mocked(getRagEvalMetrics).mockResolvedValue({
    source: 'live',
    metrics: z
      ? [{ alert: { firing: false } }]
      : [{ alert: { firing: false } }, { alert: { firing: false } }, { alert: { firing: true } }],
  } as unknown as RagEvalDashboard);
};

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
    stubModuleSources('values');

    renderPage();

    await waitFor(() => expect(within(screen.getByTestId('metric-tenants')).getByText('2')).toBeInTheDocument());
    expect(within(screen.getByTestId('metric-assignments')).getByText('5')).toBeInTheDocument();
    expect(within(screen.getByTestId('metric-review-open')).getByText('6')).toBeInTheDocument();
    expect(within(screen.getByTestId('module-companies')).getByText('3')).toBeInTheDocument();
    expect(within(screen.getByTestId('module-companies')).getByText('4')).toBeInTheDocument();
    expect(within(screen.getByTestId('module-suppliers')).getAllByText('8')).toHaveLength(2);
    expect(screen.queryByText('7')).not.toBeInTheDocument();

    // AIQ-1329: the five previously-broken module cards now show live counts.
    // (Each card repeats its headline value in a row, so assert presence, not count.)
    expect(within(screen.getByTestId('module-ops-analytics')).getAllByText('11').length).toBeGreaterThan(0);
    expect(within(screen.getByTestId('module-workflow-analytics')).getAllByText('13').length).toBeGreaterThan(0);
    expect(within(screen.getByTestId('module-resources')).getAllByText('15').length).toBeGreaterThan(0);
    expect(within(screen.getByTestId('module-prospects')).getAllByText('17').length).toBeGreaterThan(0);
    expect(within(screen.getByTestId('module-rag-quality')).getByText('2/3')).toBeInTheDocument();
    // The broken-looking placeholders must be gone.
    expect(screen.queryByText('No aggregate endpoint connected')).not.toBeInTheDocument();
    expect(screen.queryByText(/Open the CMS|Open pipeline|Open dashboard/)).not.toBeInTheDocument();
  });

  it('preserves real zeroes instead of substituting demo counts', async () => {
    mocked(adminAPI.listCompanies).mockResolvedValue({ companies: [] });
    mocked(adminAPI.listHrUsers).mockResolvedValue({ hr_users: [] });
    mocked(adminAPI.listEmployees).mockResolvedValue({ employees: [] });
    mocked(adminAPI.listAssignments).mockResolvedValue({ assignments: [] });
    mocked(adminReviewQueueAPI.getStats).mockResolvedValue({ open_items_count: 0, unassigned_count: 0 });
    mocked(suppliersAPI.list).mockResolvedValue({ suppliers: [] });
    stubModuleSources('zeros');

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
    stubModuleSources('reject');

    renderPage();

    // KPI tiles (StatCard) keep the amber 'Unavailable' marker — unchanged by AIQ-1329.
    await waitFor(() =>
      expect(within(screen.getByTestId('metric-tenants')).getByText('Unavailable')).toBeInTheDocument(),
    );
    expect(within(screen.getByTestId('metric-assignments')).getByText('Unavailable')).toBeInTheDocument();
    expect(within(screen.getByTestId('metric-review-open')).getByText('Unavailable')).toBeInTheDocument();
    // AIQ-1329: module cards degrade to a neutral muted dash, never the amber alarm.
    expect(within(screen.getByTestId('module-companies')).queryByText('Unavailable')).not.toBeInTheDocument();
    expect(within(screen.getByTestId('module-companies')).getAllByText('—')).toHaveLength(5);
    for (const id of ['module-ops-analytics', 'module-workflow-analytics', 'module-resources', 'module-prospects', 'module-rag-quality']) {
      expect(within(screen.getByTestId(id)).queryByText('Unavailable')).not.toBeInTheDocument();
    }
    expect(screen.queryByText('42')).not.toBeInTheDocument();
    expect(screen.queryByText('38')).not.toBeInTheDocument();
    expect(screen.queryByText('1204')).not.toBeInTheDocument();
    expect(screen.queryByText('168')).not.toBeInTheDocument();
    expect(screen.queryByText('7')).not.toBeInTheDocument();
  });
});
