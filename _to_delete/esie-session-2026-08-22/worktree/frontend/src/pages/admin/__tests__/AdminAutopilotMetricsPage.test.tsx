import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { getAutopilotMetrics } from '../../../api/autopilotMetrics';
import { AdminAutopilotMetricsPage } from '../AdminAutopilotMetricsPage';

vi.mock('../AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
}));
vi.mock('../../../api/autopilotMetrics', () => ({ getAutopilotMetrics: vi.fn() }));

const mocked = <T,>(fn: T) => fn as T & ReturnType<typeof vi.fn>;

const empty = {
  since: null,
  funnel: {},
  dedup: { raw: 0, unique: 0, dedup_factor: null },
  cost: { by_stage: [], total_usd: 0, monthly_cap_usd: 25, remaining_usd: 25 },
  kpis: { dedup_factor: null, tasks_dispatched: 0, merged: 0, tasks_done: 0, reverted: 0,
          escalated_to_human: 0, runs_halted: 0, canary_pass_rate: null, revert_rate: null },
};

afterEach(() => cleanup());

describe('AdminAutopilotMetricsPage', () => {
  it('renders KPI tiles + funnel counts when there is activity', async () => {
    mocked(getAutopilotMetrics).mockResolvedValue({
      ...empty,
      funnel: { 'autopilot.task_dispatched': 8, 'autopilot.merged': 5, 'autopilot.task_done': 4 },
      dedup: { raw: 30, unique: 10, dedup_factor: 3 },
      cost: { by_stage: [{ stage: 'autopilot.dispatch', cost_usd: 0.5, n_calls: 10 }], total_usd: 0.5, monthly_cap_usd: 25, remaining_usd: 24.5 },
      kpis: { ...empty.kpis, dedup_factor: 3, tasks_dispatched: 8, merged: 5, tasks_done: 4, canary_pass_rate: 0.8, revert_rate: 0.2 },
    });
    render(<AdminAutopilotMetricsPage />);
    await waitFor(() => expect(screen.getByText('3×')).toBeInTheDocument());
    expect(screen.getByText('autopilot.dispatch')).toBeInTheDocument();
    expect(screen.getByText('80%')).toBeInTheDocument(); // canary pass rate
  });

  it('shows an empty state when the automation is dormant', async () => {
    mocked(getAutopilotMetrics).mockResolvedValue(empty);
    render(<AdminAutopilotMetricsPage />);
    await waitFor(() => expect(screen.getByText('No autopilot activity recorded yet')).toBeInTheDocument());
  });

  it('shows an error state when the fetch fails', async () => {
    mocked(getAutopilotMetrics).mockRejectedValue(new Error('offline'));
    render(<AdminAutopilotMetricsPage />);
    await waitFor(() => expect(screen.getByText('Failed to load')).toBeInTheDocument());
  });
});
