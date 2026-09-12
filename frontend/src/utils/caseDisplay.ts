/**
 * Case-row display helpers (BRAND-4 / BRAND-5).
 *
 * The brand promise is "every relocation case is visible". These helpers keep
 * that promise at the row level even with sparse pre-launch data: lead with a
 * human display name (email only as a genuine fallback) and render intentional
 * muted empty labels instead of "tbd" / bare "-".
 *
 * Shared across the HR Dashboard cases table, the Mobility Control Center
 * "All relocation cases" table, and the Case Detail header.
 */

/** Display name with email fallback. Email is used only when no name exists. */
export function displayNameOrEmail(
  name: string | null | undefined,
  email: string | null | undefined,
): string {
  const n = (name ?? '').trim();
  if (n) return n;
  const e = (email ?? '').trim();
  return e || 'Unnamed case';
}

/**
 * Intentional empty-state label instead of "tbd" / "-". Returns the trimmed
 * value when present, otherwise the human label, plus an `isEmpty` flag so the
 * caller can mute the label (slate-400).
 */
export function orEmptyLabel(
  value: string | null | undefined,
  label: string,
): { text: string; isEmpty: boolean } {
  const v = (value ?? '').trim();
  return v ? { text: v, isEmpty: false } : { text: label, isEmpty: true };
}

/** Destination missing or the case has not left "not started". */
export function isInactiveOrIncompleteCase(assignment: {
  status: string;
  case?: { host_country?: string } | null;
}): boolean {
  const destEmpty = !(assignment.case?.host_country || '').trim();
  const notStarted = assignment.status === 'assigned' || assignment.status === 'created';
  return destEmpty || notStarted;
}
