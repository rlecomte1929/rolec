/**
 * Executive dashboard — renders KPI tiles + AI-health from the aggregated overview,
 * shows honest 'not instrumented' cards, and degrades unavailable panels without
 * crashing. API + AdminLayout mocked (keeps the admin shell + supabase out of jsdom).
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../../../api/execOverview', () => ({ getExecOverview: vi.fn() }));
vi.mock('../AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { getExecOverview } from '../../../api/execOverview';
import { ExecutiveDashboardPage } from './ExecutiveDashboardPage';

vi.mock('../../../api/adminMetrics', async () => {
  const actual = await vi.importActual<typeof import('../../../api/adminMetrics')>('../../../api/adminMetrics');
  return {
    ...actual,
    useAdminMetrics: vi.fn(() => ({ data: { as_of: '2026-09-12T12:00:00.000Z' }, isLoading: false })),
  };
});

const renderPage = () =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ExecutiveDashboardPage />
    </QueryClientProvider>,
  );

const mock = getExecOverview as unknown as ReturnType<typeof vi.fn>;

const OVERVIEW = {
  generated_at: '2026-06-30T00:00:00Z',
  window_days: 30,
  growth: { available: true, data_source: 'live', companies: 3, employees: 40 },
  funnel: { available: true, data_source: 'live', signups: 12, cases: 8, in_intake: 2, completed: 5 },
  throughput: { available: true, data_source: 'live', median_completion_days: 42 },
  ai_cost: { available: true, data_source: 'estimated', total_cost_usd: 1.23 },
  ai_health: { available: true, data_source: 'mock', score: 92, healthy: 11, total: 12 },
  reliability: { available: false, data_source: 'unavailable', note: 'Sentry-only.' },
  nps: { available: false, data_source: 'unavailable', note: 'No surveys yet.' },
};

afterEach(cleanup);
beforeEach(() => mock.mockReset());

describe('ExecutiveDashboardPage', () => {
  it('renders KPI tiles + AI-health score', async () => {
    mock.mockResolvedValue(OVERVIEW);
    renderPage();
    await waitFor(() => expect(screen.getByTestId('kpi-companies')).toHaveTextContent('3'));
    expect(screen.getByTestId('ai-health')).toHaveTextContent('92');
    expect(screen.getByTestId('kpi-cost')).toHaveTextContent('1.23');
  });

  it('shows the not-instrumented reliability + NPS cards', async () => {
    mock.mockResolvedValue(OVERVIEW);
    renderPage();
    expect(await screen.findByTestId('reliability')).toHaveTextContent(/not instrumented/i);
    expect(screen.getByTestId('nps')).toHaveTextContent(/not instrumented/i);
  });

  it('degrades an unavailable panel without crashing', async () => {
    mock.mockResolvedValue({ ...OVERVIEW, growth: { available: false, data_source: 'unavailable' } });
    renderPage();
    await waitFor(() => expect(screen.getByTestId('kpi-companies')).toHaveTextContent(/unavailable/i));
  });

  // ── AIQ-1564 (BUG-260716-D23E) ────────────────────────────────────────────────
  // A failed fetch used to leave `data` null, so every panel read as undefined and
  // EVERY tile printed "unavailable" — a claim about the data. The reporter read that
  // as "the dashboard isn't connected to its endpoints" and filed it as such. A load
  // failure must never be dressed up as a data-provenance verdict.

  it('a failed load never renders tiles as "unavailable" — it says so and offers retry', async () => {
    mock.mockRejectedValueOnce(new Error('network'));
    renderPage();

    expect(await screen.findByTestId('exec-load-error')).toBeInTheDocument();
    expect(screen.getByTestId('exec-retry')).toBeInTheDocument();
    // The regression itself: no tile may claim the DATA is unavailable.
    expect(screen.getByTestId('kpi-companies')).not.toHaveTextContent(/unavailable/i);
    expect(screen.getByTestId('kpi-cost')).not.toHaveTextContent(/unavailable/i);
    expect(screen.getByTestId('exec-kpis')).not.toHaveTextContent(/unavailable/i);
  });

  it('names a 429 as a rate limit rather than missing data', async () => {
    mock.mockRejectedValueOnce({ response: { status: 429 } });
    renderPage();
    expect(await screen.findByTestId('exec-load-error')).toHaveTextContent(/rate limit, not missing data/i);
  });

  it('Retry refetches and recovers the tiles', async () => {
    mock.mockRejectedValueOnce({ response: { status: 429 } }).mockResolvedValueOnce(OVERVIEW);
    renderPage();

    const retry = await screen.findByTestId('exec-retry');
    fireEvent.click(retry);

    await waitFor(() => expect(screen.getByTestId('kpi-companies')).toHaveTextContent('3'));
    expect(screen.queryByTestId('exec-load-error')).not.toBeInTheDocument();
    expect(mock).toHaveBeenCalledTimes(2);
  });
});
