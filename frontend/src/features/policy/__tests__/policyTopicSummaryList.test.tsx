/**
 * PolicyTopicSummaryList — Section 2 drill-down on the HR policy page.
 * Covers:
 *   - empty state when no matrix published
 *   - theme summary counts (included/excluded/conditional)
 *   - accordion expand/collapse shows row details
 *   - row details show label + cap + applicability + status chip
 *   - "View details" button fires the onRequestDetails callback
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { PolicyTopicSummaryList } from '../PolicyTopicSummaryList';

afterEach(cleanup);

function payload(overrides: Record<string, unknown> = {}) {
  return {
    policy_version: 'pv-1',
    version_number: 1,
    effective_date: '2026-01-01',
    status: 'published',
    categories: [
      {
        category_key: 'relocation_assistance',
        category_label: 'Relocation assistance',
        benefits: [
          {
            benefit_key: 'relocation_allowance_assignee_partner',
            benefit_label: 'Relocation allowance (assignee / partner)',
            covered: true,
            amount_value: 5000,
            currency_code: 'EUR',
            unit_frequency: 'one_time',
            assignment_types: ['long_term'],
            family_statuses: [],
            employee_levels: [],
            conditions_json: {},
            targeting_signature: 'sig-1',
          },
          {
            benefit_key: 'removal_expenses',
            benefit_label: 'Removal expenses',
            covered: false,
            amount_value: null,
            currency_code: null,
            unit_frequency: 'one_time',
            assignment_types: [],
            family_statuses: [],
            employee_levels: [],
            conditions_json: {},
            targeting_signature: 'sig-2',
          },
          {
            benefit_key: 'storage',
            benefit_label: 'Storage',
            covered: true,
            amount_value: 1000,
            currency_code: 'EUR',
            unit_frequency: 'monthly',
            assignment_types: [],
            family_statuses: [],
            employee_levels: [],
            conditions_json: { max_months: 6 },
            targeting_signature: 'sig-3',
          },
        ],
      },
    ],
    ...overrides,
  };
}

describe('PolicyTopicSummaryList', () => {
  it('shows empty-state message when no matrix categories exist', () => {
    render(
      <PolicyTopicSummaryList matrixPayload={null} onRequestDetails={() => {}} />
    );
    expect(
      screen.getByText(/No structured matrix has been published yet/i)
    ).toBeInTheDocument();
  });

  it('renders theme header with counts and collapsed by default', () => {
    render(
      <PolicyTopicSummaryList
        matrixPayload={payload()}
        onRequestDetails={() => {}}
      />
    );
    expect(screen.getByText('Relocation assistance')).toBeInTheDocument();
    expect(screen.getByText(/2 incl/)).toBeInTheDocument();
    expect(screen.getByText(/1 excl/)).toBeInTheDocument();
    expect(screen.getByText(/1 cond/)).toBeInTheDocument();
    // Rows are not rendered until the theme is expanded.
    expect(screen.queryByTestId('policy-topic-row')).not.toBeInTheDocument();
  });

  it('expands a theme on click and shows benefit rows with their caps', () => {
    render(
      <PolicyTopicSummaryList
        matrixPayload={payload()}
        onRequestDetails={() => {}}
      />
    );
    const header = screen.getByRole('button', { name: /Relocation assistance/i });
    fireEvent.click(header);
    expect(header).toHaveAttribute('aria-expanded', 'true');

    const rows = screen.getAllByTestId('policy-topic-row');
    expect(rows).toHaveLength(3);

    expect(screen.getByText(/Relocation allowance \(assignee \/ partner\)/i)).toBeInTheDocument();
    expect(screen.getByText('EUR 5000 · one_time')).toBeInTheDocument();
    // Excluded row renders its status chip and no cap.
    expect(screen.getByText('Excluded')).toBeInTheDocument();
    // Conditional row renders with amber chip (label text check).
    expect(screen.getByText('Conditional')).toBeInTheDocument();
  });

  it('fires onRequestDetails when "View details" is clicked', () => {
    const spy = vi.fn();
    render(
      <PolicyTopicSummaryList
        matrixPayload={payload()}
        onRequestDetails={spy}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /View details/i }));
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('shows applicability label when the row narrows targeting', () => {
    render(
      <PolicyTopicSummaryList
        matrixPayload={payload()}
        onRequestDetails={() => {}}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /Relocation assistance/i }));
    // The first row narrows assignment_types=['long_term']; label comes
    // from humanizeAssignmentTypeLabel which maps long_term → "Long-term assignment".
    expect(screen.getByText(/Applies to: Long-term assignment/i)).toBeInTheDocument();
  });
});
