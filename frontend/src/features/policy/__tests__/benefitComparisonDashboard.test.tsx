import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

// Sever the api/exceptions → supabase client chain (needs env we don't set in unit tests).
vi.mock('../../../api/exceptions', () => ({
  createExceptionRequest: vi.fn(),
}));

import { BenefitComparisonDashboard } from '../BenefitComparisonDashboard';
import type { EffectiveServiceComparisonRow } from '../../../types';

function row(
  p: Partial<EffectiveServiceComparisonRow> &
    Pick<EffectiveServiceComparisonRow, 'service_key' | 'comparison_status'>,
): EffectiveServiceComparisonRow {
  return {
    coverage_status: 'included',
    policy_limit_snapshot: {},
    selected_value_snapshot: {},
    delta: null,
    explanation: '',
    approval_required: false,
    ...p,
  };
}

const COVERED = row({
  service_key: 'temporary_housing',
  comparison_status: 'within_envelope',
  policy_limit_snapshot: { max_value: 2000, currency: 'EUR' },
  selected_value_snapshot: { estimated_cost: 1800, currency: 'EUR' },
  delta: -200,
});
const PARTIAL = row({
  service_key: 'school_search',
  comparison_status: 'exceeds_envelope',
  policy_limit_snapshot: { max_value: 1000, currency: 'EUR' },
  selected_value_snapshot: { estimated_cost: 2500, currency: 'EUR' },
  delta: 1500,
});

afterEach(cleanup);

describe('BenefitComparisonDashboard', () => {
  it('renders the 3 KPI tiles', () => {
    render(<BenefitComparisonDashboard rows={[COVERED, PARTIAL]} caseId="c1" />);
    expect(screen.getByText('Total policy allocation')).toBeInTheDocument();
    expect(screen.getByText('Total service ask')).toBeInTheDocument();
    expect(screen.getByText('Estimated out-of-pocket')).toBeInTheDocument();
  });

  it('shows the exact partial delta in red and an exception button on the Partial row', () => {
    render(<BenefitComparisonDashboard rows={[COVERED, PARTIAL]} caseId="c1" />);
    const table = screen.getByRole('table');
    const partialRow = within(table).getByText('School search').closest('tr')!;
    const deltaCell = within(partialRow).getByText('+€1,500');
    expect(deltaCell).toHaveClass('text-[#b91c1c]');
    expect(within(partialRow).getByRole('button', { name: /request exception/i })).toBeInTheDocument();
  });

  it('does NOT show an exception button on a Covered row', () => {
    render(<BenefitComparisonDashboard rows={[COVERED, PARTIAL]} caseId="c1" />);
    const table = screen.getByRole('table');
    const coveredRow = within(table).getByText('Temporary housing').closest('tr')!;
    expect(within(coveredRow).queryByRole('button', { name: /request exception/i })).toBeNull();
  });

  it('out-of-pocket section lists only Partial/Uncovered categories', () => {
    render(<BenefitComparisonDashboard rows={[COVERED, PARTIAL]} caseId="c1" />);
    const section = screen.getByLabelText('Where you may pay out of pocket');
    expect(within(section).getByText('School search')).toBeInTheDocument();
    expect(within(section).queryByText('Temporary housing')).toBeNull();
  });

  it('shows an amber expired banner when the policy expiry is in the past', () => {
    render(
      <BenefitComparisonDashboard
        rows={[COVERED]}
        caseId="c1"
        policy={{ version: 3, effectiveDate: '2026-01-01', expiryDate: '2026-03-01' }}
        now={new Date('2026-06-04T00:00:00Z')}
      />,
    );
    expect(screen.getByRole('alert')).toHaveTextContent(/expired/i);
  });

  it('renders the policy version + effective date footer', () => {
    render(
      <BenefitComparisonDashboard
        rows={[COVERED]}
        caseId="c1"
        policy={{ companyName: 'Acme', version: 3, effectiveDate: '2026-01-01' }}
      />,
    );
    expect(screen.getByText(/Acme relocation policy v3, effective 2026-01-01/)).toBeInTheDocument();
  });

  it('renders an empty state without errors when there are no rows', () => {
    render(<BenefitComparisonDashboard rows={[]} caseId={null} />);
    expect(screen.getByText(/No services to compare yet/i)).toBeInTheDocument();
  });
});
