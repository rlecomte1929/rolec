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
    // Linking how-to lives once, on the claim card (AIQ-2288).
    expect(screen.queryByText(/case code from hr/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/link it below/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/no code needed/i)).not.toBeInTheDocument();
  });

  it('includes the (backed) email-notice line and omits the unavailable HR-contact link', () => {
    render(<EmployeeNoCaseOnboarding />);
    // The case-assignment invite email genuinely fires on HR assign
    // (_dispatch_hr_assign_side_effects → send_assignment_invite_email), so the
    // "we'll email you" reassurance is accurate and present.
    expect(screen.getByText(/email you when everything is in place/i)).toBeInTheDocument();
    // HR-contact data isn't available to a no-case employee → no contact link.
    expect(screen.queryByText(/contact your hr team directly/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });
});
