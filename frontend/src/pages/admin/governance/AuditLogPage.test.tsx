/**
 * Audit-log viewer — renders the timeline (action = event||action_type, actor =
 * actor_name||actor_id||system) and reloads on filter change. API + AdminLayout mocked.
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup, fireEvent, waitFor, within } from '@testing-library/react';

expect.extend(matchers);

vi.mock('../../../api/governance', () => ({ listAuditLogs: vi.fn() }));
vi.mock('../AdminLayout', () => ({
  AdminLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import { listAuditLogs } from '../../../api/governance';
import { AuditLogPage } from './AuditLogPage';

const mock = listAuditLogs as unknown as ReturnType<typeof vi.fn>;

afterEach(cleanup);
beforeEach(() => {
  mock.mockReset();
  mock.mockResolvedValue({
    items: [
      { id: '1', entity_type: 'admin_allowlist', entity_id: 'x', action_type: 'insert', event: 'admin_allowlist_grant', actor_name: 'Jane Admin', created_at: '2026-06-30T10:00:00Z' },
      { id: '2', entity_type: 'mobility_cases', entity_id: 'y', action_type: 'update', actor_id: null, created_at: '2026-06-30T09:00:00Z' },
    ],
    total: 2, limit: 50, offset: 0, table_ready: true,
  });
});

describe('AuditLogPage', () => {
  it('renders events with humanised action + actor fallback', async () => {
    render(<AuditLogPage />);
    await screen.findByText('admin allowlist grant');  // event, underscores→spaces
    const rows = within(screen.getByTestId('audit-rows'));
    expect(rows.getByText('Jane Admin')).toBeInTheDocument();
    expect(rows.getByText('system')).toBeInTheDocument();  // null actor → 'system'
    expect(rows.getByText('update')).toBeInTheDocument();   // no event → action_type (scoped to rows, not the filter <option>)
  });

  it('reloads when the action filter changes', async () => {
    render(<AuditLogPage />);
    await screen.findByText('admin allowlist grant');
    fireEvent.change(screen.getByLabelText('Action filter'), { target: { value: 'delete' } });
    await waitFor(() => expect(mock).toHaveBeenCalledWith(expect.objectContaining({ action_type: 'delete' })));
  });
});
