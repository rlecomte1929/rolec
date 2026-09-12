import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EmployeeTaskPage } from '../EmployeeTaskPage';

vi.mock('../../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock('../../../api/client', () => ({
  servicesAPI: { getTasks: vi.fn() },
  apiGet: vi.fn().mockResolvedValue({ acknowledged: true }),
}));
vi.mock('../../../api/roadmapV2', () => ({
  getCaseRoadmapV2: vi.fn(),
}));
vi.mock('../../../contexts/SelectedCaseContext', () => ({
  useSelectedCase: () => ({
    selectedCaseId: '053c93bb-6ba4-4a7e-a26d-bc05dcfe3abe',
    setSelectedCaseId: () => {},
  }),
}));
vi.mock('../../../contexts/EmployeeAssignmentContext', () => ({
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

import { servicesAPI } from '../../../api/client';
import { getCaseRoadmapV2 } from '../../../api/roadmapV2';

describe('EmployeeTaskPage unlinked (AIQ-2358)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows No case linked and does not fetch tasks or roadmap data', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <EmployeeTaskPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText(/No case linked/)).toBeInTheDocument();
    expect(screen.queryByText(/Action needed/)).toBeNull();
    expect(servicesAPI.getTasks).not.toHaveBeenCalled();
    expect(getCaseRoadmapV2).not.toHaveBeenCalled();
  });
});
