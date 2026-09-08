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

describe('movePlan precedence — the Oslo→Singapore default', () => {
  // MovePlan.origin/destination used to default to "Oslo, Norway" / "Singapore" in
  // backend/schemas.py, so profile_json carried them on 1365 of 1401 production cases.
  // deriveCaseEssentials reads `movePlan ?? hint` — movePlan FIRST — so a non-empty default
  // beat the real route: a Paris→Oslo case on the FR-NO corridor rendered "Oslo, Norway →
  // Singapore". The defaults are now "", which `nonEmpty` maps to undefined so the `??` falls
  // through. These pin that fallthrough.

  it('an empty movePlan falls through to the real route', () => {
    const e = deriveCaseEssentials(
      mk({
        profile: { movePlan: { origin: '', destination: '' } },
        caseOriginCity: 'Paris',
        caseOriginHint: 'FR',
        caseDestinationCity: 'Oslo',
        caseDestinationHint: 'NO',
      } as Partial<AssignmentDetail>),
    );
    expect(e.origin).toBe('Paris, France');
    expect(e.destination).toBe('Oslo, Norway');
  });

  it('a whitespace-only movePlan is also treated as absent', () => {
    const e = deriveCaseEssentials(
      mk({
        profile: { movePlan: { origin: '   ', destination: '\t' } },
        caseOriginHint: 'FR',
        caseDestinationHint: 'NO',
      } as Partial<AssignmentDetail>),
    );
    expect(e.origin).toBe('France');
    expect(e.destination).toBe('Norway');
  });

  it('a REAL movePlan value still wins over the hint', () => {
    // The precedence itself is correct and must survive: an explicitly entered move plan is
    // better data than the case-level hint. Only the invented default was the problem.
    const e = deriveCaseEssentials(
      mk({
        profile: { movePlan: { origin: 'Lyon', destination: 'Bergen' } },
        caseOriginHint: 'FR',
        caseDestinationHint: 'NO',
      } as Partial<AssignmentDetail>),
    );
    expect(e.origin).toBe('Lyon');
    expect(e.destination).toBe('Bergen');
  });
});
