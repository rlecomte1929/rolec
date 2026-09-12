import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

/**
 * AIQ-2285 / T8 — when the overview does not resolve, nothing on the dashboard
 * may assert that the employee has no relocation case.
 *
 * #2324 gated the manual-claim onboarding and the assignment sections on
 * resolveOverviewState. The page HEADER was left behind: shellSubtitle still
 * fell through to "Your case appears here once it is linked.", so the error
 * alert rendered directly underneath a title bar making the opposite claim.
 *
 * This renders the real page through the real context so the wiring is covered,
 * not just the pure function (which overviewResolution.test.ts already pins).
 */

const mocks = vi.hoisted(() => ({ getAssignmentsOverview: vi.fn() }));

vi.mock('../../api/client', () => ({
  employeeAPI: {
    getAssignmentsOverview: (...a: unknown[]) => mocks.getAssignmentsOverview(...a),
  },
  invalidateApiCache: vi.fn(),
}));
vi.mock('../../api/supabase', () => ({ supabase: {} }));
vi.mock('../../components/AppShell', () => ({
  AppShell: ({ title, subtitle, children }: { title?: string; subtitle?: string; children: React.ReactNode }) => (
    <div>
      <h1>{title}</h1>
      {subtitle ? <p>{subtitle}</p> : null}
      {children}
    </div>
  ),
}));
vi.mock('../../hooks/useWelcomeRedirect', () => ({ useWelcomeRedirect: () => {} }));
vi.mock('../../contexts/SelectedCaseContext', () => ({
  useSelectedCase: () => ({ selectedCaseId: null, setSelectedCaseId: () => {} }),
}));
// jsdom in this config has no localStorage, so stub the accessor layer instead
// of seeding storage (utils/demo reads localStorage directly).
vi.mock('../../utils/demo', () => ({
  getAuthItem: (k: string) =>
    ({ relopass_token: 'tok', relopass_role: 'EMPLOYEE' } as Record<string, string>)[k] ?? null,
  setAuthItem: vi.fn(),
  clearAuthItems: vi.fn(),
  normalizeStoredRole: (r: string | null | undefined) => (r ?? '').toUpperCase(),
  setStoredRoles: vi.fn(),
  getStoredRoles: () => ['EMPLOYEE'],
  getActiveRole: () => 'EMPLOYEE',
  setActiveRole: vi.fn(),
}));
vi.mock('../../utils/welcomeSeen', () => ({ hasSeenWelcome: () => true, markWelcomeSeen: vi.fn() }));

import { EmployeeJourney } from '../EmployeeJourney';
import { EmployeeAssignmentProvider } from '../../contexts/EmployeeAssignmentContext';

/** Every phrase that asserts, as fact, that the user has no relocation case. */
const NO_CASE_ASSERTIONS = [
  /your case appears here once it is linked/i,            // shell subtitle
  /not linked/i,                                          // status badge
  /if HR already set up a case for your verified email/i, // linking instruction
  /nothing's gone wrong/i,                                // onboarding block
];

function renderDashboard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/employee/dashboard']}>
        <EmployeeAssignmentProvider>
          <EmployeeJourney />
        </EmployeeAssignmentProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('EmployeeJourney — unresolved overview', () => {
  it('makes no "no case" claim anywhere on the page when the overview errored', async () => {
    mocks.getAssignmentsOverview.mockRejectedValue(
      Object.assign(new Error('forbidden'), { response: { status: 403 } }),
    );

    renderDashboard();

    expect(await screen.findByText(/cannot open employee assignments/i)).toBeInTheDocument();
    for (const phrase of NO_CASE_ASSERTIONS) {
      expect(screen.queryByText(phrase)).not.toBeInTheDocument();
    }
  });

  it('makes no "no case" claim when the backend flagged the payload degraded', async () => {
    mocks.getAssignmentsOverview.mockResolvedValue({ linked: [], pending: [], overview_degraded: true });

    renderDashboard();

    // Degraded is a 200, so the guard has to come from the flag, not from isError.
    expect(await screen.findByText(/could not load your assignments just now/i)).toBeInTheDocument();
    for (const phrase of NO_CASE_ASSERTIONS) {
      expect(screen.queryByText(phrase)).not.toBeInTheDocument();
    }
  });

  it('still shows the onboarding and the subtitle when the overview resolved genuinely empty', async () => {
    mocks.getAssignmentsOverview.mockResolvedValue({ linked: [], pending: [] });

    renderDashboard();

    // Control: without this the fix could "pass" by hiding the empty state forever.
    expect(await screen.findByText(/nothing's gone wrong/i)).toBeInTheDocument();
    expect(screen.getByText(/your case appears here once it is linked/i)).toBeInTheDocument();
    expect(screen.queryByText(/cannot open employee assignments/i)).not.toBeInTheDocument();
  });
});
