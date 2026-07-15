import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { HrPolicyCapsSection } from '../HrPolicyCapsSection';
import { budgetAPI, type BudgetSummaryResponse, type HrPolicyCap } from '../../../api/budget';

vi.mock('../../../api/budget', () => ({
  budgetAPI: { getBudgetSummary: vi.fn() },
}));

const resp = (caps: HrPolicyCap[]): BudgetSummaryResponse => ({
  case_id: 'c1',
  categories: [],
  hr_policy_caps: caps,
});

describe('HrPolicyCapsSection', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows a loading skeleton while fetching', () => {
    vi.mocked(budgetAPI.getBudgetSummary).mockImplementation(() => new Promise(() => {}));
    render(<HrPolicyCapsSection caseId="c1" />);
    expect(screen.getByLabelText(/loading hr policy caps/i)).toBeInTheDocument();
  });

  it('renders the full CAP list with name + category, honest "Covered" for unquantified', async () => {
    vi.mocked(budgetAPI.getBudgetSummary).mockResolvedValueOnce(
      resp([
        { benefit_key: 'host_housing_cap', name: 'Housing allowance', category: 'compensation_allowances', cap_type: 'currency_amount', amount: 2000, currency: 'EUR', unit_frequency: 'yearly', notes: null },
        { benefit_key: 'settling_in_services', name: 'Settling-in', category: 'relocation_support', cap_type: 'no_monetary_cap', amount: null, currency: null, unit_frequency: 'one_time', notes: null },
      ]),
    );
    render(<HrPolicyCapsSection caseId="c1" />);
    expect(await screen.findByText('Housing allowance')).toBeInTheDocument();
    expect(screen.getByText('Settling-in')).toBeInTheDocument();
    // Covered-but-unquantified benefit shows "Covered", never a fabricated number.
    expect(screen.getByText(/^covered$/i)).toBeInTheDocument();
  });

  it('shows the empty state when the company has no published CAPs', async () => {
    vi.mocked(budgetAPI.getBudgetSummary).mockResolvedValueOnce(resp([]));
    render(<HrPolicyCapsSection caseId="c1" />);
    expect(await screen.findByText(/no caps published yet/i)).toBeInTheDocument();
  });

  it('treats a response without the field as empty (backward-compat)', async () => {
    vi.mocked(budgetAPI.getBudgetSummary).mockResolvedValueOnce({ case_id: 'c1', categories: [] });
    render(<HrPolicyCapsSection caseId="c1" />);
    expect(await screen.findByText(/no caps published yet/i)).toBeInTheDocument();
  });

  it('shows an error with a Retry that refetches', async () => {
    vi.mocked(budgetAPI.getBudgetSummary)
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce(resp([
        { benefit_key: 'k', name: 'Language support', category: null, cap_type: 'currency_amount', amount: 500, currency: 'EUR', unit_frequency: 'one_time', notes: null },
      ]));
    render(<HrPolicyCapsSection caseId="c1" />);
    const retry = await screen.findByRole('button', { name: /retry/i });
    fireEvent.click(retry);
    await waitFor(() => expect(screen.getByText('Language support')).toBeInTheDocument());
  });
});
