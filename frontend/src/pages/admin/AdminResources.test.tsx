import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('./AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('../../components/location', () => ({
  CountryPicker: () => <div />,
}));

vi.mock('../../components/admin/resources/ResourceRowActions', () => ({
  ResourceRowActions: () => null,
}));

const getCounts = vi.fn();
const listCategories = vi.fn();
const listResources = vi.fn();
const getDashboard = vi.fn();

vi.mock('../../api/client', () => ({
  adminResourcesAPI: {
    getCounts: (...a: unknown[]) => getCounts(...a),
    listCategories: (...a: unknown[]) => listCategories(...a),
    listResources: (...a: unknown[]) => listResources(...a),
  },
  adminStagingAPI: {
    getDashboard: (...a: unknown[]) => getDashboard(...a),
  },
}));

import { AdminResources } from './AdminResources';

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

function renderOverview() {
  return render(
    <MemoryRouter>
      <AdminResources />
    </MemoryRouter>,
  );
}

function renderList() {
  return render(
    <MemoryRouter initialEntries={['/admin/resources?view=list']}>
      <AdminResources />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  installLocalStorage('ADMIN');
  getCounts.mockReset();
  listCategories.mockReset();
  listResources.mockReset();
  getDashboard.mockReset();
  getCounts.mockResolvedValue({ resources_published: 0, events_published: 0, resources_draft: 0, resources_in_review: 0, resources_archived: 0 });
  listCategories.mockResolvedValue({ categories: [] });
  getDashboard.mockResolvedValue({ resource_candidates_new: 0, event_candidates_new: 0 });
  listResources.mockResolvedValue({ items: [], total: 0 });
});
afterEach(cleanup);

describe('AdminResources · failed loads are not empty collections', () => {
  it('surfaces a counts error instead of looking like a successful zero dashboard', async () => {
    getCounts.mockRejectedValue({ response: { data: { detail: 'Counts exploded' } } });
    renderOverview();
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Counts exploded'));
  });

  it('surfaces a staging error when the dashboard request fails', async () => {
    getDashboard.mockRejectedValue(new Error('Could not load staging counts.'));
    renderOverview();
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/staging/i));
  });

  it('surfaces a categories error when the taxonomy request fails', async () => {
    listCategories.mockRejectedValue(new Error("Couldn't load categories."));
    renderOverview();
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/categories/i));
  });

  it('does not show an error when overview loads with genuine zeros', async () => {
    renderOverview();
    await waitFor(() => expect(screen.getByText(/Manage content/i)).toBeInTheDocument());
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('surfaces a list error and suppresses the empty state', async () => {
    listResources.mockRejectedValue({ response: { data: { detail: 'Upstream exploded' } } });
    renderList();
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Upstream exploded'));
    expect(screen.queryByText(/No resources found/i)).not.toBeInTheDocument();
  });

  it('still shows the empty state when the list genuinely returns nothing', async () => {
    renderList();
    await waitFor(() => expect(screen.getByText(/No resources found/i)).toBeInTheDocument());
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
