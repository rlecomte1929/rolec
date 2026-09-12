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
    refetch: async () => {},
  }),
}));
vi.mock('../../contexts/SelectedCaseContext', () => ({
  useSelectedCase: () => ({ selectedCaseId: null, setSelectedCaseId: () => {} }),
}));

describe('PlatformShellSidebar nav hints (AIQ-2278)', () => {
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

  it('exposes hint copy as a tooltip, not a truncated subtitle in the link name', () => {
    const sidebarRole = 'HR' as const;
    render(
      <MemoryRouter>
        <PlatformShellSidebar
          role={sidebarRole}
          user={{ initials: 'TA', name: 'Testing April', role: 'Workspace HR' }}
        />
      </MemoryRouter>,
    );

    const cases = screen.getByRole('link', { name: 'Cases' });
    expect(cases).toHaveAttribute('title', 'Case list and the new-case form');
    expect(screen.queryByText(/case list and the new-case/i)).toBeNull();

    const providers = screen.getByRole('link', { name: 'Service providers' });
    expect(providers).toHaveAttribute('title', 'Manage vendors and track provider status');
    expect(screen.queryByText(/manage vendors and track/i)).toBeNull();
  });
});
