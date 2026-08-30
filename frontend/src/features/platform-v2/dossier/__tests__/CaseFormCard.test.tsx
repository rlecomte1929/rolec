/**
 * [P1-05] CaseFormCard.test.tsx
 *
 * Coverage for the Dossier & Forms card additions:
 *   - Official Tier-1 source URL renders as an external link (target=_blank,
 *     rel=noopener noreferrer) once the card is expanded.
 *   - The roadmap-step label renders when roadmap_step_title is present.
 *   - Neither block renders when both are absent (legacy / ad-hoc forms).
 */

import { describe, it, expect, afterEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { CaseFormSummary } from '../../../../api/dossier';

// The axios client transitively imports the Supabase client, which throws at
// import time without VITE_SUPABASE_URL set. Mock it (and the PDF drawer that
// pulls it in) — neither is exercised by these render assertions.
vi.mock('../../../../api/client', () => ({
  default: { get: vi.fn(), put: vi.fn(), patch: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));
vi.mock('../OriginalPdfDrawer', () => ({ OriginalPdfDrawer: () => null }));
// FormDocuments mounts its own document-loading effect (via the mocked api
// client, which returns undefined) — not exercised by these render assertions.
vi.mock('../FormDocuments', () => ({ FormDocuments: () => null }));

// Imported after the mocks so the mocked modules are in place.
const { CaseFormCard } = await import('../CaseFormCard');

expect.extend(matchers);
afterEach(cleanup);

function makeForm(overrides: Partial<CaseFormSummary> = {}): CaseFormSummary {
  return {
    id: 'form-1',
    case_id: 'case-1',
    status: 'auto_filled',
    completion_pct: 40,
    deadline: null,
    deadline_trigger: null,
    blocker_form_id: null,
    blocker_form_code: null,
    is_blocked: false,
    original_file_url: null,
    draft_pdf_url: null,
    submitted_at: null,
    receipt_ref: null,
    rejection_reason: null,
    roadmap_step_id: 'step-1',
    roadmap_step_title: 'Register your arrival',
    is_adhoc: false,
    notes: null,
    template: {
      id: 'tpl-1',
      code: 'GP-7-04',
      name: 'D-number application',
      authority_code: 'Skatteetaten',
      authority_name: 'Norwegian Tax Administration',
      country: 'NO',
      category: 'registration',
      version: '1.0.0',
      fields_total: 5,
      source_url: 'https://www.skatteetaten.no/en/person/foreign/norwegian-identification-number/d-number/',
      // Relative to "now" so the source never crosses the staleness window and
      // flips the card to the StalenessBadge branch (a hardcoded date made this
      // a time-bomb that started failing 30 days after it was written).
      source_last_verified: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
      required_documents: [],
      verification_status: 'representative',
    },
    person: { kind: 'employee', name: 'Marc Bouchard', dependent_id: null, profile_id: 'p1' },
    fields_summary: { total: 5, filled_by_ai: 2, filled_by_human: 0, reviewed: 0, overridden: 0, missing_required: 3 },
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-02T00:00:00Z',
    ...overrides,
  };
}

function renderCard(form: CaseFormSummary) {
  return render(
    <MemoryRouter>
      <CaseFormCard form={form} />
    </MemoryRouter>,
  );
}

describe('CaseFormCard — official source link + roadmap step', () => {
  it('renders the official Tier-1 source link and step label when expanded', () => {
    renderCard(makeForm());
    // Collapsed by default — expand by clicking the header (form name).
    fireEvent.click(screen.getByText('D-number application'));

    const link = screen.getByRole('link', { name: /official source/i });
    expect(link).toHaveAttribute(
      'href',
      'https://www.skatteetaten.no/en/person/foreign/norwegian-identification-number/d-number/',
    );
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');

    expect(screen.getByText('Register your arrival')).toBeInTheDocument();
    // [P1-05d] last-verified date rendered alongside the source link.
    expect(screen.getByText(/Last verified ·/)).toBeInTheDocument();
  });

  it('omits both the link and step label when neither is present', () => {
    renderCard(
      makeForm({
        roadmap_step_id: null,
        roadmap_step_title: null,
        template: { ...makeForm().template, source_url: null },
      }),
    );
    fireEvent.click(screen.getByText('D-number application'));

    expect(screen.queryByRole('link', { name: /official source/i })).toBeNull();
    expect(screen.queryByText(/Roadmap step:/i)).toBeNull();
  });
});

describe('CaseFormCard — [WS1] content-honesty notice', () => {
  it('shows the indicative-guidance notice (naming the authority) for representative content', () => {
    renderCard(makeForm()); // template.verification_status === 'representative'
    fireEvent.click(screen.getByText('D-number application'));

    expect(screen.getByText(/Indicative guidance/i)).toBeInTheDocument();
    expect(screen.getByText('Norwegian Tax Administration')).toBeInTheDocument();
  });

  it('hides the notice once the content is verified', () => {
    renderCard(
      makeForm({ template: { ...makeForm().template, verification_status: 'verified' } }),
    );
    fireEvent.click(screen.getByText('D-number application'));

    expect(screen.queryByText(/Indicative guidance/i)).toBeNull();
  });
});

/**
 * [BUG-260706-ECA9] "when clicking on 'view original pdf', nothing gets loaded".
 * The button used to render unconditionally, but GET .../original-pdf 404s when the
 * template has no original attached — true for 85 of the 86 production templates.
 * The card now only offers it when the server says one exists.
 */
describe('View original PDF — only offered when there is one', () => {
  /** The card starts collapsed, so every assertion must expand it first —
   *  otherwise "not in the document" passes for the wrong reason. */
  function renderExpanded(hasOriginal: boolean | undefined) {
    const form = makeForm();
    if (hasOriginal === undefined) {
      delete (form.template as { has_original_pdf?: boolean }).has_original_pdf;
    } else {
      (form.template as { has_original_pdf?: boolean }).has_original_pdf = hasOriginal;
    }
    render(<MemoryRouter><CaseFormCard form={form} initialExpanded /></MemoryRouter>);
  }

  it('offers it when an original really is attached', () => {
    renderExpanded(true);
    expect(screen.getByRole('button', { name: /view original pdf/i })).toBeInTheDocument();
  });

  it('hides the action when the template has no original attached', () => {
    renderExpanded(false);
    expect(screen.queryByRole('button', { name: /view original pdf/i })).not.toBeInTheDocument();
  });

  it('hides it when the flag is absent entirely (older payload)', () => {
    renderExpanded(undefined);
    expect(screen.queryByRole('button', { name: /view original pdf/i })).not.toBeInTheDocument();
  });
});
