/**
 * [P5-1] input_guardrails.ts — Input sanitisation and scope enforcement
 *
 * Runs before any LLM call to:
 *   1. Strip PII (phone numbers, IBANs, passport numbers, SSNs, ID numbers)
 *   2. Detect escalation-trigger language and attach the escalation footer
 *   3. Enforce topic scope via the topic_classifier (reject off_topic; flag borderline)
 *
 * Audit logging records {session_id, trigger_type, timestamp} — NEVER raw query text.
 */

import { classifyQuery, REJECTION_MSG } from './topic_classifier';
import { logger } from '../../lib/logger';

// ---------------------------------------------------------------------------
// Public constants
// ---------------------------------------------------------------------------

export const ESCALATION_FOOTER =
  'For matters involving a personal commitment or dispute, please consult your HR Business Partner directly. ' +
  'Policy information provided here reflects published guidelines only.';

// ---------------------------------------------------------------------------
// PII patterns
// ---------------------------------------------------------------------------

/**
 * Named PII pattern definitions.
 * Flags are stripped here — `scanAndRedactPii` resets them on each call
 * to avoid lastIndex statefulness bugs with /g regexes.
 */
export const PII_PATTERNS: Record<string, RegExp> = {
  PHONE:     /\+?\d[\d\s\-().]{7,15}\d/g,
  IBAN:      /[A-Z]{2}\d{2}[A-Z0-9]{4,30}/g,
  PASSPORT:  /[A-Z]{1,2}\d{6,9}/g,
  SSN:       /\d{3}-\d{2}-\d{4}/g,
  ID_NUMBER: /\b\d{8,12}\b/g,
};

const PII_REPLACEMENTS: Record<string, string> = {
  PHONE:     '[PHONE_REDACTED]',
  IBAN:      '[IBAN_REDACTED]',
  PASSPORT:  '[PASSPORT_REDACTED]',
  SSN:       '[SSN_REDACTED]',
  ID_NUMBER: '[ID_REDACTED]',
};

/**
 * Application order: more-specific patterns first to prevent false positives.
 * SSN and IBAN are matched before the generic ID_NUMBER / PASSPORT patterns
 * that could otherwise consume digits that belong to a more specific token.
 */
const PII_SCAN_ORDER = ['SSN', 'IBAN', 'PASSPORT', 'PHONE', 'ID_NUMBER'] as const;

// ---------------------------------------------------------------------------
// Escalation keywords (lower-cased for comparison)
// ---------------------------------------------------------------------------

const ESCALATION_KEYWORDS: readonly string[] = [
  'i was promised',
  'my contract says',
  'want to escalate',
  "i'm entitled to",
  'they told me',
  'legal action',
  'dispute',
];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PiiScanResult {
  sanitized: string;
  /** PII type names that were detected and redacted */
  detected_types: string[];
}

export interface EscalationScanResult {
  triggered: boolean;
  matched_keywords: string[];
}

export interface GuardrailResult {
  /** Whether the query may proceed to the LLM */
  safe: boolean;
  /** PII-stripped version of the original query */
  sanitized_query: string;
  pii_detected: boolean;
  pii_types: string[];
  escalation_triggered: boolean;
  /**
   * Appended to the assistant's response when escalation language is detected.
   * Always equals the exported ESCALATION_FOOTER constant.
   */
  escalation_footer?: string;
  /**
   * Set when topic_classifier returns 'off_topic'.
   * Always equals the hardcoded REJECTION_MSG — never LLM-generated.
   */
  topic_rejection?: string;
  /**
   * Set when topic_classifier returns 'borderline'.
   * Contains a clarification prompt; query is still forwarded (safe=true).
   */
  topic_clarification?: string;
  /** SHA-256 truncated hash of the original (pre-redaction) query, for logging */
  query_hash: string;
}

export interface GuardrailOptions {
  /** Caller-provided session identifier for audit logs */
  session_id?: string;
  /** Anthropic API key forwarded to topic_classifier */
  anthropic_key?: string;
  /**
   * Skip topic classification (e.g. in unit tests that have no API key).
   * When true, the result is always treated as hr_policy scope.
   */
  skip_topic_check?: boolean;
}

// ---------------------------------------------------------------------------
// Audit logging — no raw query text
// ---------------------------------------------------------------------------

type TriggerType =
  | 'PII_DETECTED'
  | 'ESCALATION_TRIGGERED'
  | 'TOPIC_REJECTED'
  | 'TOPIC_BORDERLINE';

function auditLog(entry: {
  session_id: string | undefined;
  trigger_type: TriggerType;
  timestamp: string;
}): void {
  logger.log(
    `[input_guardrails] session=${entry.session_id ?? 'unknown'} ` +
    `trigger=${entry.trigger_type} ts=${entry.timestamp}`,
  );
}

// ---------------------------------------------------------------------------
// PII scanning
// ---------------------------------------------------------------------------

/**
 * Scan `query` for PII and return a sanitised copy with tokens replaced.
 *
 * Each PII type's pattern is cloned fresh on every call (resetting lastIndex)
 * to avoid the statefulness pitfall of global regexes reused across calls.
 */
export function scanAndRedactPii(query: string): PiiScanResult {
  const detected_types: string[] = [];
  let sanitized = query;

  for (const name of PII_SCAN_ORDER) {
    // Clone to get a fresh lastIndex each time
    const pattern = new RegExp(PII_PATTERNS[name].source, 'g');
    if (pattern.test(sanitized)) {
      detected_types.push(name);
      const replacePattern = new RegExp(PII_PATTERNS[name].source, 'g');
      sanitized = sanitized.replace(replacePattern, PII_REPLACEMENTS[name]);
    }
  }

  return { sanitized, detected_types };
}

// ---------------------------------------------------------------------------
// Escalation detection
// ---------------------------------------------------------------------------

/**
 * Check whether `query` contains escalation-trigger language.
 * Matching is case-insensitive. Returns all matched keywords.
 */
export function scanForEscalation(query: string): EscalationScanResult {
  const lower = query.toLowerCase();
  const matched_keywords = ESCALATION_KEYWORDS.filter((kw) => lower.includes(kw));
  return {
    triggered: matched_keywords.length > 0,
    matched_keywords,
  };
}

// ---------------------------------------------------------------------------
// Main guardrail pipeline
// ---------------------------------------------------------------------------

/**
 * Run all input guardrails against a raw query.
 *
 * Steps (in order):
 *   1. Redact PII from the query text.
 *   2. Detect escalation-trigger language (on the original, pre-redaction text).
 *   3. Classify topic scope via topic_classifier (unless skip_topic_check=true).
 *
 * Escalation does NOT block the query — it attaches ESCALATION_FOOTER so the
 * caller can append it to the assistant's eventual response.
 *
 * A query is "safe" (may proceed to the LLM) unless the topic classifier
 * returns 'off_topic'.
 */
export async function runGuardrails(
  rawQuery: string,
  options: GuardrailOptions = {},
): Promise<GuardrailResult> {
  const { session_id, anthropic_key, skip_topic_check = false } = options;
  const now = new Date().toISOString();

  // -- Step 1: PII redaction ---------------------------------------------------
  const { sanitized, detected_types: pii_types } = scanAndRedactPii(rawQuery);

  if (pii_types.length > 0) {
    auditLog({ session_id, trigger_type: 'PII_DETECTED', timestamp: now });
  }

  // -- Step 2: Escalation detection -------------------------------------------
  // Run on the original query so redacted placeholders don't interfere.
  const { triggered: escalation_triggered } = scanForEscalation(rawQuery);

  if (escalation_triggered) {
    auditLog({ session_id, trigger_type: 'ESCALATION_TRIGGERED', timestamp: now });
  }

  // -- Step 3: Topic classification -------------------------------------------
  let query_hash = 'skipped';
  let topic_rejection: string | undefined;
  let topic_clarification: string | undefined;
  let safe = true;

  if (!skip_topic_check) {
    // Pass the sanitized query to the classifier (PII already stripped)
    const classification = await classifyQuery(
      sanitized.trim() !== '' ? sanitized : rawQuery,
      anthropic_key,
    );
    query_hash = classification.query_hash;

    if (classification.category === 'off_topic') {
      safe = false;
      topic_rejection = classification.rejection_reason ?? REJECTION_MSG;
      auditLog({ session_id, trigger_type: 'TOPIC_REJECTED', timestamp: now });
    } else if (classification.category === 'borderline') {
      // Borderline: allow but surface a clarification prompt
      topic_clarification = classification.clarification_prompt;
      auditLog({ session_id, trigger_type: 'TOPIC_BORDERLINE', timestamp: now });
    }
  }

  // -- Assemble result --------------------------------------------------------
  const result: GuardrailResult = {
    safe,
    sanitized_query: sanitized,
    pii_detected: pii_types.length > 0,
    pii_types,
    escalation_triggered,
    query_hash,
  };

  if (escalation_triggered) {
    result.escalation_footer = ESCALATION_FOOTER;
  }
  if (topic_rejection !== undefined) {
    result.topic_rejection = topic_rejection;
  }
  if (topic_clarification !== undefined) {
    result.topic_clarification = topic_clarification;
  }

  return result;
}
