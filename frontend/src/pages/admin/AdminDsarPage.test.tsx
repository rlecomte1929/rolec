import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../../api/dsar', () => ({
  listErasureRequests: vi.fn(),
  exportUserData: vi.fn(),
  eraseUserData: vi.fn(),
}));
vi.mock('./AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { listErasureRequests, exportUserData, eraseUserData } from '../../api/dsar';
import { AdminDsarPage } from './AdminDsarPage';

const mockList = listErasureRequests as unknown as ReturnType<typeof vi.fn>;
const mockExport = exportUserData as unknown as ReturnType<typeof vi.fn>;
const mockErase = eraseUserData as unknown as ReturnType<typeof vi.fn>;

afterEach(cleanup);
beforeEach(() => {
  mockList.mockReset(); mockExport.mockReset(); mockErase.mockReset();
  mockList.mockResolvedValue({
    items: [{ id: 'er1', employee_id: 'user-9', status: 'pending', requested_at: '2026-06-01T00:00:00Z', statutory_due_at: '2026-07-01T00:00:00Z' }],
    total: 1, table_ready: true,
  });
});

describe('AdminDsarPage', () => {
  it('lists erasure requests and exports', async () => {
    mockExport.mockResolvedValue({ user_id: 'user-9' });
    render(<AdminDsarPage />);
    expect(await screen.findByText('user-9')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Export' }));
    await waitFor(() => expect(mockExport).toHaveBeenCalledWith('user-9'));
  });

  it('requires typing DELETE before erase fires', async () => {
    mockErase.mockResolvedValue({});
    render(<AdminDsarPage />);
    await screen.findByText('user-9');
    fireEvent.click(screen.getByRole('button', { name: 'Erase' }));
    expect(await screen.findByTestId('erase-modal')).toBeInTheDocument();

    // Confirm is disabled until the exact word is typed
    const confirmBtn = screen.getByRole('button', { name: /erase permanently/i });
    expect(confirmBtn).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Type DELETE to confirm'), { target: { value: 'DELETE' } });
    expect(confirmBtn).not.toBeDisabled();
    fireEvent.click(confirmBtn);
    await waitFor(() => expect(mockErase).toHaveBeenCalledWith('user-9'));
  });
});
