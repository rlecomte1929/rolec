/**
 * WS3 Task 3.4 — status transitions go through formEditor.patchStatus,
 * not raw fetch('/api/cases/.../forms/...').
 */
import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { CaseFormSummary } from '../../../../api/dossier';

const patchStatus = vi.fn().mockResolvedValue({});

vi.mock('../../../../api/client', () => ({
  default: { get: vi.fn(), put: vi.fn(), patch: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

vi.mock('../../../../api/formEditor', () => ({
  formEditorAPI: {
    patchStatus: (...args: unknown[]) => patchStatus(...args),
  },
}));

vi.mock('../../../../api/dossier', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../../api/dossier')>();
  return {
    ...actual,
    commentsAPI: { list: vi.fn().mockResolvedValue([]), create: vi.fn() },
    eventsAPI: { list: vi.fn().mockResolvedValue([]) },
    flagAPI: { patch: vi.fn() },
    adhocFormsAPI: { replacePdf: vi.fn() },
  };
});

const { HrCaseFormRow } = await import('../HrCaseFormRow');

expect.extend(matchers);

let fetchSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  patchStatus.mockReset();
  patchStatus.mockResolvedValue({});
  fetchSpy = vi.spyOn(globalThis, 'fetch');
});

afterEach(() => {
  cleanup();
  fetchSpy.mockRestore();
});

function makeForm(overrides: Partial<CaseFormSummary> = {}): CaseFormSummary {
  return {
    id: 'form-1',
    case_id: 'case-1',
    status: 'in_progress',
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
      source_url: null,
      source_last_verified: null,
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

async function expandRow() {
  fireEvent.click(screen.getByText('D-number application'));
  await screen.findByText('Change status:');
}

describe('HrCaseFormRow — status PATCH via formEditor', () => {
  it('calls formEditor.patchStatus (not fetch) when marking ready', async () => {
    const onRefresh = vi.fn();
    render(<HrCaseFormRow form={makeForm()} onRefresh={onRefresh} />);
    await expandRow();

    fireEvent.click(screen.getByRole('button', { name: 'Mark Ready' }));

    await waitFor(() => {
      expect(patchStatus).toHaveBeenCalledWith('case-1', 'form-1', {
        status: 'ready',
        note: undefined,
      });
    });
    expect(fetchSpy).not.toHaveBeenCalled();
    await waitFor(() => expect(onRefresh).toHaveBeenCalled());
  });

  it('calls formEditor.patchStatus (not fetch) for reject then reopen', async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    render(<HrCaseFormRow form={makeForm({ status: 'submitted' })} onRefresh={onRefresh} />);
    await expandRow();

    fireEvent.click(screen.getByRole('button', { name: 'Reject' }));
    const reason = await screen.findByLabelText(/Rejection reason/);
    await user.type(reason, 'Missing apostille');
    fireEvent.click(screen.getByRole('button', { name: 'Reject Form' }));

    await waitFor(() => {
      expect(patchStatus).toHaveBeenCalledWith('case-1', 'form-1', {
        status: 'rejected',
        rejection_reason: 'Missing apostille',
        note: 'Missing apostille',
      });
    });
    await waitFor(() => {
      expect(patchStatus).toHaveBeenCalledWith('case-1', 'form-1', {
        status: 'not_started',
        note: 'Re-opened for employee correction',
      });
    });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('surfaces axios response.detail on a failed mark-ready', async () => {
    patchStatus.mockRejectedValueOnce({
      response: { data: { detail: 'Missing required fields' } },
    });
    render(<HrCaseFormRow form={makeForm()} onRefresh={vi.fn()} />);
    await expandRow();

    fireEvent.click(screen.getByRole('button', { name: 'Mark Ready' }));

    expect(await screen.findByText('Missing required fields')).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
