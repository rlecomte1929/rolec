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
import { getAiUnitEconomics } from '../../../api/aiUnitEconomics';
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

vi.mock('../../../api/aiUnitEconomics', () => ({ getAiUnitEconomics: vi.fn() }));

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
    mocked(getAiUnitEconomics).mockRejectedValue(failure);
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
  mocked(getAiUnitEconomics).mockResolvedValue({
    rows: z
      ? []
      : [{ customer_id: 'acme', feature_key: 'policy_assistant', n_calls: 18, total_cost_usd: 1.23, total_tokens_in: 100, total_tokens_out: 50, total_co2e_grams: 19 }],
    totals: {
      n_calls: z ? 0 : 18,
      total_cost_usd: z ? 0 : 1.23,
      total_tokens_in: z ? 0 : 100,
      total_tokens_out: z ? 0 : 50,
      total_co2e_grams: z ? 0 : 19,
    },
    filters: { customer_id: null, feature_key: null, from: null, to: null },
  });
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
    expect(within(screen.getByTestId('module-ai-unit-economics')).getByText('$1.23')).toBeInTheDocument();
    expect(within(screen.getByTestId('module-ai-unit-economics')).getByText('18')).toBeInTheDocument();
    // The broken-looking placeholders must be gone.
    expect(screen.queryByText('No aggregate endpoint connected')).not.toBeInTheDocument();
    expect(screen.queryByText(/Open the CMS|Open pipeline|Open dashboard/)).not.toBeInTheDocument();
  });

  // [AIQ-1822] An unmeasured metric is not a healthy one.
  //
  // `rag_eval_reports.py:208` returns `{firing: false, reason: 'no_data'}` for a metric with no
  // readings. The card used to count health as `!alert.firing`, so "never evaluated" and
  // "evaluated and fine" were the same thing and an empty dataset rendered as 3/3 healthy.
  // These two tests pin the distinction from both ends.
  async function renderWithRagMetrics(
    metrics: Array<{ firing: boolean; reason: string }>,
    expected: string,
  ) {
    mocked(adminAPI.listCompanies).mockResolvedValue({ companies: [] });
    mocked(adminAPI.listHrUsers).mockResolvedValue({ hr_users: [] });
    mocked(adminAPI.listEmployees).mockResolvedValue({ employees: [] });
    mocked(adminAPI.listAssignments).mockResolvedValue({ assignments: [] });
    mocked(adminReviewQueueAPI.getStats).mockResolvedValue({ open_items_count: 0, unassigned_count: 0 });
    mocked(suppliersAPI.list).mockResolvedValue({ suppliers: [] });
    stubModuleSources('zeros');
    mocked(getRagEvalMetrics).mockResolvedValue({
      source: 'live',
      metrics: metrics.map((m) => ({ alert: m })),
    } as unknown as RagEvalDashboard);
    renderPage();
    // Waiting for the card to EXIST is not enough — it renders immediately in a loading state,
    // which is how the first version of this test asserted against a skeleton and failed for
    // the wrong reason. Wait for the headline metric to settle to a real value.
    await waitFor(() =>
      expect(
        within(screen.getByTestId('module-rag-quality')).getByText(expected),
      ).toBeInTheDocument(),
    );
    return within(screen.getByTestId('module-rag-quality'));
  }

  it('does not count an unmeasured metric as healthy', async () => {
    // One real pass, one genuinely failing, one never measured. Healthy is 1 of the 2 that
    // were MEASURED — not 2 of 3, which is what counting non-firing alerts gives.
    const card = await renderWithRagMetrics(
      [
        { firing: false, reason: 'healthy' },
        { firing: true, reason: 'below_threshold' },
        { firing: false, reason: 'no_data' },
      ],
      '1/2',
    );
    expect(card.queryByText('2/3')).not.toBeInTheDocument();
    // The gap is reported on its own row rather than averaged away.
    expect(card.getByText('Metrics not yet measured')).toBeInTheDocument();
  });

  it('says Unmeasured rather than a ratio when nothing has been evaluated', async () => {
    // The regression in its purest form: every metric no_data. The old code rendered 3/3.
    const card = await renderWithRagMetrics(
      [
        { firing: false, reason: 'no_data' },
        { firing: false, reason: 'no_data' },
        { firing: false, reason: 'no_data' },
      ],
      'Unmeasured',
    );
    expect(card.queryByText('3/3')).not.toBeInTheDocument();
    expect(card.queryByText('0/0')).not.toBeInTheDocument();
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
