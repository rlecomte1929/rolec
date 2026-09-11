import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ClaimRemainingBar } from '../ClaimRemainingBar';
import type { BudgetDrawdown } from '../../../api/budget';

const row = (partial: Partial<BudgetDrawdown>): BudgetDrawdown => ({
  benefit_key: 'installation_allowance',
  name: 'Installation allowance',
  cap_amount: 3049,
  currency: 'EUR',
  claimed_approved: 1549,
  remaining: 1500,
  status: 'within_budget',
  ...partial,
});

describe('ClaimRemainingBar', () => {
  it("renders remaining copy from a mocked drawdown (€ X of €3,049)", () => {
    render(
      <ClaimRemainingBar
        caseId="c1"
        drawdown={[row({})]}
      />,
    );
    expect(screen.getByText(/of/i)).toBeInTheDocument();
    expect(screen.getByText(/3,049|3049/)).toBeInTheDocument();
    expect(screen.getByText(/1,500|1500/)).toBeInTheDocument();
  });
});
