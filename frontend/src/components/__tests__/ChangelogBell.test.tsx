/**
 * ChangelogBell — AIQ-407-followup regression tests.
 *
 * Covers:
 *   1. Renders the bell and fetches /changelog.json on mount.
 *   2. Unread red dot shows when localStorage seen-date is unset.
 *   3. Clicking the bell opens the panel and lists entries.
 *   4. Opening the panel persists the most-recent date to localStorage
 *      so the unread dot clears.
 *   5. Escape key closes the open panel.
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ChangelogBell } from '../ChangelogBell';

const SAMPLE_ENTRIES = [
  {
    id: '2026-05-27-a',
    date: '2026-05-27',
    title: 'Estimate Review',
    description: 'Per-category policy caps view for HR.',
  },
  {
    id: '2026-05-26-b',
    date: '2026-05-26',
    title: 'Country expansion',
    description: '11 new destinations added.',
  },
];

function mockChangelogFetch(payload: unknown = SAMPLE_ENTRIES) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(payload),
  });
  (globalThis as any).fetch = fetchMock;
  return fetchMock;
}

// jsdom in some vitest configs doesn't expose a fully-featured Storage.
// Install a minimal in-memory polyfill for the tests so the component's
// localStorage reads/writes work deterministically.
function installLocalStorageStub() {
  const store: Record<string, string> = {};
  const storage: Storage = {
    get length() {
      return Object.keys(store).length;
    },
    clear: () => {
      for (const k of Object.keys(store)) delete store[k];
    },
    getItem: (k: string) => (k in store ? store[k] : null),
    key: (i: number) => Object.keys(store)[i] ?? null,
    removeItem: (k: string) => {
      delete store[k];
    },
    setItem: (k: string, v: string) => {
      store[k] = String(v);
    },
  };
  Object.defineProperty(window, 'localStorage', {
    value: storage,
    configurable: true,
    writable: true,
  });
}

describe('ChangelogBell', () => {
  beforeEach(() => {
    installLocalStorageStub();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders the bell button and fetches the changelog', async () => {
    const fetchMock = mockChangelogFetch();
    render(<ChangelogBell />);
    expect(screen.getByRole('button', { name: /what'?s new/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/changelog.json', { cache: 'no-store' });
    });
  });

  it('shows the unread dot when seen-date is unset and there are entries', async () => {
    mockChangelogFetch();
    render(<ChangelogBell />);
    expect(await screen.findByTestId('changelog-bell-unread-dot')).toBeInTheDocument();
  });

  it('opens the panel on click, lists entries, and clears the unread dot', async () => {
    mockChangelogFetch();
    render(<ChangelogBell />);

    // Wait for entries to load (unread dot appears).
    expect(await screen.findByTestId('changelog-bell-unread-dot')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /what'?s new/i }));

    // Panel renders with the entry titles.
    expect(screen.getByText('Estimate Review')).toBeInTheDocument();
    expect(screen.getByText('Country expansion')).toBeInTheDocument();

    // Most-recent date persisted, unread dot cleared.
    expect(window.localStorage.getItem('relopass_changelog_seen')).toBe('2026-05-27');
    expect(screen.queryByTestId('changelog-bell-unread-dot')).not.toBeInTheDocument();
  });

  it('closes the panel when Escape is pressed', async () => {
    mockChangelogFetch();
    render(<ChangelogBell />);

    expect(await screen.findByTestId('changelog-bell-unread-dot')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /what'?s new/i }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('renders the empty-state copy when changelog returns []', async () => {
    mockChangelogFetch([]);
    render(<ChangelogBell />);

    fireEvent.click(screen.getByRole('button', { name: /what'?s new/i }));
    expect(await screen.findByText(/no updates yet/i)).toBeInTheDocument();
  });
});
