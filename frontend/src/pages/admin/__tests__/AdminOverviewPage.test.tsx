import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { adminAPI, adminProspectsAPI } from '../../../api/client';
import { getReviewSummary } from '../../../api/contentReview';
import { AdminOverviewPage } from '../AdminOverviewPage';

vi.mock('../AdminLayout', () => ({
  AdminLayout: ({
    children,
    subtitle,
  }: {
    children: React.ReactNode;
    subtitle?: string;
  }) => (
    <main>
      {subtitle ? <p data-testid="admin-today-subtitle">{subtitle}</p> : null}
      {children}
    </main>
  ),
}));

vi.mock('../../../api/client', () => ({
  adminAPI: {
    listCompanies: vi.fn(),
  },
  adminProspectsAPI: { list: vi.fn() },
}));

vi.mock('../../../api/contentReview', () => ({ getReviewSummary: vi.fn() }));

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

  it('renders today stats and four job doors without a module-card grid', async () => {
    mocked(adminAPI.listCompanies).mockResolvedValue({ companies: [{}, {}] });
    mocked(adminProspectsAPI.list).mockResolvedValue({ total: 17, limit: 1, offset: 0, prospects: [] });
    mocked(getReviewSummary).mockResolvedValue({
      by_destination: {},
      totals: { pending: 6 },
      pending_evidence: {},
      pending: 6,
    });

    renderPage();

    await waitFor(() => expect(within(screen.getByTestId('metric-tenants')).getByText('2')).toBeInTheDocument());
    expect(within(screen.getByTestId('metric-review-open')).getByText('6')).toBeInTheDocument();
    expect(within(screen.getByTestId('metric-prospects')).getByText('17')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Catalog\s+Coverage/i })).toHaveAttribute(
      'href',
      expect.stringContaining('coverage'),
    );
    expect(screen.getByTestId('job-door-catalog')).toHaveTextContent('6 pending');
    expect(screen.getByTestId('job-door-catalog')).toHaveClass('hover:bg-slate-50');
    expect(screen.getByTestId('job-door-usage')).toHaveTextContent('Companies');
    expect(screen.getByTestId('job-door-pipeline')).toHaveTextContent('17');
    expect(screen.getByTestId('job-door-machine')).toHaveTextContent('Feature flags');
    expect(screen.queryByTestId('module-companies')).not.toBeInTheDocument();
    expect(screen.queryByTestId('module-prospects')).not.toBeInTheDocument();
    expect(screen.queryByTestId('module-rag-quality')).not.toBeInTheDocument();
    expect(screen.getByTestId('admin-today-subtitle')).toHaveTextContent('What needs attention today');
    expect(screen.queryByText(/Executive and Ops stay nested/i)).not.toBeInTheDocument();
  });

  it('treats a real zero pending review as empty, not as a fake count', async () => {
    mocked(adminAPI.listCompanies).mockResolvedValue({ companies: [] });
    mocked(adminProspectsAPI.list).mockResolvedValue({ total: 0, limit: 1, offset: 0, prospects: [] });
    mocked(getReviewSummary).mockResolvedValue({
      by_destination: {},
      totals: { pending: 0 },
      pending_evidence: {},
      pending: 0,
    });

    renderPage();

    await waitFor(() => expect(screen.getByText('No review waiting.')).toBeInTheDocument());
    expect(within(screen.getByTestId('metric-tenants')).getByText('0')).toBeInTheDocument();
    expect(within(screen.getByTestId('metric-prospects')).getByText('0')).toBeInTheDocument();
    expect(screen.getByTestId('job-door-catalog')).not.toHaveTextContent('pending');
    expect(screen.queryByText('1204')).not.toBeInTheDocument();
  });

  it('shows unavailable for failed sources and never renders fabricated fallback counts', async () => {
    const failure = new Error('offline');
    mocked(adminAPI.listCompanies).mockRejectedValue(failure);
    mocked(adminProspectsAPI.list).mockRejectedValue(failure);
    mocked(getReviewSummary).mockRejectedValue(failure);

    renderPage();

    await waitFor(() =>
      expect(within(screen.getByTestId('metric-tenants')).getByText('Unavailable')).toBeInTheDocument(),
    );
    expect(within(screen.getByTestId('metric-review-open')).getByText('Unavailable')).toBeInTheDocument();
    expect(within(screen.getByTestId('metric-prospects')).getByText('Unavailable')).toBeInTheDocument();
    expect(screen.getByTestId('job-doors')).toBeInTheDocument();
    expect(screen.queryByText('42')).not.toBeInTheDocument();
    expect(screen.queryByText('7')).not.toBeInTheDocument();
  });
});
