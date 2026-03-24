import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { HrPolicyConfigPage } from '../../../pages/HrPolicyConfigPage';
import { AdminPolicyConfigPage } from '../../../pages/admin/AdminPolicyConfigPage';
import { EmployeePolicyPage } from '../../../pages/employee/EmployeePolicyPage';
import { PolicyConfigFilters } from '../PolicyConfigFilters';
import { PolicyConfigHeader } from '../PolicyConfigHeader';
import { BenefitRowEditor } from '../BenefitRowEditor';
import { PolicyCapEstimateRow } from '../PolicyCapEstimateRow';
import type { PolicyConfigBenefitRow } from '../types';

const apiMocks = vi.hoisted(() => ({
  hrGet: vi.fn(),
  hrPutDraft: vi.fn(),
  hrPublish: vi.fn(),
  adminGet: vi.fn(),
  adminListCompanies: vi.fn(),
  employeeGet: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  policyConfigMatrixAPI: {
    hrGet: (...args: unknown[]) => apiMocks.hrGet(...args),
    hrPutDraft: (...args: unknown[]) => apiMocks.hrPutDraft(...args),
    hrPublish: (...args: unknown[]) => apiMocks.hrPublish(...args),
    adminGet: (...args: unknown[]) => apiMocks.adminGet(...args),
    employeeGet: (...args: unknown[]) => apiMocks.employeeGet(...args),
  },
  adminAPI: {
    listCompanies: (...args: unknown[]) => apiMocks.adminListCompanies(...args),
  },
}));

vi.mock('../../../utils/demo', () => ({
  getAuthItem: (k: string) => (k === 'relopass_role' ? 'ADMIN' : k === 'relopass_token' ? 't' : null),
  normalizeStoredRole: (r: string | null) => (r ?? '').trim().toUpperCase(),
}));

vi.mock('../../../components/AppShell', () => ({
  AppShell: ({ children, title, subtitle }: { children: React.ReactNode; title?: string; subtitle?: string }) => (
    <div data-testid="app-shell">
      {title ? <h1>{title}</h1> : null}
      {subtitle ? <p>{subtitle}</p> : null}
      {children}
    </div>
  ),
}));

vi.mock('../usePolicyConfigLeaveGuard', () => ({
  usePolicyConfigLeaveGuard: () => {},
}));

vi.mock('../../../pages/admin/AdminLayout', () => ({
  AdminLayout: ({ children, title, subtitle }: { children: React.ReactNode; title?: string; subtitle?: string }) => (
    <div data-testid="admin-layout">
      {title ? <h1>{title}</h1> : null}
      {subtitle ? <p>{subtitle}</p> : null}
      {children}
    </div>
  ),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const matrixPayload = {
  policy_version: 'pv-draft-1',
  version_number: 1,
  effective_date: '2025-04-01',
  status: 'draft',
  editable: true,
  source: 'draft',
  created_at: '2025-01-01T00:00:00',
  updated_at: '2025-01-02T00:00:00',
  categories: [
    {
      category_key: 'compensation_allowances',
      category_label: 'Compensation & allowances',
      benefits: [
        {
          benefit_key: 'cola',
          benefit_label: 'COLA',
          category: 'compensation_allowances',
          covered: true,
          value_type: 'currency',
          amount_value: 500,
          currency_code: 'USD',
          unit_frequency: 'monthly',
          assignment_types: [] as string[],
          family_statuses: [] as string[],
          cap_rule_json: {},
          conditions_json: {},
        },
        {
          benefit_key: 'mobility_premium',
          benefit_label: 'Mobility premium',
          category: 'compensation_allowances',
          covered: false,
          value_type: 'none',
          unit_frequency: 'one_time',
          assignment_types: ['long_term'],
          family_statuses: [] as string[],
          cap_rule_json: {},
          conditions_json: {},
        },
      ],
    },
  ],
};

describe('Compensation & Allowance — routes render', () => {
  beforeEach(() => {
    apiMocks.hrGet.mockResolvedValue(matrixPayload);
    apiMocks.adminGet.mockResolvedValue(matrixPayload);
    apiMocks.adminListCompanies.mockResolvedValue({
      companies: [{ id: 'co-1', name: 'Acme Co' }],
    });
    apiMocks.employeeGet.mockResolvedValue({
      has_policy_config: true,
      effective_date: '2025-04-01',
      policy_version: 'pub-1',
      version_number: 1,
      categories: [
        {
          category_key: 'compensation_allowances',
          category_label: 'Compensation & allowances',
          benefits: [
            {
              benefit_key: 'cola',
              benefit_label: 'COLA',
              covered: true,
              value_type: 'currency',
              amount_value: 500,
              currency_code: 'USD',
              unit_frequency: 'monthly',
            },
          ],
        },
      ],
    });
  });

  it('renders /hr/policy-config with matrix heading and category', async () => {
    render(
      <MemoryRouter initialEntries={['/hr/policy-config']}>
        <Routes>
          <Route path="/hr/policy-config" element={<HrPolicyConfigPage />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(apiMocks.hrGet).toHaveBeenCalled());
    expect(
      screen.getAllByRole('heading', { name: /Compensation & Allowance/i }).length
    ).toBeGreaterThanOrEqual(1);
    expect(await screen.findByText(/Compensation & allowances/i)).toBeInTheDocument();
    expect(await screen.findByDisplayValue('500')).toBeInTheDocument();
    expect(screen.getByText('cola')).toBeInTheDocument();
  });

  it('renders /admin/policy-config when company selected', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/policy-config?companyId=co-1']}>
        <Routes>
          <Route path="/admin/policy-config" element={<AdminPolicyConfigPage />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(apiMocks.adminListCompanies).toHaveBeenCalled());
    await waitFor(() => expect(apiMocks.adminGet).toHaveBeenCalled());
    expect(
      screen.getAllByRole('heading', { name: /Compensation & Allowance/i }).length
    ).toBeGreaterThanOrEqual(1);
  });

  it('renders /employee/policy with covered benefit only', async () => {
    render(
      <MemoryRouter initialEntries={['/employee/policy']}>
        <Routes>
          <Route path="/employee/policy" element={<EmployeePolicyPage />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => expect(apiMocks.employeeGet).toHaveBeenCalled());
    await waitFor(() => {
      const benefitTitles = screen
        .getAllByRole('heading', { level: 3 })
        .map((el) => el.textContent || '');
      // Benefit h3 concatenates visible label + sr-only glossary copy — avoid \b word boundaries on "COLA".
      expect(benefitTitles.some((t) => /COLA/i.test(t))).toBe(true);
      expect(benefitTitles.some((t) => /Mobility premium/i.test(t))).toBe(false);
    });
  });
});

describe('PolicyConfigFilters preview selectors', () => {
  it('invokes callbacks when assignment and family preview change', () => {
    const onAt = vi.fn();
    const onFs = vi.fn();
    render(
      <PolicyConfigFilters
        assignmentType={null}
        familyStatus={null}
        onAssignmentType={onAt}
        onFamilyStatus={onFs}
      />
    );
    const selects = screen.getAllByRole('combobox');
    expect(selects.length).toBeGreaterThanOrEqual(2);
    fireEvent.change(selects[0], { target: { value: 'long_term' } });
    fireEvent.change(selects[1], { target: { value: 'dependents' } });
    expect(onAt).toHaveBeenCalledWith('long_term');
    expect(onFs).toHaveBeenCalledWith('dependents');
  });
});

describe('PolicyConfigHeader publish gate', () => {
  it('disables Publish when publishAllowed is false', () => {
    render(
      <PolicyConfigHeader
        meta={{
          status: 'draft',
          source: 'draft',
          version_number: 1,
          effective_date: '2025-01-01',
          published_at: null,
          created_at: null,
          updated_at: null,
          policy_version: 'pv1',
        }}
        readOnlySnapshot={null}
        editingLocked={false}
        dirty={false}
        saving={false}
        publishing={false}
        lastSavedAt={null}
        onSaveDraft={() => undefined}
        onPublishClick={() => undefined}
        onReload={() => undefined}
        onViewPublished={() => undefined}
        onBackToDraft={() => undefined}
        onOpenHistory={() => undefined}
        onStartEditing={() => undefined}
        publishAllowed={false}
        publishDisabledHint="Set an effective date before publishing."
      />
    );
    expect(screen.getByRole('button', { name: /Publish…/i })).toBeDisabled();
  });
});

describe('BenefitRowEditor', () => {
  const baseRow: PolicyConfigBenefitRow = {
    benefit_key: 'cola',
    benefit_label: 'COLA',
    covered: true,
    value_type: 'currency',
    amount_value: 100,
    currency_code: 'USD',
    unit_frequency: 'monthly',
    assignment_types: [],
    family_statuses: [],
    cap_rule_json: {},
    conditions_json: {},
  };

  it('toggles covered and hides value fields when off', () => {
    const onChange = vi.fn();
    const { container } = render(
      <BenefitRowEditor row={baseRow} disabled={false} onChange={onChange} />
    );
    const covered = container.querySelector('input[type="checkbox"]') as HTMLInputElement;
    expect(covered).toBeTruthy();
    fireEvent.click(covered);
    expect(onChange).toHaveBeenCalled();
    const arg = onChange.mock.calls[0][0] as PolicyConfigBenefitRow;
    expect(arg.covered).toBe(false);
  });

  it('shows amount field when covered and currency type', () => {
    render(<BenefitRowEditor row={baseRow} disabled={false} onChange={() => undefined} />);
    expect(screen.getByRole('spinbutton')).toBeInTheDocument();
  });
});

describe('PolicyCapEstimateRow — over-cap badge', () => {
  it('renders Exceeds policy when comparison is over cap', () => {
    render(
      <PolicyCapEstimateRow
        title="Housing"
        result={{
          benefit_key: 'housing',
          matched_cap: true,
          supported_comparison: true,
          within_cap: false,
          cap_amount: 3000,
          estimate_amount: 4000,
          difference_amount: 1000,
          difference_direction: 'over',
          currency_code: 'USD',
        }}
        estimateAmount={4000}
        estimateCurrency="USD"
      />
    );
    expect(screen.getByText(/Exceeds policy/i)).toBeInTheDocument();
    expect(screen.getByText(/Estimate exceeds approved budget/i)).toBeInTheDocument();
  });
});
