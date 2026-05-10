import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { MemoryRouter } from 'react-router-dom';
import { EmployeePolicyPanel } from '../EmployeePolicyPanel';
import { mockEmployeePackage } from './hrPolicyTestUtils';
import type { EffectiveServiceComparisonRow } from '../../../types';

const employeeApiMocks = vi.hoisted(() => ({
  getMyAssignmentPackagePolicy: vi.fn(),
  getPolicyServiceComparison: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  employeeAPI: {
    getMyAssignmentPackagePolicy: (...args: unknown[]) =>
      employeeApiMocks.getMyAssignmentPackagePolicy(...args),
    getPolicyServiceComparison: (...args: unknown[]) =>
      employeeApiMocks.getPolicyServiceComparison(...args),
  },
}));

function row(
  overrides: Partial<EffectiveServiceComparisonRow> & Pick<EffectiveServiceComparisonRow, 'service_key' | 'comparison_status'>
): EffectiveServiceComparisonRow {
  return {
    coverage_status: 'included',
    policy_limit_snapshot: { max_value: 5000, currency: 'USD' },
    selected_value_snapshot: { estimated_cost: 4000, currency: 'USD' },
    delta: 0,
    explanation: 'Test explanation for this service.',
    approval_required: false,
    ...overrides,
  };
}

function renderPanel(pack: ReturnType<typeof mockEmployeePackage>, loading = false) {
  return render(
    <MemoryRouter>
      <EmployeePolicyPanel pack={pack} loading={loading} />
    </MemoryRouter>
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  employeeApiMocks.getPolicyServiceComparison.mockResolvedValue({
    assignment_id: 'asg-1',
    comparisons: [],
    effective_service_comparison: [],
    comparison_available: false,
    comparison_readiness: { comparison_ready: false, comparison_blockers: [] },
  });
});

describe('EmployeePolicyPanel — lifecycle messaging', () => {
  it('no published policy: neutral banner copy', () => {
    renderPanel(mockEmployeePackage('no_policy_found'));
    expect(screen.getByText(/No live relocation policy yet/i)).toBeInTheDocument();
    expect(screen.getByText(/HR has not published/i)).toBeInTheDocument();
  });

  it('policy live but comparison not ready: informational / under-review banner', () => {
    renderPanel(mockEmployeePackage('found_under_review'));
    expect(screen.getByText(/Policy is live—some details are still filling in/i)).toBeInTheDocument();
  });

  it('partial comparison: amber-style partial title', () => {
    renderPanel(mockEmployeePackage('found_partial'));
    expect(screen.getByText(/Your benefits from the published policy/i)).toBeInTheDocument();
    expect(screen.getByText(/Temporary housing/i)).toBeInTheDocument();
  });

  it('full comparison: green-style title', async () => {
    employeeApiMocks.getPolicyServiceComparison.mockResolvedValue({
      assignment_id: 'asg-1',
      comparisons: [],
      effective_service_comparison: [],
      comparison_available: true,
      comparison_readiness: { comparison_ready: true, comparison_blockers: [] },
    });
    renderPanel(mockEmployeePackage('found_full'));
    await waitFor(() => expect(screen.getByText(/Your benefits and policy comparisons/i)).toBeInTheDocument());
  });

  it('read-only: no editable fields', () => {
    renderPanel(mockEmployeePackage('found_partial'));
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('employee-facing strings avoid internal API jargon', () => {
    const { container } = renderPanel(mockEmployeePackage('found_partial'));
    const t = container.textContent ?? '';
    expect(t).not.toMatch(/\brls\b/i);
    expect(t).not.toMatch(/\bpolicy_readiness\b/i);
  });
});

describe('EmployeePolicyPanel — service comparison behavior', () => {
  beforeEach(() => {
    employeeApiMocks.getPolicyServiceComparison.mockImplementation(async () => ({
      assignment_id: 'asg-1',
      comparisons: [],
      comparison_readiness: { comparison_ready: true, comparison_blockers: [] },
      comparison_available: true,
      effective_service_comparison: [] as EffectiveServiceComparisonRow[],
    }));
  });

  it('within envelope: shows within-limit wording and difference line', async () => {
    employeeApiMocks.getPolicyServiceComparison.mockResolvedValue({
      assignment_id: 'asg-1',
      comparisons: [],
      comparison_available: true,
      comparison_readiness: { comparison_ready: true, comparison_blockers: [] },
      effective_service_comparison: [
        row({
          service_key: 'temporary_housing',
          comparison_status: 'within_envelope',
          delta: -500,
          explanation: 'Within cap.',
        }),
      ],
    });
    renderPanel(mockEmployeePackage('found_full'));
    await waitFor(() => expect(screen.getByText(/Within policy limit/i)).toBeInTheDocument());
    expect(screen.getByText(/Within limit/i)).toBeInTheDocument();
  });

  it('exceeds envelope: shows over-by wording', async () => {
    employeeApiMocks.getPolicyServiceComparison.mockResolvedValue({
      assignment_id: 'asg-1',
      comparisons: [],
      comparison_available: true,
      comparison_readiness: { comparison_ready: true, comparison_blockers: [] },
      effective_service_comparison: [
        row({
          service_key: 'home_search',
          comparison_status: 'exceeds_envelope',
          delta: 1200,
          explanation: 'Over limit.',
        }),
      ],
    });
    renderPanel(mockEmployeePackage('found_full'));
    await waitFor(() => expect(screen.getByText(/Above policy limit/i)).toBeInTheDocument());
    expect(screen.getByText(/Over by/i)).toBeInTheDocument();
  });

  it('excluded: labeled excluded, no numeric delta', async () => {
    employeeApiMocks.getPolicyServiceComparison.mockResolvedValue({
      assignment_id: 'asg-1',
      comparisons: [],
      comparison_available: true,
      comparison_readiness: { comparison_ready: true, comparison_blockers: [] },
      effective_service_comparison: [
        row({
          service_key: 'visa_support',
          comparison_status: 'excluded',
          coverage_status: 'excluded',
          delta: null,
          explanation: 'Not covered for this route.',
        }),
      ],
    });
    renderPanel(mockEmployeePackage('found_full'));
    await waitFor(() => expect(screen.getByText(/Excluded/i)).toBeInTheDocument());
    expect(screen.queryByText(/Difference vs limit/i)).not.toBeInTheDocument();
  });

  it('informational only: no delta vs limit', async () => {
    employeeApiMocks.getPolicyServiceComparison.mockResolvedValue({
      assignment_id: 'asg-1',
      comparisons: [],
      comparison_available: true,
      comparison_readiness: { comparison_ready: true, comparison_blockers: [] },
      effective_service_comparison: [
        row({
          service_key: 'school_search',
          comparison_status: 'information_only',
          delta: 100,
          explanation: 'Descriptive only.',
        }),
      ],
    });
    renderPanel(mockEmployeePackage('found_full'));
    await waitFor(() => expect(screen.getByText(/Informational/i)).toBeInTheDocument());
    expect(screen.queryByText(/Difference vs limit/i)).not.toBeInTheDocument();
  });

  it('not enough policy data: no delta vs limit', async () => {
    employeeApiMocks.getPolicyServiceComparison.mockResolvedValue({
      assignment_id: 'asg-1',
      comparisons: [],
      comparison_available: true,
      comparison_readiness: { comparison_ready: true, comparison_blockers: [] },
      effective_service_comparison: [
        row({
          service_key: 'household_goods_shipment',
          comparison_status: 'not_enough_policy_data',
          delta: 50,
          explanation: 'Policy missing numeric cap.',
        }),
      ],
    });
    renderPanel(mockEmployeePackage('found_full'));
    await waitFor(() => expect(screen.getByText(/Needs more detail/i)).toBeInTheDocument());
    expect(screen.queryByText(/Difference vs limit/i)).not.toBeInTheDocument();
  });

  it('approval flag surfaces on comparison row', async () => {
    employeeApiMocks.getPolicyServiceComparison.mockResolvedValue({
      assignment_id: 'asg-1',
      comparisons: [],
      comparison_available: true,
      comparison_readiness: { comparison_ready: true, comparison_blockers: [] },
      effective_service_comparison: [
        row({
          service_key: 'temporary_housing',
          comparison_status: 'within_envelope',
          approval_required: true,
          delta: 0,
        }),
      ],
    });
    renderPanel(mockEmployeePackage('found_full'));
    await waitFor(() => expect(screen.getByText(/Approval may be required/i)).toBeInTheDocument());
  });

  it('benefit row shows approval when required', () => {
    renderPanel(
      mockEmployeePackage('found_partial', {
        benefits: [
          {
            benefit_key: 'temporary_housing',
            included: true,
            max_value: 2000,
            currency: 'USD',
            approval_required: true,
          },
        ],
      })
    );
    expect(screen.getByText(/Your employer requires approval before this benefit is used/i)).toBeInTheDocument();
  });
});
