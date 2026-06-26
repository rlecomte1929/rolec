/**
 * [P1-6] EmployeeDossierPage — roadmap-step filter receiver.
 *
 * Coverage:
 *   - ?roadmap_step=<id> scopes the rendered list to forms with that
 *     roadmap_step_id, and shows the scope banner.
 *   - "Clear filter" removes the param, hides the banner, and shows all forms.
 *   - No param → no banner, all forms shown.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

expect.extend(matchers);

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// --- mocks -----------------------------------------------------------------

const mockList = vi.fn();

vi.mock('../../../api/dossier', () => ({
  dossierAPI: {
    list: (...args: unknown[]) => mockList(...args),
  },
}));
vi.mock('../../../api/relocationPlanView', () => ({
  fetchRelocationPlanView: () => Promise.resolve({ roadmap_validated: true }),
}));

// Realtime hook pulls in the Supabase client — stub it to a no-op.
vi.mock('../../../hooks/useCaseFormsRealtime', () => ({
  useCaseFormsRealtime: () => undefined,
}));

// AppShell drags in nav/auth context that's irrelevant here.
vi.mock('../../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

// Render each card as a simple testid so we can assert which forms are shown.
vi.mock('../../../features/platform-v2/dossier/CaseFormCard', () => ({
  CaseFormCard: ({ form }: { form: { id: string } }) => (
    <div data-testid={`form-${form.id}`} />
  ),
}));

import { EmployeeDossierPage } from '../EmployeeDossierPage';

// --- helpers ---------------------------------------------------------------

const CASE_ID = 'case-1';

function makeForm(id: string, roadmapStepId: string | null) {
  return {
    id,
    case_id: CASE_ID,
    status: 'in_progress',
    completion_pct: 0,
    blocker_form_id: null,
    roadmap_step_id: roadmapStepId,
  };
}

const FORMS = [
  makeForm('a', 'step-1'),
  makeForm('b', 'step-1'),
  makeForm('c', 'step-2'),
  makeForm('d', null),
];

function renderAt(search: string) {
  return render(
    <MemoryRouter initialEntries={[`/employee/case/${CASE_ID}/dossier${search}`]}>
      <Routes>
        <Route path="/employee/case/:caseId/dossier" element={<EmployeeDossierPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

// --- tests -----------------------------------------------------------------

describe('EmployeeDossierPage roadmap-step filter', () => {
  beforeEach(() => {
    mockList.mockReset();
    mockList.mockResolvedValue(FORMS);
  });

  it('scopes the list to the roadmap step and shows the banner', async () => {
    renderAt('?roadmap_step=step-1');

    expect(await screen.findByTestId('form-a')).toBeInTheDocument();
    expect(screen.getByTestId('form-b')).toBeInTheDocument();
    // forms from other steps / unlinked are excluded
    expect(screen.queryByTestId('form-c')).not.toBeInTheDocument();
    expect(screen.queryByTestId('form-d')).not.toBeInTheDocument();
    expect(screen.getByTestId('roadmap-step-filter-banner')).toBeInTheDocument();
  });

  it('clears the filter and shows all forms when "Clear filter" is clicked', async () => {
    renderAt('?roadmap_step=step-1');

    expect(await screen.findByTestId('form-a')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Clear filter'));

    expect(await screen.findByTestId('form-c')).toBeInTheDocument();
    expect(screen.getByTestId('form-d')).toBeInTheDocument();
    expect(screen.queryByTestId('roadmap-step-filter-banner')).not.toBeInTheDocument();
  });

  it('shows no banner and all forms when no param is present', async () => {
    renderAt('');

    expect(await screen.findByTestId('form-a')).toBeInTheDocument();
    expect(screen.getByTestId('form-c')).toBeInTheDocument();
    expect(screen.getByTestId('form-d')).toBeInTheDocument();
    expect(screen.queryByTestId('roadmap-step-filter-banner')).not.toBeInTheDocument();
  });
});
