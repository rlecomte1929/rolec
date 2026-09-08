import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { getAiUnitEconomics } from '../../../api/aiUnitEconomics';
import { AdminAiUnitEconomicsPage } from '../AdminAiUnitEconomicsPage';

vi.mock('../AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
}));

vi.mock('../../../api/aiUnitEconomics', () => ({ getAiUnitEconomics: vi.fn() }));

const mocked = <T,>(fn: T) => fn as T & ReturnType<typeof vi.fn>;

afterEach(() => cleanup());

describe('AdminAiUnitEconomicsPage', () => {
  it('renders totals and a per-feature row', async () => {
    mocked(getAiUnitEconomics).mockResolvedValue({
      rows: [
        {
          customer_id: 'acme',
          feature_key: 'policy_assistant',
          n_calls: 42,
          total_cost_usd: 1.68,
          total_tokens_in: 1000,
          total_tokens_out: 400,
          total_co2e_grams: 12.5,
        },
      ],
      totals: { n_calls: 42, total_cost_usd: 1.68, total_tokens_in: 1000, total_tokens_out: 400, total_co2e_grams: 12.5 },
      filters: { customer_id: null, feature_key: null, from: null, to: null },
    });

    render(<AdminAiUnitEconomicsPage />);

    await waitFor(() => expect(screen.getByText('policy_assistant')).toBeInTheDocument());
    expect(screen.getByText('acme')).toBeInTheDocument();
    // Cost is formatted as $1.68 in both the totals strip and the row.
    expect(screen.getAllByText('$1.68').length).toBeGreaterThan(0);
  });

  it('shows an empty state when no usage is recorded', async () => {
    mocked(getAiUnitEconomics).mockResolvedValue({
      rows: [],
      totals: { n_calls: 0, total_cost_usd: 0, total_tokens_in: 0, total_tokens_out: 0, total_co2e_grams: 0 },
      filters: { customer_id: null, feature_key: null, from: null, to: null },
    });

    render(<AdminAiUnitEconomicsPage />);

    await waitFor(() => expect(screen.getByText('No AI usage recorded yet')).toBeInTheDocument());
  });

  it('shows an error state when the fetch fails', async () => {
    mocked(getAiUnitEconomics).mockRejectedValue(new Error('offline'));

    render(<AdminAiUnitEconomicsPage />);

    await waitFor(() => expect(screen.getByText('Could not load AI unit-economics.')).toBeInTheDocument());
  });
});
