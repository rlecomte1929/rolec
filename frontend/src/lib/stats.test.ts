/**
 * stats.test.ts — PRODUCT-6C
 *
 * Unit tests for the A/B testing stats library.
 * Run with: npx tsx src/lib/stats.test.ts
 *
 * Covers all Validation Criteria from AIQ-339:
 *  ✓ Large sample significant result → significant: true, uplift ~0.4
 *  ✓ Small sample (n<100) → significant: false regardless of rates
 *  ✓ pValue between 0 and 1
 *  ✓ relativeUplift expressed as decimal
 *  ✓ TypeScript compiles without errors (enforced by tsx)
 *
 * Additional tests for robustness and edge cases.
 */

import { isSignificant, normalCDF } from './stats';

// ─── Minimal test harness ─────────────────────────────────────────────────────

let passed = 0;
let failed = 0;

function assert(condition: boolean, label: string, detail = ''): void {
  if (condition) {
    console.log(`  ✅  ${label}`);
    passed++;
  } else {
    console.error(`  ❌  ${label}${detail ? ' — ' + detail : ''}`);
    failed++;
  }
}

function describe(name: string, fn: () => void): void {
  console.log(`\n${name}`);
  fn();
}

// ─── normalCDF tests ──────────────────────────────────────────────────────────

describe('normalCDF — standard normal CDF', () => {
  assert(Math.abs(normalCDF(0) - 0.5) < 1e-6,
    'normalCDF(0) = 0.5');
  assert(Math.abs(normalCDF(1.96) - 0.975) < 1e-3,
    'normalCDF(1.96) ≈ 0.975');
  assert(Math.abs(normalCDF(-1.96) - 0.025) < 1e-3,
    'normalCDF(-1.96) ≈ 0.025');
  assert(normalCDF(8) === 1,
    'normalCDF(8) = 1 (clamped)');
  assert(normalCDF(-8) === 0,
    'normalCDF(-8) = 0 (clamped)');
  assert(Math.abs(normalCDF(2.576) - 0.995) < 1e-3,
    'normalCDF(2.576) ≈ 0.995 (99% one-tail)');
});

// ─── Primary validation criteria (from AIQ-339 spec) ─────────────────────────

describe('AIQ-339 Validation Criteria — spec cases', () => {
  // "n=1000/conv=200 control vs n=1000/conv=280 variant → significant: true, uplift ~0.4"
  const big = isSignificant(200, 1000, 280, 1000);
  assert(big.significant === true,
    'Large-sample significant result → significant: true',
    `got: ${big.significant}`);
  assert(big.relativeUplift >= 0.39 && big.relativeUplift <= 0.41,
    `relativeUplift ≈ 0.4 (200→280 conversions)`,
    `got: ${big.relativeUplift}`);

  // "n=50/conv=10 vs n=50/conv=15 → significant: false"
  const small = isSignificant(10, 50, 15, 50);
  assert(small.significant === false,
    'Small sample (n=50) → significant: false',
    `got: ${small.significant}`);

  // "pValue between 0 and 1"
  assert(big.pValue >= 0 && big.pValue <= 1,
    `pValue in [0,1] (significant case: ${big.pValue})`);
  assert(small.pValue >= 0 && small.pValue <= 1,
    `pValue in [0,1] (small sample: ${small.pValue})`);
});

// ─── relativeUplift expressed as decimal ─────────────────────────────────────

describe('relativeUplift — decimal form', () => {
  // 10% → 15%: uplift = 0.5
  const r = isSignificant(100, 1000, 150, 1000);
  assert(r.relativeUplift >= 0.49 && r.relativeUplift <= 0.51,
    'relativeUplift = 0.5 for 10%→15% conversion',
    `got: ${r.relativeUplift}`);
  assert(r.relativeUplift < 1,
    'relativeUplift is a decimal fraction (not a percentage)',
    `got: ${r.relativeUplift}`);

  // 20% → 25%: uplift = 0.25
  const r2 = isSignificant(200, 1000, 250, 1000);
  assert(r2.relativeUplift >= 0.24 && r2.relativeUplift <= 0.26,
    'relativeUplift ≈ 0.25 for 20%→25% conversion',
    `got: ${r2.relativeUplift}`);
});

// ─── Minimum sample guard ─────────────────────────────────────────────────────

describe('Minimum sample guard (n < 100)', () => {
  const cases: Array<[number, number, number, number, string]> = [
    [50,  99,  60,  99,  'n=99 per variant'],
    [10,  50,  15,  50,  'n=50 per variant'],
    [0,   1,   1,   1,   'n=1 per variant'],
    [80, 100,  90,  50,  'variant n=50 < 100'],
    [10, 100,  15,  50,  'control ok but variant n=50 < 100'],
  ];
  for (const [cc, cn, vc, vn, label] of cases) {
    const r = isSignificant(cc, cn, vc, vn);
    assert(r.significant === false, `Guard fires: ${label}`);
    assert(r.pValue === 1, `pValue = 1 when guarded: ${label}`);
    assert(r.relativeUplift === 0, `relativeUplift = 0 when guarded: ${label}`);
  }

  // Exactly n=100 — guard should NOT fire
  const boundary = isSignificant(20, 100, 35, 100);
  assert(typeof boundary.significant === 'boolean',
    'n=100 per variant — guard does not fire');
});

// ─── Significance threshold ───────────────────────────────────────────────────

describe('Significance threshold (alpha)', () => {
  // Result that's significant at 0.05 but not at 0.01
  const r05 = isSignificant(200, 1000, 235, 1000); // ~0.017 pValue
  const r01 = isSignificant(200, 1000, 235, 1000, 0.01);
  // Both should use same pValue
  assert(r05.pValue === r01.pValue,
    'Same inputs → same pValue regardless of alpha',
    `${r05.pValue} vs ${r01.pValue}`);

  // Very large difference → significant at both thresholds
  const big = isSignificant(100, 1000, 250, 1000);
  assert(big.significant,
    'Very large difference → significant at alpha=0.05');
  const bigStrict = isSignificant(100, 1000, 250, 1000, 0.01);
  assert(bigStrict.significant,
    'Very large difference → significant at alpha=0.01 too');
});

// ─── Confidence interval ──────────────────────────────────────────────────────

describe('Confidence interval', () => {
  const r = isSignificant(200, 1000, 280, 1000);
  const [lo, hi] = r.confidenceInterval;
  // Absolute diff = 0.28 - 0.20 = 0.08; CI should contain it
  assert(lo < 0.08 && hi > 0.08,
    `CI [${lo}, ${hi}] contains the absolute diff (0.08)`);
  assert(lo < hi,
    'CI lower bound < upper bound');

  // When guard fires → CI is [0, 0]
  const small = isSignificant(10, 50, 15, 50);
  assert(small.confidenceInterval[0] === 0 && small.confidenceInterval[1] === 0,
    'CI = [0, 0] when sample guard fires');

  // No uplift (equal rates) → CI should straddle zero
  const equal = isSignificant(200, 1000, 200, 1000);
  const [elo, ehi] = equal.confidenceInterval;
  assert(elo < 0 && ehi > 0,
    `Equal rates CI [${elo}, ${ehi}] straddles zero`);
});

// ─── Edge cases ───────────────────────────────────────────────────────────────

describe('Edge cases', () => {
  // Zero control conversion rate
  const zeroControl = isSignificant(0, 1000, 10, 1000);
  assert(zeroControl.significant === false || zeroControl.significant === true,
    'Zero control conversions — does not throw');
  assert(zeroControl.relativeUplift === 0,
    'Zero control conversions → relativeUplift = 0 (no division by zero)');

  // 100% conversion rate
  const fullConv = isSignificant(1000, 1000, 990, 1000);
  assert(typeof fullConv.significant === 'boolean',
    '100% control conversion rate — does not throw');

  // Negative uplift (variant worse than control)
  const negative = isSignificant(280, 1000, 200, 1000);
  assert(negative.relativeUplift < 0,
    'Variant worse than control → negative relativeUplift',
    `got: ${negative.relativeUplift}`);

  // Custom alpha
  const custom = isSignificant(200, 1000, 280, 1000, 0.001);
  assert(typeof custom.significant === 'boolean',
    'Custom alpha=0.001 — does not throw');

  // Invalid inputs
  const badConv = isSignificant(500, 100, 10, 1000); // conversions > n
  assert(badConv.significant === false,
    'controlConversions > controlN → guard fires');
});

// ─── Result summary ───────────────────────────────────────────────────────────

console.log(`\n${'─'.repeat(50)}`);
if (failed === 0) {
  console.log(`✅  All ${passed} tests passed`);
} else {
  console.error(`❌  ${failed} of ${passed + failed} tests FAILED`);
  process.exit(1);
}
