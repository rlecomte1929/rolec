/**
 * HrPolicyRealityPage — wiring tests
 *
 * Verifies:
 *   1. Real cases from the API are rendered (not mock data).
 *   2. Spend columns show the "coming soon" gate, not euro figures.
 *   3. Empty cases array → honest empty state.
 *   4. Loading and error states render correctly.
 */
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';

// ── Mock the API module before importing the page ─────────────────────────────
vi.mock('../../../../api/hrAnalytics', () => ({
  getPolicyComplianceMatrix: vi.fn(),
}));

// ── Mock AppShell + Checkbox so we don't need full UI deps ────────────────────
vi.mock('../../../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('../../../../components/antigravity/Checkbox', () => ({
  Checkbox: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input type="checkbox" {...props} />,
}));

vi.mock('../../../../components/antigravity/Button', () => ({
  Button: ({ children, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement> & { unstyled?: boolean }) => (
    <button {...rest}>{children}</button>
  ),
}));

import { getPolicyComplianceMatrix } from '../../../../api/hrAnalytics';
import { HrPolicyRealityPage } from '../HrPolicyRealityPage';

const mockGetMatrix = getPolicyComplianceMatrix as ReturnType<typeof vi.fn>;

const FAKE_KPIS = {
  compliance_pct: 82,
  active_count: 2,
  avg_overage_eur: null,
  most_overrun_benefit: 'immigration',
  benefit_columns: ['immigration', 'temporary_housing', 'shipment'],
  benefit_labels: {
    immigration: 'Immigration',
    temporary_housing: 'Temp housing',
    shipment: "Int'l shipping",
  },
};

const FAKE_CASES = [
  {
    id: 'case-001',
    name: 'Alice Dupont',
    init: 'AD',
    origin: 'FR',
    dest: 'DE',
    tier: 'Manager',
    assignment_type: 'long_term',
    start_date: '2026-01-15',
    budget_eur: null,
    spend_eur: null,
    cells: {
      immigration: 'green',
      temporary_housing: 'amber',
      shipment: 'blue',
    },
  },
  {
    id: 'case-002',
    name: 'Bob Singh',
    init: 'BS',
    origin: 'IN',
    dest: 'NO',
    tier: 'Director',
    assignment_type: 'short_term',
    start_date: '2026-03-01',
    budget_eur: null,
    spend_eur: null,
    cells: {
      immigration: 'red',
      temporary_housing: 'green',
      shipment: 'grey',
    },
  },
];

beforeEach(() => {
  vi.clearAllMocks();
});

describe('HrPolicyRealityPage', () => {
  it('renders real employee names from the API response', async () => {
    mockGetMatrix.mockResolvedValue({ cases: FAKE_CASES, kpis: FAKE_KPIS });

    render(<HrPolicyRealityPage />);

    await waitFor(() => {
      expect(screen.getByText('Alice Dupont')).toBeTruthy();
      expect(screen.getByText('Bob Singh')).toBeTruthy();
    });
  });

  it('renders real benefit labels from the API kpis', async () => {
    mockGetMatrix.mockResolvedValue({ cases: FAKE_CASES, kpis: FAKE_KPIS });

    render(<HrPolicyRealityPage />);

    await waitFor(() => {
      // Benefit labels from kpis.benefit_labels, not the hardcoded BENEFITS array
      expect(screen.getAllByText('Immigration').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Temp housing').length).toBeGreaterThan(0);
    });
  });

  it('shows the compliance KPI from the API (not hardcoded)', async () => {
    mockGetMatrix.mockResolvedValue({ cases: FAKE_CASES, kpis: FAKE_KPIS });

    render(<HrPolicyRealityPage />);

    await waitFor(() => {
      // 82% comes from kpis.compliance_pct
      expect(screen.getByText(/82/)).toBeTruthy();
    });
  });

  it('shows spend-gated state instead of euro figures', async () => {
    mockGetMatrix.mockResolvedValue({ cases: FAKE_CASES, kpis: FAKE_KPIS });

    render(<HrPolicyRealityPage />);

    await waitFor(() => {
      // Multiple "Spend tracking coming soon" labels expected (KPI + per-row)
      const comingSoonItems = screen.getAllByText('Spend tracking coming soon');
      expect(comingSoonItems.length).toBeGreaterThan(0);
    });

    // Must NOT show fabricated euro amounts from charCodeAt seed logic
    expect(screen.queryByText(/€\d{1,3}(,\d{3})*/)).toBeNull();
  });

  it('shows honest empty state when no cases are returned', async () => {
    mockGetMatrix.mockResolvedValue({
      cases: [],
      kpis: { ...FAKE_KPIS, active_count: 0, compliance_pct: 0, most_overrun_benefit: null },
    });

    render(<HrPolicyRealityPage />);

    await waitFor(() => {
      expect(screen.getByText('No active cases yet')).toBeTruthy();
    });
  });

  it('shows a loading state before the fetch resolves', () => {
    // Never resolves during this test
    mockGetMatrix.mockReturnValue(new Promise(() => {}));

    render(<HrPolicyRealityPage />);

    expect(screen.getByText(/Loading compliance data/i)).toBeTruthy();
  });

  it('shows an error message when the fetch fails', async () => {
    mockGetMatrix.mockRejectedValue(new Error('Network error'));

    render(<HrPolicyRealityPage />);

    await waitFor(() => {
      expect(screen.getByText(/Network error/i)).toBeTruthy();
    });
  });

  it('does NOT render mock employees (Marc Bouchard, Priya Nair)', async () => {
    mockGetMatrix.mockResolvedValue({ cases: FAKE_CASES, kpis: FAKE_KPIS });

    render(<HrPolicyRealityPage />);

    await waitFor(() => {
      expect(screen.getByText('Alice Dupont')).toBeTruthy();
    });

    expect(screen.queryByText('Marc Bouchard')).toBeNull();
    expect(screen.queryByText('Priya Nair')).toBeNull();
  });
});
