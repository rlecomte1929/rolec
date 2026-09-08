import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

import {
  HrNoCompanyOnboarding,
  httpStatusOf,
  isNoCompanyError,
} from '../hrNoCompanyOnboarding';

afterEach(() => cleanup());

describe('[T2.4] httpStatusOf', () => {
  it('reads axios-style error.response.status', () => {
    expect(httpStatusOf({ response: { status: 403 } })).toBe(403);
  });
  it('reads flat error.status', () => {
    expect(httpStatusOf({ status: 500 })).toBe(500);
  });
  it('returns undefined for a network error / null', () => {
    expect(httpStatusOf(new Error('Network Error'))).toBeUndefined();
    expect(httpStatusOf(null)).toBeUndefined();
    expect(httpStatusOf(undefined)).toBeUndefined();
  });
});

describe('[T2.4] isNoCompanyError — detect 403 specifically', () => {
  it('true for a 403 (axios + flat shapes)', () => {
    expect(isNoCompanyError({ response: { status: 403 } })).toBe(true);
    expect(isNoCompanyError({ status: 403 })).toBe(true);
  });
  it('false for non-403 errors — real errors must not be swallowed as onboarding', () => {
    expect(isNoCompanyError({ response: { status: 404 } })).toBe(false);
    expect(isNoCompanyError({ response: { status: 500 } })).toBe(false);
    expect(isNoCompanyError({ status: 401 })).toBe(false);
    expect(isNoCompanyError(new Error('Network Error'))).toBe(false);
    expect(isNoCompanyError(null)).toBe(false);
  });
});

describe('[T2.4] HrNoCompanyOnboarding', () => {
  it('renders a friendly onboarding state (no error tone)', () => {
    render(<HrNoCompanyOnboarding />);
    expect(screen.getByTestId('hr-no-company-onboarding')).toBeInTheDocument();
    expect(screen.getByText(/Complete your account setup/i)).toBeInTheDocument();
    expect(screen.getByText(/contact your ReloPass admin/i)).toBeInTheDocument();
    // Not an error: no "error"/"failed" wording.
    expect(screen.queryByText(/failed|error|something went wrong/i)).toBeNull();
  });
});
