/**
 * TD-FIX-7 (AIQ-1510) — the route fields lock ONLY on a test drive.
 *
 * Why this test exists: relocation_cases.home_country/host_country are written back from
 * the EMPLOYEE's own intake answers (backend/db/intake.py apply_wizard_patch_side_effects
 * → touch_relocation_case_route_from_wizard). The hydration effect re-reads those columns,
 * so on a second visit a REAL employee sees their own answers coming back. Locking them
 * would badge the user's own input "🔒 HR pre-filled" — a false provenance claim.
 *
 * So:
 *   • test drive  → origin + destination locked (the corridor really is fixed by us)
 *   • real user   → origin stays EDITABLE (regression guard)
 *
 * The test-drive signal is the localStorage slice that /test-drive stashes at provision.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { EmployeeLinkedOverviewRow } from '../../../../types/employeeAssignmentOverview';
import { EmployeeIntakePage } from '../EmployeeIntakePage';

vi.mock('../../../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

// A case whose route columns are populated — i.e. exactly what a real employee sees on
// their SECOND visit (their own answers written back), and what a test-drive tester sees
// on their first (the corridor stamped at assign).
const linkedRow: EmployeeLinkedOverviewRow = {
  assignment_id: 'a1',
  case_id: 'c1',
  status: 'awaiting_intake',
  intake_step: 1,
  destination: {
    home_country: 'Netherlands',
    home_city: 'Amsterdam',
    host_country: 'Singapore',
    host_city: 'Singapore',
  },
};

vi.mock('../../../../contexts/EmployeeAssignmentContext', () => ({
  useEmployeeAssignment: () => ({
    assignmentId: 'a1',
    primaryCaseId: 'c1',
    primaryAssignmentCompany: null,
    isLoading: false,
    linkedCount: 1,
    pendingCount: 0,
    linkedSummaries: [linkedRow],
    pendingSummaries: [],
    overviewError: null,
    refetch: vi.fn(),
  }),
}));

vi.mock('../../../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
  apiGet: vi.fn().mockResolvedValue([]),
  apiPost: vi.fn().mockResolvedValue({}),
  invalidateApiCache: vi.fn(),
  employeeAPI: {
    getIntake: vi.fn().mockResolvedValue({
      assignmentId: 'a1',
      intakeStep: 1,
      intakeTotalSteps: 5,
      intakeUpdatedAt: null,
      intakeDraft: null,
    }),
    updateIntakeDraft: vi.fn().mockResolvedValue({ assignmentId: 'a1', intakeUpdatedAt: null }),
    updateIntakeProgress: vi.fn().mockResolvedValue({ assignmentId: 'a1', intakeStep: 1 }),
    submitAssignment: vi.fn().mockResolvedValue({}),
  },
}));

let store: Map<string, string>;

beforeEach(() => {
  // jsdom here has no localStorage — the page reads the test-drive slice through it.
  store = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => { store.set(k, v); },
    removeItem: (k: string) => { store.delete(k); },
    clear: () => store.clear(),
  });
});

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

function renderPage() {
  return render(
    <MemoryRouter>
      <EmployeeIntakePage />
    </MemoryRouter>,
  );
}

const asTestDrive = () =>
  store.set('relopass_test_drive', JSON.stringify({
    campaign: 'insead-2026', corridor_id: 'NL_SG', session_id: 's1',
  }));

describe('intake route fields — locked only on a test drive', () => {
  it('TEST DRIVE: origin and destination are pre-filled, disabled, and offer no "Edit"', async () => {
    asTestDrive();
    renderPage();

    const origin = await screen.findByTestId('intake-origin_country');
    expect(origin).toHaveValue('Netherlands');
    expect(origin).toBeDisabled();
    expect(screen.getByTestId('intake-origin_city')).toBeDisabled();
    expect(screen.getByTestId('intake-dest_country')).toBeDisabled();
    expect(screen.getByTestId('intake-dest_city')).toBeDisabled();

    // The corridor is fixed and the server overrides it anyway — re-opening the field
    // would only let the tester enter a value that is silently discarded.
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument();
  });

  it('REAL USER: origin stays EDITABLE — their own answer is never badged "HR pre-filled"', async () => {
    // no test-drive slice in localStorage
    renderPage();

    const origin = await screen.findByTestId('intake-origin_country');
    expect(origin).not.toBeDisabled();
    expect(screen.getByTestId('intake-origin_city')).not.toBeDisabled();
    // destination city likewise stays editable for real users (pre-TD-FIX-7 behaviour)
    expect(screen.getByTestId('intake-dest_city')).not.toBeDisabled();
  });
});
