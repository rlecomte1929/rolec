import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../../api/policyVersions', () => ({
  listCompaniesForVersions: vi.fn(),
  listPolicyVersions: vi.fn(),
  getActivePolicyVersion: vi.fn(),
  rollbackToVersion: vi.fn(),
}));
vi.mock('./AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { listCompaniesForVersions, listPolicyVersions, rollbackToVersion } from '../../api/policyVersions';
import { AdminPolicyVersionsPage } from './AdminPolicyVersionsPage';

const mockCompanies = listCompaniesForVersions as unknown as ReturnType<typeof vi.fn>;
const mockVersions = listPolicyVersions as unknown as ReturnType<typeof vi.fn>;
const mockRollback = rollbackToVersion as unknown as ReturnType<typeof vi.fn>;

afterEach(cleanup);
beforeEach(() => {
  mockCompanies.mockReset(); mockVersions.mockReset(); mockRollback.mockReset();
  mockCompanies.mockResolvedValue([{ id: 'co-1', name: 'Acme' }]);
  mockVersions.mockResolvedValue([
    { id: 'v2', policy_id: 'p', version_number: 2, status: 'published', effective_date: '2026-06-01' },
    { id: 'v1', policy_id: 'p', version_number: 1, status: 'archived', effective_date: '2026-01-01' },
  ]);
});

describe('AdminPolicyVersionsPage', () => {
  it('lists versions after selecting a company', async () => {
    render(<AdminPolicyVersionsPage />);
    await screen.findByText('Acme');
    fireEvent.change(screen.getByLabelText('Company'), { target: { value: 'co-1' } });
    await waitFor(() => expect(mockVersions).toHaveBeenCalledWith('co-1'));
    expect(await screen.findByText('v2')).toBeInTheDocument();
    expect(screen.getByText('published')).toBeInTheDocument();
  });

  it('rolls back to an older (non-published) version after confirm', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    mockRollback.mockResolvedValue({});
    render(<AdminPolicyVersionsPage />);
    await screen.findByText('Acme');
    fireEvent.change(screen.getByLabelText('Company'), { target: { value: 'co-1' } });
    await screen.findByText('v1');
    fireEvent.click(screen.getByRole('button', { name: /roll back to this/i }));  // only the archived v1 has it
    await waitFor(() => expect(mockRollback).toHaveBeenCalledWith('v1'));
    confirmSpy.mockRestore();
  });
});
