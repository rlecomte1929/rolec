import { describe, it, expect, afterEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, within } from '@testing-library/react';

expect.extend(matchers);

vi.mock('./AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { AdminPermissionsPage } from './AdminPermissionsPage';

afterEach(cleanup);

describe('AdminPermissionsPage', () => {
  it('renders the matrix and filters by path', () => {
    render(<AdminPermissionsPage />);
    const rows = () => within(screen.getByTestId('permissions-rows')).queryAllByRole('row');
    const all = rows().length;
    expect(all).toBeGreaterThan(10);
    fireEvent.change(screen.getByLabelText('Filter routes'), { target: { value: '/admin/permissions' } });
    expect(rows().length).toBeLessThan(all);
    expect(screen.getByText('adminPermissions')).toBeInTheDocument();
  });
});
