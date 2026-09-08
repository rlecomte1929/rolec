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

  it('exposes exactly one upload affordance, and it is the per-row one', () => {
    // The header carried a primary "Upload" button wired to `onClick={() => {}}`.
    // It cannot be implemented from this layer: it has no row, so it has no
    // document_key, and GET /api/cases/{id}/documents only returns keys the case's
    // relocation plan requires — a file stored under an invented key is never listed
    // back, so the upload would silently vanish. It was removed rather than wired.
    //
    // This asserts the removal AND that we did not grow a second upload path: with a
    // single row on screen there is exactly one Upload control and one file input.
    const doc = makeDoc({ key: 'passport_copy', filename: 'Passport copy' });
    const { container } = render(<DocumentsScreen documents={[doc]} />);

    const uploadButtons = screen.getAllByRole('button', { name: /upload/i });
    expect(uploadButtons).toHaveLength(1);
    // The survivor is the row control — it carries the row's title, the header one did not.
    expect(uploadButtons[0]).toHaveAttribute('title', 'Upload document');
    expect(container.querySelectorAll('input[type="file"]')).toHaveLength(1);
  });

  // Reads the number rendered next to a stat-tile label. Scoped to `p` because the
  // row status pills use the same words ("Missing") in a <span>.
  function statValue(label: string): string {
    const labelEl = screen.getByText(label, { selector: 'p' });
    const tile = labelEl.parentElement!;
    return tile.querySelector('p')!.textContent!;
  }

  it('separates Missing from In review so an upload visibly moves the needle', () => {
    // One uploaded-and-awaiting-review, one still required. Under the old single
    // 'Outstanding' tile both landed in the same bucket, so uploading a document
    // changed nothing on screen until an approval arrived.
    const docs = [
      makeDoc({ key: 'passport_copy', filename: 'Passport copy', status: 'submitted', uploaded_at: '2026-08-16T10:00:00Z' }),
      makeDoc({ key: 'employment_letter', filename: 'Employment letter', status: 'required' }),
    ];
    render(<DocumentsScreen documents={docs} />);

    expect(screen.queryByText('Outstanding')).not.toBeInTheDocument();
    expect(statValue('Missing')).toBe('1');
    expect(statValue('In review')).toBe('1');
  });

  it('a fully uploaded case reads Missing 0 / In review 2 with no approval', () => {
    // The task's metric: with 2 required docs, uploading both → Missing 0, In review 2.
    const docs = [
      makeDoc({ key: 'passport_copy', filename: 'Passport copy', status: 'submitted', uploaded_at: '2026-08-16T10:00:00Z' }),
      makeDoc({ key: 'employment_letter', filename: 'Employment letter', status: 'under_review', uploaded_at: '2026-08-16T10:05:00Z' }),
    ];
    render(<DocumentsScreen documents={docs} />);

    expect(statValue('Missing')).toBe('0');
    expect(statValue('In review')).toBe('2');
    // Nothing is approved yet, so the progress figure must not move.
    expect(statValue('Approved')).toBe('0');
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
