/**
 * TEST-4 — Behavioral integration test for the Roadmap orchestrator
 * (EmployeeCaseRoadmapPage).
 *
 * The page resolves :caseId, drives the generating → ready/empty/failed state
 * machine off the milestone-backed plan view, and renders the redesigned
 * roadmap template (phase stepper + per-phase task list). We mock the plan-view
 * fetch (the load-bearing call), the header-details fetch, and the validate
 * endpoint, then assert the ready state renders the task list and phase stepper.
 *
 * AppShell is stubbed (layout + unrelated mount-time network). The page uses a
 * custom data hook (not useQuery), so only MemoryRouter (for :caseId) is needed.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { RelocationPlanViewResponseDTO } from '../../../types/relocationPlanView';
import { EmployeeCaseRoadmapPage } from '../EmployeeCaseRoadmapPage';
import { resolveRoadmapBuildVariant } from '../roadmapBuildVariant';

// ── Stub AppShell ────────────────────────────────────────────────────────────
// The data sheet is orthogonal to roadmap behaviour and pulls in React Query; stub it so this
// page test needs no QueryClientProvider. DataSheetView has its own coverage in features/datasheet.
vi.mock('../../../features/datasheet/DataSheetView', () => ({ DataSheetView: () => null }));
vi.mock('../../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="app-shell">{children}</div>
  ),
}));

// The page imports ExplainTermPopover → api/client → the Supabase singleton,
// which calls createClient() at module load and throws "supabaseUrl is required"
// with no env. Stub it (established pattern; the client is never exercised here).
vi.mock('../../../api/supabase', () => ({ supabase: {} }));
vi.mock('../../../api/supabaseAuth', () => ({ signOutSupabase: vi.fn() }));

// ── Mock the plan-view fetch the roadmap hook chain depends on ───────────────
const fetchRelocationPlanView = vi.fn();
vi.mock('../../../api/relocationPlanView', () => ({
  fetchRelocationPlanView: (...a: unknown[]) => fetchRelocationPlanView(...a),
}));

// ── Header-details + validate are imported by the page; stub them ─────────────
vi.mock('../../../api/caseDetails', () => ({
  getCaseDetailsByAssignmentId: vi.fn().mockResolvedValue({ data: null, error: null }),
}));
vi.mock('../../../api/cases', () => ({
  validateRoadmap: vi.fn().mockResolvedValue({ roadmap_validated_at: null }),
}));
// [AIQ-2142] The page now always consults server entitlement (no build flag). Resolve it
// unlocked so these tests exercise the roadmap render, not the paywall gate — the same
// state production sees while the server-side paywall is off.
vi.mock('../../../utils/paymentStatus', () => ({
  fetchRoadmapUnlocked: vi.fn().mockResolvedValue(true),
}));

const READY_PLAN: RelocationPlanViewResponseDTO = {
  case_id: 'c1',
  assignment_id: 'a1',
  role: 'employee',
  summary: {
    total_tasks: 3,
    completed_tasks: 1,
    in_progress_tasks: 1,
    blocked_tasks: 0,
    overdue_tasks: 0,
    due_soon_tasks: 0,
    completion_ratio: 0.33,
  },
  phases: [
    {
      phase_key: 'immigration',
      title: 'Immigration & visas',
      status: 'active',
      completion_ratio: 0.33,
      task_counts: { total: 1, completed: 0, in_progress: 0, blocked: 0 },
      tasks: [
        {
          task_id: 't1',
          task_code: 'IMM_VISA_APPLY',
          title: 'Apply for work visa',
          status: 'not_started',
          owner: 'employee',
          priority: 'critical',
          is_overdue: false,
          is_due_soon: false,
          blocked_by: [],
          depends_on: [],
          instructions: ['Gather your passport and contract.'],
          required_inputs: [],
          auto_completion_source: 'manual',
          notes_enabled: true,
        },
      ],
    },
  ],
  roadmap_validated: false,
};

// The roadmap template / text selection can auto-scroll; jsdom lacks it.
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/employee/case/c1/roadmap']}>
      <Routes>
        <Route path="/employee/case/:caseId/roadmap" element={<EmployeeCaseRoadmapPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe('EmployeeCaseRoadmapPage — roadmap orchestration', () => {
  it('renders the phase stepper and task list from the mocked plan view', async () => {
    fetchRelocationPlanView.mockResolvedValue(READY_PLAN);
    renderPage();

    // Ready state: the task from the plan view surfaces (an actionable employee
    // task renders both in "What you can do now" and in its phase row).
    const taskMatches = await screen.findAllByText('Apply for work visa');
    expect(taskMatches.length).toBeGreaterThan(0);
    // Phase rendered (appears in both the hero mini-timeline and the phase section).
    expect(screen.getAllByText('Immigration & visas').length).toBeGreaterThan(0);
    // The page heading renders. (PhaseContextBar's "Roadmap" stepper step was
    // removed in AIQ-1246c; the page now leads with the "My roadmap" heading.)
    expect(screen.getByText('My roadmap')).toBeInTheDocument();
    expect(fetchRelocationPlanView).toHaveBeenCalledWith('c1', expect.objectContaining({ role: 'employee' }));
  });
});

// ── AIQ-1526: HR approves the plan before the employee ACTS on it. ────────────
// The first cut (#1465) hid the whole roadmap while HR reviewed. Too blunt: exploring
// the plan is reassuring and costs nothing. What waits for HR is ACTION — HR can still
// send the plan back for regeneration, and work done against a superseded plan is wasted.
// So: reads open, writes gated. These pin BOTH halves.
describe('EmployeeCaseRoadmapPage — HR review gate', () => {
  it('lets the employee EXPLORE a plan HR has not approved yet', async () => {
    fetchRelocationPlanView.mockResolvedValue({ ...READY_PLAN, roadmap_released: false });
    renderPage();

    // The roadmap is fully visible — this is the whole point of the change.
    expect((await screen.findAllByText('Apply for work visa')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Immigration & visas').length).toBeGreaterThan(0);
    // ...and they're told HR is reviewing (AIQ-1606: non-blocking — they can still act).
    expect(screen.getByText('Your HR team is reviewing this plan')).toBeInTheDocument();
  });

  it('stays fully interactive while HR is reviewing (AIQ-1606 non-blocking tag)', async () => {
    fetchRelocationPlanView.mockResolvedValue({ ...READY_PLAN, roadmap_released: false });
    renderPage();
    await screen.findByText('Your HR team is reviewing this plan');

    // AIQ-1606: under-review is a non-blocking, informational tag — the employee can
    // validate and start tasks immediately. The validate footer is shown...
    expect(screen.getByText(/Validate & start tasks/)).toBeInTheDocument();
    // ...and every task CTA is enabled.
    const ctas = screen.queryAllByRole('button', { name: /Start now|Continue/ });
    expect(ctas.length).toBeGreaterThan(0);
    ctas.forEach((b) => expect(b).not.toBeDisabled());
  });

  it('unlocks everything once HR approves', async () => {
    fetchRelocationPlanView.mockResolvedValue({ ...READY_PLAN, roadmap_released: true });
    renderPage();

    expect((await screen.findAllByText('Apply for work visa')).length).toBeGreaterThan(0);
    expect(screen.queryByText('Your HR team is reviewing this plan')).not.toBeInTheDocument();
    screen
      .queryAllByRole('button', { name: /Start now|Continue/ })
      .forEach((b) => expect(b).not.toBeDisabled());
  });

  // THE ONE THAT MATTERS. 47 live cases have a roadmap and no review row, so the backend
  // omits the flag for them. If the gate were written `!released`, every one of those
  // employees would be locked out of their own tasks.
  it('does not gate a case whose flag is absent (every pre-existing case)', async () => {
    const { roadmap_released: _omitted, ...withoutFlag } = {
      ...READY_PLAN,
      roadmap_released: undefined,
    };
    fetchRelocationPlanView.mockResolvedValue(withoutFlag);
    renderPage();

    expect((await screen.findAllByText('Apply for work visa')).length).toBeGreaterThan(0);
    expect(screen.queryByText('Your HR team is reviewing this plan')).not.toBeInTheDocument();
    screen
      .queryAllByRole('button', { name: /Start now|Continue/ })
      .forEach((b) => expect(b).not.toBeDisabled());
  });
});

// ── AIQ-1377: the plan-view endpoint can transiently 4xx/5xx for a freshly-
// provisioned employee. A single error must NOT dead-end the page with
// "We couldn't load your roadmap"; it should keep retrying within the bounded
// window and only resolve to the failed state on a PERSISTENT error.
describe('EmployeeCaseRoadmapPage — AIQ-1377 transient-error resilience', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('retries through a transient error and renders the roadmap (never "couldn\'t load")', async () => {
    // first fetch fails, the retry succeeds. (mockReset: clearAllMocks keeps impls.)
    fetchRelocationPlanView.mockReset();
    fetchRelocationPlanView.mockRejectedValueOnce(new Error('boom')).mockResolvedValue(READY_PLAN);
    renderPage();

    // first (rejected) fetch settles → must NOT be a dead-end yet.
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.queryByText(/couldn't load/i)).toBeNull();

    // the 4s poll fires → the retry resolves → the roadmap renders.
    await act(async () => { await vi.advanceTimersByTimeAsync(4000); });
    expect(screen.getAllByText('Apply for work visa').length).toBeGreaterThan(0);
    expect(screen.queryByText(/couldn't load/i)).toBeNull();
  });

  it('keeps showing the "building" state on a persistent error within the window (no dead-end)', async () => {
    fetchRelocationPlanView.mockReset();
    fetchRelocationPlanView.mockRejectedValue(new Error('down'));
    renderPage();

    // first error + a couple of retries: still "building", never the dead-end screen.
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    await act(async () => { await vi.advanceTimersByTimeAsync(4000); });
    expect(screen.getByText(/building your roadmap/i)).toBeInTheDocument();
    expect(screen.queryByText(/couldn't load/i)).toBeNull();
  });
});

// The terminal-variant mapping (give-up after the retry window) is deterministic
// and is unit-tested directly — driving 15 self-rescheduling async polls under
// fake timers is a harness fight, not a code path worth asserting that way.
describe('resolveRoadmapBuildVariant — terminal state mapping (AIQ-1377)', () => {
  it('stays "generating" until the retry window elapses', () => {
    expect(resolveRoadmapBuildVariant(false, true)).toBe('generating');
    expect(resolveRoadmapBuildVariant(false, false)).toBe('generating');
  });
  it('resolves a persistent error to "failed" once the window elapses', () => {
    expect(resolveRoadmapBuildVariant(true, true)).toBe('failed');
  });
  it('resolves a persistently-empty plan to "empty" once the window elapses', () => {
    expect(resolveRoadmapBuildVariant(true, false)).toBe('empty');
  });
});

// ── [BUG-260817-4CD6] "chat disappeared" ─────────────────────────────────────
// The policy-assistant FAB was mounted ONLY in the final happy-path return, so every
// early return dropped it — including the "building your roadmap" state, which can hold
// for the whole ~60s retry window and is terminal when generation fails. The chat
// vanished at precisely the moment someone wants to ask why their roadmap is empty.
describe('EmployeeCaseRoadmapPage — the assistant survives every state', () => {
  it('keeps the chat reachable while the roadmap is still building', async () => {
    vi.useFakeTimers();
    try {
    fetchRelocationPlanView.mockReset();
    fetchRelocationPlanView.mockRejectedValue(new Error('down'));
    renderPage();

    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    await act(async () => { await vi.advanceTimersByTimeAsync(4000); });

    // Precondition: we really are in the non-happy branch.
    expect(screen.getByText(/building your roadmap/i)).toBeInTheDocument();
    // The bug: this was absent.
    expect(screen.getByTestId('policy-assistant-fab')).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('still offers it on the ready roadmap (no regression)', async () => {
    fetchRelocationPlanView.mockReset();
    fetchRelocationPlanView.mockResolvedValue(READY_PLAN);
    renderPage();

    await screen.findAllByText('Apply for work visa');
    expect(screen.getByTestId('policy-assistant-fab')).toBeInTheDocument();
  });
});

