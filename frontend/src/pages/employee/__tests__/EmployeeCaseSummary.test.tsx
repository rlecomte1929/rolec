import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { EmployeeCaseSummary } from '../EmployeeCaseSummary';

const mockGetCaseDetails = vi.fn();

vi.mock('../../../components/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('../../../api/caseDetails', () => ({
  getCaseDetailsByAssignmentId: (...args: unknown[]) => mockGetCaseDetails(...args),
}));

vi.mock('../../../utils/demo', () => ({
  getAuthItem: () => null,
}));

vi.mock('../../AssignmentDebugPanel', () => ({
  AssignmentDebugPanel: () => null,
}));

vi.mock('../../../components/employee/EmployeeNextActionBar', () => ({
  EmployeeNextActionBar: () => null,
}));

vi.mock('../../../hooks/useTrackLastVisited', () => ({
  useTrackLastVisited: () => {},
}));

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/employee/case/case-1/summary']}>
      <Routes>
        <Route path="/employee/case/:caseId/summary" element={<EmployeeCaseSummary />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('EmployeeCaseSummary', () => {
  beforeEach(() => {
    mockGetCaseDetails.mockReset();
  });

  it('hides empty summary rows and expands country codes to names', async () => {
    mockGetCaseDetails.mockResolvedValue({
      error: null,
      data: {
        case: {
          status: 'submitted',
          originCountry: 'AE',
          originCity: 'Dubai',
          destCountry: 'CA',
          destCity: 'Toronto',
          purpose: '',
          targetMoveDate: '',
          draft: {
            relocationBasics: {},
            employeeProfile: {
              fullName: 'Ada Lovelace',
              email: '',
              nationality: 'CA',
              passportCountry: 'AE',
              residenceCountry: '',
            },
            familyMembers: {
              spouse: { fullName: '' },
              children: [],
            },
            assignmentContext: {},
          },
        },
      },
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Origin: Dubai, United Arab Emirates')).toBeInTheDocument();
    });

    expect(screen.getByText('Destination: Toronto, Canada')).toBeInTheDocument();
    expect(screen.getByText('Nationality: Canada')).toBeInTheDocument();
    expect(screen.getByText('Passport country: United Arab Emirates')).toBeInTheDocument();
    expect(screen.queryByText(/^Purpose:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Email:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Spouse:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/: -/)).not.toBeInTheDocument();
  });
});
