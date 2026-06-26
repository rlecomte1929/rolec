/**
 * [P2-08d] EmployeeDossierPage — stale-source overview banner.
 *
 * Coverage:
 *   - Banner appears with the correct count when forms have unverified sources.
 *   - Banner hides entirely when every form's source is fresh.
 *   - Singular vs plural copy.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

expect.extend(matchers);

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// --- mocks -----------------------------------------------------------------

const mockList = vi.fn();

vi.mock('../../../api/dossier', () => ({
  dossierAPI: { list: (...args: unknown[]) => mockList(...args) },
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
vi.mock('../../../features/platform-v2/dossier/CaseFormCard', () => ({
  CaseFormCard: ({ form }: { form: { id: string } }) => <div data-testid={`form-${form.id}`} />,
}));

import { EmployeeDossierPage } from '../EmployeeDossierPage';

// --- helpers ---------------------------------------------------------------

const CASE_ID = 'case-1';

// `source_last_verified` far in the past → reliably stale (30-day default)
// regardless of when the suite runs. Fresh uses "now-ish" today.
const STALE_DATE = '2000-01-01T00:00:00Z';
const FRESH_DATE = new Date().toISOString();

function makeForm(id: string, lastVerified: string | null) {
  return {
    id,
    case_id: CASE_ID,
    status: 'in_progress',
    completion_pct: 0,
    blocker_form_id: null,
    roadmap_step_id: null,
    template: {
      source_url: 'https://www.example.gov/official',
      source_last_verified: lastVerified,
    },
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

// --- tests -----------------------------------------------------------------

describe('EmployeeDossierPage stale-source banner', () => {
  beforeEach(() => mockList.mockReset());

  it('shows the banner with the correct count when sources are stale', async () => {
    mockList.mockResolvedValue([
      makeForm('a', STALE_DATE),
      makeForm('b', STALE_DATE),
      makeForm('c', FRESH_DATE),
    ]);
    renderPage();

    const banner = await screen.findByTestId('stale-sources-banner');
    expect(banner).toHaveTextContent(/2 forms in your dossier have sources/i);
  });

  it('uses singular copy for a single stale form', async () => {
    mockList.mockResolvedValue([makeForm('a', STALE_DATE), makeForm('b', FRESH_DATE)]);
    renderPage();

    const banner = await screen.findByTestId('stale-sources-banner');
    expect(banner).toHaveTextContent(/1 form in your dossier has a source/i);
  });

  it('hides the banner when no form has a stale source', async () => {
    mockList.mockResolvedValue([makeForm('a', FRESH_DATE), makeForm('b', null)]);
    renderPage();

    expect(await screen.findByTestId('form-a')).toBeInTheDocument();
    expect(screen.queryByTestId('stale-sources-banner')).not.toBeInTheDocument();
  });
});
