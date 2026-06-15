import { describe, it, expect, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup } from '@testing-library/react';
import { EmployeeNoCaseOnboarding } from '../EmployeeNoCaseOnboarding';

expect.extend(matchers);
afterEach(cleanup);

describe('EmployeeNoCaseOnboarding', () => {
  it('renders expectation-setting copy that points to the existing claim flow', () => {
    render(<EmployeeNoCaseOnboarding />);
    expect(screen.getByTestId('employee-no-case-onboarding')).toBeInTheDocument();
    expect(screen.getByText(/your hr team is setting things up/i)).toBeInTheDocument();
    expect(screen.getByText(/nothing's gone wrong/i)).toBeInTheDocument();
    // keeps the self-serve claim path (CTA kept), not a dead-end
    expect(screen.getByText(/case code from hr/i)).toBeInTheDocument();
  });

  it('omits unbacked copy: no "we\'ll email you" line and no HR-contact link', () => {
    render(<EmployeeNoCaseOnboarding />);
    expect(screen.queryByText(/email you/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/contact your hr team directly/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });
});
