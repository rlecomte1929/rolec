import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mocks = vi.hoisted(() => ({
  deleteEmployee: vi.fn(),
  updateEmployee: vi.fn(),
  getEmployee: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  hrAPI: {
    getEmployee: (...args: unknown[]) => mocks.getEmployee(...args),
    updateEmployee: (...args: unknown[]) => mocks.updateEmployee(...args),
    deleteEmployee: (...args: unknown[]) => mocks.deleteEmployee(...args),
  },
}));
vi.mock('../../api/supabase', () => ({ supabase: {} }));
vi.mock('../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock('../../navigation/registry', () => ({ useRegisterNav: () => {} }));
vi.mock('../../navigation/safeNavigate', () => ({ safeNavigate: vi.fn() }));

import { HrEmployeeDetail } from '../HrEmployeeDetail';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/hr/employees/emp-1']}>
        <Routes>
          <Route path="/hr/employees/:id" element={<HrEmployeeDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('HrEmployeeDetail remove', () => {
  it('lets HR confirm remove from the profile page', async () => {
    mocks.getEmployee.mockResolvedValue({
      employee: {
        id: 'emp-1',
        company_id: 'co-1',
        profile_id: 'prof-1',
        created_at: '2026-01-01',
        full_name: 'Ada Lovelace',
        email: 'ada@example.com',
        band: 'manager',
        assignment_type: 'Long-Term',
        status: 'active',
      },
    });
    mocks.deleteEmployee.mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderPage();
    expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Remove from company' }));
    await user.click(screen.getByRole('button', { name: 'Confirm remove' }));
    expect(mocks.deleteEmployee).toHaveBeenCalledWith('emp-1');
  });
});
