/**
 * [P1-05c] FormDocuments.test.tsx — upload + list + delete widget.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';

expect.extend(matchers);

const mockList = vi.fn();
const mockUpload = vi.fn();
const mockRemove = vi.fn();

vi.mock('../../../../api/dossier', () => ({
  formDocumentsAPI: {
    list: (...a: unknown[]): unknown => mockList(...a),
    upload: (...a: unknown[]): unknown => mockUpload(...a),
    remove: (...a: unknown[]): unknown => mockRemove(...a),
  },
}));

const { FormDocuments } = await import('../FormDocuments');

const DOC = {
  id: 'doc-1', case_form_id: 'f1', case_id: 'c1', file_name: 'passport.pdf',
  content_type: 'application/pdf', size_bytes: 2048, uploaded_by: 'u1', doc_key: null,
  created_at: '2026-06-04T00:00:00Z', download_url: 'https://signed.example/passport',
};

beforeEach(() => {
  mockList.mockReset();
  mockUpload.mockReset();
  mockRemove.mockReset();
});
afterEach(cleanup);

describe('FormDocuments', () => {
  it('lists uploaded documents with a download link', async () => {
    mockList.mockResolvedValueOnce([DOC]);
    render(<FormDocuments caseId="c1" formId="f1" />);
    const link = await screen.findByRole('link', { name: 'passport.pdf' });
    expect(link).toHaveAttribute('href', 'https://signed.example/passport');
    expect(mockList).toHaveBeenCalledWith('c1', 'f1');
  });

  it('shows the empty state when there are no documents', async () => {
    mockList.mockResolvedValueOnce([]);
    render(<FormDocuments caseId="c1" formId="f1" />);
    expect(await screen.findByText('No documents uploaded yet.')).toBeInTheDocument();
  });

  it('uploads a selected file then reloads the list', async () => {
    mockList.mockResolvedValueOnce([]).mockResolvedValueOnce([DOC]);
    mockUpload.mockResolvedValueOnce(DOC);
    render(<FormDocuments caseId="c1" formId="f1" />);
    await screen.findByText('No documents uploaded yet.');

    const file = new File(['x'], 'passport.pdf', { type: 'application/pdf' });
    const input = screen.getByLabelText('Upload supporting document');
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(mockUpload).toHaveBeenCalledWith('c1', 'f1', file, null));
    expect(await screen.findByRole('link', { name: 'passport.pdf' })).toBeInTheDocument();
  });

  it('deletes a document then reloads', async () => {
    mockList.mockResolvedValueOnce([DOC]).mockResolvedValueOnce([]);
    mockRemove.mockResolvedValueOnce(undefined);
    render(<FormDocuments caseId="c1" formId="f1" />);
    const del = await screen.findByRole('button', { name: 'Delete passport.pdf' });
    fireEvent.click(del);
    await waitFor(() => expect(mockRemove).toHaveBeenCalledWith('c1', 'f1', 'doc-1'));
    expect(await screen.findByText('No documents uploaded yet.')).toBeInTheDocument();
  });

  it('surfaces an upload error', async () => {
    mockList.mockResolvedValueOnce([]);
    mockUpload.mockRejectedValueOnce({ response: { data: { detail: 'File exceeds the 20 MB limit' } } });
    render(<FormDocuments caseId="c1" formId="f1" />);
    await screen.findByText('No documents uploaded yet.');
    const file = new File(['x'], 'big.pdf', { type: 'application/pdf' });
    fireEvent.change(screen.getByLabelText('Upload supporting document'), { target: { files: [file] } });
    expect(await screen.findByText('File exceeds the 20 MB limit')).toBeInTheDocument();
  });

  const REQ = [
    { key: 'passport_number', label: 'Passport number' },
    { key: 'marriage_cert', label: 'Marriage certificate' },
  ];

  it('renders the required-document checklist with provided/missing state', async () => {
    // One required doc satisfied by an upload tagged with its doc_key.
    mockList.mockResolvedValueOnce([{ ...DOC, doc_key: 'passport_number' }]);
    render(<FormDocuments caseId="c1" formId="f1" requiredDocuments={REQ} />);
    const list = await screen.findByTestId('required-doc-checklist');
    expect(list).toHaveTextContent('Passport number');
    expect(list).toHaveTextContent('Marriage certificate');
    // The satisfied item has no Upload affordance; the missing one does.
    const items = list.querySelectorAll('li');
    expect(items[0]).toHaveTextContent('✓');          // passport provided
    expect(items[1]).toHaveTextContent('○');          // marriage missing
  });

  it('tags a per-item upload with the checklist doc_key', async () => {
    mockList.mockResolvedValueOnce([]).mockResolvedValueOnce([]);
    mockUpload.mockResolvedValueOnce({ ...DOC, doc_key: 'marriage_cert' });
    render(<FormDocuments caseId="c1" formId="f1" requiredDocuments={REQ} />);
    await screen.findByTestId('required-doc-checklist');

    // Click the "Upload" button on the (missing) Marriage-certificate row.
    const uploadButtons = screen.getAllByRole('button', { name: 'Upload' });
    fireEvent.click(uploadButtons[1]);
    const file = new File(['x'], 'cert.pdf', { type: 'application/pdf' });
    fireEvent.change(screen.getByLabelText('Upload supporting document'), { target: { files: [file] } });

    await waitFor(() =>
      expect(mockUpload).toHaveBeenCalledWith('c1', 'f1', file, 'marriage_cert'),
    );
  });
});
