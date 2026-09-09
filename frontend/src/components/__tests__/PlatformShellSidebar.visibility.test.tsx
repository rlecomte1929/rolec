import { act, render, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PlatformShellSidebar } from '../PlatformShellSidebar';
import { getHrNotificationCounts } from '../../api/hrCatalog';
import { getAdminNotificationCounts } from '../../api/adminCatalog';
import { getUnreadMessageCount } from '../../api/messageNotifications';

vi.mock('../../api/hrCatalog', () => ({
  getHrNotificationCounts: vi.fn(),
}));
vi.mock('../../api/adminCatalog', () => ({
  getAdminNotificationCounts: vi.fn(),
}));
vi.mock('../../api/messageNotifications', () => ({
  getUnreadMessageCount: vi.fn(),
}));
vi.mock('../../api/client', () => ({
  authAPI: { logout: vi.fn() },
}));

const HR_COUNTS = {
  employees_waiting: 2,
  destinations_with_demand: 1,
  pending_admin_tickets: 0,
};
const ADMIN_COUNTS = {
  pending_tickets: 3,
  allowlisted_destinations: 4,
  pending_capabilities: 1,
};

function renderSidebar(role: 'EMPLOYEE' | 'HR' | 'ADMIN') {
  return render(
    <MemoryRouter>
      <PlatformShellSidebar role={role} />
    </MemoryRouter>,
  );
}

function setVisibility(state: DocumentVisibilityState) {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    get: () => state,
  });
  document.dispatchEvent(new Event('visibilitychange'));
}

describe('PlatformShellSidebar notification poll pause', () => {
  beforeEach(() => {
    vi.mocked(getHrNotificationCounts).mockReset().mockResolvedValue(HR_COUNTS);
    vi.mocked(getAdminNotificationCounts).mockReset().mockResolvedValue(ADMIN_COUNTS);
    vi.mocked(getUnreadMessageCount).mockReset().mockResolvedValue(0);
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: (query: string) => ({
        matches: false,
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }),
    });
    setVisibility('visible');
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    setVisibility('visible');
  });

  it('polls HR counts on an interval while visible and skips ticks while hidden', async () => {
    renderSidebar('HR');
    await waitFor(() => expect(getHrNotificationCounts).toHaveBeenCalledTimes(1));
    expect(getAdminNotificationCounts).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    await waitFor(() => expect(getHrNotificationCounts).toHaveBeenCalledTimes(2));

    setVisibility('hidden');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(getHrNotificationCounts).toHaveBeenCalledTimes(2);

    setVisibility('visible');
    await waitFor(() => expect(getHrNotificationCounts).toHaveBeenCalledTimes(3));
  });

  it('pauses and resumes the admin poller the same way', async () => {
    renderSidebar('ADMIN');
    await waitFor(() => {
      expect(getHrNotificationCounts).toHaveBeenCalledTimes(1);
      expect(getAdminNotificationCounts).toHaveBeenCalledTimes(1);
    });

    setVisibility('hidden');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });
    expect(getAdminNotificationCounts).toHaveBeenCalledTimes(1);
    expect(getHrNotificationCounts).toHaveBeenCalledTimes(1);

    setVisibility('visible');
    await waitFor(() => {
      expect(getAdminNotificationCounts).toHaveBeenCalledTimes(2);
      expect(getHrNotificationCounts).toHaveBeenCalledTimes(2);
    });
  });

  it('does not poll HR or admin counts for an employee session', async () => {
    renderSidebar('EMPLOYEE');
    await waitFor(() => expect(getUnreadMessageCount).toHaveBeenCalled());
    expect(getHrNotificationCounts).not.toHaveBeenCalled();
    expect(getAdminNotificationCounts).not.toHaveBeenCalled();
  });
});
