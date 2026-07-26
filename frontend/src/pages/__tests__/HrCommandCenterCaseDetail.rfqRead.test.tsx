/**
 * The HR case-detail RFQ panel read.
 *
 * The route param on /hr/command-center/cases/:id is the ASSIGNMENT id, but the
 * employee's RFQ is keyed on the CASE id (`rfqs.case_id` = `case_assignments.case_id`).
 * The panel was handed `detail.id` (the assignment id), so
 * GET /api/hr/cases/{id}/rfqs 404'd on its tenant check and HR saw an empty panel for
 * every case — 0 of 22 production RFQs are keyed on an assignment id, so this never
 * once resolved. It must read with `detail.caseId`, and fail closed (query nothing)
 * when that cannot be resolved.
 */
import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const ASSIGNMENT_ID = '3d55c9ad-e29e-48db-a412-5815a9710a89';
const CASE_ID = '27b80b5e-2dea-41ac-a1d0-8048100c8881';

const mocks = vi.hoisted(() => ({
  getCommandCenterCaseDetail: vi.fn(),
  getCaseRfqs: vi.fn(),
}));

// Mock the api barrel (also dodges the api/supabase jsdom import trap).
vi.mock('../../api/client', () => ({
  hrAPI: { getCommandCenterCaseDetail: mocks.getCommandCenterCaseDetail },
}));
vi.mock('../../api/supabase', () => ({ supabase: {} }));
// Only the canonical `rfqs` reader is real here; PendingRfqsPanel calls it.
vi.mock('../../api/hrCoordination', () => ({ getCaseRfqs: mocks.getCaseRfqs }));

// Passthrough shell + nav so the test focuses on the page body.
vi.mock('../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock('../../navigation/registry', () => ({ useRegisterNav: () => {} }));
vi.mock('../../navigation/safeNavigate', () => ({ safeNavigate: vi.fn() }));

// Sibling panels each fire their own reads; stub them so this test exercises only
// the RFQ panel's id resolution.
vi.mock('../../components/case/ExceptionFlagsPanel', () => ({ ExceptionFlagsPanel: () => null }));
vi.mock('../../components/case/RoadmapReviewPanel', () => ({ RoadmapReviewPanel: () => null }));
// HrCaseTasksPanel owns the provider-coordination subtree (providers, rfqs, assign-task and
// the HR-gated dispatch), which is keyed on the canonical case id via `coordinationCaseId`
// while its own task reads keep using `caseId`. The stub surfaces both so we can assert the
// page hands each subtree the id-space it actually queries.
vi.mock('../../components/case/HrCaseTasksPanel', () => ({
  HrCaseTasksPanel: ({ caseId, coordinationCaseId }: { caseId: string; coordinationCaseId?: string | null }) => (
    <div data-testid="tasks-panel" data-case-id={caseId} data-coordination-case-id={coordinationCaseId ?? ''} />
  ),
}));
vi.mock('../../components/case/VendorBrowsePanel', () => ({ VendorBrowsePanel: () => null }));
vi.mock('../../components/case/ImmigrationStatusPanel', () => ({ ImmigrationStatusPanel: () => null }));
vi.mock('../../components/case/AdvisorsPanel', () => ({ AdvisorsPanel: () => null }));
vi.mock('../../components/case/AssignmentExceptionsPanel', () => ({ AssignmentExceptionsPanel: () => null }));
vi.mock('../../components/case/PetRequirementsSection', () => ({ PetRequirementsSection: () => null }));
vi.mock('../../components/case/CaseAuditTimeline', () => ({ CaseAuditTimeline: () => null }));
vi.mock('../../components/case/CaseNotesPanel', () => ({ CaseNotesPanel: () => null }));
vi.mock('../../components/case/CasePredictionCard', () => ({ CasePredictionCard: () => null }));
vi.mock('../../components/case/CaseSummaryCard', () => ({ CaseSummaryCard: () => null }));
vi.mock('../../components/case/EscalateCaseModal', () => ({ EscalateCaseModal: () => null }));
vi.mock('../../components/case/ReassignCaseModal', () => ({ ReassignCaseModal: () => null }));
vi.mock('../../features/ai-oversight/AIRecommendationCard', () => ({ AIRecommendationCard: () => null }));
vi.mock('../../features/coordinator/CoordinatorChatPanel', () => ({ CoordinatorChatPanel: () => null }));

import { HrCommandCenterCaseDetail } from '../HrCommandCenterCaseDetail';

// jsdom here has no localStorage (the page reads the role gate from it).
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

const DETAIL = {
  id: ASSIGNMENT_ID,
  caseId: CASE_ID,
  employeeIdentifier: 'emp-alex@probe.test',
  destCountry: 'NO',
  destCity: 'Oslo',
  status: 'submitted',
  riskStatus: 'on_track',
  tasksTotal: 0,
  tasksDone: 0,
  tasksOverdue: 0,
  phases: [],
  events: [],
};

/** The six suppliers an employee picked, as the canonical reader returns them. */
const RFQ_WITH_SIX_VENDORS = {
  id: 'e08377f4-ab9e-4bec-b857-dd40ee09de17',
  rfq_ref: 'RFQ-20260723-e08377f4',
  case_id: CASE_ID,
  status: 'sent',
  created_at: '2026-07-23T10:00:00Z',
  service_keys: ['movers', 'housing'],
  recipients: [
    { supplier_id: 's1', supplier_name: 'Oslo Movers AS', status: 'sent', last_activity_at: null },
    { supplier_id: 's2', supplier_name: 'Nordic Relocation', status: 'sent', last_activity_at: null },
    { supplier_id: 's3', supplier_name: 'Fjord Logistics', status: 'sent', last_activity_at: null },
    { supplier_id: 's4', supplier_name: 'Bergen Housing Co', status: 'sent', last_activity_at: null },
    { supplier_id: 's5', supplier_name: 'Viking Van Lines', status: 'sent', last_activity_at: null },
    { supplier_id: 's6', supplier_name: 'Scandi Home Finders', status: 'sent', last_activity_at: null },
  ],
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/hr/command-center/cases/${ASSIGNMENT_ID}`]}>
        <Routes>
          <Route path="/hr/command-center/cases/:id" element={<HrCommandCenterCaseDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  window.localStorage.setItem('relopass_role', 'HR');
  mocks.getCaseRfqs.mockResolvedValue([RFQ_WITH_SIX_VENDORS]);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe('HrCommandCenterCaseDetail — RFQ panel reads the canonical case id', () => {
  it('queries the canonical rfqs reader with the CASE id, never the assignment id', async () => {
    mocks.getCommandCenterCaseDetail.mockResolvedValue(DETAIL);
    renderPage();

    await waitFor(() => expect(mocks.getCaseRfqs).toHaveBeenCalled());
    expect(mocks.getCaseRfqs).toHaveBeenCalledWith(CASE_ID);
    expect(mocks.getCaseRfqs).not.toHaveBeenCalledWith(ASSIGNMENT_ID);
  });

  it('renders the six vendors the employee picked, with status', async () => {
    mocks.getCommandCenterCaseDetail.mockResolvedValue(DETAIL);
    renderPage();

    for (const r of RFQ_WITH_SIX_VENDORS.recipients) {
      expect(await screen.findByText(r.supplier_name)).toBeInTheDocument();
    }
    // ...and never the dead "no quote requests from the employee" empty state.
    expect(screen.queryByText(/No quote requests from the employee yet/i)).not.toBeInTheDocument();
  });

  it('hands the dispatch surface the CASE id, so the RFQ → supplier-link chain is reachable', async () => {
    mocks.getCommandCenterCaseDetail.mockResolvedValue(DETAIL);
    renderPage();

    // Every hr_coordination endpoint behind that subtree (providers, rfqs, assign-task,
    // dispatch) validates the case id against relocation_cases/cases and 404s on an
    // assignment id — which is what made the dispatch button unreachable.
    const panel = await screen.findByTestId('tasks-panel');
    expect(panel).toHaveAttribute('data-coordination-case-id', CASE_ID);
    // The task reads keep their own id-space — this fix must not move them.
    expect(panel).toHaveAttribute('data-case-id', ASSIGNMENT_ID);
  });

  it('fails closed when the case id cannot be resolved — no query with the raw assignment id', async () => {
    mocks.getCommandCenterCaseDetail.mockResolvedValue({ ...DETAIL, caseId: null });
    renderPage();

    // The page has rendered the RFQ card, and it says so honestly …
    expect(await screen.findByText(/can't be loaded for this case yet/i)).toBeInTheDocument();
    // … but the RFQ read never fired with the wrong id.
    expect(mocks.getCaseRfqs).not.toHaveBeenCalled();
    // …and the dispatch subtree gets no id rather than a wrong one (it renders nothing).
    expect(screen.getByTestId('tasks-panel')).toHaveAttribute('data-coordination-case-id', '');
  });
});
