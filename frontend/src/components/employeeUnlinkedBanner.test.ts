import { describe, it, expect } from 'vitest';
import { employeeUnlinkedActionCopy, employeeUnlinkedBannerClassName } from './employeeUnlinkedBanner';

describe('employeeUnlinkedActionCopy (AIQ-2287)', () => {
  it('does not send the user to the dashboard when they are already there', () => {
    expect(employeeUnlinkedActionCopy(true)).toMatch(/link case below/i);
    expect(employeeUnlinkedActionCopy(true)).not.toMatch(/dashboard/i);
  });

  it('points other employee pages at the dashboard', () => {
    expect(employeeUnlinkedActionCopy(false)).toMatch(/dashboard/i);
  });
});

describe('employeeUnlinkedBannerClassName (AIQ-2293)', () => {
  it('uses navy info tokens, not amber warning', () => {
    expect(employeeUnlinkedBannerClassName).toContain('bg-navy-50');
    expect(employeeUnlinkedBannerClassName).toContain('text-navy-800');
    expect(employeeUnlinkedBannerClassName).not.toMatch(/amber/);
  });
});
