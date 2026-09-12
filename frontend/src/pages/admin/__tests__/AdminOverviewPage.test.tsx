import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAdminMetrics } from '../../../api/adminMetrics';
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

vi.mock('../../../api/adminMetrics', async () => {
  const actual = await vi.importActual<typeof import('../../../api/adminMetrics')>('../../../api/adminMetrics');
  return {
    ...actual,
    useAdminMetrics: vi.fn(),
    getAdminMetrics: vi.fn(),
  };
});

const mocked = <T,>(fn: T) => fn as T & ReturnType<typeof vi.fn>;

const storage = new Map<string, string>();
vi.stubGlobal('localStorage', {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => storage.delete(key),
  clear: () => storage.clear(),
});

const asOf = '2026-09-12T12:00:00.000Z';
const metric = (value: number, definition: string) => ({
  value,
  definition,
  source: 's',
  as_of: asOf,
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
    mocked(useAdminMetrics).mockReturnValue({
      data: {
        as_of: asOf,
        tenants_total: metric(2, 'Companies on the platform, excluding test tenants.'),
        content_review_pending: metric(6, 'Requirement facts waiting for a human to review before they are shown.'),
        prospects_waiting: metric(17, 'People in the outreach pipeline who have not become tenants yet.'),
      },
      isLoading: false,
    } as ReturnType<typeof useAdminMetrics>);

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
    expect(within(screen.getByTestId('metric-tenants')).getByTestId('stat-card-definition')).toHaveTextContent(
      /Companies on the platform, excluding test tenants\. · as of/,
    );
  });

  it('treats a real zero pending review as empty, not as a fake count', async () => {
    mocked(useAdminMetrics).mockReturnValue({
      data: {
        as_of: asOf,
        tenants_total: metric(0, 'Companies on the platform, excluding test tenants.'),
        content_review_pending: metric(0, 'Requirement facts waiting for a human to review before they are shown.'),
        prospects_waiting: metric(0, 'People in the outreach pipeline who have not become tenants yet.'),
      },
      isLoading: false,
    } as ReturnType<typeof useAdminMetrics>);

    renderPage();

    await waitFor(() => expect(screen.getByText('No review waiting.')).toBeInTheDocument());
    expect(within(screen.getByTestId('metric-tenants')).getByText('0')).toBeInTheDocument();
    expect(within(screen.getByTestId('metric-prospects')).getByText('0')).toBeInTheDocument();
    expect(screen.getByTestId('job-door-catalog')).not.toHaveTextContent('pending');
    expect(screen.queryByText('1204')).not.toBeInTheDocument();
  });

  it('omits tiles when the metric is missing and never renders Unavailable', async () => {
    mocked(useAdminMetrics).mockReturnValue({
      data: { as_of: asOf },
      isLoading: false,
    } as ReturnType<typeof useAdminMetrics>);

    renderPage();

    await waitFor(() => expect(screen.getByTestId('job-doors')).toBeInTheDocument());
    expect(screen.queryByTestId('metric-tenants')).not.toBeInTheDocument();
    expect(screen.queryByTestId('metric-review-open')).not.toBeInTheDocument();
    expect(screen.queryByTestId('metric-prospects')).not.toBeInTheDocument();
    expect(screen.queryByText('Unavailable')).not.toBeInTheDocument();
    expect(screen.queryByText('42')).not.toBeInTheDocument();
    expect(screen.queryByText('7')).not.toBeInTheDocument();
  });
});
