/**
 * TEST-4 — Behavioral integration test for the Intake orchestrator
 * (EmployeeIntakePage — the autosave wizard / state-machine layer).
 *
 * Chosen over RelocatePlanIntakePage because this is the page that actually
 * drives the intake state machine through `employeeAPI.getIntake /
 * updateIntakeDraft / updateIntakeProgress`: assignment-resolution → saved-draft
 * hydration → debounced autosave → step advance. RelocatePlanIntakePage uses
 * `patchCase` + localStorage + hardcoded predictions, not those APIs.
 *
 * Behaviour asserted (one end-to-end orchestration flow):
 *   hydrate from a returned draft (starts on the persisted step, fields filled)
 *   → edit a field with user-event → advance a step → reach the next step.
 *
 * The API and the assignment context are mocked; AppShell is stubbed to a
 * passthrough (it is layout, not the unit under test, and fires unrelated
 * network calls on mount).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import type { EmployeeLinkedOverviewRow } from '../../../../types/employeeAssignmentOverview';
import { EmployeeIntakePage } from '../EmployeeIntakePage';

// ── Stub AppShell (layout shell with its own mount-time network) ──────────────
vi.mock('../../../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="app-shell">{children}</div>
  ),
}));

// ── Mock the assignment context: one linked assignment, persisted at step 2 ───
const linkedRow: EmployeeLinkedOverviewRow = {
  assignment_id: 'a1',
  case_id: 'c1',
  status: 'awaiting_intake',
  intake_step: 2,
  destination: { host_country: 'Germany', host_city: 'Berlin', home_country: 'France' },
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

// ── Mock the intake API surface the wizard's state machine drives ─────────────
const getIntake = vi.fn();
const updateIntakeDraft = vi.fn();
const updateIntakeProgress = vi.fn();

vi.mock('../../../../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
  apiGet: vi.fn().mockResolvedValue([]),
  apiPost: vi.fn().mockResolvedValue({}),
  invalidateApiCache: vi.fn(),
  employeeAPI: {
    getIntake: (...a: unknown[]): unknown => getIntake(...a),
    updateIntakeDraft: (...a: unknown[]): unknown => updateIntakeDraft(...a),
    updateIntakeProgress: (...a: unknown[]): unknown => updateIntakeProgress(...a),
    submitAssignment: vi.fn().mockResolvedValue({}),
  },
}));

const SAVED_DRAFT = {
  full_name: 'Marc Bouchard',
  email: 'marc@example.com',
  nationality: 'FR',
  passport_country: 'FR',
  passport_expiry: '2030-01-01',
  origin_country: 'FR',
  origin_city: 'Paris',
  dest_country: 'DE',
  dest_city: 'Berlin',
  target_date: '2026-09-01',
  purpose: 'Employment',
  has_pets: false,
};

function mockGetIntakeWithDraft() {
  getIntake.mockResolvedValue({
    assignmentId: 'a1',
    intakeStep: 2,
    intakeTotalSteps: 5,
    intakeUpdatedAt: null,
    intakeDraft: SAVED_DRAFT,
  });
  updateIntakeDraft.mockResolvedValue({ assignmentId: 'a1', intakeUpdatedAt: null });
  updateIntakeProgress.mockResolvedValue({
    assignmentId: 'a1',
    intakeStep: 2,
    intakeTotalSteps: 5,
    intakeUpdatedAt: null,
  });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <EmployeeIntakePage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  // jsdom in this project doesn't expose localStorage; provide an in-memory stub
  // (the wizard reads relopass_email/role/token via getAuthItem on mount).
  const store = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => {
      store.set(k, v);
    },
    removeItem: (k: string) => {
      store.delete(k);
    },
    clear: () => store.clear(),
  });
});

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe('EmployeeIntakePage — intake orchestration', () => {
  it('hydrates from the saved draft and lands on the persisted step', async () => {
    mockGetIntakeWithDraft();
    renderPage();

    // intake_step:2 puts the user back on "About You", which shows the
    // hydrated full_name from the returned draft.
    expect(await screen.findByDisplayValue('Marc Bouchard')).toBeInTheDocument();
    expect(screen.getByTestId('intake-step-indicator')).toHaveTextContent('Step 2 / 5');
  });

  it('edits a hydrated field and advances to the next step', async () => {
    const user = userEvent.setup();
    mockGetIntakeWithDraft();
    renderPage();

    // Edit (user-event): clear the hydrated value and type a new one.
    const fullName = await screen.findByDisplayValue('Marc Bouchard');
    await user.clear(fullName);
    await user.type(fullName, 'Marc B. Updated');
    expect(fullName).toHaveValue('Marc B. Updated');

    // Advance: step 2 is valid (name/nationality/passport all hydrated), so
    // Continue advances the machine to step 3 ("My People"). goTo() awaits a
    // real updateIntakeDraft flush before moving on.
    await user.click(screen.getByTestId('intake-continue'));

    expect(await screen.findByText(/who's relocating with you\?/i)).toBeInTheDocument();
    expect(screen.getByTestId('intake-step-indicator')).toHaveTextContent('Step 3 / 5');
    expect(updateIntakeDraft).toHaveBeenCalled();
  });
});
