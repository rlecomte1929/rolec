import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PlatformShellSidebar } from '../PlatformShellSidebar';

const getHrNotificationCounts = vi.fn();
const getAdminNotificationCounts = vi.fn();
const getUnreadMessageCount = vi.fn();

vi.mock('../../api/hrCatalog', () => ({
  getHrNotificationCounts: (...a: unknown[]) => getHrNotificationCounts(...a),
}));
vi.mock('../../api/adminCatalog', () => ({
  getAdminNotificationCounts: (...a: unknown[]) => getAdminNotificationCounts(...a),
}));
vi.mock('../../api/messageNotifications', () => ({
  getUnreadMessageCount: (...a: unknown[]) => getUnreadMessageCount(...a),
}));
vi.mock('../../api/client', () => ({
  authAPI: { logout: vi.fn() },
}));
vi.mock('../../contexts/EmployeeAssignmentContext', () => ({
  useEmployeeAssignment: () => ({
    assignmentId: null,
    primaryCaseId: null,
    primaryAssignmentCompany: null,
    isLoading: false,
    linkedCount: 0,
    pendingCount: 0,
    linkedSummaries: [],
    pendingSummaries: [],
    overviewError: null,
    refetch: async () => {},
  }),
}));
vi.mock('../../contexts/SelectedCaseContext', () => ({
  useSelectedCase: () => ({ selectedCaseId: null, setSelectedCaseId: () => {} }),
}));

function setVisibility(state: DocumentVisibilityState) {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    get: () => state,
  });
}

function renderSidebar(role: 'ADMIN' | 'EMPLOYEE') {
  const props = {
    role,
    user: {
      initials: role === 'ADMIN' ? 'A' : 'E',
      name: role === 'ADMIN' ? 'Admin' : 'Emp',
      role,
    },
  };
  return render(
    <MemoryRouter>
      <PlatformShellSidebar {...props} />
    </MemoryRouter>,
  );
}

describe('PlatformShellSidebar notification polls', () => {
  beforeEach(() => {
    vi.useFakeTimers();
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
        onchange: null,
      }),
    });
    setVisibility('visible');
    getHrNotificationCounts.mockReset().mockResolvedValue({
      employees_waiting: 0,
      destinations_with_demand: 0,
      pending_admin_tickets: 0,
    });
    getAdminNotificationCounts.mockReset().mockResolvedValue({
      pending_tickets: 0,
      allowlisted_destinations: 0,
      pending_capabilities: 0,
    });
    getUnreadMessageCount.mockReset().mockResolvedValue(0);
  });

  afterEach(() => {
    vi.useRealTimers();
    setVisibility('visible');
  });

  it('pauses HR and admin 60s polls while hidden and refetches once on visible', async () => {
    renderSidebar('ADMIN');
    await act(() => Promise.resolve());

    expect(getHrNotificationCounts).toHaveBeenCalledTimes(1);
    expect(getAdminNotificationCounts).toHaveBeenCalledTimes(1);

    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(getHrNotificationCounts).toHaveBeenCalledTimes(2);
    expect(getAdminNotificationCounts).toHaveBeenCalledTimes(2);

    setVisibility('hidden');
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(getHrNotificationCounts).toHaveBeenCalledTimes(2);
    expect(getAdminNotificationCounts).toHaveBeenCalledTimes(2);

    setVisibility('visible');
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'));
    });
    expect(getHrNotificationCounts).toHaveBeenCalledTimes(3);
    expect(getAdminNotificationCounts).toHaveBeenCalledTimes(3);
  });

  it('does not start HR/admin notification polls for an employee session', async () => {
    renderSidebar('EMPLOYEE');
    await act(() => Promise.resolve());

    expect(getUnreadMessageCount).toHaveBeenCalled();
    expect(getHrNotificationCounts).not.toHaveBeenCalled();
    expect(getAdminNotificationCounts).not.toHaveBeenCalled();
  });
});
