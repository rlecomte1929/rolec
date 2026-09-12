/**
 * [Validate gate] EmployeeDossierPage soft gate.
 *
 * The dossier shows a "validate your roadmap" nudge while the roadmap is not
 * validated, and hides it once it is. Forms are never hard-blocked (soft gate).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { EmployeeDossierPage } from '../EmployeeDossierPage';

expect.extend(matchers);

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const mockList = vi.fn();
const mockPlanView = vi.fn();

vi.mock('../../../api/dossier', () => ({
  dossierAPI: { list: (...a: unknown[]) => mockList(...a) },
  // [AIQ-1855] the page now mounts ImmigrationFormFill; stub it to "no fillable forms".
  immigrationFormsAPI: {
    available: () => Promise.resolve({ corridor_to: '', visa_type: null, forms: [] }),
    generate: () => Promise.resolve({ download_url: null, fill_report: { form_id: '', filled_count: 0, blank_count: 0, warning_count: 0, not_in_pdf_count: 0, fields: [] } }),
  },
}));
vi.mock('../../../api/relocationPlanView', () => ({
  fetchRelocationPlanView: (...a: unknown[]) => mockPlanView(...a),
}));
vi.mock('../../../hooks/useCaseFormsRealtime', () => ({
  useCaseFormsRealtime: () => undefined,
}));
vi.mock('../../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock('../../../contexts/EmployeeAssignmentContext', () => ({
  useEmployeeAssignment: () => ({
    assignmentId: 'a1',
    primaryCaseId: 'case-1',
    primaryAssignmentCompany: null,
    isLoading: false,
    linkedCount: 1,
    pendingCount: 0,
    linkedSummaries: [{ assignment_id: 'a1', case_id: 'case-1' }],
    pendingSummaries: [],
    overviewError: null,
    overviewDegraded: false,
    refetch: async () => {},
  }),
}));
vi.mock('../../../features/platform-v2/dossier/CaseFormCard', () => ({
  CaseFormCard: ({ form }: { form: { id: string } }) => <div data-testid={`form-${form.id}`} />,
}));

const CASE_ID = 'case-1';
const FORMS = [{
  id: 'a', case_id: CASE_ID, status: 'in_progress',
  completion_pct: 0, blocker_form_id: null, roadmap_step_id: null,
}];

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/employee/case/${CASE_ID}/dossier`]}>
      <Routes>
        <Route path="/employee/case/:caseId/dossier" element={<EmployeeDossierPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('EmployeeDossierPage validate-roadmap soft gate', () => {
  beforeEach(() => {
    mockList.mockReset();
    mockList.mockResolvedValue(FORMS);
    mockPlanView.mockReset();
  });

  it('shows the gate when the roadmap is not validated', async () => {
    mockPlanView.mockResolvedValue({ roadmap_validated: false });
    renderPage();
    expect(await screen.findByTestId('form-a')).toBeInTheDocument();
    expect(screen.getByTestId('validate-roadmap-gate')).toBeInTheDocument();
  });

  it('hides the gate when the roadmap is validated', async () => {
    mockPlanView.mockResolvedValue({ roadmap_validated: true });
    renderPage();
    expect(await screen.findByTestId('form-a')).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.queryByTestId('validate-roadmap-gate')).not.toBeInTheDocument(),
    );
  });
});
