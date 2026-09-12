import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PlatformShellSidebar } from '../PlatformShellSidebar';

vi.mock('../../api/hrCatalog', () => ({
  getHrNotificationCounts: vi.fn().mockResolvedValue({
    employees_waiting: 0,
    destinations_with_demand: 0,
    pending_admin_tickets: 0,
  }),
}));
vi.mock('../../api/adminCatalog', () => ({
  getAdminNotificationCounts: vi.fn().mockResolvedValue({}),
}));
vi.mock('../../api/messageNotifications', () => ({
  getUnreadMessageCount: vi.fn().mockResolvedValue(0),
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
    overviewDegraded: false,
    refetch: async () => {},
  }),
}));
vi.mock('../../contexts/SelectedCaseContext', () => ({
  useSelectedCase: () => ({
    selectedCaseId: '053c93bb-6ba4-4a7e-a26d-bc05dcfe3abe',
    setSelectedCaseId: () => {},
  }),
}));

describe('PlatformShellSidebar unlinked employee (AIQ-2359)', () => {
  beforeEach(() => {
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
  });

  it('hides Roadmap and Dossier and never emits a case UUID in hrefs', () => {
    const sidebarProps = {
      role: 'EMPLOYEE' as const,
      user: { initials: 'HH', name: 'Hannah HR', role: 'Employee' },
    };
    render(
      <MemoryRouter>
        <PlatformShellSidebar {...sidebarProps} />
      </MemoryRouter>,
    );

    expect(screen.queryByRole('link', { name: 'Roadmap' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Dossier & forms' })).toBeNull();
    expect(screen.getByRole('link', { name: 'Tasks' })).toHaveAttribute('href', '/employee/tasks');
    expect(document.body.innerHTML).not.toContain('053c93bb-6ba4-4a7e-a26d-bc05dcfe3abe');
  });
});
