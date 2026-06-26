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
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { RelocationPlanViewResponseDTO } from '../../../types/relocationPlanView';

// ── Stub AppShell ────────────────────────────────────────────────────────────
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

import { EmployeeCaseRoadmapPage } from '../EmployeeCaseRoadmapPage';

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
    // The Roadmap stepper step is present (PhaseContextBar).
    expect(screen.getAllByText('Roadmap').length).toBeGreaterThan(0);
    expect(fetchRelocationPlanView).toHaveBeenCalledWith('c1', expect.objectContaining({ role: 'employee' }));
  });
});
