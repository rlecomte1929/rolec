/**
 * [P2-05a] successProbability.ts
 *
 * Pure, deterministic scoring function for the roadmap "probability of success"
 * estimate. Combines the per-step confidence of a case roadmap (the P0-08 /
 * P2-01b ConfidenceLevel taxonomy: high | medium | low | unknown) with an
 * optional historical outcome adjustment for similar-profile cases.
 *
 * The score is intentionally framed as an estimate of *process complexity*, not
 * a legal guarantee — see DISCLAIMER builders below. It is rounded to the
 * nearest 5% to avoid false precision (a hard constraint from the task).
 *
 * Model (a weighted product of per-step confidence scores):
 *   base = Π  CONFIDENCE_VALUE[step.confidence] ^ step.weight
 * Each step contributes a multiplicative factor < 1; lower confidence drags the
 * product down. A clean, all-HIGH roadmap stays in the 90s; any LOW/UNKNOWN
 * steps pull it toward the amber/red bands.
 *
 * Historical adjustment (only when caseHistory is non-empty — "platform_data"):
 *   blended = base * (1 - HISTORY_WEIGHT) + observedSuccessRate * HISTORY_WEIGHT
 * With no history (the common case today) the basis is "official_only" and the
 * score is the confidence-only base.
 *
 * This module is deliberately self-contained (it does not import RoadmapStep)
 * so it can be unit-tested in isolation and reused by any caller that can map
 * its steps to a ConfidenceLevel.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Per-step confidence taxonomy, mirroring the roadmap confidence gate (P2-01b). */
export type ConfidenceLevel = 'high' | 'medium' | 'low' | 'unknown';

/** A roadmap step reduced to what scoring needs. */
export interface ScoringStep {
  /** Stable identifier, surfaced back in factors so the UI can link to the step. */
  id: string;
  /** Human-readable step title, used to build factor labels. */
  title: string;
  /** Per-step confidence. Absent/unrecognised values are treated as 'unknown'. */
  confidence: ConfidenceLevel;
  /**
   * Relative weight (exponent) for this step's contribution. Defaults to 1.
   * A higher weight makes a low-confidence step penalise the score more.
   */
  weight?: number;
}

/** The scoring input: the steps of a case roadmap. */
export interface ScoringRoadmap {
  steps: ScoringStep[];
}

/** A single historical outcome for a similar-profile case (P1-07 / P2-04). */
export interface CaseOutcome {
  outcome: 'approved' | 'rejected' | 'withdrawn';
}

/** Whether the score leans on official rules only, or also on platform history. */
export type ConfidenceBasis = 'official_only' | 'platform_data';

/** One line in the "Factors affecting your score" panel. */
export interface ScoreFactor {
  /** Step id when the factor derives from a specific step; omitted for aggregate factors. */
  stepId?: string;
  /** Short label, e.g. "Tax registration — LOW confidence". */
  label: string;
  /** Signed percentage-point impact, e.g. -15 or +0. */
  impactPct: number;
  /** Whether this factor raises, lowers, or is neutral to the score. */
  direction: 'raises' | 'lowers' | 'neutral';
  /** One-sentence explanation for the user. */
  detail: string;
}

/** The full result returned by {@link successProbability}. */
export interface SuccessProbabilityResult {
  /** Probability of success, 0–100, rounded to the nearest 5%. */
  scorePct: number;
  /** Basis the score was computed from. */
  confidenceBasis: ConfidenceBasis;
  /** Ordered factors (most impactful first) for the transparency panel. */
  factors: ScoreFactor[];
  /** Mandatory, non-removable disclaimer text. Always non-empty. */
  disclaimer: string;
  /** Number of similar historical cases used in the adjustment (0 = official_only). */
  sampleSize: number;
}

// ---------------------------------------------------------------------------
// Calibration constants
// ---------------------------------------------------------------------------

/**
 * Per-step multiplicative confidence value. Calibrated so that:
 *   - a clean, all-HIGH roadmap scores ≥ 90% (e.g. France→Norway EEA), and
 *   - a roadmap with several LOW/UNKNOWN steps drops below 60%.
 * Locked by successProbability.test.ts — change with the tests, not in isolation.
 */
export const CONFIDENCE_VALUE: Record<ConfidenceLevel, number> = {
  high: 0.99,
  medium: 0.93,
  low: 0.85,
  unknown: 0.75,
};

/** Weight given to historical outcome rate when platform data is available. */
export const HISTORY_WEIGHT = 0.3;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function normaliseLevel(level: unknown): ConfidenceLevel {
  return level === 'high' || level === 'medium' || level === 'low' ? level : 'unknown';
}

/** Round to the nearest 5, clamped to [0, 100]. */
function roundTo5(pct: number): number {
  const clamped = Math.max(0, Math.min(100, pct));
  return Math.round(clamped / 5) * 5;
}

const LEVEL_LABEL: Record<ConfidenceLevel, string> = {
  high: 'HIGH',
  medium: 'MEDIUM',
  low: 'LOW',
  unknown: 'UNKNOWN',
};

function buildDisclaimer(sampleSize: number): string {
  if (sampleSize > 0) {
    const plural = sampleSize === 1 ? 'case' : 'cases';
    return (
      `This is an estimate of process complexity based on ${sampleSize} similar ${plural}. ` +
      'It is not a legal guarantee of outcome. Immigration authorities exercise discretion.'
    );
  }
  // No historical data yet (official_only): keep the mandatory non-guarantee +
  // discretion language without claiming "0 similar cases".
  return (
    'This is an estimate of process complexity based on the official requirements for your corridor. ' +
    'It is not a legal guarantee of outcome. Immigration authorities exercise discretion.'
  );
}

// ---------------------------------------------------------------------------
// Main function
// ---------------------------------------------------------------------------

/**
 * Compute the probability-of-success estimate for a case roadmap.
 *
 * @param roadmap     The case roadmap, reduced to steps carrying a ConfidenceLevel.
 * @param caseHistory Outcomes of similar-profile cases. Empty → "official_only".
 * @returns           {@link SuccessProbabilityResult} with score, basis, factors, disclaimer.
 */
export function successProbability(
  roadmap: ScoringRoadmap,
  caseHistory: CaseOutcome[] = [],
): SuccessProbabilityResult {
  const steps = roadmap?.steps ?? [];
  const sampleSize = caseHistory.length;
  const hasHistory = sampleSize > 0;
  const confidenceBasis: ConfidenceBasis = hasHistory ? 'platform_data' : 'official_only';

  // --- Base: weighted product of per-step confidence values --------------
  let base = 1;
  for (const step of steps) {
    const level = normaliseLevel(step.confidence);
    const weight = step.weight != null && step.weight > 0 ? step.weight : 1;
    base *= Math.pow(CONFIDENCE_VALUE[level], weight);
  }
  // An empty roadmap carries no information — treat as fully unknown rather
  // than a misleading 100%.
  if (steps.length === 0) base = CONFIDENCE_VALUE.unknown;

  // --- Historical adjustment --------------------------------------------
  let blended = base;
  let historicalRate: number | null = null;
  if (hasHistory) {
    const approved = caseHistory.filter((c) => c.outcome === 'approved').length;
    historicalRate = approved / sampleSize;
    blended = base * (1 - HISTORY_WEIGHT) + historicalRate * HISTORY_WEIGHT;
  }

  const scorePct = roundTo5(blended * 100);

  // --- Factors -----------------------------------------------------------
  const factors: ScoreFactor[] = [];
  for (const step of steps) {
    const level = normaliseLevel(step.confidence);
    // Marginal drag of this step vs. an ideal HIGH-confidence step.
    const impactPct = Math.round((CONFIDENCE_VALUE[level] - CONFIDENCE_VALUE.high) * 100);
    if (level === 'high') {
      factors.push({
        stepId: step.id,
        label: `${step.title} — HIGH confidence`,
        impactPct: 0,
        direction: 'raises',
        detail: 'Backed by an official source with no known exceptions for your profile.',
      });
    } else {
      factors.push({
        stepId: step.id,
        label: `${step.title} — ${LEVEL_LABEL[level]} confidence`,
        impactPct,
        direction: 'lowers',
        detail:
          level === 'unknown'
            ? 'No verified official source was found for this step, so it carries the most uncertainty.'
            : `Confidence is ${LEVEL_LABEL[level].toLowerCase()} for this step, which lowers the overall estimate.`,
      });
    }
  }

  if (hasHistory && historicalRate != null) {
    const approvedPct = Math.round(historicalRate * 100);
    factors.push({
      label: `Historical outcomes — ${approvedPct}% approved across ${sampleSize} similar ${
        sampleSize === 1 ? 'case' : 'cases'
      }`,
      impactPct: Math.round((blended - base) * 100),
      direction: historicalRate >= base ? 'raises' : 'lowers',
      detail: 'Adjusted using anonymised outcomes of cases with a similar profile and corridor.',
    });
  }

  // Most impactful first; raises/neutral after lowers of equal magnitude.
  factors.sort((a, b) => Math.abs(b.impactPct) - Math.abs(a.impactPct));

  return {
    scorePct,
    confidenceBasis,
    factors,
    disclaimer: buildDisclaimer(sampleSize),
    sampleSize,
  };
}
