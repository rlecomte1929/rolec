import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('./AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('../../lib/logger', () => ({
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn() },
}));

const listAssignments = vi.fn();
const listCompanies = vi.fn();
const listHrUsers = vi.fn();
const listEmployees = vi.fn();
const getAssignmentDetail = vi.fn();

vi.mock('../../api/client', () => ({
  adminAPI: {
    listAssignments: (...a: unknown[]) => listAssignments(...a),
    listCompanies: (...a: unknown[]) => listCompanies(...a),
    listHrUsers: (...a: unknown[]) => listHrUsers(...a),
    listEmployees: (...a: unknown[]) => listEmployees(...a),
    getAssignmentDetail: (...a: unknown[]) => getAssignmentDetail(...a),
  },
}));

import { AdminAssignments } from './AdminAssignments';

function renderPage(path = '/admin/assignments?company_id=co-1') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AdminAssignments />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  listAssignments.mockReset();
  listCompanies.mockReset();
  listHrUsers.mockReset();
  listEmployees.mockReset();
  getAssignmentDetail.mockReset();
  listCompanies.mockResolvedValue({ companies: [{ id: 'co-1', name: 'Acme' }] });
  listAssignments.mockResolvedValue({ assignments: [] });
  listHrUsers.mockResolvedValue({ hr_users: [] });
  listEmployees.mockResolvedValue({ employees: [] });
});
afterEach(cleanup);

describe('AdminAssignments · failed loads are not empty collections', () => {
  it('surfaces an assignments error and suppresses the empty state', async () => {
    listAssignments.mockRejectedValue(new Error('Could not load assignments.'));
    renderPage();
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Could not load assignments.'));
    expect(screen.queryByText(/No assignments for selected company/i)).not.toBeInTheDocument();
  });

  it('still shows the empty state when the list genuinely returns nothing', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText(/No assignments for selected company/i)).toBeInTheDocument());
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('surfaces an error when add-modal people lookups fail instead of pretending there are no HR users', async () => {
    listHrUsers.mockRejectedValue(new Error('Could not load HR users.'));
    listEmployees.mockResolvedValue({ employees: [] });
    renderPage();
    await waitFor(() => expect(screen.getByText(/Add assignment/i)).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /Add assignment/i }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Could not load HR users.'));
    expect(screen.queryByText(/No HR users for this company/i)).not.toBeInTheDocument();
  });
});
