import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { ServicesEstimate } from '../ServicesEstimate';

vi.mock('../../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('../../../features/services/ServicesNavRibbon', () => ({
  ServicesNavRibbon: () => <div data-testid="services-nav" />,
}));

vi.mock('../../../features/services/BudgetSummaryTable', () => ({
  BudgetSummaryTable: () => <div data-testid="budget-summary" />,
}));

vi.mock('../../../features/recommendations/PackageSummary', () => ({
  PackageSummary: () => <div data-testid="package-summary" />,
}));

vi.mock('../../../contexts/EmployeeAssignmentContext', () => ({
  useEmployeeAssignment: () => ({
    assignmentId: 'case-1',
    linkedSummaries: [],
  }),
}));

vi.mock('../../../utils/employeeAssignmentScope', () => ({
  parseAssignmentSearchParam: () => null,
  resolveScopedAssignmentId: () => ({ effectiveId: 'case-1', needsPicker: false }),
}));

vi.mock('../../../features/services/ServicesFlowContext', () => ({
  useServicesFlow: () => ({
    recommendations: { movers: { recommendations: [] } },
    shortlist: new Map([['movers', 'vendor-1']]),
    displayCurrency: 'CAD',
    setActiveCaseId: vi.fn(),
  }),
}));

vi.mock('../../../hooks/useTrackLastVisited', () => ({
  useTrackLastVisited: () => {},
}));

vi.mock('../../../featureFlags', () => ({
  isRfqEnabled: () => false,
}));

describe('ServicesEstimate', () => {
  it('renders breadcrumb and back link for estimate review', () => {
    render(
      <MemoryRouter initialEntries={['/services/estimate?assignment=case-1']}>
        <ServicesEstimate />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText('Breadcrumb')).toHaveTextContent('Services/Review & budget');
    const back = screen.getAllByRole('link', { name: /back to recommendations/i })[0];
    expect(back).toHaveAttribute('href', '/services/recommendations?assignment=case-1');
  });
});
