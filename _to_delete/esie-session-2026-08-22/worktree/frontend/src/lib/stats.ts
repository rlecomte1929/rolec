/**
 * stats.ts — PRODUCT-6C
 *
 * A/B testing statistical significance library.
 * Pure TypeScript — no external dependencies.
 * Works in browser, Node.js, and Deno/Edge runtimes.
 *
 * Implements a two-proportion z-test for determining
 * whether an A/B variant difference is statistically significant.
 */

// ─── Types ────────────────────────────────────────────────────────────────────

export interface SignificanceResult {
  /** Whether the result clears the significance threshold (p < alpha) */
  significant: boolean;
  /** Two-tailed p-value in [0, 1] */
  pValue: number;
  /** Relative uplift of variant vs control, expressed as decimal (0.12 = 12%) */
  relativeUplift: number;
  /** 95% confidence interval around the absolute conversion rate difference */
  confidenceInterval: [number, number];
}

// ─── Constants ────────────────────────────────────────────────────────────────

/** Minimum sample size per variant before we attempt inference. */
const MIN_SAMPLE_SIZE = 100;

// ─── Normal CDF ───────────────────────────────────────────────────────────────

/**
 * Approximation of the cumulative distribution function of the
 * standard normal distribution N(0,1) using Abramowitz & Stegun
 * rational approximation (formula 26.2.17, max error ≤ 7.5×10⁻⁸).
 *
 * @param z  Standard normal deviate
 * @returns  P(Z ≤ z)
 */
export function normalCDF(z: number): number {
  if (z <= -8) return 0;
  if (z >=  8) return 1;

  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const poly =
    t * (0.319381530 +
    t * (-0.356563782 +
    t * (1.781477937 +
    t * (-1.821255978 +
    t *  1.330274429))));

  const pdf = Math.exp(-0.5 * z * z) / Math.sqrt(2 * Math.PI);
  const cdf = 1 - pdf * poly;

  return z >= 0 ? cdf : 1 - cdf;
}

// ─── Main export ──────────────────────────────────────────────────────────────

/**
 * Two-proportion z-test for A/B experiment results.
 *
 * @param controlConversions   Number of conversions in the control group
 * @param controlN             Total users in the control group
 * @param variantConversions   Number of conversions in the variant group
 * @param variantN             Total users in the variant group
 * @param alpha                Significance level (default 0.05 → 95% confidence)
 *
 * @returns SignificanceResult — always returns a valid object; never throws.
 *
 * @example
 * // Significant result
 * isSignificant(200, 1000, 280, 1000)
 * // → { significant: true, pValue: 0.000…, relativeUplift: 0.4, … }
 *
 * // Small sample → not significant
 * isSignificant(10, 50, 15, 50)
 * // → { significant: false, pValue: 1, relativeUplift: 0, confidenceInterval: [0, 0] }
 */
export function isSignificant(
  controlConversions: number,
  controlN: number,
  variantConversions: number,
  variantN: number,
  alpha = 0.05,
): SignificanceResult {
  const notSignificant: SignificanceResult = {
    significant: false,
    pValue: 1,
    relativeUplift: 0,
    confidenceInterval: [0, 0],
  };

  // ── Guard: minimum sample size ──────────────────────────────────────────────
  if (
    controlN < MIN_SAMPLE_SIZE ||
    variantN  < MIN_SAMPLE_SIZE ||
    controlConversions < 0     ||
    variantConversions < 0     ||
    controlConversions > controlN ||
    variantConversions > variantN
  ) {
    return notSignificant;
  }

  const pControl = controlConversions / controlN;
  const pVariant = variantConversions  / variantN;

  // ── Relative uplift ─────────────────────────────────────────────────────────
  const relativeUplift = pControl === 0
    ? 0
    : (pVariant - pControl) / pControl;

  // ── Pooled proportion & standard error ─────────────────────────────────────
  const pPooled = (controlConversions + variantConversions) / (controlN + variantN);
  const se = Math.sqrt(pPooled * (1 - pPooled) * (1 / controlN + 1 / variantN));

  if (se === 0) return notSignificant;

  // ── Z-score & two-tailed p-value ────────────────────────────────────────────
  const z = (pVariant - pControl) / se;
  const pValue = 2 * (1 - normalCDF(Math.abs(z)));

  // ── 95% confidence interval on the absolute rate difference ─────────────────
  // Uses unpooled SE for the CI (standard practice)
  const seUnpooled = Math.sqrt(
    pControl * (1 - pControl) / controlN +
    pVariant * (1 - pVariant) / variantN,
  );
  const zCritical = 1.959964; // z_{0.025} for 95% CI
  const diff = pVariant - pControl;
  const margin = zCritical * seUnpooled;

  const confidenceInterval: [number, number] = [
    Math.round((diff - margin) * 1e6) / 1e6,
    Math.round((diff + margin) * 1e6) / 1e6,
  ];

  return {
    significant: pValue < alpha,
    pValue:      Math.round(pValue  * 1e8) / 1e8,
    relativeUplift: Math.round(relativeUplift * 1e6) / 1e6,
    confidenceInterval,
  };
}
