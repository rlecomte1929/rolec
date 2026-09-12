import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CompanyBrand } from './CompanyBrand';

vi.mock('../utils/demo', () => ({
  getAuthItem: (key: string) => (key === 'relopass_role' ? 'HR' : null),
}));
vi.mock('../contexts/HrCompanyContext', () => ({
  useHrCompanyContext: () => ({
    company: { id: 'c1', name: 'Testing April', logo_url: null },
    loading: false,
  }),
}));
vi.mock('../contexts/EmployeeAssignmentContext', () => ({
  useEmployeeAssignment: () => ({
    primaryAssignmentCompany: null,
    isLoading: false,
  }),
}));
vi.mock('../hooks/useCompany', () => ({
  useCompany: () => ({ company: null, loading: false }),
}));

function renderBrand(compact = false) {
  return render(
    <MemoryRouter initialEntries={['/hr/welcome']}>
      <CompanyBrand compact={compact} />
    </MemoryRouter>,
  );
}

describe('CompanyBrand (AIQ-2280)', () => {
  it('renders the workspace name without an orphaned vertical divider', () => {
    renderBrand();
    expect(screen.getByText('Testing April')).toBeInTheDocument();
    expect(screen.queryByText('|')).toBeNull();
  });

  it('does not render a divider in the collapsed mark-only row', () => {
    renderBrand(true);
    expect(screen.queryByText('|')).toBeNull();
    expect(screen.queryByText('Testing April')).toBeNull();
  });
});
