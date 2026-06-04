import { describe, it, expect } from 'vitest';
import {
  successProbability,
  CONFIDENCE_VALUE,
  type ScoringRoadmap,
  type ConfidenceLevel,
  type CaseOutcome,
} from '../successProbability';

// ── Fixtures ────────────────────────────────────────────────────────────────

/** Build a roadmap from a list of confidence levels. */
function roadmapOf(levels: ConfidenceLevel[]): ScoringRoadmap {
  return {
    steps: levels.map((confidence, i) => ({
      id: `step-${i + 1}`,
      title: `Step ${i + 1}`,
      confidence,
    })),
  };
}

/**
 * Marc Bouchard — French national relocating to Norway under EEA freedom of
 * movement. Clean legal basis: every step is HIGH confidence.
 */
const MARC_BOUCHARD_EEA: ScoringRoadmap = {
  steps: [
    { id: 'eea-register', title: 'Register as an EEA resident', confidence: 'high' },
    { id: 'd-number', title: 'Obtain a D-number', confidence: 'high' },
    { id: 'residence-reg', title: 'Register your address', confidence: 'high' },
    { id: 'tax-card', title: 'Get a tax deduction card', confidence: 'high' },
    { id: 'police-reg', title: 'Police registration', confidence: 'high' },
  ],
};

/** Same case, deliberately weakened: several LOW/UNKNOWN steps. */
const WEAKENED_CASE: ScoringRoadmap = {
  steps: [
    { id: 'eea-register', title: 'Register as an EEA resident', confidence: 'high' },
    { id: 'd-number', title: 'Obtain a D-number', confidence: 'high' },
    { id: 'residence-reg', title: 'Register your address', confidence: 'low' },
    { id: 'tax-card', title: 'Get a tax deduction card', confidence: 'low' },
    { id: 'work-permit', title: 'Obtain a work permit', confidence: 'unknown' },
    { id: 'family-reunif', title: 'Family reunification', confidence: 'unknown' },
  ],
};

// ── Validation criteria (from the task) ──────────────────────────────────────

describe('successProbability — validation criteria', () => {
  it('scores a clean France→Norway EEA case ≥ 90%', () => {
    const result = successProbability(MARC_BOUCHARD_EEA);
    expect(result.scorePct).toBeGreaterThanOrEqual(90);
    expect(result.confidenceBasis).toBe('official_only');
  });

  it('scores a deliberately weakened case < 60%', () => {
    const result = successProbability(WEAKENED_CASE);
    expect(result.scorePct).toBeLessThan(60);
  });

  it('factors correctly identify which steps raise vs. lower the score', () => {
    const result = successProbability(WEAKENED_CASE);
    const lowers = result.factors.filter((f) => f.direction === 'lowers');
    const raises = result.factors.filter((f) => f.direction === 'raises');

    // The two HIGH steps raise (neutral drag), the four LOW/UNKNOWN steps lower.
    expect(raises).toHaveLength(2);
    expect(lowers).toHaveLength(4);

    // UNKNOWN steps drag more than LOW steps.
    const unknownFactor = result.factors.find((f) => f.stepId === 'work-permit')!;
    const lowFactor = result.factors.find((f) => f.stepId === 'tax-card')!;
    expect(unknownFactor.impactPct).toBeLessThan(lowFactor.impactPct);
    expect(lowFactor.impactPct).toBeLessThan(0);
  });
});

// ── Rounding / precision ─────────────────────────────────────────────────────

describe('successProbability — rounding', () => {
  it('always rounds the score to the nearest 5%', () => {
    for (const rm of [MARC_BOUCHARD_EEA, WEAKENED_CASE, roadmapOf(['medium', 'low', 'high'])]) {
      const { scorePct } = successProbability(rm);
      expect(scorePct % 5).toBe(0);
    }
  });

  it('clamps the score to the 0–100 range', () => {
    const { scorePct } = successProbability(roadmapOf(['high']));
    expect(scorePct).toBeLessThanOrEqual(100);
    expect(scorePct).toBeGreaterThanOrEqual(0);
  });
});

// ── Historical adjustment ────────────────────────────────────────────────────

describe('successProbability — historical adjustment', () => {
  const history = (approved: number, rejected: number): CaseOutcome[] => [
    ...Array.from({ length: approved }, () => ({ outcome: 'approved' as const })),
    ...Array.from({ length: rejected }, () => ({ outcome: 'rejected' as const })),
  ];

  it('uses official_only basis when no history is supplied', () => {
    const result = successProbability(MARC_BOUCHARD_EEA, []);
    expect(result.confidenceBasis).toBe('official_only');
    expect(result.sampleSize).toBe(0);
  });

  it('switches to platform_data basis when history is supplied', () => {
    const result = successProbability(MARC_BOUCHARD_EEA, history(8, 2));
    expect(result.confidenceBasis).toBe('platform_data');
    expect(result.sampleSize).toBe(10);
  });

  it('a poor historical outcome rate drags the score down', () => {
    const clean = successProbability(MARC_BOUCHARD_EEA);
    const withBadHistory = successProbability(MARC_BOUCHARD_EEA, history(1, 9));
    expect(withBadHistory.scorePct).toBeLessThan(clean.scorePct);
    expect(withBadHistory.factors.some((f) => f.label.includes('Historical outcomes'))).toBe(true);
  });
});

// ── Disclaimer (mandatory) ───────────────────────────────────────────────────

describe('successProbability — disclaimer', () => {
  it('always returns a non-empty disclaimer with the legal-guarantee caveat', () => {
    const result = successProbability(MARC_BOUCHARD_EEA);
    expect(result.disclaimer.trim().length).toBeGreaterThan(0);
    expect(result.disclaimer).toContain('not a legal guarantee');
    expect(result.disclaimer).toContain('discretion');
  });

  it('references the similar-case count when history is present', () => {
    const result = successProbability(MARC_BOUCHARD_EEA, [
      { outcome: 'approved' },
      { outcome: 'approved' },
      { outcome: 'rejected' },
    ]);
    expect(result.disclaimer).toContain('3 similar cases');
  });

  it('does not claim "0 similar cases" when there is no history', () => {
    const result = successProbability(MARC_BOUCHARD_EEA, []);
    expect(result.disclaimer).not.toContain('0 similar');
    expect(result.disclaimer).toContain('official requirements');
  });
});

// ── Edge cases ───────────────────────────────────────────────────────────────

describe('successProbability — edge cases', () => {
  it('treats an empty roadmap as fully uncertain, not 100%', () => {
    const result = successProbability({ steps: [] });
    expect(result.scorePct).toBe(Math.round((CONFIDENCE_VALUE.unknown * 100) / 5) * 5);
    expect(result.factors).toHaveLength(0);
  });

  it('treats an unrecognised confidence value as unknown', () => {
    const rm = { steps: [{ id: 's1', title: 'Mystery step', confidence: 'bogus' as ConfidenceLevel }] };
    const result = successProbability(rm);
    expect(result.factors[0].label).toContain('UNKNOWN');
  });

  it('respects per-step weight (a heavier low-confidence step hurts more)', () => {
    const light = successProbability({
      steps: [
        { id: 'a', title: 'A', confidence: 'high' },
        { id: 'b', title: 'B', confidence: 'low', weight: 1 },
      ],
    });
    const heavy = successProbability({
      steps: [
        { id: 'a', title: 'A', confidence: 'high' },
        { id: 'b', title: 'B', confidence: 'low', weight: 3 },
      ],
    });
    expect(heavy.scorePct).toBeLessThan(light.scorePct);
  });
});
