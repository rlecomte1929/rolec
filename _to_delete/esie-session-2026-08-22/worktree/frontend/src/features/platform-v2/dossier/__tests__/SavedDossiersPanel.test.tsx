/**
 * [P3-6] SavedDossiersPanel.test.tsx
 *
 * Coverage:
 *   - Loading state
 *   - Empty state (no packages)
 *   - Renders package rows with name, form count, generated date
 *   - Stale badge visible when is_stale=true
 *   - No stale badge when is_stale=false
 *   - Error state when API rejects
 *   - Regenerate: calls API, removes stale badge from the updated row
 *   - Delete: calls confirm + API, removes row from the list
 *   - data-testid attributes on key elements
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, fireEvent, waitFor, act, cleanup } from '@testing-library/react';
import { SavedDossiersPanel } from '../SavedDossiersPanel';

expect.extend(matchers);

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Mock dossierPackageAPI
// ---------------------------------------------------------------------------

const mockList = vi.fn();
const mockRegenerate = vi.fn();
const mockDelete = vi.fn();

vi.mock('../../../../api/dossier', () => ({
  dossierPackageAPI: {
    list: (...args: unknown[]): unknown => mockList(...args),
    regenerate: (...args: unknown[]): unknown => mockRegenerate(...args),
    delete: (...args: unknown[]): unknown => mockDelete(...args),
    getPdfUrl: (caseId: string, id: string) => `/api/cases/${caseId}/dossiers/${id}/pdf`,
    getZipUrl: (caseId: string, id: string) => `/api/cases/${caseId}/dossiers/${id}/zip`,
  },
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CASE_ID = 'case-abc-123';

function makePackage(overrides: Record<string, unknown> = {}) {
  return {
    id: 'pkg-1',
    case_id: CASE_ID,
    name: 'My Dossier',
    form_ids: ['form-1', 'form-2'],
    cover_page: true,
    pdf_url: null,
    generated_at: '2026-05-01T10:00:00',
    created_at: '2026-05-01T09:00:00',
    is_stale: false,
    ...overrides,
  };
}

function renderPanel(caseId = CASE_ID, onChanged?: () => void) {
  return render(<SavedDossiersPanel caseId={caseId} onChanged={onChanged} />);
}

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

describe('SavedDossiersPanel — loading state', () => {
  it('shows a loading spinner while fetching', () => {
    // Never resolves during this test
    mockList.mockReturnValue(new Promise(() => {}));
    renderPanel();
    expect(screen.getByText(/loading saved dossiers/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

describe('SavedDossiersPanel — empty state', () => {
  beforeEach(() => {
    mockList.mockResolvedValue([]);
  });

  it('shows empty message when there are no packages', async () => {
    renderPanel();
    expect(await screen.findByText(/no saved dossier packages yet/i)).toBeInTheDocument();
  });

  it('does not render the saved-dossiers-panel testid when empty', async () => {
    renderPanel();
    await screen.findByText(/no saved dossier packages yet/i);
    expect(screen.queryByTestId('saved-dossiers-panel')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

describe('SavedDossiersPanel — error state', () => {
  it('shows error message when API rejects', async () => {
    mockList.mockRejectedValue(new Error('Server error'));
    renderPanel();
    expect(await screen.findByText(/server error/i)).toBeInTheDocument();
  });

  it('shows API detail error when available', async () => {
    mockList.mockRejectedValue({ response: { data: { detail: 'Forbidden' } } });
    renderPanel();
    expect(await screen.findByText('Forbidden')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Renders package rows
// ---------------------------------------------------------------------------

describe('SavedDossiersPanel — package rows', () => {
  beforeEach(() => {
    mockList.mockResolvedValue([makePackage()]);
  });

  it('renders the panel testid after loading', async () => {
    renderPanel();
    expect(await screen.findByTestId('saved-dossiers-panel')).toBeInTheDocument();
  });

  it('shows the package name', async () => {
    renderPanel();
    expect(await screen.findByText('My Dossier')).toBeInTheDocument();
  });

  it('shows form count in metadata line', async () => {
    renderPanel();
    expect(await screen.findByText(/2 forms/i)).toBeInTheDocument();
  });

  it('renders download PDF and ZIP links', async () => {
    renderPanel();
    expect(await screen.findByTestId('download-pdf-link')).toBeInTheDocument();
    expect(screen.getByTestId('download-zip-link')).toBeInTheDocument();
  });

  it('PDF link href points to pdf endpoint', async () => {
    renderPanel();
    const link = await screen.findByTestId('download-pdf-link');
    expect(link).toHaveAttribute('href', `/api/cases/${CASE_ID}/dossiers/pkg-1/pdf`);
  });

  it('ZIP link href points to zip endpoint', async () => {
    renderPanel();
    const link = await screen.findByTestId('download-zip-link');
    expect(link).toHaveAttribute('href', `/api/cases/${CASE_ID}/dossiers/pkg-1/zip`);
  });

  it('renders regenerate and delete buttons', async () => {
    renderPanel();
    expect(await screen.findByTestId('regenerate-button')).toBeInTheDocument();
    expect(screen.getByTestId('delete-button')).toBeInTheDocument();
  });

  it('renders multiple packages', async () => {
    mockList.mockResolvedValue([
      makePackage({ id: 'pkg-1', name: 'First Package' }),
      makePackage({ id: 'pkg-2', name: 'Second Package' }),
    ]);
    renderPanel();
    await waitFor(() =>
      expect(screen.getAllByTestId('saved-dossier-row')).toHaveLength(2),
    );
    expect(screen.getByText('First Package')).toBeInTheDocument();
    expect(screen.getByText('Second Package')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Stale badge
// ---------------------------------------------------------------------------

describe('SavedDossiersPanel — stale badge', () => {
  it('shows stale badge when is_stale=true', async () => {
    mockList.mockResolvedValue([makePackage({ is_stale: true })]);
    renderPanel();
    expect(await screen.findByTestId('stale-badge')).toBeInTheDocument();
  });

  it('does not show stale badge when is_stale=false', async () => {
    mockList.mockResolvedValue([makePackage({ is_stale: false })]);
    renderPanel();
    expect(await screen.findByTestId('saved-dossier-row')).toBeInTheDocument();
    expect(screen.queryByTestId('stale-badge')).not.toBeInTheDocument();
  });

  it('shows staleness warning banner when is_stale=true', async () => {
    mockList.mockResolvedValue([makePackage({ is_stale: true })]);
    renderPanel();
    expect(await screen.findByText(/form fields were updated/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Regenerate action
// ---------------------------------------------------------------------------

describe('SavedDossiersPanel — regenerate', () => {
  it('calls dossierPackageAPI.regenerate with caseId and dossierId', async () => {
    mockList.mockResolvedValue([makePackage({ is_stale: true })]);
    const freshPkg = makePackage({ is_stale: false });
    mockRegenerate.mockResolvedValue(freshPkg);
    renderPanel();

    const btn = await screen.findByTestId('regenerate-button');
    act(() => { fireEvent.click(btn); });

    expect(mockRegenerate).toHaveBeenCalledWith(CASE_ID, 'pkg-1');
  });

  it('removes the stale badge after successful regeneration', async () => {
    mockList.mockResolvedValue([makePackage({ is_stale: true })]);
    mockRegenerate.mockResolvedValue(makePackage({ is_stale: false }));
    renderPanel();

    // Stale badge should be present before regenerate
    expect(await screen.findByTestId('stale-badge')).toBeInTheDocument();

    const btn = screen.getByTestId('regenerate-button');
    act(() => { fireEvent.click(btn); });

    await waitFor(() =>
      expect(screen.queryByTestId('stale-badge')).not.toBeInTheDocument(),
    );
  });

  it('calls onChanged callback after successful regeneration', async () => {
    mockList.mockResolvedValue([makePackage()]);
    mockRegenerate.mockResolvedValue(makePackage());
    const onChanged = vi.fn();
    renderPanel(CASE_ID, onChanged);

    const btn = await screen.findByTestId('regenerate-button');
    act(() => { fireEvent.click(btn); });

    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
  });
});

// ---------------------------------------------------------------------------
// Delete action
// ---------------------------------------------------------------------------

describe('SavedDossiersPanel — delete', () => {
  beforeEach(() => {
    // Suppress window.confirm
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('calls window.confirm before deleting', async () => {
    mockList.mockResolvedValue([makePackage()]);
    mockDelete.mockResolvedValue(undefined);
    renderPanel();

    const btn = await screen.findByTestId('delete-button');
    act(() => { fireEvent.click(btn); });

    expect(window.confirm).toHaveBeenCalled();
  });

  it('calls dossierPackageAPI.delete with correct args', async () => {
    mockList.mockResolvedValue([makePackage()]);
    mockDelete.mockResolvedValue(undefined);
    renderPanel();

    const btn = await screen.findByTestId('delete-button');
    act(() => { fireEvent.click(btn); });

    await waitFor(() =>
      expect(mockDelete).toHaveBeenCalledWith(CASE_ID, 'pkg-1'),
    );
  });

  it('removes the row from the list after delete', async () => {
    mockList.mockResolvedValue([
      makePackage({ id: 'pkg-1', name: 'To Delete' }),
      makePackage({ id: 'pkg-2', name: 'To Keep' }),
    ]);
    mockDelete.mockResolvedValue(undefined);
    renderPanel();

    // Wait for both rows
    await waitFor(() =>
      expect(screen.getAllByTestId('saved-dossier-row')).toHaveLength(2),
    );

    // Delete the first one — find delete buttons in order
    const deleteButtons = screen.getAllByTestId('delete-button');
    act(() => { fireEvent.click(deleteButtons[0]); }); // sync click, no await needed

    await waitFor(() =>
      expect(screen.getAllByTestId('saved-dossier-row')).toHaveLength(1),
    );
    expect(screen.queryByText('To Delete')).not.toBeInTheDocument();
    expect(screen.getByText('To Keep')).toBeInTheDocument();
  });

  it('does not delete if user cancels confirmation', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    mockList.mockResolvedValue([makePackage()]);
    renderPanel();

    const btn = await screen.findByTestId('delete-button');
    act(() => { fireEvent.click(btn); });

    expect(mockDelete).not.toHaveBeenCalled();
    // Row should still be visible
    expect(screen.getByTestId('saved-dossier-row')).toBeInTheDocument();
  });

  it('calls onChanged callback after successful delete', async () => {
    mockList.mockResolvedValue([makePackage()]);
    mockDelete.mockResolvedValue(undefined);
    const onChanged = vi.fn();
    renderPanel(CASE_ID, onChanged);

    const btn = await screen.findByTestId('delete-button');
    act(() => { fireEvent.click(btn); });

    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
  });
});
