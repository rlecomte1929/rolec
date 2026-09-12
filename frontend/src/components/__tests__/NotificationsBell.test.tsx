import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { NotificationsBell } from '../NotificationsBell';

// Mock the in-app notifications API (no network, no supabase). vi.mock is hoisted
// above the imports above by vitest, so these run before NotificationsBell loads.
// [AIQ-1618] The badge is now derived from the fetched list (single source of truth),
// so getUnreadCount is no longer consulted — it's not mocked here.
const listNotifications = vi.fn();
const markNotificationRead = vi.fn();
vi.mock('../../api/notifications', () => ({
  listNotifications: (...a: unknown[]) => listNotifications(...a),
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
    markNotificationRead.mockReset().mockResolvedValue(undefined);
  });

  it('shows the unread badge derived from the unread items in the list', async () => {
    // [AIQ-1618] 3 unread items in the list → badge 3.
    listNotifications.mockResolvedValue([item({ id: 'a' }), item({ id: 'b' }), item({ id: 'c' })]);
    renderBell();
    await waitFor(() => expect(screen.getByTestId('notifications-bell-badge')).toHaveTextContent('3'));
    expect(screen.getByRole('button', { name: 'Notifications, 3 unread' })).toBeInTheDocument();
    expect(screen.getByText('Notifications, 3 unread').closest('[aria-live="polite"]')).toBeTruthy();
  });

  it('caps the badge at 9+', async () => {
    listNotifications.mockResolvedValue(
      Array.from({ length: 12 }, (_v, i) => item({ id: `n${i}` }))
    );
    renderBell();
    await waitFor(() => expect(screen.getByTestId('notifications-bell-badge')).toHaveTextContent('9+'));
  });

  it('shows NO badge when every listed notification is already read (no false dot)', async () => {
    // [AIQ-1618] The exact reported bug: a red dot over a panel that has nothing unread.
    // Read items (read_at set) must not raise the badge.
    listNotifications.mockResolvedValue([
      item({ id: 'a', read_at: new Date().toISOString() }),
      item({ id: 'b', read_at: new Date().toISOString() }),
    ]);
    renderBell();
    await waitFor(() => expect(listNotifications).toHaveBeenCalled());
    expect(screen.queryByTestId('notifications-bell-badge')).not.toBeInTheDocument();
  });

  it('opens the dropdown and lists notifications', async () => {
    listNotifications.mockResolvedValue([item()]);
    renderBell();
    await waitFor(() => expect(screen.getByTestId('notifications-bell-badge')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /notifications/i }));
    expect(await screen.findByText('Your relocation case is ready')).toBeInTheDocument();
  });

  it('marks an item read on click', async () => {
    listNotifications.mockResolvedValue([item()]);
    renderBell();
    await waitFor(() => expect(screen.getByTestId('notifications-bell-badge')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /notifications/i }));
    fireEvent.click(await screen.findByText('Your relocation case is ready'));
    await waitFor(() => expect(markNotificationRead).toHaveBeenCalledWith('n1'));
  });

  it('renders the empty state with no badge when there are no notifications', async () => {
    listNotifications.mockResolvedValue([]);
    renderBell();
    await waitFor(() => expect(listNotifications).toHaveBeenCalled());
    expect(screen.queryByTestId('notifications-bell-badge')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /notifications/i }));
    expect(await screen.findByText(/no notifications yet/i)).toBeInTheDocument();
    expect(
      screen.getByText(/when a case is assigned, HR leaves feedback, or intake is submitted/i)
    ).toBeInTheDocument();
  });
});

