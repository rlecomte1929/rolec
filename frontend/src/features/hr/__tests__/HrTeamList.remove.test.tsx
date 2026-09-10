import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import type { HrCompanyEmployee } from '../../../types';

const mocks = vi.hoisted(() => ({
  deleteEmployee: vi.fn(),
  updateEmployee: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  hrAPI: {
    deleteEmployee: (...args: unknown[]) => mocks.deleteEmployee(...args),
    updateEmployee: (...args: unknown[]) => mocks.updateEmployee(...args),
  },
}));
vi.mock('../../../api/supabase', () => ({ supabase: {} }));
vi.mock('../../../navigation/registry', () => ({ useRegisterNav: () => {} }));

import { HrTeamList } from '../HrTeamList';

const EMP: HrCompanyEmployee = {
  id: 'emp-1',
  company_id: 'co-1',
  profile_id: 'prof-1',
  created_at: '2026-01-01',
  full_name: 'Ada Lovelace',
  email: 'ada@example.com',
  status: 'active',
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('HrTeamList remove', () => {
  it('shows the API detail when remove fails', async () => {
    mocks.deleteEmployee.mockRejectedValue({
      response: {
        data: {
          detail:
            'This person is still linked to other records. Remove their relocation case first, then try again.',
        },
      },
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <HrTeamList employees={[EMP]} onReload={vi.fn()} />
      </MemoryRouter>,
    );
    await user.click(screen.getByTitle('Remove employee'));
    await user.click(screen.getByRole('button', { name: 'Remove' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('still linked');
  });
});
