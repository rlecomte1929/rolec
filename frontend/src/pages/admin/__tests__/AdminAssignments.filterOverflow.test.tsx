import '@testing-library/jest-dom/vitest';
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { adminAPI } from '../../../api/client';
import { AdminAssignments } from '../AdminAssignments';

vi.mock('../AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
}));

vi.mock('../../../api/client', () => ({
  adminAPI: {
    listCompanies: vi.fn(),
    listAssignments: vi.fn(),
    listHrUsers: vi.fn(),
    listEmployees: vi.fn(),
  },
}));

const mocked = <T,>(fn: T) => fn as T & ReturnType<typeof vi.fn>;

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AdminAssignments />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('AdminAssignments filter bar — BUG-260816-BEF6', () => {
  beforeEach(() => {
    mocked(adminAPI.listCompanies).mockResolvedValue({
      companies: [{ id: 'c1', name: 'Google Ireland T18-A-1786634420882' }],
    });
    mocked(adminAPI.listAssignments).mockResolvedValue({ assignments: [] });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('keeps Company and Employee search in shrinkable full-width grid tracks', async () => {
    renderPage();
    const companyLabel = await screen.findByText('Company');
    const employeeLabel = screen.getByText('Employee search');
    const grid = companyLabel.parentElement?.parentElement;
    expect(grid?.className).toContain('[&>*]:min-w-0');

    const companySelect = companyLabel.parentElement?.querySelector('select');
    const employeeInput = employeeLabel.parentElement?.querySelector('input');
    expect(companySelect).toHaveClass('min-w-0');
    expect(employeeInput).toHaveClass('min-w-0');
  });
});
