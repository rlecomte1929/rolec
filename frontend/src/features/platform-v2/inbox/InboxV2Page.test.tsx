import type { ReactNode } from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { InboxV2Page } from './InboxV2Page';

const getAuthItem = vi.fn<(k: string) => string | null>();
vi.mock('../../../utils/demo', () => ({
  getAuthItem: (k: string) => getAuthItem(k),
}));

const listMessageConversations = vi.fn();
const listMessages = vi.fn();
const getAssignmentsOverview = vi.fn();
vi.mock('../../../api/client', () => ({
  hrAPI: {
    listMessageConversations: (...a: unknown[]) => listMessageConversations(...a),
    getMessageThread: vi.fn(),
    sendMessage: vi.fn(),
    archiveMessageConversations: vi.fn(),
  },
  employeeAPI: {
    listMessages: (...a: unknown[]) => listMessages(...a),
    getAssignmentsOverview: (...a: unknown[]) => getAssignmentsOverview(...a),
    sendMessage: vi.fn(),
  },
}));

vi.mock('../../../api/messageNotifications', () => ({
  markConversationRead: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('../../../components/AppShell', () => ({
  AppShell: ({
    children,
    section,
    navRole,
  }: {
    children: ReactNode;
    section?: string;
    navRole?: string;
  }) => (
    <div data-testid="appshell" data-section={section} data-nav={navRole}>
      {children}
    </div>
  ),
}));

function renderInbox(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/hr/messages" element={<InboxV2Page />} />
        <Route path="/messages" element={<InboxV2Page />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('InboxV2Page (AIQ-2362)', () => {
  afterEach(cleanup);
  beforeEach(() => {
    vi.clearAllMocks();
    getAuthItem.mockImplementation((k) => {
      if (k === 'relopass_role') return 'EMPLOYEE';
      if (k === 'relopass_id') return 'u1';
      if (k === 'relopass_name') return 'Hannah';
      return null;
    });
    listMessageConversations.mockResolvedValue({
      conversations: [
        {
          assignment_id: 'aid-hr',
          employee_name: 'Ada',
          last_message_preview: 'Welcome',
          host_country: 'NL',
        },
      ],
    });
    listMessages.mockResolvedValue({ messages: [], quote_threads: [] });
    getAssignmentsOverview.mockResolvedValue({ linked: [], pending: [] });
  });

  it('loads HR threads on /hr/messages even when stored role is EMPLOYEE', async () => {
    renderInbox('/hr/messages');
    await waitFor(() => expect(listMessageConversations).toHaveBeenCalled());
    expect(listMessages).not.toHaveBeenCalled();
    expect(screen.getByTestId('appshell')).toHaveAttribute('data-section', 'HR Operations');
    expect(screen.getByTestId('appshell')).toHaveAttribute('data-nav', 'HR');
    expect((await screen.findAllByText('Ada')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Netherlands').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: /sent to employees/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /from hr/i })).not.toBeInTheDocument();
  });

  it('loads the employee inbox on /messages', async () => {
    renderInbox('/messages');
    await waitFor(() => expect(listMessages).toHaveBeenCalled());
    expect(listMessageConversations).not.toHaveBeenCalled();
    expect(screen.getByTestId('appshell')).toHaveAttribute('data-section', 'Employee');
    expect(await screen.findByRole('button', { name: /from hr/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^new$/i })).not.toBeInTheDocument();
  });

  it('shows a contextual empty state for an empty Vendors mailbox', async () => {
    renderInbox('/hr/messages');
    await waitFor(() => expect(listMessageConversations).toHaveBeenCalled());
    screen.getByRole('button', { name: /vendors/i }).click();
    expect(
      (await screen.findAllByText(/vendor threads appear here when a supplier is on a case/i)).length
    ).toBeGreaterThan(0);
  });
});
