/**
 * Governance page — lists admins, grants (with the @relopass.com client guard),
 * and revokes (confirm-gated). API + AdminLayout mocked (admin shell + supabase
 * out of jsdom).
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../../../api/governance', () => ({
  listAllowlist: vi.fn(),
  grantAdmin: vi.fn(),
  revokeAdmin: vi.fn(),
}));
vi.mock('../AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { listAllowlist, grantAdmin, revokeAdmin } from '../../../api/governance';
import { GovernancePage } from './GovernancePage';

const mockList = listAllowlist as unknown as ReturnType<typeof vi.fn>;
const mockGrant = grantAdmin as unknown as ReturnType<typeof vi.fn>;
const mockRevoke = revokeAdmin as unknown as ReturnType<typeof vi.fn>;

const renderPage = () => render(<MemoryRouter><GovernancePage /></MemoryRouter>);

afterEach(cleanup);
beforeEach(() => {
  mockList.mockReset(); mockGrant.mockReset(); mockRevoke.mockReset();
  mockList.mockResolvedValue({ items: [{ email: 'admin@relopass.com', enabled: 1, created_at: '2026-01-01T00:00:00Z' }] });
});

describe('GovernancePage', () => {
  it('lists current admins', async () => {
    renderPage();
    expect(await screen.findByText('admin@relopass.com')).toBeInTheDocument();
  });

  it('grants a valid @relopass.com admin', async () => {
    mockGrant.mockResolvedValue({ ok: true, email: 'new@relopass.com' });
    renderPage();
    await screen.findByText('admin@relopass.com');
    fireEvent.change(screen.getByLabelText('Admin email'), { target: { value: 'new@relopass.com' } });
    fireEvent.click(screen.getByRole('button', { name: /grant admin/i }));
    await waitFor(() => expect(mockGrant).toHaveBeenCalledWith('new@relopass.com'));
  });

  it('blocks a non-relopass email client-side', async () => {
    renderPage();
    await screen.findByText('admin@relopass.com');
    fireEvent.change(screen.getByLabelText('Admin email'), { target: { value: 'attacker@gmail.com' } });
    fireEvent.click(screen.getByRole('button', { name: /grant admin/i }));
    await screen.findByText(/must end with @relopass.com/i);
    expect(mockGrant).not.toHaveBeenCalled();
  });

  it('revokes after confirm', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    mockRevoke.mockResolvedValue({ ok: true, email: 'admin@relopass.com' });
    renderPage();
    await screen.findByText('admin@relopass.com');
    fireEvent.click(screen.getByRole('button', { name: 'Revoke' }));
    await waitFor(() => expect(mockRevoke).toHaveBeenCalledWith('admin@relopass.com'));
    confirmSpy.mockRestore();
  });
});
