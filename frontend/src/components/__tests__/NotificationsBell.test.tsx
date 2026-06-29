import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { NotificationsBell } from '../NotificationsBell';

// Mock the in-app notifications API (no network, no supabase). vi.mock is hoisted
// above the imports above by vitest, so these run before NotificationsBell loads.
const listNotifications = vi.fn();
const getUnreadCount = vi.fn();
const markNotificationRead = vi.fn();
vi.mock('../../api/notifications', () => ({
  listNotifications: (...a: unknown[]) => listNotifications(...a),
  getUnreadCount: (...a: unknown[]) => getUnreadCount(...a),
  markNotificationRead: (...a: unknown[]) => markNotificationRead(...a),
}));
// Realtime subscriber is lazy-imported inside an effect; stub it so no supabase loads.
vi.mock('../../api/notificationsRealtime', () => ({
  subscribeToNotificationsRealtime: () => () => undefined,
}));
vi.mock('../../api/supabase', () => ({
  supabase: { auth: { getUser: () => Promise.resolve({ data: { user: null } }) } },
}));
vi.mock('../../utils/demo', () => ({
  getAuthItem: () => 'EMPLOYEE',
  normalizeStoredRole: (r: string) => (r || '').toUpperCase(),
}));

const item = (over: Record<string, unknown> = {}) => ({
  id: 'n1', created_at: new Date().toISOString(), assignment_id: 'case-1', case_id: 'case-1',
  type: 'ASSIGNMENT_CREATED', title: 'Your relocation case is ready', body: 'Start your intake.',
  metadata: {}, read_at: null, ...over,
});

function renderBell() {
  return render(<MemoryRouter><NotificationsBell /></MemoryRouter>);
}

describe('NotificationsBell', () => {
  beforeEach(() => {
    listNotifications.mockReset();
    getUnreadCount.mockReset();
    markNotificationRead.mockReset().mockResolvedValue(undefined);
  });

  it('shows the unread badge from getUnreadCount', async () => {
    listNotifications.mockResolvedValue([item()]);
    getUnreadCount.mockResolvedValue(3);
    renderBell();
    await waitFor(() => expect(screen.getByTestId('notifications-bell-badge')).toHaveTextContent('3'));
  });

  it('caps the badge at 9+', async () => {
    listNotifications.mockResolvedValue([item()]);
    getUnreadCount.mockResolvedValue(42);
    renderBell();
    await waitFor(() => expect(screen.getByTestId('notifications-bell-badge')).toHaveTextContent('9+'));
  });

  it('opens the dropdown and lists notifications', async () => {
    listNotifications.mockResolvedValue([item()]);
    getUnreadCount.mockResolvedValue(1);
    renderBell();
    await waitFor(() => expect(screen.getByTestId('notifications-bell-badge')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /notifications/i }));
    expect(await screen.findByText('Your relocation case is ready')).toBeInTheDocument();
  });

  it('marks an item read on click', async () => {
    listNotifications.mockResolvedValue([item()]);
    getUnreadCount.mockResolvedValue(1);
    renderBell();
    await waitFor(() => expect(screen.getByTestId('notifications-bell-badge')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /notifications/i }));
    fireEvent.click(await screen.findByText('Your relocation case is ready'));
    await waitFor(() => expect(markNotificationRead).toHaveBeenCalledWith('n1'));
  });

  it('renders the empty state with no badge when there are no notifications', async () => {
    listNotifications.mockResolvedValue([]);
    getUnreadCount.mockResolvedValue(0);
    renderBell();
    await waitFor(() => expect(listNotifications).toHaveBeenCalled());
    expect(screen.queryByTestId('notifications-bell-badge')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /notifications/i }));
    expect(await screen.findByText(/no notifications yet/i)).toBeInTheDocument();
  });
});
