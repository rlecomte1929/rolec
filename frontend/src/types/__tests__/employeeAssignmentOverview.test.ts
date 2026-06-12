import { describe, it, expect } from 'vitest';
import {
  formatDestinationLabel,
  formatCaseReference,
} from '../employeeAssignmentOverview';

/**
 * AIQ-977: assignment rows must be distinguishable. A null destination reads
 * as "Not set yet" (not the system-y "Destination TBD"), and every row carries
 * a stable case reference so two cases that share a company and have no
 * destination set still render different text.
 */
describe('formatDestinationLabel', () => {
  it('prefers the provided label', () => {
    expect(formatDestinationLabel({ label: 'Berlin, Germany' })).toBe('Berlin, Germany');
  });

  it('composes "city, country" from host fields when no label', () => {
    expect(formatDestinationLabel({ host_city: 'Berlin', host_country: 'Germany' })).toBe(
      'Berlin, Germany',
    );
  });

  it('uses country alone when only country is present', () => {
    expect(formatDestinationLabel({ host_country: 'Germany' })).toBe('Germany');
  });

  it('falls back to "Not set yet" for null/empty destination', () => {
    expect(formatDestinationLabel(null)).toBe('Not set yet');
    expect(formatDestinationLabel(undefined)).toBe('Not set yet');
    expect(formatDestinationLabel({ label: '   ' })).toBe('Not set yet');
  });
});

describe('formatCaseReference', () => {
  it('returns the last 8 chars of case_id, upper-cased', () => {
    expect(formatCaseReference({ case_id: 'abc12345-6789-defg', assignment_id: 'x' })).toBe('789-DEFG');
  });

  it('falls back to assignment_id when case_id is absent', () => {
    expect(formatCaseReference({ assignment_id: 'assign-90ab' })).toBe('IGN-90AB');
  });

  it('distinguishes two cases with the same (empty) destination', () => {
    const a = { case_id: 'case-aaaaaaaa', assignment_id: '1' };
    const b = { case_id: 'case-bbbbbbbb', assignment_id: '2' };
    expect(formatCaseReference(a)).not.toBe(formatCaseReference(b));
  });

  it('returns empty string when no id is available', () => {
    expect(formatCaseReference({})).toBe('');
  });
});
