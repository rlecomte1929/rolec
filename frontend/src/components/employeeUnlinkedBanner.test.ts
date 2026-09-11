import { describe, it, expect } from 'vitest';
import { employeeUnlinkedActionCopy } from './employeeUnlinkedBanner';

describe('employeeUnlinkedActionCopy (AIQ-2287)', () => {
  it('does not send the user to the dashboard when they are already there', () => {
    expect(employeeUnlinkedActionCopy(true)).toMatch(/link case below/i);
    expect(employeeUnlinkedActionCopy(true)).not.toMatch(/dashboard/i);
  });

  it('points other employee pages at the dashboard', () => {
    expect(employeeUnlinkedActionCopy(false)).toMatch(/dashboard/i);
  });
});
