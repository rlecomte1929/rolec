import { describe, it, expect } from 'vitest';
import { deriveCaseEssentials } from './caseEssentials';
import type { AssignmentDetail } from '../../types';

// deriveCaseEssentials reads many optional fields; cast a minimal shape per case.
const mk = (over: Partial<AssignmentDetail>): AssignmentDetail => over as AssignmentDetail;

describe('deriveCaseEssentials corridor — AIQ-1336 city-level', () => {
  it('renders "City, Country → City, Country" when city is present', () => {
    const e = deriveCaseEssentials(
      mk({
        caseOriginCity: 'Paris',
        caseOriginHint: 'FR',
        caseDestinationCity: 'Amsterdam',
        caseDestinationHint: 'Netherlands',
      }),
    );
    expect(e.origin).toBe('Paris, France');
    expect(e.destination).toBe('Amsterdam, Netherlands');
  });

  it('falls back to country-only when a city is missing (no "undefined, …")', () => {
    const e = deriveCaseEssentials(
      mk({
        caseOriginHint: 'France', // no origin city
        caseDestinationCity: 'Amsterdam',
        caseDestinationHint: 'Netherlands',
      }),
    );
    expect(e.origin).toBe('France');
    expect(e.destination).toBe('Amsterdam, Netherlands');
  });

  it('resolves ISO country codes and degrades to "Not provided" when no data', () => {
    const e = deriveCaseEssentials(mk({ caseDestinationCity: 'Oslo', caseDestinationHint: 'NO' }));
    expect(e.destination).toBe('Oslo, Norway');
    expect(e.origin).toBe('Not provided');
  });
});
