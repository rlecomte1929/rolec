/**
 * Executive dashboard — renders KPI tiles + AI-health from the aggregated overview,
 * shows honest 'not instrumented' cards, and degrades unavailable panels without
 * crashing. API + AdminLayout mocked (keeps the admin shell + supabase out of jsdom).
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../../../api/execOverview', () => ({ getExecOverview: vi.fn() }));
vi.mock('../AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { getExecOverview } from '../../../api/execOverview';
import { ExecutiveDashboardPage } from './ExecutiveDashboardPage';

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
    render(<ExecutiveDashboardPage />);
    await waitFor(() => expect(screen.getByTestId('kpi-companies')).toHaveTextContent('3'));
    expect(screen.getByTestId('ai-health')).toHaveTextContent('92');
    expect(screen.getByTestId('kpi-cost')).toHaveTextContent('1.23');
  });

  it('shows the not-instrumented reliability + NPS cards', async () => {
    mock.mockResolvedValue(OVERVIEW);
    render(<ExecutiveDashboardPage />);
    expect(await screen.findByTestId('reliability')).toHaveTextContent(/not instrumented/i);
    expect(screen.getByTestId('nps')).toHaveTextContent(/not instrumented/i);
  });

  it('degrades an unavailable panel without crashing', async () => {
    mock.mockResolvedValue({ ...OVERVIEW, growth: { available: false, data_source: 'unavailable' } });
    render(<ExecutiveDashboardPage />);
    await waitFor(() => expect(screen.getByTestId('kpi-companies')).toHaveTextContent(/unavailable/i));
  });
});
