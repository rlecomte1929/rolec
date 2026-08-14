/**
 * AIQ-1648: the Package & limits page rendered the EMPLOYEE's identity under the
 * "HR owner" chip. It must show the HR account that owns the case
 * (case_assignments.hr_user_id → users.email, surfaced as assignment.hrOwnerEmail),
 * never the employee.
 */
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mocks = vi.hoisted(() => ({ getAssignment: vi.fn() }));
// Mock the api barrel (also dodges the api/supabase jsdom import trap).
vi.mock('../../api/client', () => ({ hrAPI: { getAssignment: mocks.getAssignment } }));
vi.mock('../../api/supabase', () => ({ supabase: {} }));
// Passthrough shell + nav so the test focuses on the page body.
vi.mock('../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock('../../navigation/registry', () => ({ useRegisterNav: () => {} }));
vi.mock('../../navigation/safeNavigate', () => ({ safeNavigate: vi.fn() }));

import { HrAssignmentPackageReview } from '../HrAssignmentPackageReview';

// jsdom here has no localStorage (the queryFn stashes the last assignment id).
if (!window.localStorage) {
  const store = new Map<string, string>();
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
      setItem: (k: string, v: string) => void store.set(k, String(v)),
      removeItem: (k: string) => void store.delete(k),
      clear: () => store.clear(),
    },
  });
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/hr/package/asg-1']}>
        <Routes>
          <Route path="/hr/package/:id" element={<HrAssignmentPackageReview />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const BASE = {
  id: 'asg-1',
  caseId: 'case-1',
  employeeIdentifier: 'emp-alex@probe.test',
  status: 'submitted',
  profile: null,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('HrAssignmentPackageReview — "HR owner" chip (AIQ-1648)', () => {
  it('shows the HR owner account, never the employee', async () => {
    mocks.getAssignment.mockResolvedValue({ ...BASE, hrOwnerEmail: 'hr-owner@probe.test' });
    renderPage();

    const chip = await screen.findByText(/HR owner:/i);
    expect(chip).toHaveTextContent('HR owner: hr-owner@probe.test');
    // The employee identity must NOT appear in the HR owner chip.
    expect(chip).not.toHaveTextContent('emp-alex');
  });

  it('falls back to "Unassigned" when there is no HR owner (still never the employee)', async () => {
    mocks.getAssignment.mockResolvedValue({ ...BASE, hrOwnerEmail: null });
    renderPage();

    const chip = await screen.findByText(/HR owner:/i);
    expect(chip).toHaveTextContent('HR owner: Unassigned');
    expect(chip).not.toHaveTextContent('emp-alex');
  });
});
