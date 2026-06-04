/**
 * P2-08a (AIQ-702) — unit tests for the staleness helper.
 *
 * Covers all 3 tiers, the exactly-N-days boundary, env override (valid +
 * malformed), input type coercion, and injected config.
 */
import { describe, expect, it } from 'vitest';

import {
  DEFAULT_THRESHOLDS_DAYS,
  isStale,
  loadConfig,
  Tier,
} from './staleness';

const NOW = new Date('2026-06-04T12:00:00Z');
const MS_PER_DAY = 24 * 60 * 60 * 1000;
const daysAgo = (n: number): Date => new Date(NOW.getTime() - n * MS_PER_DAY);

const TIERS: ReadonlyArray<Tier> = ['tier1_critical', 'tier1_stable', 'tier2'];

describe('isStale — per-tier thresholds', () => {
  for (const tier of TIERS) {
    const threshold = DEFAULT_THRESHOLDS_DAYS[tier];

    it(`${tier}: one day below threshold (${threshold - 1}d) is fresh`, () => {
      expect(isStale(daysAgo(threshold - 1), tier, NOW)).toBe(false);
    });

    it(`${tier}: exactly ${threshold} days old is stale (boundary)`, () => {
      // The exactly-N-days boundary: first day stale.
      expect(isStale(daysAgo(threshold), tier, NOW)).toBe(true);
    });

    it(`${tier}: well above threshold is stale`, () => {
      expect(isStale(daysAgo(threshold + 5), tier, NOW)).toBe(true);
    });
  }

  it('just-now is fresh for every tier', () => {
    for (const tier of TIERS) expect(isStale(NOW, tier, NOW)).toBe(false);
  });

  it('throws on unknown tier', () => {
    // @ts-expect-error — exercising the runtime guard
    expect(() => isStale(NOW, 'tier3', NOW)).toThrow(/unknown tier/);
  });
});

describe('isStale — input coercion', () => {
  it('accepts ISO string with Z suffix', () => {
    expect(isStale('2026-05-05T12:00:00Z', 'tier1_critical', NOW)).toBe(true);
  });

  it('accepts numeric epoch ms', () => {
    expect(isStale(daysAgo(40).getTime(), 'tier1_critical', NOW)).toBe(true);
  });

  it('throws on unparseable string', () => {
    expect(() => isStale('not a date', 'tier1_critical', NOW)).toThrow(/unparseable/);
  });
});

describe('loadConfig', () => {
  it('uses defaults when env is unset', () => {
    expect(loadConfig({}).thresholdsDays).toEqual(DEFAULT_THRESHOLDS_DAYS);
  });

  it('applies a full override', () => {
    const cfg = loadConfig({
      VITE_STALENESS_THRESHOLDS_DAYS: '{"tier1_critical":7,"tier1_stable":14,"tier2":21}',
    });
    expect(cfg.thresholdsDays).toEqual({ tier1_critical: 7, tier1_stable: 14, tier2: 21 });
  });

  it('partial override falls back to defaults for missing tiers', () => {
    const cfg = loadConfig({ VITE_STALENESS_THRESHOLDS_DAYS: '{"tier1_critical":7}' });
    expect(cfg.thresholdsDays.tier1_critical).toBe(7);
    expect(cfg.thresholdsDays.tier1_stable).toBe(DEFAULT_THRESHOLDS_DAYS.tier1_stable);
    expect(cfg.thresholdsDays.tier2).toBe(DEFAULT_THRESHOLDS_DAYS.tier2);
  });

  it.each([
    ['not json'],
    ['[1, 2, 3]'],
    ['{"tier1_critical":"thirty"}'],
    ['{"tier1_critical":-1}'],
    ['{"tier1_critical":1.5}'],
  ])('malformed env (%s) falls back safely', (raw) => {
    const cfg = loadConfig({ VITE_STALENESS_THRESHOLDS_DAYS: raw });
    expect(cfg.thresholdsDays.tier1_critical).toBe(
      DEFAULT_THRESHOLDS_DAYS.tier1_critical,
    );
  });

  it('isStale honours an injected config', () => {
    const cfg = {
      thresholdsDays: { tier1_critical: 7, tier1_stable: 14, tier2: 21 } as Record<Tier, number>,
    };
    // 10 days old < default 30 (fresh) but > injected 7 (stale).
    expect(isStale(daysAgo(10), 'tier1_critical', NOW)).toBe(false);
    expect(isStale(daysAgo(10), 'tier1_critical', NOW, cfg)).toBe(true);
  });
});
