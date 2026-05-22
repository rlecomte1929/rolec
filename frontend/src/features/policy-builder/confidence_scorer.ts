/**
 * [P2-4] confidence_scorer.ts
 *
 * Deterministic, rule-based confidence scorer for extracted policy values.
 * No LLM calls — pure TypeScript with regex-based language analysis.
 *
 * Scoring factors (total max = 1.0):
 *   +0.40  Explicit value    — numeric value stated directly, not hedged
 *   +0.20  Tier present      — value associated with a specific tier/grade
 *   +0.20  No conditionals   — no conditional/ambiguity language detected
 *   +0.20  Cross-doc OK      — consistent with (or no) existing stored value
 *
 * Score → action bands:
 *   ≥ 0.90  high         → auto-approve into knowledge base
 *   0.70–0.89 medium     → publish but flag for review at next cycle
 *   0.50–0.69 low        → mandatory HR review before publishing
 *   < 0.50  insufficient → block, return to HR with explanation
 */

// ---------------------------------------------------------------------------
// Input / output types
// ---------------------------------------------------------------------------

/** The output of P2-3 classification for a single extracted fact */
export interface ClassifiedChunk {
  /** Raw text excerpt from the policy document that was classified */
  source_quote: string;
  /** Category code, e.g. 'CAT-01' or 'housing_allowance' */
  category_code: string;
  /** Tier/grade label, e.g. 'Manager', 'Director'; null if not tier-specific */
  tier: string | null;
  /** Extracted structured value from the classification */
  normalized_value: {
    value?: string | number | null;
    currency?: string | null;
    unit?: string | null;
    /** Any condition string extracted, e.g. 'subject to line manager approval' */
    condition?: string | null;
  };
  /** Whether the P2-3 classifier already set an ambiguity flag */
  ambiguity_flag?: boolean;
}

/**
 * Existing stored value for the same (category_code, tier) — used for the
 * cross-document consistency check. Callers are responsible for fetching this
 * from policy_facts / policy_values before calling scoreChunk().
 */
export interface ExistingPolicyValue {
  value: string | number;
  currency?: string | null;
}

export type ConfidenceBand = 'high' | 'medium' | 'low' | 'insufficient';

export interface ScoringResult {
  /** Confidence score in the range [0.0, 1.0], rounded to 2 decimal places */
  score: number;
  /** Human-readable explanation, always ≤ 99 chars */
  reason: string;
  /** Categorical band derived from score */
  band: ConfidenceBand;
  /** Breakdown of each factor's contribution */
  factors: {
    explicit_value: number;     // 0 or 0.40
    tier_present: number;       // 0 or 0.20
    no_conditionals: number;    // 0 or 0.20
    cross_doc_consistent: number; // 0 or 0.20
  };
}

// ---------------------------------------------------------------------------
// Factor 1: Explicit value detection  (+0.40)
// ---------------------------------------------------------------------------

/**
 * Hedge prefixes that negate directness — if the numeric value in the quote is
 * immediately preceded by one of these within a 40-char window, the value is
 * considered inferred/hedged rather than explicit.
 */
const HEDGE_PREFIXES = [
  'up to a maximum of',
  'up to',
  'not more than',
  'not exceeding',
  'approximately',
  'around',
  'about',
  'maximum',
  'max',
] as const;

/**
 * Returns true when the source quote contains a numeric value that is NOT
 * immediately preceded by hedging language.
 *
 * Handles thousand-separator variants: value '3500' matches '3,500' in the quote.
 */
export function hasExplicitValue(chunk: ClassifiedChunk): boolean {
  const { source_quote, normalized_value } = chunk;
  if (normalized_value.value == null || normalized_value.value === '') {
    return false;
  }
  const valueStr = String(normalized_value.value);

  // Build candidate search strings: bare value AND thousand-formatted variants
  const candidates: string[] = [valueStr];
  const numericOnly = valueStr.replace(/[,\s]/g, '');
  if (/^\d{4,}$/.test(numericOnly)) {
    // Format with commas: 3500 → '3,500', 10000 → '10,000'
    const formatted = Number(numericOnly).toLocaleString('en-US');
    if (formatted !== valueStr) candidates.push(formatted);
    // Also try period-separated (European) e.g. '3.500'
    candidates.push(numericOnly.replace(/(\d)(?=(\d{3})+$)/g, '$1.'));
  }

  // Try each candidate; return true if any is found without a preceding hedge
  for (const candidate of candidates) {
    const idx = source_quote.indexOf(candidate);
    if (idx === -1) continue;
    const before = source_quote.slice(Math.max(0, idx - 40), idx).toLowerCase();
    if (!HEDGE_PREFIXES.some((prefix) => before.includes(prefix))) {
      return true;
    }
  }
  return false;
}

// ---------------------------------------------------------------------------
// Factor 3: Conditional language detection  (+0.20)
// ---------------------------------------------------------------------------

const AMBIGUITY_PATTERNS: RegExp[] = [
  /\bup\s+to\b/i,
  /\bapproximately\b/i,
  /\baround\b/i,
  /\bsubject\s+to\b/i,
  /\bat\s+the\s+discretion\s+of\b/i,
  /\bmay\s+be\s+provided\b/i,
  /\bwhere\s+applicable\b/i,
  /\bif\s+applicable\b/i,
  /\bcan\s+be\b/i,
  /\bpossibly\b/i,
  /\bat\s+management\s+discretion\b/i,
  /\bpending\s+approval\b/i,
  /\bsubject\s+to\s+approval\b/i,
];

/** Returns true if the text contains conditional or ambiguous language */
export function hasAmbiguityLanguage(text: string): boolean {
  return AMBIGUITY_PATTERNS.some((re) => re.test(text));
}

// ---------------------------------------------------------------------------
// Factor 4: Cross-document consistency  (+0.20)
// ---------------------------------------------------------------------------

/** Tolerance for numeric comparison: ±2% */
const NUMERIC_TOLERANCE = 0.02;

/**
 * Returns true if the new value is consistent with the existing stored value.
 * - null existingValue → assumed consistent (nothing to contradict)
 * - Numeric: consistent if within ±2% relative difference
 * - String: consistent if normalised lowercase values match
 */
export function isConsistentWithExisting(
  newValue: string | number | null | undefined,
  existing: ExistingPolicyValue | null | undefined,
): boolean {
  if (existing == null || newValue == null) return true;

  const normaliseNum = (v: string | number) =>
    parseFloat(String(v).replace(/[,\s]/g, '').replace(/[^0-9.]/g, ''));

  const a = normaliseNum(newValue);
  const b = normaliseNum(existing.value);

  if (!Number.isNaN(a) && !Number.isNaN(b)) {
    if (b === 0) return a === 0;
    return Math.abs(a - b) / b <= NUMERIC_TOLERANCE;
  }

  // String comparison — normalise whitespace and case
  const normaliseStr = (s: string | number) =>
    String(s).toLowerCase().replace(/\s+/g, ' ').trim();
  return normaliseStr(newValue) === normaliseStr(existing.value);
}

// ---------------------------------------------------------------------------
// Band derivation
// ---------------------------------------------------------------------------

export function scoreToBand(score: number): ConfidenceBand {
  if (score >= 0.90) return 'high';
  if (score >= 0.70) return 'medium';
  if (score >= 0.50) return 'low';
  return 'insufficient';
}

// ---------------------------------------------------------------------------
// Reason builder
// ---------------------------------------------------------------------------

function buildReason(
  factors: ScoringResult['factors'],
  band: ConfidenceBand,
): string {
  const missing: string[] = [];
  if (factors.explicit_value === 0)       missing.push('value not explicit');
  if (factors.tier_present === 0)         missing.push('no tier label');
  if (factors.no_conditionals === 0)      missing.push('conditional language');
  if (factors.cross_doc_consistent === 0) missing.push('conflicts with existing');

  if (missing.length === 0) return 'All scoring factors met';

  const prefix =
    band === 'high'         ? 'High confidence' :
    band === 'medium'       ? 'Medium confidence' :
    band === 'low'          ? 'Low confidence' :
    /* insufficient */        'Insufficient confidence';

  const text = `${prefix}: ${missing.join(', ')}`;
  return text.length <= 99 ? text : text.slice(0, 96) + '…';
}

// ---------------------------------------------------------------------------
// Main scorer
// ---------------------------------------------------------------------------

/**
 * Score a single classified chunk.
 *
 * @param chunk         The classified fact (output of P2-3 classification)
 * @param existingValue Optional: existing stored value for the same
 *                      (category_code, tier) pair. Pass null if no stored value
 *                      exists yet — the cross-doc factor will be awarded.
 * @returns             ScoringResult with score, band, reason, and factor breakdown
 */
export function scoreChunk(
  chunk: ClassifiedChunk,
  existingValue: ExistingPolicyValue | null = null,
): ScoringResult {
  const factors: ScoringResult['factors'] = {
    explicit_value: 0,
    tier_present: 0,
    no_conditionals: 0,
    cross_doc_consistent: 0,
  };

  // Factor 1: Explicit value (+0.40)
  if (hasExplicitValue(chunk)) {
    factors.explicit_value = 0.40;
  }

  // Factor 2: Tier label present (+0.20)
  if (chunk.tier != null && chunk.tier.trim().length > 0) {
    factors.tier_present = 0.20;
  }

  // Factor 3: No conditional language (+0.20)
  const ambiguous =
    chunk.ambiguity_flag === true ||
    hasAmbiguityLanguage(chunk.source_quote) ||
    (chunk.normalized_value.condition != null &&
      hasAmbiguityLanguage(chunk.normalized_value.condition));
  if (!ambiguous) {
    factors.no_conditionals = 0.20;
  }

  // Factor 4: Cross-doc consistency (+0.20)
  if (isConsistentWithExisting(chunk.normalized_value.value, existingValue)) {
    factors.cross_doc_consistent = 0.20;
  }

  const rawScore =
    factors.explicit_value +
    factors.tier_present +
    factors.no_conditionals +
    factors.cross_doc_consistent;

  const score = Math.round(rawScore * 100) / 100;
  const band = scoreToBand(score);
  const reason = buildReason(factors, band);

  return { score, reason, band, factors };
}
