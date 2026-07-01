/**
 * ImportFlow — "Import from document" wiring to the REAL policy-extraction
 * backend (upload → poll status → import-extraction). Guards that the modal
 * renders the REAL returned rows (not the old fabricated MOCK_RULES) and that
 * failure/empty states are honest.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// The page module transitively constructs the Supabase client at import time,
// which needs env vars absent in the test runner — mock it (hoisted).
vi.mock('../../../../api/supabase', () => ({
  supabase: {
    auth: {
      getSession: () => Promise.resolve({ data: { session: null } }),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
    },
    from: () => ({ select: () => ({}) }),
  },
}));

const mocks = vi.hoisted(() => ({
  upload: vi.fn(),
  getDoc: vi.fn(),
  hrImportExtraction: vi.fn(),
  hrGet: vi.fn(),
}));

vi.mock('../../../../api/client', () => ({
  policyDocumentsAPI: {
    upload: mocks.upload,
    get: mocks.getDoc,
  },
  policyConfigMatrixAPI: {
    hrImportExtraction: mocks.hrImportExtraction,
    hrGet: mocks.hrGet,
    hrPostDraft: vi.fn(),
    hrPutDraft: vi.fn(),
    hrPublish: vi.fn(),
  },
}));

import { ImportFlow } from '../HrPolicyBuilderV2Page';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function selectFileAndStart(container: HTMLElement) {
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  const file = new File(['policy bytes'], 'policy.pdf', { type: 'application/pdf' });
  fireEvent.change(input, { target: { files: [file] } });
  fireEvent.click(screen.getByText(/Start extraction/));
}

describe('ImportFlow — real extraction wiring', () => {
  it('uploads, polls real status, imports, and renders the REAL returned rows', async () => {
    mocks.upload.mockResolvedValue({ ok: true, document: { id: 'doc-1' } });
    mocks.getDoc.mockResolvedValue({ document: { id: 'doc-1', assistant_import_status: 'classified' } });
    mocks.hrImportExtraction.mockResolvedValue({
      imported: ['host_housing_cap', 'mobility_premium'],
      skipped_existing: [],
      unmapped: ['gym_membership'],
      version_id: 'v1',
    });

    const { container } = render(<ImportFlow onClose={() => {}} onImported={() => {}} />);
    selectFileAndStart(container);

    // Real imported benefit labels (mapped from the returned matrix keys).
    expect(await screen.findByText('Host country housing cap')).toBeInTheDocument();
    expect(screen.getByText('Mobility premium')).toBeInTheDocument();
    // Honest "couldn't map" surfacing of the unmapped extraction key.
    expect(screen.getByText('gym_membership')).toBeInTheDocument();
    expect(screen.getByText(/imported into your draft/)).toBeInTheDocument();

    // Wired to the real endpoints with the captured document id.
    expect(mocks.upload).toHaveBeenCalledTimes(1);
    expect(mocks.getDoc).toHaveBeenCalledWith('doc-1');
    expect(mocks.hrImportExtraction).toHaveBeenCalledWith({ policy_id: 'doc-1' });
  });

  it('shows an honest error state when extraction fails', async () => {
    mocks.upload.mockResolvedValue({ ok: true, document: { id: 'doc-2' } });
    mocks.getDoc.mockResolvedValue({
      document: { id: 'doc-2', assistant_import_status: 'failed', extraction_error: 'Unreadable scan' },
    });

    const { container } = render(<ImportFlow onClose={() => {}} onImported={() => {}} />);
    selectFileAndStart(container);

    expect(await screen.findByText('Extraction failed')).toBeInTheDocument();
    expect(screen.getByText('Unreadable scan')).toBeInTheDocument();
    // No import call should fire on a failed document.
    expect(mocks.hrImportExtraction).not.toHaveBeenCalled();
  });

  it('shows an honest empty state when nothing could be imported', async () => {
    mocks.upload.mockResolvedValue({ ok: true, document: { id: 'doc-3' } });
    mocks.getDoc.mockResolvedValue({ document: { id: 'doc-3', assistant_import_status: 'normalized' } });
    mocks.hrImportExtraction.mockResolvedValue({
      imported: [],
      skipped_existing: [],
      unmapped: [],
      version_id: 'v3',
    });

    const { container } = render(<ImportFlow onClose={() => {}} onImported={() => {}} />);
    selectFileAndStart(container);

    expect(await screen.findByText('No benefits could be imported')).toBeInTheDocument();
  });

  it('no longer references the fabricated MOCK_RULES / MOCK_LOG', () => {
    const src = readFileSync(
      resolve(process.cwd(), 'src/features/platform-v2/policy-builder/HrPolicyBuilderV2Page.tsx'),
      'utf8',
    );
    expect(src).not.toMatch(/MOCK_RULES|MOCK_LOG/);
  });
});
