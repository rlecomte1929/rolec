/**
 * AIQ-1357 — header role switcher.
 *
 * Hidden for single-role users; for a dual-role user, switching calls
 * POST /api/auth/switch-role and navigates to the new role's home.
 */
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

const getStoredRoles = vi.fn<() => string[]>();
const getActiveRole = vi.fn<() => string>();
const setStoredRoles = vi.fn();
const setActiveRole = vi.fn();
const switchRole = vi.fn();
const navigate = vi.fn();

vi.mock('../../utils/demo', () => ({
  getStoredRoles: (): string[] => getStoredRoles(),
  getActiveRole: (): string => getActiveRole(),
  setStoredRoles: (r: string[]) => setStoredRoles(r),
  setActiveRole: (r: string) => setActiveRole(r),
  normalizeStoredRole: (r: string | null | undefined): string => (r ?? '').trim().toUpperCase(),
}));
vi.mock('../../api/client', () => ({ authAPI: { switchRole: (r: string) => switchRole(r) } }));
vi.mock('react-router-dom', () => ({ useNavigate: () => navigate }));

import { RoleSwitcher } from '../RoleSwitcher';

describe('RoleSwitcher', () => {
  beforeEach(() => {
    getStoredRoles.mockReset();
    getActiveRole.mockReset();
    setStoredRoles.mockReset();
    setActiveRole.mockReset();
    switchRole.mockReset();
    navigate.mockReset();
  });

  it('renders nothing for a single-role user', () => {
    getStoredRoles.mockReturnValue(['HR']);
    getActiveRole.mockReturnValue('HR');
    const { container } = render(<RoleSwitcher />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows a switcher for a dual-role user and switches + navigates', async () => {
    getStoredRoles.mockReturnValue(['HR', 'EMPLOYEE']);
    getActiveRole.mockReturnValue('HR');
    switchRole.mockResolvedValue({ roles: ['HR', 'EMPLOYEE'], primary_role: 'HR' });

    render(<RoleSwitcher />);
    const select = screen.getByRole('combobox') as HTMLSelectElement;
    expect(select).toBeInTheDocument();

    fireEvent.change(select, { target: { value: 'EMPLOYEE' } });

    await waitFor(() => expect(switchRole).toHaveBeenCalledWith('EMPLOYEE'));
    await waitFor(() => expect(setActiveRole).toHaveBeenCalledWith('EMPLOYEE'));
    expect(navigate).toHaveBeenCalledWith('/employee/dashboard');
  });

  it('keeps the selected role when the API primary_role disagrees', async () => {
    getStoredRoles.mockReturnValue(['HR', 'EMPLOYEE']);
    getActiveRole.mockReturnValue('EMPLOYEE');
    switchRole.mockResolvedValue({ roles: ['HR', 'EMPLOYEE'], primary_role: 'EMPLOYEE' });

    render(<RoleSwitcher />);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'HR' } });

    await waitFor(() => expect(setActiveRole).toHaveBeenCalledWith('HR'));
    expect(navigate).toHaveBeenCalledWith('/hr/dashboard');
  });

  it('shows an error when the switch request fails', async () => {
    getStoredRoles.mockReturnValue(['HR', 'EMPLOYEE']);
    getActiveRole.mockReturnValue('EMPLOYEE');
    switchRole.mockRejectedValue(new Error('nope'));

    render(<RoleSwitcher />);
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'HR' } });

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not switch role');
    expect(setActiveRole).not.toHaveBeenCalled();
  });
});
