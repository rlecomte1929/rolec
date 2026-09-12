import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminLayout } from './AdminLayout';

vi.mock('../../components/PlatformShellSidebar', () => ({
  PlatformShellSidebar: () => <nav aria-label="sidebar" />,
}));
vi.mock('../../components/FeedbackWidget', () => ({ FeedbackWidget: () => null }));
vi.mock('../../features/admin/AdminViewingCompanyContext', () => ({
  useAdminViewingCompany: () => ({
    companies: [],
    selectedCompany: null,
    setSelectedCompanyId: () => undefined,
    loading: false,
    error: null,
  }),
}));

const storage = new Map<string, string>();
vi.stubGlobal('localStorage', {
  getItem: (key: string) => storage.get(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => storage.delete(key),
  clear: () => storage.clear(),
});

function renderLayout() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <AdminLayout title="Companies">hello</AdminLayout>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('AdminLayout show-test-data toggle', () => {
  beforeEach(() => {
    storage.clear();
  });
  afterEach(cleanup);

  it('renders the switch off by default and persists on toggle', async () => {
    const user = userEvent.setup();
    renderLayout();
    const toggle = screen.getByRole('switch', { name: 'Show test data' });
    expect(toggle).toHaveAttribute('aria-checked', 'false');
    expect(storage.get('admin_show_test_data')).toBeUndefined();
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-checked', 'true');
    expect(storage.get('admin_show_test_data')).toBe('true');
  });
});
