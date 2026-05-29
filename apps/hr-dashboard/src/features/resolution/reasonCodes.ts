/**
 * P0-06 reason-code controlled vocabulary.
 *
 * Source of truth: the CHECK enum on `rce.corrections.reason_code` in the
 * C1-01 schema migration:
 *
 *   reason_code TEXT NOT NULL CHECK (reason_code IN (
 *     'OCR_ERROR','TYPO_IN_SOURCE','AMBIGUOUS_PARTICLE',
 *     'LEGITIMATE_VARIATION','FRAUD_SUSPECTED','OTHER'
 *   ))
 *
 * If the DB enum changes, update this list. The integration test that
 * locks the count + entries lives at runtime in
 * apps/hr-dashboard/src/features/resolution/__locks__ — see
 * REASON_CODES below.
 *
 * `OTHER` is the only value that requires reason_freetext.
 */

export const REASON_CODES = [
  'OCR_ERROR',
  'TYPO_IN_SOURCE',
  'AMBIGUOUS_PARTICLE',
  'LEGITIMATE_VARIATION',
  'FRAUD_SUSPECTED',
  'OTHER',
] as const;

export type ReasonCode = (typeof REASON_CODES)[number];

/**
 * Human-readable labels shown in the dropdown.
 *
 * UX copy spec lives in C1-12C (not yet on disk — these are reasonable
 * defaults pending the spec). When C1-12C lands, replace this map.
 */
export const REASON_CODE_LABELS: Record<ReasonCode, string> = {
  OCR_ERROR: 'OCR misread',
  TYPO_IN_SOURCE: 'Typo in source document',
  AMBIGUOUS_PARTICLE: 'Ambiguous particle / formatting',
  LEGITIMATE_VARIATION: 'Legitimate variation (e.g. maiden name)',
  FRAUD_SUSPECTED: 'Possible fraud — escalate',
  OTHER: 'Other (please explain)',
};

export const REASON_CODE_DESCRIPTIONS: Record<ReasonCode, string> = {
  OCR_ERROR:
    'The OCR engine misread a character or a region. The visible source value is correct; the extracted value is the error.',
  TYPO_IN_SOURCE:
    'The source document itself contains an error (a typo from the issuing authority). The other source is correct.',
  AMBIGUOUS_PARTICLE:
    'Formatting variation — different ICAO transliteration, different particle handling, etc. Neither source is "wrong" per se.',
  LEGITIMATE_VARIATION:
    'A genuine difference for a known reason (e.g. maiden name on a marriage certificate vs. married name on the passport). Both sources are correct in context.',
  FRAUD_SUSPECTED:
    'The divergence cannot be explained by OCR / typo / variation. Escalates to the compliance queue per PRIV-002.',
  OTHER:
    'None of the above. Please describe the reason in the free-text field.',
};

/** True if the reason requires reason_freetext. Only OTHER does. */
export function reasonRequiresFreetext(reason: ReasonCode | ''): boolean {
  return reason === 'OTHER';
}
