import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../utils/demo', () => ({ getAuthItem: () => 'u-1' }));
vi.mock('../../utils/welcomeSeen', () => ({ markWelcomeSeen: vi.fn() }));
vi.mock('../../api/welcome', () => ({ persistWelcomeSeen: vi.fn(() => Promise.resolve()) }));
vi.mock('../../components/WelcomeShell', () => ({
  WelcomeShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { EmployeeWelcomePage } from './EmployeeWelcomePage';

afterEach(cleanup);

describe('EmployeeWelcomePage CTAs', () => {
  it('has a single Get started link plus the primary intake button', () => {
    render(
      <MemoryRouter>
        <EmployeeWelcomePage />
      </MemoryRouter>,
    );
    expect(screen.getAllByText('Get started →')).toHaveLength(1);
    expect(screen.getByRole('button', { name: /begin the intake form/i })).toBeInTheDocument();
  });
});
