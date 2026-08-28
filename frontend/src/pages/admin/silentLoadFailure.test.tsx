/**
 * A failed READ must never render as an empty collection.
 *
 * These pages caught the load error, set the list to [], and rendered "No categories yet."
 * — indistinguishable from a genuinely empty taxonomy. The mutation paths in the same files
 * already surfaced their errors via alert(), so the read-path silence was an oversight.
 *
 * Each case asserts BOTH halves: the error is shown AND the reassuring empty state is gone.
 * Asserting only the first would still pass if both rendered together, which is the
 * confusing state we are actually trying to prevent.
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

expect.extend(matchers);

vi.mock('./AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const listCategories = vi.fn();
const listSources = vi.fn();
const listTags = vi.fn();

vi.mock('../../api/client', () => ({
  adminResourcesAPI: {
    listCategories: (...a: unknown[]) => listCategories(...a),
    listSources: (...a: unknown[]) => listSources(...a),
    listTags: (...a: unknown[]) => listTags(...a),
  },
}));

import { AdminCategories } from './AdminCategories';
import { AdminSources } from './AdminSources';
import { AdminTags } from './AdminTags';

// jsdom in this repo ships no localStorage — the pages read `relopass_role` through it.
function installLocalStorage(role: string) {
  const store = new Map<string, string>([['relopass_role', role]]);
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, String(v)),
      removeItem: (k: string) => void store.delete(k),
      clear: () => store.clear(),
      key: (i: number) => Array.from(store.keys())[i] ?? null,
      get length() {
        return store.size;
      },
    },
  });
}

const CASES = [
  { name: 'AdminCategories', Cmp: AdminCategories, mock: listCategories, empty: /No categories yet/i },
  { name: 'AdminSources', Cmp: AdminSources, mock: listSources, empty: /No sources yet/i },
  { name: 'AdminTags', Cmp: AdminTags, mock: listTags, empty: /No tags yet/i },
] as const;

beforeEach(() => {
  installLocalStorage('ADMIN');
  listCategories.mockReset();
  listSources.mockReset();
  listTags.mockReset();
});
afterEach(cleanup);

describe('admin taxonomy pages · a failed load is not an empty collection', () => {
  for (const { name, Cmp, mock, empty } of CASES) {
    it(`${name} surfaces the error and suppresses the empty state`, async () => {
      mock.mockRejectedValue({ response: { data: { detail: 'Upstream exploded' } } });
      render(
        <MemoryRouter>
          <Cmp />
        </MemoryRouter>,
      );
      await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
      expect(screen.getByRole('alert')).toHaveTextContent('Upstream exploded');
      expect(screen.queryByText(empty)).not.toBeInTheDocument();
    });

    it(`${name} still shows the empty state when the load genuinely returns nothing`, async () => {
      mock.mockResolvedValue({ categories: [], sources: [], tags: [] });
      render(
        <MemoryRouter>
          <Cmp />
        </MemoryRouter>,
      );
      await waitFor(() => expect(screen.getByText(empty)).toBeInTheDocument());
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  }
});
