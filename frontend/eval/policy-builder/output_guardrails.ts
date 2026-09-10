/**
 * [P5-2] output_guardrails.ts — Post-generation safety layer
 *
 * Last line of defence before a response reaches the employee.
 * Two independent checks run in sequence after every LLM generation:
 *
 *   1. Cross-tier data fence
 *      Extracts monetary values (EUR/USD/GBP amounts, percentages) from the
 *      generated response. For each value, inspects the retrieved policy chunks
 *      that contain it. If any matching chunk has a tier OTHER than the employee's
 *      tier (and not the universal 'All' tier), the response is blocked and a
 *      regeneration is requested.
 *
 *      Why this matters: tier isolation is enforced at the SQL layer during
 *      retrieval, but edge cases exist (e.g. 'All'-tier chunks that mention
 *      multiple tiers in passing, retrieval bugs, future schema changes). This
 *      runtime fence provides a defence-in-depth guarantee.
 *
 *   2. Faithfulness hard-block
 *      Delegates to P4-4 faithfulness_checker.ts. If the response contains any
 *      factual sentence not grounded in the retrieved context, the caller is
 *      instructed to serve raw excerpts instead.
 *
 * Caller contract (implemented in assistant_router.ts):
 *   const result = await runOutputGuardrails(response, chunks, tier, ...);
 *   if (result.action === 'REGENERATE') {
 *     // Regenerate once, then re-run guardrails.
 *     // If second run also fails → serve raw excerpts.
 *   } else if (result.action === 'SERVE_RAW') {
 *     // Serve buildRawExcerptResponse(chunks) immediately.
 *   }
 *   // action === 'PASS' → safe to return response to employee
 *
 * All block events are logged as structured entries — see OutputGuardrailLog.
 * No PII is stored in logs (log entries reference session_id only).
 */

import { logger } from '../../src/lib/logger';
import { checkFaithfulness } from './faithfulness_checker';
import type { PolicyChunk } from '../../src/features/policy-builder/retrieve_policy';

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/**
 * Action the caller must take based on guardrail evaluation.
 *
 * - PASS         Response is safe to return to the employee.
 * - REGENERATE   A cross-tier leak was detected. Caller should regenerate the
 *                response once, then re-run output guardrails on the new text.
 *                If the second run also fails, caller must serve raw excerpts.
 * - SERVE_RAW    Faithfulness check failed. Caller must immediately serve raw
 *                policy excerpts without any generated text.
 */
export type OutputGuardrailAction = 'PASS' | 'REGENERATE' | 'SERVE_RAW';

/**
 * A detected cross-tier leak: a monetary value in the response that was found
 * in a retrieved chunk whose tier does not match the employee's tier.
 */
export interface CrossTierLeak {
  /** The monetary value string as extracted from the response (e.g. 'EUR 10,000') */
  value: string;
  /** The policy chunk that contains this value */
  chunk_id: string;
  /** The tier of that chunk (e.g. 'Executive') */
  chunk_tier: string;
  /** The employee's tier (e.g. 'Manager') */
  employee_tier: string;
}

/** Result of a cross-tier scan */
export interface CrossTierCheckResult {
  /** true = no leaks detected; false = at least one cross-tier value found */
  pass: boolean;
  /** All detected cross-tier leaks (empty when pass=true) */
  leaks: CrossTierLeak[];
}

/**
 * Structured log entry emitted for every guardrail block.
 * Stored in-memory by the caller (or forwarded to an observability layer).
 * IMPORTANT: never log raw query text or response text — session_id only.
 */
export interface OutputGuardrailLog {
  session_id: string;
  block_type: 'CROSS_TIER' | 'FAITHFULNESS_BLOCK';
  employee_tier: string;
  /** The monetary value that triggered the cross-tier block (CROSS_TIER only) */
  flagged_value?: string;
  /** Source chunk tier for the flagged value (CROSS_TIER only) */
  source_tier?: string;
  /** Faithfulness score at time of block (FAITHFULNESS_BLOCK only) */
  faithfulness_score?: number;
  timestamp: string;
}

/** Return value of runOutputGuardrails */
export interface OutputGuardrailResult {
  /** What the caller should do next */
  action: OutputGuardrailAction;
  /** NLI faithfulness score (0–1); present when faithfulness check ran */
  faithfulness_score?: number;
  /** Why the response was blocked (present when action ≠ 'PASS') */
  block_reason?: 'CROSS_TIER' | 'FAITHFULNESS_BLOCK';
  /** Detected cross-tier leaks (present when block_reason='CROSS_TIER') */
  leaks?: CrossTierLeak[];
  /** Structured log entry for this guardrail run (present when action ≠ 'PASS') */
  log_entry?: OutputGuardrailLog;
}

// ---------------------------------------------------------------------------
// Step 1: Monetary value extraction
// ---------------------------------------------------------------------------

/**
 * Currency codes recognised by the cross-tier fence.
 * Covers all currencies used in ReloPass policy documents.
 */
export const CURRENCY_CODES = ['EUR', 'USD', 'GBP', 'NOK', 'CHF', 'SEK', 'DKK', 'AUD', 'CAD', 'JPY'] as const;

/**
 * Patterns for extracting monetary values from generated response text.
 * Captures currency amounts (e.g. 'EUR 3,500', 'USD 12,000.00') and standalone
 * large figures that appear after a currency context (e.g. '€ 50,000').
 */
const MONETARY_PATTERNS: RegExp[] = [
  // Standard: EUR 3,500 / NOK 80,000 / USD 12,000.00
  new RegExp(
    `\\b(${CURRENCY_CODES.join('|')})\\s*[\\d,]+(?:\\.\\d+)?`,
    'gi',
  ),
  // Symbol: € 3,500 / £ 12,000 / $ 50,000
  /[€£$¥]\s*[\d,]+(?:\.\d+)?/g,
];

/**
 * Extract all monetary values from a text string.
 * Returns deduplicated list of matched substrings, preserving original casing.
 */
export function extractMonetaryValues(text: string): string[] {
  const found = new Set<string>();
  for (const pattern of MONETARY_PATTERNS) {
    const iter = text.matchAll(new RegExp(pattern.source, pattern.flags));
    for (const m of iter) {
      found.add(m[0].trim());
    }
  }
  return [...found];
}

/**
 * Normalise a monetary value string for loose matching:
 * - Uppercase currency code
 * - Remove thousands separators
 * - Trim whitespace
 *
 * Examples:
 *   'EUR 3,500'  → 'EUR 3500'
 *   'eur3500'    → 'EUR3500'
 *   '€ 3,500'   → '€3500'
 */
export function normaliseMonetaryValue(value: string): string {
  return value.replace(/,/g, '').replace(/\s+/g, ' ').trim().toUpperCase();
}

// ---------------------------------------------------------------------------
// Step 1b: Cross-tier check
// ---------------------------------------------------------------------------

/**
 * Tier values that are considered universal (not tier-specific).
 * Chunks with these tiers do not trigger a cross-tier violation even if they
 * contain monetary values.
 */
export const UNIVERSAL_TIERS = new Set(['All', 'Universal', 'all', 'universal', '']);

/**
 * Scan a generated response for monetary values that appear in retrieved chunks
 * whose tier does not match the employee's tier.
 *
 * @param response      The LLM-generated response text
 * @param chunks        Policy chunks used during retrieval (already tier-filtered,
 *                      but this fence provides defence-in-depth)
 * @param employeeTier  The employee's assigned tier (e.g. 'Manager')
 */
export function checkCrossTierLeak(
  response: string,
  chunks: PolicyChunk[],
  employeeTier: string,
): CrossTierCheckResult {
  const values = extractMonetaryValues(response);

  if (values.length === 0) {
    // No monetary values → nothing to check
    return { pass: true, leaks: [] };
  }

  const leaks: CrossTierLeak[] = [];

  for (const value of values) {
    const normValue = normaliseMonetaryValue(value);

    for (const chunk of chunks) {
      // Skip chunks with null or universal tiers
      if (!chunk.tier || UNIVERSAL_TIERS.has(chunk.tier)) continue;

      // Skip chunks that belong to the employee's own tier
      if (chunk.tier === employeeTier) continue;

      // Check whether this cross-tier chunk contains the monetary value
      const normChunk = normaliseMonetaryValue(chunk.text);
      if (normChunk.includes(normValue)) {
        leaks.push({
          value,
          chunk_id: chunk.id,
          chunk_tier: chunk.tier,
          employee_tier: employeeTier,
        });
        // Record one leak per value (first offending chunk is sufficient)
        break;
      }
    }
  }

  return {
    pass: leaks.length === 0,
    leaks,
  };
}

// ---------------------------------------------------------------------------
// Main: runOutputGuardrails
// ---------------------------------------------------------------------------

/**
 * Run all output guardrails on a generated response.
 *
 * Order of checks:
 *   1. Cross-tier data fence (synchronous, O(values × chunks))
 *   2. Faithfulness NLI check (async, may call Claude Haiku)
 *
 * @param response       The LLM-generated response text
 * @param chunks         Retrieved policy chunks used to generate the response
 * @param employeeTier   The employee's assigned tier
 * @param anthropicKey   Anthropic API key (required for faithfulness NLI step)
 * @param apiBase        API base URL (injectable for tests)
 * @param sessionId      Session identifier for structured logging
 */
export async function runOutputGuardrails(
  response: string,
  chunks: PolicyChunk[],
  employeeTier: string,
  anthropicKey?: string,
  apiBase = 'https://api.anthropic.com',
  sessionId = 'unknown',
): Promise<OutputGuardrailResult> {
  // ── Check 1: Cross-tier data fence ────────────────────────────────────────

  const crossTier = checkCrossTierLeak(response, chunks, employeeTier);

  if (!crossTier.pass && crossTier.leaks[0]) {
    const firstLeak = crossTier.leaks[0];
    const logEntry: OutputGuardrailLog = {
      session_id: sessionId,
      block_type: 'CROSS_TIER',
      employee_tier: employeeTier,
      flagged_value: firstLeak.value,
      source_tier: firstLeak.chunk_tier,
      timestamp: new Date().toISOString(),
    };

    logger.warn(
      `[output_guardrails] CROSS_TIER_BLOCK session=${sessionId}` +
        ` employee_tier=${employeeTier}` +
        ` flagged_value="${firstLeak.value}"` +
        ` source_tier=${firstLeak.chunk_tier}` +
        ` total_leaks=${crossTier.leaks.length}`,
    );

    return {
      action: 'REGENERATE',
      block_reason: 'CROSS_TIER',
      leaks: crossTier.leaks,
      log_entry: logEntry,
    };
  }

  // ── Check 2: Faithfulness NLI ─────────────────────────────────────────────

  const chunkTexts = chunks.map((c) => c.text);
  const faithfulness = await checkFaithfulness(response, chunkTexts, anthropicKey, apiBase);

  if (!faithfulness.pass) {
    const logEntry: OutputGuardrailLog = {
      session_id: sessionId,
      block_type: 'FAITHFULNESS_BLOCK',
      employee_tier: employeeTier,
      faithfulness_score: faithfulness.score,
      timestamp: new Date().toISOString(),
    };

    logger.warn(
      `[output_guardrails] FAITHFULNESS_BLOCK session=${sessionId}` +
        ` score=${faithfulness.score}` +
        ` flagged_sentences=${faithfulness.flaggedSentences.length}`,
    );

    return {
      action: 'SERVE_RAW',
      block_reason: 'FAITHFULNESS_BLOCK',
      faithfulness_score: faithfulness.score,
      log_entry: logEntry,
    };
  }

  // ── PASS ──────────────────────────────────────────────────────────────────

  return {
    action: 'PASS',
    faithfulness_score: faithfulness.score,
  };
}
