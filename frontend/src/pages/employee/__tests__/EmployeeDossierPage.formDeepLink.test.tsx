/**
 * [AIQ-1319] EmployeeDossierPage — roadmap "Start now" ?form=<key> deep-link.
 *
 * A roadmap document task (e.g. "Upload passport copy") deep-links ?form=passport,
 * but that document may have no corresponding form in this corridor's dossier
 * (which holds compliance forms like NL-30RULING / NL-BSN). Behaviour:
 *   - ?form=<key> that MATCHES a form → param is kept (the page scrolls/highlights it).
 *   - ?form=<key> that matches NOTHING (once forms load) → the stale param is stripped,
 *     so the employee lands cleanly with no phantom highlight target.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
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
// api/supabase runs createClient() at import time → "supabaseUrl is required" in jsdom.
// Stub it so the page tree mounts without real env (a lazy dossier child pulls it in).
vi.mock('../../../api/supabase', () => ({ supabase: {} }));
vi.mock('../../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock('../../../features/platform-v2/dossier/CaseFormCard', () => ({
  CaseFormCard: ({ form }: { form: { id: string } }) => <div data-testid={`form-${form.id}`} />,
}));

const CASE_ID = 'case-1';

const FORMS = [
  { id: 'f1', case_id: CASE_ID, status: 'in_progress', completion_pct: 0, blocker_form_id: null,
    roadmap_step_id: null, template: { code: 'NL-30RULING', name: '30% ruling', required_documents: [] } },
  { id: 'f2', case_id: CASE_ID, status: 'in_progress', completion_pct: 0, blocker_form_id: null,
    roadmap_step_id: null, template: { code: 'NL-BSN', name: 'BSN registration', required_documents: [] } },
];

function LocationProbe() {
  const loc = useLocation();
  return <div data-testid="loc-search">{loc.search}</div>;
}

function renderAt(search: string) {
  return render(
    <MemoryRouter initialEntries={[`/employee/case/${CASE_ID}/dossier${search}`]}>
      <Routes>
        <Route
          path="/employee/case/:caseId/dossier"
          element={<><EmployeeDossierPage /><LocationProbe /></>}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe('EmployeeDossierPage ?form= deep-link', () => {
  beforeEach(() => {
    mockList.mockReset();
    mockList.mockResolvedValue(FORMS);
    // jsdom has no scrollIntoView; the deep-link match path calls it.
    Element.prototype.scrollIntoView = vi.fn();
  });

  it('keeps ?form= when it matches a dossier form (by template code)', async () => {
    renderAt('?form=nl-30ruling');
    expect(await screen.findByTestId('form-f1')).toBeInTheDocument();
    // matched → param retained (the page highlights/scrolls to it).
    expect(screen.getByTestId('loc-search')).toHaveTextContent('form=nl-30ruling');
  });

  it('strips a stale ?form= once forms load and nothing matches', async () => {
    renderAt('?form=passport');
    expect(await screen.findByTestId('form-f1')).toBeInTheDocument();
    // no matching form → param removed so the URL reflects the actual landing.
    await waitFor(() => {
      expect(screen.getByTestId('loc-search')).not.toHaveTextContent('form=');
    });
  });

  it('leaves the URL untouched when there is no ?form= param', async () => {
    renderAt('');
    expect(await screen.findByTestId('form-f1')).toBeInTheDocument();
    expect(screen.getByTestId('loc-search')).toHaveTextContent('');
  });
});
