import { describe, it, expect } from 'vitest';
import { destinationPermitLabel } from './hrAssignmentPermit';

describe('destinationPermitLabel', () => {
  it('maps Singapore (name) to Employment Pass', () => {
    expect(destinationPermitLabel('Singapore')).toBe('Employment Pass (EP)');
  });

  it('maps the SG code to Employment Pass', () => {
    expect(destinationPermitLabel('SG')).toBe('Employment Pass (EP)');
  });

  it('is case/whitespace insensitive', () => {
    expect(destinationPermitLabel('  germany ')).toBe('EU Blue Card');
  });

  it('returns null for an unknown/unmapped destination', () => {
    expect(destinationPermitLabel('Atlantis')).toBeNull();
  });

  it('returns null for empty/undefined input', () => {
    expect(destinationPermitLabel('')).toBeNull();
    expect(destinationPermitLabel(undefined)).toBeNull();
    expect(destinationPermitLabel(null)).toBeNull();
  });
});
