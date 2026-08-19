/**
 * The candidate beam review queue.
 *
 * These tests pin the honesty properties, not the layout. The queue shows unreviewed model
 * output, and every assertion below covers a way the screen could make that output look
 * more finished than it is.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const listRuns = vi.fn();
const listItems = vi.fn();
const review = vi.fn();
const importPlan = vi.fn();

vi.mock('../../../api/candidateBeam', () => ({
  candidateBeamAPI: {
    listRuns: (...a: unknown[]) => listRuns(...a),
    listItems: (...a: unknown[]) => listItems(...a),
    review: (...a: unknown[]) => review(...a),
    importPlan: (...a: unknown[]) => importPlan(...a),
    pillars: vi.fn(),
  },
}));

vi.mock('../AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { AdminCandidateBeamPage } from '../AdminCandidateBeamPage';

const RUN = {
  id: 'run-1',
  set_uid: 'beam:FR-NO:eea:msxfblnkte2p',
  corridor: 'FR-NO',
  employee_type: 'eea',
  status: 'pending_review' as const,
  passes_requested: 5,
  passes_completed: 5,
  llm_provider: 'platform',
  llm_model: 'gpt-4o-mini',
  candidate_count: 35,
  error: null,
  created_by: 'romain',
  created_at: '2026-08-19T00:00:00Z',
};

const sourced = {
  id: 'i1',
  candidate_uid: 'c1',
  rank: 1,
  pass_frequency: 4,
  passes_total: 5,
  confidence_band: 'strong' as const,
  flagged: false,
  source_missing: false,
  title: 'Preserving Digital Identity',
  official_guidance: 'Guidance',
  actual_reality: 'Reality',
  action_required: 'Keep the account alive',
  source: 'https://www.impots.gouv.fr/x',
  category: 'tax',
  variants: [
    { pass: 1, arrival_ordinal: 4, framing: 'zero_shot_official_audit', title: 'Digital Identity Preservation' },
    { pass: 3, arrival_ordinal: 4, framing: 'lived_experience', title: 'Digital identity preservation' },
  ],
  status: 'pending_review' as const,
  review_note: null,
  reviewed_by: null,
  reviewed_at: null,
  import_country: null,
  import_requirement_type: null,
  imported_ref: null,
  imported_at: null,
};

const unsourced = { ...sourced, id: 'i2', candidate_uid: 'c2', rank: 2, title: 'Voting Registration in Norway', source: null, source_missing: true };

const counts = {
  total: 2, pending_review: 2, approved: 0, rejected: 0, imported: 0, source_missing: 1,
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/admin/candidate-beam?run=run-1']}>
      <AdminCandidateBeamPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  listRuns.mockReset().mockResolvedValue([RUN]);
  listItems.mockReset().mockResolvedValue({ items: [sourced, unsourced], counts });
  review.mockReset().mockResolvedValue(undefined);
  importPlan.mockReset();
});

describe('AdminCandidateBeamPage', () => {
  it('says up front that nothing on the page has been checked by a person', async () => {
    renderPage();
    expect(await screen.findByText(/Unreviewed model drafting/i)).toBeInTheDocument();
  });

  it('labels a cited source as an unverified claim, not a citation', async () => {
    renderPage();
    expect(await screen.findByText(/Claimed source \(unverified\)/i)).toBeInTheDocument();
  });

  it('shows an unsourced candidate as research to do rather than hiding it', async () => {
    renderPage();
    expect(await screen.findByText(/No source cited/i)).toBeInTheDocument();
    expect(screen.getByText(/research worklist, not importable/i)).toBeInTheDocument();
  });

  it('never describes a candidate as verified, compliant or counsel-approved', async () => {
    const { container } = renderPage();
    await screen.findByText(/Preserving Digital Identity/);
    expect(container.textContent).not.toMatch(/lawyer|counsel[- ]approved|compliant|certified/i);
  });

  it('exposes the contributing variants so the merge can be judged against the spread', async () => {
    renderPage();
    const toggle = await screen.findAllByText(/contributing/i);
    await userEvent.click(toggle[0]);
    expect(await screen.findByText(/zero_shot_official_audit/)).toBeInTheDocument();
    expect(screen.getByText(/lived_experience/)).toBeInTheDocument();
  });

  it('records an approval through the API', async () => {
    renderPage();
    const buttons = await screen.findAllByRole('button', { name: /Approve for staging/i });
    await userEvent.click(buttons[0]);
    await waitFor(() => expect(review).toHaveBeenCalledWith('i1', 'approved', undefined));
  });

  it('calls the approval "for staging" — never "publish"', async () => {
    renderPage();
    const buttons = await screen.findAllByRole('button', { name: /Approve for staging/i });
    expect(buttons[0]).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /publish|promote/i })).toBeNull();
  });

  it('offers no promote control at all', async () => {
    const { container } = renderPage();
    await screen.findByText(/Preserving Digital Identity/);
    expect(container.textContent).not.toMatch(/promote/i);
  });

  it('states that the import preview writes nothing', async () => {
    renderPage();
    expect(await screen.findByText(/Shows what an import would do\. Writes nothing\./i)).toBeInTheDocument();
  });

  it('shows each skipped candidate with its reason', async () => {
    importPlan.mockResolvedValue({
      importable: 1,
      skipped: [{ candidate_uid: 'c2', title: 'Voting Registration in Norway', reason: 'no source: research worklist, not importable' }],
      skips_by_reason: { 'no source': 1 },
      pillar_by_uid: { c1: 'EMPLOYMENT' },
      written: false,
    });
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /Preview import/i }));
    expect(await screen.findByText(/no source: research worklist/i)).toBeInTheDocument();
  });

  it('surfaces a load failure instead of rendering an empty queue as success', async () => {
    listItems.mockRejectedValue(new Error('boom'));
    renderPage();
    expect(await screen.findByText(/Could not load candidates/i)).toBeInTheDocument();
  });
});
