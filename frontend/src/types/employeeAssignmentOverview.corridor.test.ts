import { describe, it, expect } from 'vitest';
import { formatCorridorLabel } from './employeeAssignmentOverview';

describe('formatCorridorLabel (EMP-1)', () => {
  it('renders "Origin → Destination" when both countries are known', () => {
    expect(formatCorridorLabel({ home_country: 'France', host_country: 'Singapore' })).toBe('France → Singapore');
  });

  it('uses the destination label alone when no origin is known', () => {
    expect(formatCorridorLabel({ host_country: 'Singapore' })).toBe('Singapore');
    expect(formatCorridorLabel({ host_city: 'Singapore', host_country: 'Singapore' })).toBe('Singapore, Singapore');
  });

  it('falls back to "Not set yet" when neither origin nor destination is set', () => {
    expect(formatCorridorLabel({})).toBe('Not set yet');
    expect(formatCorridorLabel(null)).toBe('Not set yet');
    // Origin known but no destination → still no fabricated corridor.
    expect(formatCorridorLabel({ home_country: 'France' })).toBe('Not set yet');
  });

  it('prefers the API-provided destination label for the destination side', () => {
    expect(formatCorridorLabel({ home_country: 'France', label: 'Berlin, Germany' })).toBe('France → Berlin, Germany');
  });
});
