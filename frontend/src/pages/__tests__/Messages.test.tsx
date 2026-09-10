import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const listMessageConversations = vi.fn();
const listMessages = vi.fn();
const getAssignmentsOverview = vi.fn();

vi.mock('../../api/client', () => ({
  hrAPI: {
    listMessageConversations: (...args: unknown[]) => listMessageConversations(...args),
    getMessageThread: vi.fn(),
    archiveMessageConversations: vi.fn(),
    deleteHrMessage: vi.fn(),
  },
  employeeAPI: {
    listMessages: (...args: unknown[]) => listMessages(...args),
    getAssignmentsOverview: (...args: unknown[]) => getAssignmentsOverview(...args),
  },
}));

vi.mock('../../api/messageNotifications', () => ({
  markConversationRead: vi.fn().mockResolvedValue(undefined),
}));

let role = 'HR';
vi.mock('../../utils/demo', () => ({
  getAuthItem: (k: string) => {
    if (k === 'relopass_role') return role;
    if (k === 'relopass_id') return 'user-1';
    if (k === 'relopass_name') return 'Test User';
    if (k === 'relopass_email') return 'test@example.com';
    return null;
  },
}));

import { Messages } from '../Messages';

function renderMessages() {
  return render(
    <MemoryRouter>
      <Messages />
    </MemoryRouter>
  );
}

describe('Messages', () => {
  beforeEach(() => {
    role = 'HR';
    listMessageConversations.mockReset();
    listMessages.mockReset();
    getAssignmentsOverview.mockReset();
    getAssignmentsOverview.mockResolvedValue({ linked: [] });
  });

  it('shows the error banner and no conversation rows when the conversations request rejects', async () => {
    expect(import.meta.env.DEV).toBe(true);
    listMessageConversations.mockRejectedValue(new Error('network'));

    renderMessages();

    expect((await screen.findAllByText('Could not load conversations.')).length).toBeGreaterThan(0);
    expect(screen.queryAllByRole('button', { name: /Conversation with/i })).toHaveLength(0);
    expect(screen.queryByText('Sarah Jenkins')).not.toBeInTheDocument();
  });

  it('renders the empty inbox in DEV when the API returns no conversations', async () => {
    expect(import.meta.env.DEV).toBe(true);
    role = 'EMPLOYEE';
    listMessages.mockResolvedValue({ messages: [], quote_threads: [] });

    renderMessages();

    await waitFor(() => {
      expect(screen.getAllByText(/No HR messages yet/i).length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText(/No provider conversations yet/i).length).toBeGreaterThan(0);
    expect(screen.queryAllByRole('button', { name: /Conversation with/i })).toHaveLength(0);
    expect(screen.queryByText('Sarah Jenkins')).not.toBeInTheDocument();
  });
});
