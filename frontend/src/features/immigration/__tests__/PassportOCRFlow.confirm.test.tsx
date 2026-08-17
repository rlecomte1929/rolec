/**
 * [AIQ-1859] The passport scan is a proposal until the employee confirms it.
 *
 * The confirm step used to be read-only, and the write had already happened: the OCR
 * endpoint called save_ocr_to_vault on upload ("Does NOT require the employee to
 * confirm — fields are saved immediately"). So "Save extracted data" was decorative and
 * "Discard & enter manually" left the passport number, MRZ lines and date of birth in
 * the vault while merely advancing the wizard.
 *
 * These tests pin the two halves that fix: the review is editable and the edit is what
 * gets saved, and Discard writes nothing at all.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';

const put = vi.fn();
vi.mock('../../../api/client', () => ({ default: { put: (...a: unknown[]) => put(...a), post: vi.fn() } }));

import { ConfirmStep } from '../PassportOCRFlow';

expect.extend(matchers);

// Drive the component straight to the confirm step by handing it an OCR result.
// The flow keeps that in state after a successful upload; rendering the step directly
// keeps the test about confirm semantics rather than about multipart upload.
const RESULT = {
  profile_id: null,
  storage_path: 'case-docs/c1/passport/x.jpg',
  extracted_fields: {
    legal_first_name: 'ANDREA',
    legal_last_name: 'PEINADO',
    passport_number: 'ESP123456',
    date_of_birth: '1990-04-12',
  },
  confidence: { legal_first_name: 0.98, legal_last_name: 0.97, passport_number: 1.0, date_of_birth: 0.95 },
  mrz_validation: { is_valid: true, error_fields: [] },
  conflicts: [],
  fields_saved: [],
};

beforeEach(() => {
  put.mockReset();
  put.mockResolvedValue({ data: { updated_fields: [] } });
});
afterEach(cleanup);

// ConfirmStep is rendered directly: the flow only reaches it after a multipart upload,
// and these tests are about confirm semantics, not about the upload.
function renderAtConfirm() {
  const onSaved = vi.fn();
  const onDiscard = vi.fn();
  render(<ConfirmStep caseId="case-1" result={RESULT} onSaved={onSaved} onDiscard={onDiscard} />);
  return { onSaved, onDiscard };
}

describe('PassportOCRFlow — confirm step', () => {
  it('saves the employee\'s corrected value, not the raw OCR value', async () => {
    const { onSaved } = renderAtConfirm();

    // OCR misread the surname; the employee fixes it before confirming.
    const surname = screen.getByLabelText(/last name|surname/i);
    fireEvent.change(surname, { target: { value: 'PEINADO GARCIA' } });
    fireEvent.click(screen.getByRole('button', { name: /confirm & save/i }));

    await waitFor(() => expect(put).toHaveBeenCalledTimes(1));
    const [url, body] = put.mock.calls[0];
    expect(url).toBe('/api/employee/cases/case-1/profile');
    expect(body.legal_last_name).toBe('PEINADO GARCIA');
    expect(body.field_source).toBe('ocr_confirmed');
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it('writes nothing when the employee discards', async () => {
    const { onDiscard, onSaved } = renderAtConfirm();

    fireEvent.click(screen.getByRole('button', { name: /discard/i }));

    expect(put).not.toHaveBeenCalled();
    expect(onSaved).not.toHaveBeenCalled();
    expect(onDiscard).toHaveBeenCalled();
  });

  it('does not claim anything has been saved while reviewing', async () => {
    renderAtConfirm();
    expect(screen.getByText(/nothing is saved yet/i)).toBeInTheDocument();
    expect(screen.queryByText(/saved to your profile/i)).not.toBeInTheDocument();
  });
});
