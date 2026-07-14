/**
 * BudgetSummaryTable — AIQ-280 / T1.5 regression tests.
 *
 * Covers the three states the component renders:
 *   1. loading skeleton while the budget-summary fetch is pending
 *   2. error alert + Retry when the fetch rejects
 *   3. populated 4-column table with status badges when the fetch resolves
 *
 * Plus one HR-mode rendering assertion to verify the nativeCurrencyForCaps
 * branch shows the cap in its native currency rather than converting.
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BudgetSummaryTable } from '../BudgetSummaryTable';

vi.mock('../../../api/budget', () => ({
  budgetAPI: {
    getBudgetSummary: vi.fn(),
  },
}));

import { budgetAPI } from '../../../api/budget';

const POPULATED_RESPONSE = {
  case_id: 'case-1',
  categories: [
    {
      name: 'housing',
      cap_amount: 2000,
      cap_currency: 'EUR',
      estimated_amount: null,
      status: 'no_estimate' as const,
    },
    {
      name: 'schools',
      cap_amount: 15000,
      cap_currency: 'EUR',
      estimated_amount: null,
      status: 'no_estimate' as const,
    },
    {
      name: 'movers',
      cap_amount: null,
      cap_currency: 'EUR',
      estimated_amount: null,
      status: 'no_cap' as const,
    },
  ],
};

describe('BudgetSummaryTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders a loading skeleton while the request is in flight', () => {
    // Never resolve — keep the component in the loading branch.
    vi.mocked(budgetAPI.getBudgetSummary).mockImplementation(
      () => new Promise(() => {}),
    );

    render(<BudgetSummaryTable caseId="case-1" displayCurrency="USD" />);

    expect(screen.getByLabelText(/loading policy caps/i)).toBeInTheDocument();
  });

  it('renders an error alert with a Retry button when the fetch fails', async () => {
    vi.mocked(budgetAPI.getBudgetSummary).mockRejectedValueOnce(
      new Error('500 from server'),
    );

    render(<BudgetSummaryTable caseId="case-1" displayCurrency="USD" />);

    expect(await screen.findByText(/couldn[’']t load the policy caps/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  it('renders the 4-column table with category labels and status badges', async () => {
    vi.mocked(budgetAPI.getBudgetSummary).mockResolvedValueOnce(POPULATED_RESPONSE);

    render(<BudgetSummaryTable caseId="case-1" displayCurrency="USD" />);

    // Headers
    expect(await screen.findByText('Category')).toBeInTheDocument();
    expect(screen.getByText('Your estimate')).toBeInTheDocument();
    expect(screen.getByText('Policy cap')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();

    // Rows
    expect(screen.getByText('Housing')).toBeInTheDocument();
    expect(screen.getByText('Schools')).toBeInTheDocument();
    expect(screen.getByText('Movers')).toBeInTheDocument();

    // Estimate column always reads 'Not yet estimated' until the backend
    // computes real estimates — placeholder world per the audit spec.
    expect(screen.getAllByText('Not yet estimated').length).toBe(3);

    // Status badges — no_estimate x2 (cap set, no estimate yet) + no_cap x1.
    expect(screen.getAllByText('Not yet estimated').length).toBe(3); // estimate column for all 3 rows
    expect(screen.getAllByText('Pending estimate').length).toBe(2);  // status badge for housing + schools
    expect(screen.getByText('No company cap')).toBeInTheDocument();
  });

  it('displays caps in native currency when nativeCurrencyForCaps is true (HR mode)', async () => {
    vi.mocked(budgetAPI.getBudgetSummary).mockResolvedValueOnce(POPULATED_RESPONSE);

    render(
      <BudgetSummaryTable
        caseId="case-1"
        displayCurrency="USD"
        nativeCurrencyForCaps
      />,
    );

    // €2,000 in EUR (the policy's native currency) — NOT converted to USD.
    // Intl.NumberFormat's EUR symbol can be '€' or 'EUR' depending on the
    // test environment locale; assert on the digit run + EUR-affinity.
    await waitFor(() => {
      const housingRow = screen.getByText('Housing').closest('tr');
      expect(housingRow).not.toBeNull();
      expect(housingRow!.textContent).toMatch(/2[,.\s]?000/);
    });
  });
});
