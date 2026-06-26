/**
 * TEST-4 — Behavioral integration test for the Comparison orchestrator
 * (EmployeeBenefitComparisonPage).
 *
 * Post-RX-3 the page fetches through TanStack `useQuery` and reads the active
 * case from `useEmployeeAssignment()`. We exercise the two orchestration
 * branches that matter:
 *   1. a linked assignment → the benefit comparison dashboard renders from the
 *      mocked engine output;
 *   2. no linked assignment → the case-aware "No company linked yet" empty card.
 *
 * AppShell is stubbed (layout + unrelated mount-time network). The render is
 * wrapped in QueryClientProvider (retry:false) + MemoryRouter; the assignment
 * context is mocked with a mutable value so each test sets its own case scope.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { createTestQueryClient } from '../../../hooks/__tests__/queryTestUtils';
import type { PolicyServiceComparisonResponse } from '../../../types';

// ── Stub AppShell ────────────────────────────────────────────────────────────
vi.mock('../../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="app-shell">{children}</div>
  ),
}));

// ── Mutable assignment-context mock (each test sets the case scope) ───────────
type AssignmentCtx = {
  assignmentId: string | null;
  primaryCaseId: string | null;
  primaryAssignmentCompany: null;
  isLoading: boolean;
  linkedCount: number;
  pendingCount: number;
  linkedSummaries: Array<{ assignment_id: string; case_id: string; status: string }>;
  pendingSummaries: never[];
  overviewError: null;
  refetch: () => void;
};

let ctx: AssignmentCtx;

vi.mock('../../../contexts/EmployeeAssignmentContext', () => ({
  useEmployeeAssignment: () => ctx,
}));

// ── Mock the comparison API surface ──────────────────────────────────────────
const getPolicyServiceComparison = vi.fn();
const getServicesPolicyContext = vi.fn();

vi.mock('../../../api/client', () => ({
  employeeAPI: {
    getPolicyServiceComparison: (...a: unknown[]) => getPolicyServiceComparison(...a),
    getServicesPolicyContext: (...a: unknown[]) => getServicesPolicyContext(...a),
  },
}));

import { EmployeeBenefitComparisonPage } from '../EmployeeBenefitComparisonPage';

function linkedCtx(): AssignmentCtx {
  return {
    assignmentId: 'a1',
    primaryCaseId: 'c1',
    primaryAssignmentCompany: null,
    isLoading: false,
    linkedCount: 1,
    pendingCount: 0,
    linkedSummaries: [{ assignment_id: 'a1', case_id: 'c1', status: 'submitted' }],
    pendingSummaries: [],
    overviewError: null,
    refetch: vi.fn(),
  };
}

function noCompanyCtx(): AssignmentCtx {
  return {
    assignmentId: null,
    primaryCaseId: null,
    primaryAssignmentCompany: null,
    isLoading: false,
    linkedCount: 0,
    pendingCount: 0,
    linkedSummaries: [],
    pendingSummaries: [],
    overviewError: null,
    refetch: vi.fn(),
  };
}

const COMPARISON: PolicyServiceComparisonResponse = {
  comparisons: [],
  resolved_policy: {
    id: 'pol-1',
    policy_version_id: 'ver-1',
    resolved_at: '2026-01-01T00:00:00Z',
  },
  assignment_id: 'a1',
  case_id: 'c1',
  effective_service_comparison: [
    {
      service_key: 'temporary_housing',
      coverage_status: 'covered',
      comparison_status: 'within_policy',
      policy_limit_snapshot: { amount: 5000, currency: 'EUR' },
      selected_value_snapshot: { amount: 4000, currency: 'EUR' },
      delta: 1000,
      explanation: 'Within your housing allowance.',
      approval_required: false,
    },
  ],
};

const POLICY_CONTEXT = {
  currency: 'EUR',
  categories: {},
  policy_surface: {
    company_name: 'Acme Corp',
    version: 1,
    effective_date: '2026-01-01',
  },
};

function renderPage() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter>
        <EmployeeBenefitComparisonPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  ctx = linkedCtx();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('EmployeeBenefitComparisonPage — comparison orchestration', () => {
  it('renders the comparison dashboard for a linked assignment', async () => {
    getPolicyServiceComparison.mockResolvedValue(COMPARISON);
    getServicesPolicyContext.mockResolvedValue(POLICY_CONTEXT);
    renderPage();

    // KPI tile from BenefitComparisonDashboard — proves the case-scoped query
    // resolved and the comparison rendered.
    expect(await screen.findByText('Total policy allocation')).toBeInTheDocument();
    expect(getPolicyServiceComparison).toHaveBeenCalledWith('a1');
  });

  it('shows the case-aware empty state when no assignment is linked', async () => {
    ctx = noCompanyCtx();
    renderPage();

    expect(await screen.findByText('No company linked yet')).toBeInTheDocument();
    // The dashboard must not render, and no comparison fetch fires without a case.
    expect(screen.queryByText('Total policy allocation')).not.toBeInTheDocument();
    expect(getPolicyServiceComparison).not.toHaveBeenCalled();
  });
});
