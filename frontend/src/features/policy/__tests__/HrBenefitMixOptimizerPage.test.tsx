import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, render, screen, waitFor, fireEvent } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { hrAPI } from '../../../api/client';
import { useHrCompanyContext } from '../../../contexts/HrCompanyContext';
import { HrBenefitMixOptimizerPage } from '../HrBenefitMixOptimizerPage';

vi.mock('../../../api/client', () => ({ hrAPI: { optimizeBenefitMix: vi.fn() } }));
vi.mock('../../../contexts/HrCompanyContext', () => ({ useHrCompanyContext: vi.fn() }));

const mocked = <T,>(fn: T) => fn as T & ReturnType<typeof vi.fn>;
const withCompany = (companyId: string | null) =>
  mocked(useHrCompanyContext).mockReturnValue({ companyId } as unknown as ReturnType<typeof useHrCompanyContext>);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('HrBenefitMixOptimizerPage', () => {
  it('renders the portfolio and budget shadow price on a feasible result', async () => {
    withCompany('co-1');
    mocked(hrAPI.optimizeBenefitMix).mockResolvedValue({
      feasible: true,
      infeasibility_reason: null,
      selected: ['temp-housing', 'language'],
      achieved_utility: 42.5,
      total_cost: 4200,
      lambda_risk: 0.3,
      shadow_prices: { budget_per_1000: 6.4, category_caps: {}, min_coverage: 0 },
    });

    render(<HrBenefitMixOptimizerPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Optimize' }));

    await waitFor(() => expect(screen.getByText(/\+6\.4 utility/)).toBeInTheDocument());
    expect(screen.getByText('Utility 42.5')).toBeInTheDocument();
    expect(screen.getAllByText('Selected')).toHaveLength(2);
  });

  it('shows a friendly infeasibility alert when no mix fits', async () => {
    withCompany('co-1');
    mocked(hrAPI.optimizeBenefitMix).mockResolvedValue({
      feasible: false,
      infeasibility_reason: 'no_feasible_mix',
      selected: [],
      achieved_utility: 0,
      total_cost: 0,
      lambda_risk: 0.3,
      shadow_prices: { budget_per_1000: 0, category_caps: {}, min_coverage: 0 },
    });

    render(<HrBenefitMixOptimizerPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Optimize' }));

    await waitFor(() =>
      expect(screen.getByText(/No combination of these benefits fits the budget/)).toBeInTheDocument(),
    );
  });

  it('disables Optimize and guides when no company is selected', () => {
    withCompany(null);

    render(<HrBenefitMixOptimizerPage />);

    expect(screen.getByRole('button', { name: 'Optimize' })).toBeDisabled();
    expect(screen.getByText('No company selected')).toBeInTheDocument();
  });
});
