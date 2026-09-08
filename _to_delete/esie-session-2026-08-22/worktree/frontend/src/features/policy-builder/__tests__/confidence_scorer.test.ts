/**
 * [P2-4] Tests for confidence_scorer.ts
 *
 * Validation criteria from Notion:
 * ✓ Score ≥ 0.90 on a chunk with explicit 'EUR 3,500/month for Manager grade'
 * ✓ Score ≤ 0.50 on a chunk with 'housing support may be provided subject to approval'
 * ✓ Score is reproducible — same input always returns same score
 * ✓ Reason string is human-readable (< 100 chars)
 */
import { describe, expect, it } from 'vitest';
import {
  scoreChunk,
  hasAmbiguityLanguage,
  hasExplicitValue,
  isConsistentWithExisting,
  scoreToBand,
} from '../confidence_scorer';
import type { ClassifiedChunk, ExistingPolicyValue } from '../confidence_scorer';

// ---------------------------------------------------------------------------
// Primary validation criteria
// ---------------------------------------------------------------------------

describe('P2-4 validation criteria', () => {
  it('VC-1: scores ≥ 0.90 on explicit EUR 3,500/month for Manager grade', () => {
    const chunk: ClassifiedChunk = {
      source_quote: 'Housing allowance is EUR 3,500 per month for Manager grade employees.',
      category_code: 'CAT-01',
      tier: 'Manager',
      normalized_value: { value: '3500', currency: 'EUR', unit: 'month' },
    };
    const result = scoreChunk(chunk, null);
    expect(result.score).toBeGreaterThanOrEqual(0.90);
    expect(result.band).toBe('high');
  });

  it('VC-2: scores ≤ 0.50 on "housing support may be provided subject to approval"', () => {
    const chunk: ClassifiedChunk = {
      source_quote: 'Housing support may be provided subject to approval.',
      category_code: 'CAT-01',
      tier: null,
      normalized_value: { value: null },
    };
    const result = scoreChunk(chunk, null);
    expect(result.score).toBeLessThanOrEqual(0.50);
    expect(result.band).not.toBe('high');
  });

  it('VC-3: score is reproducible — same input always returns same score', () => {
    const chunk: ClassifiedChunk = {
      source_quote: 'Relocation lump sum is EUR 5,000 for Director level.',
      category_code: 'CAT-02',
      tier: 'Director',
      normalized_value: { value: '5000', currency: 'EUR' },
    };
    const r1 = scoreChunk(chunk, null);
    const r2 = scoreChunk(chunk, null);
    const r3 = scoreChunk(chunk, null);
    expect(r1.score).toBe(r2.score);
    expect(r2.score).toBe(r3.score);
    expect(r1.reason).toBe(r2.reason);
    expect(r1.band).toBe(r2.band);
  });

  it('VC-4: reason string is always < 100 characters', () => {
    const cases: ClassifiedChunk[] = [
      {
        source_quote: 'EUR 3,500/month for Manager grade.',
        category_code: 'CAT-01', tier: 'Manager',
        normalized_value: { value: '3500', currency: 'EUR', unit: 'month' },
      },
      {
        source_quote: 'Housing support may be provided subject to approval where applicable.',
        category_code: 'CAT-01', tier: null,
        normalized_value: { value: null },
      },
      {
        source_quote: 'Up to EUR 2,000 for relocation.',
        category_code: 'CAT-03', tier: null,
        normalized_value: { value: '2000', currency: 'EUR' },
      },
    ];
    for (const chunk of cases) {
      const result = scoreChunk(chunk, null);
      expect(result.reason.length).toBeLessThanOrEqual(99);
    }
  });
});

// ---------------------------------------------------------------------------
// hasAmbiguityLanguage
// ---------------------------------------------------------------------------

describe('hasAmbiguityLanguage', () => {
  it.each([
    ['subject to approval', true],
    ['may be provided', true],
    ['up to EUR 3,000', true],
    ['where applicable', true],
    ['at the discretion of management', true],
    ['approximately EUR 2,500', true],
    ['around 3,000 EUR', true],
  ])('detects ambiguity in "%s"', (text, expected) => {
    expect(hasAmbiguityLanguage(text)).toBe(expected);
  });

  it.each([
    ['EUR 3,500 per month for Manager grade'],
    ['The relocation allowance is EUR 5,000.'],
    ['Standard lump sum: EUR 2,000 for all tiers.'],
  ])('returns false for clear text "%s"', (text) => {
    expect(hasAmbiguityLanguage(text)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// hasExplicitValue
// ---------------------------------------------------------------------------

describe('hasExplicitValue', () => {
  it('returns true when numeric value appears directly in quote', () => {
    const chunk: ClassifiedChunk = {
      source_quote: 'The housing allowance is EUR 3,500 per month.',
      category_code: 'CAT-01',
      tier: 'Manager',
      normalized_value: { value: '3,500', currency: 'EUR' },
    };
    expect(hasExplicitValue(chunk)).toBe(true);
  });

  it('returns false when value is prefixed with "up to"', () => {
    const chunk: ClassifiedChunk = {
      source_quote: 'Housing support up to 3000 EUR per month.',
      category_code: 'CAT-01',
      tier: 'Manager',
      normalized_value: { value: '3000', currency: 'EUR' },
    };
    expect(hasExplicitValue(chunk)).toBe(false);
  });

  it('returns false when value is null', () => {
    const chunk: ClassifiedChunk = {
      source_quote: 'Housing support may be provided.',
      category_code: 'CAT-01',
      tier: null,
      normalized_value: { value: null },
    };
    expect(hasExplicitValue(chunk)).toBe(false);
  });

  it('returns false when value not present in source quote', () => {
    const chunk: ClassifiedChunk = {
      source_quote: 'Relocation support is available to all employees.',
      category_code: 'CAT-01',
      tier: 'Manager',
      normalized_value: { value: '3500' },
    };
    expect(hasExplicitValue(chunk)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// isConsistentWithExisting
// ---------------------------------------------------------------------------

describe('isConsistentWithExisting', () => {
  it('is consistent when values are identical', () => {
    expect(isConsistentWithExisting('3500', { value: 3500 })).toBe(true);
  });

  it('is consistent within 2% tolerance', () => {
    // 3510 vs 3500 → 0.29% difference — within tolerance
    expect(isConsistentWithExisting('3510', { value: 3500 })).toBe(true);
    // 3570 vs 3500 → 2.0% — boundary
    expect(isConsistentWithExisting('3570', { value: 3500 })).toBe(true);
  });

  it('is inconsistent beyond 2%', () => {
    // 3000 vs 3500 → ~14% — clearly inconsistent
    expect(isConsistentWithExisting('3000', { value: 3500 })).toBe(false);
    // 3600 vs 3500 → 2.86% — exceeds tolerance
    expect(isConsistentWithExisting('3600', { value: 3500 })).toBe(false);
  });

  it('treats null existing as consistent (no data to contradict)', () => {
    expect(isConsistentWithExisting('3500', null)).toBe(true);
    expect(isConsistentWithExisting('3500', undefined)).toBe(true);
  });

  it('treats null new value as consistent', () => {
    expect(isConsistentWithExisting(null, { value: 3500 })).toBe(true);
  });

  it('compares string values case-insensitively', () => {
    expect(isConsistentWithExisting('lump sum', { value: 'Lump Sum' })).toBe(true);
    expect(isConsistentWithExisting('monthly', { value: 'weekly' })).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// scoreToBand
// ---------------------------------------------------------------------------

describe('scoreToBand', () => {
  it('maps 1.0 → high', () => expect(scoreToBand(1.0)).toBe('high'));
  it('maps 0.90 → high', () => expect(scoreToBand(0.90)).toBe('high'));
  it('maps 0.80 → medium', () => expect(scoreToBand(0.80)).toBe('medium'));
  it('maps 0.70 → medium', () => expect(scoreToBand(0.70)).toBe('medium'));
  it('maps 0.60 → low', () => expect(scoreToBand(0.60)).toBe('low'));
  it('maps 0.50 → low', () => expect(scoreToBand(0.50)).toBe('low'));
  it('maps 0.49 → insufficient', () => expect(scoreToBand(0.49)).toBe('insufficient'));
  it('maps 0.0 → insufficient', () => expect(scoreToBand(0.0)).toBe('insufficient'));
});

// ---------------------------------------------------------------------------
// Full factor breakdown
// ---------------------------------------------------------------------------

describe('scoreChunk factor breakdown', () => {
  it('awards all 4 factors for a perfect explicit chunk', () => {
    const chunk: ClassifiedChunk = {
      source_quote: 'Housing allowance is EUR 3,500 per month for Manager grade.',
      category_code: 'CAT-01',
      tier: 'Manager',
      normalized_value: { value: '3,500', currency: 'EUR', unit: 'month' },
    };
    const result = scoreChunk(chunk, { value: 3500 });
    expect(result.factors.explicit_value).toBe(0.40);
    expect(result.factors.tier_present).toBe(0.20);
    expect(result.factors.no_conditionals).toBe(0.20);
    expect(result.factors.cross_doc_consistent).toBe(0.20);
    expect(result.score).toBe(1.00);
    expect(result.band).toBe('high');
  });

  it('deducts 0.20 when new value contradicts existing', () => {
    const chunk: ClassifiedChunk = {
      source_quote: 'Housing allowance is EUR 3,000 per month for Manager grade.',
      category_code: 'CAT-01',
      tier: 'Manager',
      normalized_value: { value: '3000', currency: 'EUR', unit: 'month' },
    };
    const existing: ExistingPolicyValue = { value: 3500, currency: 'EUR' };
    const withConflict = scoreChunk(chunk, existing);
    const withoutConflict = scoreChunk(chunk, null);
    expect(withConflict.factors.cross_doc_consistent).toBe(0);
    expect(withConflict.score).toBe(
      Math.round((withoutConflict.score - 0.20) * 100) / 100,
    );
  });

  it('deducts 0.20 for conditional language in source quote', () => {
    const chunk: ClassifiedChunk = {
      source_quote: 'Housing allowance up to 3500 EUR for Manager, subject to approval.',
      category_code: 'CAT-01',
      tier: 'Manager',
      normalized_value: { value: '3500', currency: 'EUR' },
    };
    const result = scoreChunk(chunk, null);
    expect(result.factors.no_conditionals).toBe(0);
  });

  it('deducts 0.20 for no tier label', () => {
    const chunk: ClassifiedChunk = {
      source_quote: 'Relocation allowance is EUR 3,500 per month.',
      category_code: 'CAT-01',
      tier: null,
      normalized_value: { value: '3500', currency: 'EUR', unit: 'month' },
    };
    const result = scoreChunk(chunk, null);
    expect(result.factors.tier_present).toBe(0);
  });

  it('honours ambiguity_flag from P2-3 classifier', () => {
    const chunk: ClassifiedChunk = {
      source_quote: 'EUR 3,500 per month for Manager grade.',
      category_code: 'CAT-01',
      tier: 'Manager',
      normalized_value: { value: '3500', currency: 'EUR' },
      ambiguity_flag: true,   // P2-3 flagged it even though text looks clear
    };
    const result = scoreChunk(chunk, null);
    expect(result.factors.no_conditionals).toBe(0);
  });
});
