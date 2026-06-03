export const REASON_CODES = [
  'WRONG_PATHWAY',
  'OUTDATED_RULE',
  'MISSING_DEPENDENCY',
  'INCORRECT_FORM',
] as const;

export type ReasonCode = (typeof REASON_CODES)[number];

export const REASON_CODE_OPTIONS: { value: ReasonCode; label: string }[] = [
  { value: 'WRONG_PATHWAY', label: 'Wrong pathway' },
  { value: 'OUTDATED_RULE', label: 'Outdated rule' },
  { value: 'MISSING_DEPENDENCY', label: 'Missing dependency' },
  { value: 'INCORRECT_FORM', label: 'Incorrect form' },
];

export type ReviewDecision = 'approve' | 'reject' | 'edit';

export function confidenceVariant(confidence?: number): 'success' | 'warning' | 'error' | 'neutral' {
  if (confidence == null) return 'neutral';
  if (confidence >= 0.8) return 'success';
  if (confidence >= 0.5) return 'warning';
  return 'error';
}

export function confidenceLabel(confidence?: number): string {
  if (confidence == null) return 'No confidence';
  const pct = Math.round(confidence * 100);
  if (confidence >= 0.8) return `HIGH (${pct}%)`;
  if (confidence >= 0.5) return `MED (${pct}%)`;
  return `LOW (${pct}%)`;
}
