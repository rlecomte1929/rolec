/**
 * DocumentsScreen — case-scoped surface (Phase 2).
 * Covers: empty state, per-row upload carrying the document_key, and the
 * ?doc=<key> deep-link highlight/scroll/focus.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { DocumentsScreen, type DocumentItem } from '../DocumentsScreen';

expect.extend(matchers);

function makeDoc(over: Partial<DocumentItem> & { key: string }): DocumentItem {
  return {
    id: over.key,
    filename: `${over.key}.pdf`,
    category: 'Identity & travel',
    status: 'required',
    uploaded_at: null,
    file_url: null,
    submission_deadline: null,
    expiry_date: null,
    rejection_reason: null,
    size_kb: 0,
    ...over,
  };
}

beforeEach(() => {
  // jsdom has no scrollIntoView.
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(cleanup);

describe('DocumentsScreen', () => {
  it('renders an empty state when there are no required documents', () => {
    render(<DocumentsScreen documents={[]} />);
    expect(screen.getByText('No documents required yet')).toBeInTheDocument();
  });

  it('uploads carry the row document_key (not just a category)', async () => {
    const onUpload = vi.fn().mockResolvedValue(undefined);
    const doc = makeDoc({ key: 'passport_copy', filename: 'Passport copy' });
    const { container } = render(<DocumentsScreen documents={[doc]} onUpload={onUpload} />);

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(['x'], 'passport_copy.pdf', { type: 'application/pdf' });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(onUpload).toHaveBeenCalledTimes(1));
    expect(onUpload).toHaveBeenCalledWith(file, 'passport_copy');
  });

  it('deep-links to the matching row and scrolls it into view', async () => {
    const docs = [
      makeDoc({ key: 'passport_copy', filename: 'Passport copy' }),
      makeDoc({ key: 'employment_letter', filename: 'Employment letter', category: 'Employment' }),
    ];
    render(<DocumentsScreen documents={docs} deepLinkKey="employment_letter" />);
    await waitFor(() => expect(Element.prototype.scrollIntoView).toHaveBeenCalled());
    // The deep-linked row's category accordion is auto-expanded so the row mounts.
    expect(screen.getByText('Employment letter')).toBeInTheDocument();
  });
});
