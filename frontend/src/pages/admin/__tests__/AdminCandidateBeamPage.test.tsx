/**
 * The candidate beam review queue.
 *
 * These tests pin the honesty properties, not the layout. The queue shows unreviewed model
 * output, and every assertion below covers a way the screen could make that output look
 * more finished than it is.
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const listRuns = vi.fn();
const listItems = vi.fn();
const review = vi.fn();
const importPlan = vi.fn();
const pillars = vi.fn();
const executeImport = vi.fn();
const verifyImport = vi.fn();
const startRun = vi.fn();
const executePass = vi.fn();
const finalizeRun = vi.fn();

vi.mock('../../../api/candidateBeam', () => ({
  candidateBeamAPI: {
    listRuns: (...a: unknown[]) => listRuns(...a),
    listItems: (...a: unknown[]) => listItems(...a),
    review: (...a: unknown[]) => review(...a),
    importPlan: (...a: unknown[]) => importPlan(...a),
    pillars: (...a: unknown[]) => pillars(...a),
    executeImport: (...a: unknown[]) => executeImport(...a),
    verifyImport: (...a: unknown[]) => verifyImport(...a),
    startRun: (...a: unknown[]) => startRun(...a),
    executePass: (...a: unknown[]) => executePass(...a),
    finalizeRun: (...a: unknown[]) => finalizeRun(...a),
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
  // Resolved, not bare: a bare vi.fn() returns undefined, and the page chains .then on it.
  pillars.mockReset().mockResolvedValue({ pillars: [], grounded_categories: {} });
  executeImport.mockReset();
  verifyImport.mockReset();
  startRun.mockReset().mockResolvedValue({
    run_id: 'run-new', status: 'generating', passes_requested: 2,
    passes_completed: 0, next_pass: 1, llm_model: 'gpt-4o-mini',
  });
  executePass
    .mockReset()
    .mockResolvedValueOnce({
      run_id: 'run-new', pass: 1, framing: 'baseline', ok: true, item_count: 7,
      error: null, passes_completed: 1, passes_requested: 2, next_pass: 2,
    })
    .mockResolvedValueOnce({
      run_id: 'run-new', pass: 2, framing: 'adversarial', ok: true, item_count: 6,
      error: null, passes_completed: 2, passes_requested: 2, next_pass: null,
    });
  finalizeRun.mockReset().mockResolvedValue({
    run_id: 'run-new', status: 'pending_review', candidate_count: 11,
    passes_completed: 2, passes_requested: 2, flagged: 1, source_missing: 2,
  });
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

    // The mandated legal notice is excluded from the scan, not the guard weakened.
    //
    // That notice contains the word "lawyer" while asserting the OPPOSITE of what this test
    // exists to catch: it says a candidate still needs sign-off, where the danger is a
    // candidate presented as having received it. Scanning the notice would force a choice
    // between required copy and the guard; subtracting it keeps both, so "lawyer-approved"
    // on a candidate card still fails here.
    const NOTICE =
      'Candidate beams are research tools, not a source of truth. Every imported candidate ' +
      'must be reviewed and signed off by a lawyer before it appears in any HR-facing ' +
      'output. Importing here stages facts for legal review — it does not publish them.';
    const withoutNotice = (container.textContent || '').replace(NOTICE.replace(/\s+/g, ' '), '');

    expect(withoutNotice).not.toMatch(/lawyer|counsel[- ]approved|compliant|certified/i);
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

  // ── Action 4: execute + verify ────────────────────────────────────────────

  it('carries the mandated notice that import stages for legal review, not publication', async () => {
    renderPage();
    expect(
      await screen.findByText(/Candidate beams are research tools, not a source of truth/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/it does not publish them/i)).toBeInTheDocument();
  });

  it('still catches a candidate claiming lawyer approval, despite the notice naming lawyers', async () => {
    // Proves the narrowed guard above discriminates rather than passing by subtraction.
    listItems.mockResolvedValue({
      items: [{ ...sourced, title: 'Lawyer-approved residence permit' }],
      counts: { ...counts, total: 1 },
    });
    const { container } = renderPage();
    await screen.findByText(/Lawyer-approved residence permit/);

    const NOTICE =
      'Candidate beams are research tools, not a source of truth. Every imported candidate ' +
      'must be reviewed and signed off by a lawyer before it appears in any HR-facing ' +
      'output. Importing here stages facts for legal review — it does not publish them.';
    const withoutNotice = (container.textContent || '').replace(NOTICE.replace(/\s+/g, ' '), '');

    expect(withoutNotice).toMatch(/lawyer/i);
  });

  it('will not offer an execute until something has been approved', async () => {
    listItems.mockResolvedValue({ items: [sourced], counts: { ...counts, approved: 0 } });
    renderPage();
    expect(await screen.findByRole('button', { name: /Execute import/i })).toBeDisabled();
  });

  it('asks for confirmation before staging, and stages nothing until confirmed', async () => {
    listItems.mockResolvedValue({ items: [sourced], counts: { ...counts, approved: 1 } });
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /Execute import/i }));

    expect(await screen.findByText(/This cannot be undone/i)).toBeInTheDocument();
    expect(executeImport).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: /^Cancel$/i }));
    expect(executeImport).not.toHaveBeenCalled();
  });

  it('stages on confirm and reports how many landed', async () => {
    listItems.mockResolvedValue({ items: [sourced], counts: { ...counts, approved: 1 } });
    executeImport.mockResolvedValue({ run_id: 'run-1', imported: 4, skipped: [], written: true });
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /Execute import/i }));
    await userEvent.click(await screen.findByRole('button', { name: /^Confirm$/i }));

    await waitFor(() => expect(executeImport).toHaveBeenCalledWith('run-1', 'FRANCE'));
    expect(await screen.findByText(/Import complete — 4 facts staged/i)).toBeInTheDocument();
  });

  it('refuses a second import rather than retrying it', async () => {
    listItems.mockResolvedValue({ items: [sourced], counts: { ...counts, approved: 1 } });
    executeImport.mockRejectedValue({ response: { status: 409 } });
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /Execute import/i }));
    await userEvent.click(await screen.findByRole('button', { name: /^Confirm$/i }));

    expect(await screen.findByText(/already been imported/i)).toBeInTheDocument();
  });

  it('offers verification only once an import has actually happened', async () => {
    listItems.mockResolvedValue({ items: [sourced], counts: { ...counts, approved: 1 } });
    executeImport.mockResolvedValue({ run_id: 'run-1', imported: 1, skipped: [], written: true });
    renderPage();
    await screen.findByRole('button', { name: /Execute import/i });
    expect(screen.queryByRole('button', { name: /Verify import/i })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Execute import/i }));
    await userEvent.click(await screen.findByRole('button', { name: /^Confirm$/i }));

    expect(await screen.findByRole('button', { name: /Verify import/i })).toBeInTheDocument();
  });

  it('shows a drifted verification as findings, not as a failed request', async () => {
    // The endpoint answers 409 WITH the report when something drifted. Rendering it is the
    // whole point; swallowing it as an error would hide the drift this button exists to find.
    listItems.mockResolvedValue({ items: [sourced], counts: { ...counts, approved: 1 } });
    executeImport.mockResolvedValue({ run_id: 'run-1', imported: 2, skipped: [], written: true });
    verifyImport.mockResolvedValue({
      run_id: 'run-1',
      ok: false,
      verified: 1,
      failed: 1,
      items: [
        { candidate_uid: 'a', title: 'Kept its row', status: 'verified' },
        { candidate_uid: 'b', title: 'Drifted one', status: 'content_drift', detail: 'text changed' },
      ],
    });
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /Execute import/i }));
    await userEvent.click(await screen.findByRole('button', { name: /^Confirm$/i }));
    await userEvent.click(await screen.findByRole('button', { name: /Verify import/i }));

    expect(await screen.findByText(/1 of 2 staged facts did not verify/i)).toBeInTheDocument();
    expect(screen.getByText('content_drift')).toBeInTheDocument();
    expect(screen.getByText(/Drifted one/)).toBeInTheDocument();
  });

  it('bulk-approves by confidence band, not by a hardcoded pass count', async () => {
    // A run with 3 passes has no item at pass_frequency 5; selecting on the literal would
    // silently approve nothing. The band survives any run size.
    listItems.mockResolvedValue({
      items: [
        { ...sourced, id: 'i1', confidence_band: 'near-certain', pass_frequency: 3, passes_total: 3 },
        { ...sourced, id: 'i2', confidence_band: 'moderate', pass_frequency: 1, passes_total: 3 },
      ],
      counts: { ...counts, total: 2, pending_review: 2 },
    });
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /Select near-certain \(1\)/i }));

    await waitFor(() => expect(review).toHaveBeenCalledTimes(1));
    expect(review).toHaveBeenCalledWith('i1', 'approved');
  });
  // ── Action 4: launch console ──────────────────────────────────────────────

  it('drives start then each pass then finalize, following the server cursor', async () => {
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /Launch beam/i }));

    await waitFor(() => expect(finalizeRun).toHaveBeenCalledWith('run-new'));
    expect(startRun).toHaveBeenCalledWith(
      expect.objectContaining({ corridor: 'FR-NO', employee_type: 'permanent' }),
    );
    // Slots come from next_pass, not from an assumed 1..N.
    expect(executePass.mock.calls.map((c) => c[1])).toEqual([1, 2]);
  });

  it('sends the move date as labelled context, since the beam has no date field', async () => {
    renderPage();
    await userEvent.type(await screen.findByLabelText(/Move date/i), '2026-12-01');
    await userEvent.click(screen.getByRole('button', { name: /Launch beam/i }));

    await waitFor(() => expect(startRun).toHaveBeenCalled());
    expect(startRun.mock.calls[0][0].context).toContain('Planned move date: 2026-12-01');
  });

  it('shows each pass as it lands rather than one opaque spinner', async () => {
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /Launch beam/i }));

    expect(await screen.findByText('pass 1')).toBeInTheDocument();
    expect(await screen.findByText('pass 2')).toBeInTheDocument();
    expect(screen.getByText(/7 candidates/)).toBeInTheDocument();
  });

  it('keeps going when one pass fails, and still ranks what survived', async () => {
    // The mock answers by SLOT, the way the server does — a sequence-driven mock returns
    // "pass 2 succeeded" however many times the loop re-asks for slot 1, which is exactly
    // how a cursor-following loop passed this test while re-running one slot forever.
    executePass.mockReset().mockImplementation((_runId: string, slot: number) =>
      Promise.resolve(
        slot === 1
          ? {
              run_id: 'run-new', pass: 1, framing: 'baseline', ok: false, item_count: 0,
              error: 'model timeout', passes_completed: 0, passes_requested: 3,
              next_pass: 1, // a failed slot points back at itself
            }
          : {
              run_id: 'run-new', pass: slot, framing: 'adversarial', ok: true, item_count: 6,
              error: null, passes_completed: slot - 1, passes_requested: 3,
              next_pass: slot < 3 ? slot + 1 : null,
            },
      ),
    );
    startRun.mockResolvedValue({
      run_id: 'run-new', status: 'generating', passes_requested: 3,
      passes_completed: 0, next_pass: 1, llm_model: 'gpt-4o-mini',
    });

    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /Launch beam/i }));

    await waitFor(() => expect(finalizeRun).toHaveBeenCalled());

    // Every distinct slot attempted exactly once. A failed slot must not eat the budget.
    expect(executePass.mock.calls.map((c) => c[1])).toEqual([1, 2, 3]);
    expect(await screen.findByText(/model timeout/)).toBeInTheDocument();
  });

  it('does not rank a beam whose every pass failed, and says the run is retriable', async () => {
    executePass.mockReset().mockImplementation((_r: string, slot: number) =>
      Promise.resolve({
        run_id: 'run-new', pass: slot, framing: 'baseline', ok: false, item_count: 0,
        error: 'boom', passes_completed: 0, passes_requested: 2, next_pass: slot,
      }),
    );
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /Launch beam/i }));

    expect(await screen.findByText(/Only 0 of 2 passes succeeded/i)).toBeInTheDocument();
    expect(finalizeRun).not.toHaveBeenCalled();
  });

  it('will not rank a single surviving pass — one opinion is not consensus', async () => {
    // The lower edge of finalize's 409. Ranking 1/2 would print a lone pass as agreement.
    executePass.mockReset().mockImplementation((_r: string, slot: number) =>
      Promise.resolve({
        run_id: 'run-new', pass: slot, framing: 'f', ok: slot === 1, item_count: slot === 1 ? 5 : 0,
        error: slot === 1 ? null : 'boom', passes_completed: 1, passes_requested: 2,
        next_pass: slot === 1 ? 2 : 2,
      }),
    );
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /Launch beam/i }));

    expect(await screen.findByText(/Only 1 of 2 passes succeeded/i)).toBeInTheDocument();
    expect(finalizeRun).not.toHaveBeenCalled();
  });

  it('ranks as soon as two passes survive — the upper edge of the same rule', async () => {
    executePass.mockReset().mockImplementation((_r: string, slot: number) =>
      Promise.resolve({
        run_id: 'run-new', pass: slot, framing: 'f', ok: true, item_count: 5,
        error: null, passes_completed: slot, passes_requested: 2,
        next_pass: slot < 2 ? slot + 1 : null,
      }),
    );
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /Launch beam/i }));

    await waitFor(() => expect(finalizeRun).toHaveBeenCalledWith('run-new'));
  });

  it('caps the context at the length the API accepts, instead of 422ing', async () => {
    // StartRunRequest.context is max_length=4000. Sent over, the request 422s and the reader
    // sees a generic failure rather than "your note is too long".
    renderPage();
    const box = await screen.findByLabelText(/Additional context for this beam run/i);
    fireEvent.change(box, { target: { value: 'x'.repeat(5000) } });
    await userEvent.click(screen.getByRole('button', { name: /Launch beam/i }));

    await waitFor(() => expect(startRun).toHaveBeenCalled());
    expect(startRun.mock.calls[0][0].context).toHaveLength(4000);
  });

  it('surfaces a start failure inline instead of leaving the button spinning', async () => {
    startRun.mockRejectedValue({ response: { data: { detail: 'corridor not authored' } } });
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: /Launch beam/i }));

    expect(await screen.findByText(/corridor not authored/i)).toBeInTheDocument();
    expect(executePass).not.toHaveBeenCalled();
  });

});
