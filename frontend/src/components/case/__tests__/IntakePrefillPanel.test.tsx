/**
 * [W1-3b] The contract read is a PROPOSAL until HR confirms it.
 *
 * The backend deliberately splits this in two: `propose` runs OCR + extraction and writes
 * nothing, `confirm` is the only writer and carries the fields in its own body. That split
 * only buys anything if the UI honours it, so these tests pin the three ways it could be
 * quietly undone:
 *
 *   1. a write happening on upload rather than on confirm;
 *   2. the model's reading being sent instead of HR's edit;
 *   3. a field the model could not read being hidden, so HR never gets to supply it —
 *      which is the field that matters most, since an unread origin_country is exactly
 *      what leaves Andrea's roadmap generic.
 *
 * Shaped after PassportOCRFlow.confirm.test.tsx: render ConfirmStep directly with a canned
 * proposal, so the test is about confirm semantics rather than multipart upload.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';

const post = vi.fn();
vi.mock('../../../api/client', () => ({
  default: { post: (...a: unknown[]) => post(...a), put: vi.fn(), get: vi.fn() },
}));

import { ConfirmStep, type ProposeResponse } from '../IntakePrefillPanel';

expect.extend(matchers);

const PROPOSAL: ProposeResponse = {
  case_id: 'case-1',
  assignment_id: 'a-1',
  document_type: 'employment_contract',
  pages_count: 3,
  fields: {
    full_name: { value: 'Andrea Ramirez', confidence: 0.97 },
    nationality: { value: 'VE', confidence: 0.9 },
    job_title: { value: 'Senior Data Engineer', confidence: 0.95 },
    salary_band: { value: '58000 EUR', confidence: 0.88 },
    contract_type: { value: 'permanent', confidence: 0.8 },
    contract_start: { value: '2026-10-01', confidence: 0.93 },
    target_date: { value: null, confidence: 0 },
    origin_city: { value: 'Madrid', confidence: 0.7 },
    origin_country: { value: 'ES', confidence: 0.85 },
    dest_city: { value: 'Dublin', confidence: 0.96 },
    dest_country: { value: 'IE', confidence: 0.96 },
  },
  written: false,
};

const ALL_FIELDS = Object.keys(PROPOSAL.fields);

function renderConfirm(overrides: Partial<ProposeResponse> = {}) {
  const onConfirmed = vi.fn();
  const onDiscard = vi.fn();
  render(
    <ConfirmStep
      caseId="case-1"
      proposal={{ ...PROPOSAL, ...overrides }}
      onConfirmed={onConfirmed}
      onDiscard={onDiscard}
    />,
  );
  return { onConfirmed, onDiscard };
}

beforeEach(() => {
  post.mockReset();
  post.mockResolvedValue({
    data: {
      case_id: 'case-1',
      assignment_id: 'a-1',
      written_fields: ['dest_country'],
      skipped_fields: [],
      provenance: 'hr_extracted',
      intake_draft: {},
    },
  });
});
afterEach(() => cleanup());

describe('IntakePrefillPanel — confirm step', () => {
  it('renders an editable row for every field, including ones the model could not read', () => {
    renderConfirm();
    for (const label of [
      'Full name',
      'Nationality (ISO)',
      'Job title',
      'Salary',
      'Contract type',
      'Start date',
      'Target move date', // value null — must still be present and editable
      'Origin city',
      'Origin country (ISO)',
      'Destination city',
      'Destination country (ISO)',
    ]) {
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    }
    expect(screen.getAllByRole('textbox')).toHaveLength(ALL_FIELDS.length);
  });

  it('shows an unread field as empty and editable rather than hiding it', () => {
    renderConfirm();
    const input = screen.getByLabelText('Target move date') as HTMLInputElement;
    expect(input.value).toBe('');
    expect(input).not.toBeDisabled();
    fireEvent.change(input, { target: { value: '2026-09-20' } });
    expect((screen.getByLabelText('Target move date') as HTMLInputElement).value).toBe('2026-09-20');
  });

  it('surfaces confidence as a hint', () => {
    renderConfirm();
    expect(screen.getByText('97%')).toBeInTheDocument();
    expect(screen.getByText('88%')).toBeInTheDocument();
  });

  it('writes NOTHING until confirm is pressed', async () => {
    renderConfirm();
    fireEvent.change(screen.getByLabelText('Job title'), {
      target: { value: 'Principal Data Engineer' },
    });
    fireEvent.change(screen.getByLabelText('Destination city'), { target: { value: 'Cork' } });
    // Rendering and editing must not touch the network.
    expect(post).not.toHaveBeenCalled();
  });

  it('posts to confirm only on the button, and sends HR EDIT not the model reading', async () => {
    renderConfirm();
    fireEvent.change(screen.getByLabelText('Job title'), {
      target: { value: 'Principal Data Engineer' },
    });
    fireEvent.click(screen.getByRole('button', { name: /confirm & prefill intake/i }));

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    const [url, body] = post.mock.calls[0];
    expect(url).toBe('/api/hr/cases/case-1/intake-extraction/confirm');
    expect(body.fields.job_title).toBe('Principal Data Engineer');
    expect(body.fields.job_title).not.toBe('Senior Data Engineer');
    // The corridor ends are what make W1-2's regeneration stop being a no-op.
    expect(body.fields.origin_country).toBe('ES');
    expect(body.fields.dest_country).toBe('IE');
  });

  it('sends every field, so a value HR typed into an unread field is not dropped', async () => {
    renderConfirm();
    fireEvent.change(screen.getByLabelText('Target move date'), {
      target: { value: '2026-09-20' },
    });
    fireEvent.click(screen.getByRole('button', { name: /confirm & prefill intake/i }));

    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post.mock.calls[0][1].fields.target_date).toBe('2026-09-20');
  });

  it('reports the confirmed result upward', async () => {
    const { onConfirmed } = renderConfirm();
    fireEvent.click(screen.getByRole('button', { name: /confirm & prefill intake/i }));
    await waitFor(() => expect(onConfirmed).toHaveBeenCalledTimes(1));
    expect(onConfirmed.mock.calls[0][0].written_fields).toEqual(['dest_country']);
  });

  it('discard writes nothing at all', () => {
    const { onDiscard } = renderConfirm();
    fireEvent.click(screen.getByRole('button', { name: /discard/i }));
    expect(onDiscard).toHaveBeenCalledTimes(1);
    expect(post).not.toHaveBeenCalled();
  });

  it('surfaces a save failure instead of reporting success', async () => {
    post.mockRejectedValueOnce({ response: { data: { detail: 'Assignment not found.' } } });
    const { onConfirmed } = renderConfirm();
    fireEvent.click(screen.getByRole('button', { name: /confirm & prefill intake/i }));
    await waitFor(() => expect(screen.getByText('Assignment not found.')).toBeInTheDocument());
    expect(onConfirmed).not.toHaveBeenCalled();
  });
});
