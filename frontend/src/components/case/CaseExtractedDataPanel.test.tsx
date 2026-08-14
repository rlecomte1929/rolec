/**
 * AIQ-1790 — the panel that finally shows an HR user what the extraction engine read.
 *
 * The states worth pinning are the AWKWARD ones, not the happy path. Only passports
 * extract today (every other document type waits on an OCR engine that is not
 * enabled), so "no data yet" is the majority case and must never render as a failure.
 * And the list endpoint's `extracted_field_count` OVER-COUNTS — it sums every
 * extraction run, so a re-processed document reads 22 for 13 real fields. Putting
 * that number in front of a customer would simply be false.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

const listDocuments = vi.fn();
const fields = vi.fn();

vi.mock('../../api/caseExtraction', () => ({
  caseExtractionAPI: {
    listDocuments: (...a: unknown[]) => listDocuments(...a),
    fields: (...a: unknown[]) => fields(...a),
  },
}));

import { CaseExtractedDataPanel } from './CaseExtractedDataPanel';

afterEach(() => {
  cleanup();
  listDocuments.mockReset();
  fields.mockReset();
});

const doc = (over: Record<string, unknown> = {}) => ({
  document_id: 'doc-1',
  document_type_code: 'PASSPORT_TD3',
  document_type_label: 'Passport',
  filename: 'passport.png',
  uploaded_at: '2026-08-10T12:00:00Z',
  confidence_mean: 0.86,
  confidence_min: 0.5,
  extracted_field_count: 22,
  document_uri: null,
  page_count: null,
  ...over,
});

const field = (key: string, value: string | null, confidence: number | null, masked = false) => ({
  field_key: key, value, confidence, resolution_status: 'Resolved', masked, page: 1,
});

describe('CaseExtractedDataPanel', () => {
  it('shows the extracted values once the document is expanded', async () => {
    listDocuments.mockResolvedValue([doc()]);
    fields.mockResolvedValue({
      document_id: 'doc-1', document_type_code: 'PASSPORT_TD3', field_count: 2,
      fields: [field('surname', 'ERIKSSON', 1.0), field('expiry_date', '2029-08-12', 1.0)],
    });

    render(<CaseExtractedDataPanel caseId="case-1" />);
    await screen.findByText('passport.png');
    fireEvent.click(screen.getByRole('button', { name: 'View data' }));

    // The point of the whole feature: a real value in front of a human.
    expect(await screen.findByText('ERIKSSON')).toBeInTheDocument();
    expect(screen.getByText('2029-08-12')).toBeInTheDocument();
    expect(screen.getByText('Surname')).toBeInTheDocument();
  });

  it('never renders the over-counting field total from the list endpoint', async () => {
    listDocuments.mockResolvedValue([doc({ extracted_field_count: 22 })]);
    fields.mockResolvedValue({
      document_id: 'doc-1', document_type_code: 'PASSPORT_TD3', field_count: 13,
      fields: [field('surname', 'ERIKSSON', 1.0)],
    });

    render(<CaseExtractedDataPanel caseId="case-1" />);
    await screen.findByText('passport.png');
    // 22 must not appear before expansion...
    expect(screen.queryByText(/22/)).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'View data' }));
    await screen.findByText('ERIKSSON');
    // ...nor after. The deduplicated 13 is the only count shown.
    expect(screen.queryByText(/22 fields/)).toBeNull();
    expect(screen.getByText(/13 fields read from this document/)).toBeInTheDocument();
  });

  it('reads a document with no extraction as pending, not as an error', async () => {
    // The MAJORITY case today — every non-passport type is gated on an unset
    // MISTRAL_API_KEY. Rendering it as a failure would misreport normal operation.
    listDocuments.mockResolvedValue([
      doc({ document_type_code: 'MARRIAGE_CERT', document_type_label: 'Marriage certificate',
            extracted_field_count: 0, confidence_min: null }),
    ]);

    render(<CaseExtractedDataPanel caseId="case-1" />);
    expect(await screen.findByText('Not yet processed')).toBeInTheDocument();
    expect(screen.queryByText(/failed/i)).toBeNull();
    expect(screen.queryByRole('button', { name: 'View data' })).toBeNull();
  });

  it('renders an empty case without an error', async () => {
    listDocuments.mockResolvedValue([]);
    render(<CaseExtractedDataPanel caseId="case-1" />);
    expect(
      await screen.findByText('No documents have been processed for this case yet.'),
    ).toBeInTheDocument();
  });

  it('surfaces a load failure as retryable rather than as an empty case', async () => {
    // Silently showing "no documents" on a failed fetch is the mock-fallback trap:
    // it reports absence of data when the truth is absence of an answer.
    listDocuments.mockRejectedValue(new Error('boom'));
    render(<CaseExtractedDataPanel caseId="case-1" />);
    expect(await screen.findByText(/Could not load extracted data/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
  });

  it('tells the user when an identifying number has been masked', async () => {
    listDocuments.mockResolvedValue([doc()]);
    fields.mockResolvedValue({
      document_id: 'doc-1', document_type_code: 'PASSPORT_TD3', field_count: 1,
      fields: [field('document_number', '••••••••', 1.0, true)],
    });

    render(<CaseExtractedDataPanel caseId="case-1" />);
    await screen.findByText('passport.png');
    fireEvent.click(screen.getByRole('button', { name: 'View data' }));
    expect(await screen.findByText(/Identifying numbers are masked/)).toBeInTheDocument();
  });

  it('fetches the field values only once per document', async () => {
    listDocuments.mockResolvedValue([doc()]);
    fields.mockResolvedValue({
      document_id: 'doc-1', document_type_code: 'PASSPORT_TD3', field_count: 1,
      fields: [field('surname', 'ERIKSSON', 1.0)],
    });

    render(<CaseExtractedDataPanel caseId="case-1" />);
    await screen.findByText('passport.png');
    fireEvent.click(screen.getByRole('button', { name: 'View data' }));
    await screen.findByText('ERIKSSON');
    fireEvent.click(screen.getByRole('button', { name: 'Hide' }));
    fireEvent.click(screen.getByRole('button', { name: 'View data' }));
    await waitFor(() => expect(fields).toHaveBeenCalledTimes(1));
  });
});
