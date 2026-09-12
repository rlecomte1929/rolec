/**
 * EmployeeDossierPage — content-honesty banner.
 *
 * Form templates are `representative`, not legally `verified`, so the dossier
 * must always carry an "Indicative — confirm with the issuing authority"
 * disclaimer whenever forms are shown. Hidden when there are no forms.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
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

vi.mock('../../../api/dossier', () => ({
  dossierAPI: { list: (...args: unknown[]) => mockList(...args) },
  // [AIQ-1855] the page now mounts ImmigrationFormFill; stub it to "no fillable forms".
  immigrationFormsAPI: {
    available: () => Promise.resolve({ corridor_to: '', visa_type: null, forms: [] }),
    generate: () => Promise.resolve({ download_url: null, fill_report: { form_id: '', filled_count: 0, blank_count: 0, warning_count: 0, not_in_pdf_count: 0, fields: [] } }),
  },
}));
vi.mock('../../../api/relocationPlanView', () => ({
  fetchRelocationPlanView: () => Promise.resolve({ roadmap_validated: true }),
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
const FRESH_DATE = new Date().toISOString();

function makeForm(id: string) {
  return {
    id,
    case_id: CASE_ID,
    status: 'in_progress',
    completion_pct: 0,
    blocker_form_id: null,
    roadmap_step_id: null,
    template: { source_url: 'https://www.example.gov/official', source_last_verified: FRESH_DATE },
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/employee/case/${CASE_ID}/dossier`]}>
      <Routes>
        <Route path="/employee/case/:caseId/dossier" element={<EmployeeDossierPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('EmployeeDossierPage content-honesty banner', () => {
  it('always shows the "Indicative — confirm with the issuing authority" disclaimer when forms exist', async () => {
    mockList.mockResolvedValue([makeForm('a'), makeForm('b')]);
    renderPage();
    const banner = await screen.findByTestId('dossier-honesty-banner');
    expect(banner).toHaveTextContent(/indicative/i);
    expect(banner).toHaveTextContent(/issuing authority/i);
  });

  it('hides the disclaimer when there are no forms', async () => {
    mockList.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText(/No forms yet/i)).toBeInTheDocument();
    expect(screen.queryByTestId('dossier-honesty-banner')).not.toBeInTheDocument();
  });
});
