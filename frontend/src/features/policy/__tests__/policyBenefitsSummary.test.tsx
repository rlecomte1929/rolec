/**
 * PolicyBenefitsSummary (AIQ-225 / P1-5) — read-only company policy truth board.
 *
 * Covers the UX invariants from the task:
 *  - version badge + effective date always visible
 *  - amber banner when policy is expired or under review (with the mandated copy)
 *  - every value row carries a "Last validated by … on …" line (mandatory)
 *  - benefit figures always render with a unit/currency (never a bare number)
 *  - no_policy empty state
 *  - tier filter re-queries the endpoint with the selected tier
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { PolicyBenefitsSummary } from '../PolicyBenefitsSummary';
import type { PolicySummaryResponse } from '../../../api/policySummary';

const mocks = vi.hoisted(() => ({ get: vi.fn() }));

vi.mock('../../../api/policySummary', () => ({
  policySummaryAPI: { get: (...args: unknown[]) => mocks.get(...args) },
}));

afterEach(() => {
  cleanup();
  mocks.get.mockReset();
});

function baseResponse(overrides: Partial<PolicySummaryResponse> = {}): PolicySummaryResponse {
  return {
    company_id: 'c1',
    version: {
      id: 'v1',
      version_number: 3,
      status: 'active',
      effective_date: '2026-05-01',
      expiry_date: null,
      published_by: 'u1',
      published_at: '2026-05-01',
    },
    status_banner: 'active',
    categories: [
      {
        code: 'housing',
        display_name: 'Housing & Accommodation',
        sort_order: 1,
        rows: [
          {
            tier_id: 't1',
            tier_name: 'Manager',
            cap_value: 5000,
            cap_unit: null,
            cap_currency: 'EUR',
            value_notes: 'Per month',
            validated_by_id: 'u9',
            validated_by_name: 'Dana HR',
            validated_at: '2026-05-02',
          },
        ],
      },
    ],
    ...overrides,
  };
}

describe('PolicyBenefitsSummary', () => {
  it('shows version badge, effective date, and a unit-bearing cap figure', async () => {
    mocks.get.mockResolvedValue(baseResponse());
    render(<PolicyBenefitsSummary />);

    expect(await screen.findByText(/v3 — active/i)).toBeInTheDocument();
    expect(screen.getByText(/Effective 1 May 2026/i)).toBeInTheDocument();
    // Figure carries its currency — never a bare "5000".
    expect(screen.getByText('5,000 EUR')).toBeInTheDocument();
  });

  it('renders the mandatory "Last validated by" line on every row', async () => {
    mocks.get.mockResolvedValue(baseResponse());
    render(<PolicyBenefitsSummary />);
    expect(await screen.findByText(/Last validated by Dana HR on 2 May 2026/i)).toBeInTheDocument();
  });

  it('falls back to "Not yet validated" when no validator is present', async () => {
    const res = baseResponse();
    res.categories[0].rows[0].validated_by_name = null;
    res.categories[0].rows[0].validated_at = null;
    mocks.get.mockResolvedValue(res);
    render(<PolicyBenefitsSummary />);
    expect(await screen.findByText(/Not yet validated/i)).toBeInTheDocument();
  });

  it('shows the amber banner with the mandated copy when under review', async () => {
    mocks.get.mockResolvedValue(baseResponse({ status_banner: 'under_review' }));
    render(<PolicyBenefitsSummary />);
    expect(
      await screen.findByText(
        /This policy is currently under review\. Contact HR for current guidance\./i,
      ),
    ).toBeInTheDocument();
  });

  it('shows an amber banner when expired', async () => {
    mocks.get.mockResolvedValue(
      baseResponse({ status_banner: 'expired', version: { ...baseResponse().version!, expiry_date: '2026-01-01' } }),
    );
    render(<PolicyBenefitsSummary />);
    expect(await screen.findByText(/This policy has expired/i)).toBeInTheDocument();
  });

  it('renders the no_policy empty state', async () => {
    mocks.get.mockResolvedValue(baseResponse({ status_banner: 'no_policy', version: null, categories: [] }));
    render(<PolicyBenefitsSummary />);
    expect(await screen.findByText(/No policy has been published yet/i)).toBeInTheDocument();
  });

  it('re-queries the endpoint with the selected tier', async () => {
    mocks.get.mockResolvedValue(baseResponse());
    render(<PolicyBenefitsSummary />);
    await screen.findByText(/v3 — active/i);

    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: 'Manager' } });

    await waitFor(() =>
      expect(mocks.get).toHaveBeenLastCalledWith({ companyId: undefined, tier: 'Manager' }),
    );
  });
});
