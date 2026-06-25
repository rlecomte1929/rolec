/**
 * Pure intake-draft hydration helpers, extracted from EmployeeIntakePage so the
 * restore-on-reload behaviour can be unit-tested without mounting the whole
 * wizard (which pulls in contexts, the API client, and country/city data).
 *
 * These back the "fill steps 1–2 → reload → assert all fields + step persisted"
 * contract: `mergeIntakeDraft` is the field-restore logic and `clampIntakeStep`
 * is the step-restore logic that the wizard runs on mount.
 */

/**
 * Merge a saved draft (from GET /api/employee/assignments/{id}/intake) back into
 * the current form state. A field receives its saved value unless the user has
 * actively edited it during the brief hydration window — detected by comparing
 * the current value against the initial default: a field that still equals its
 * default is untouched and gets the saved value; genuinely empty fields always
 * do too. Fields with NON-empty defaults (e.g. `purpose='Employment'`, `members`)
 * are restored on this path — the previous isEmpty-only check silently dropped
 * them on reload.
 */
export function mergeIntakeDraft<T extends object>(
  current: T,
  savedDraft: Record<string, unknown>,
  initialData: T,
): T {
  const merged = { ...current } as Record<string, unknown>;
  for (const [key, value] of Object.entries(savedDraft)) {
    const cur = merged[key];
    const initialDefault = (initialData as Record<string, unknown>)[key];
    const isStillDefault = JSON.stringify(cur) === JSON.stringify(initialDefault);
    const isEmpty =
      cur === '' ||
      cur === null ||
      cur === undefined ||
      (Array.isArray(cur) && cur.length === 0);
    if (isEmpty || isStillDefault) merged[key] = value;
  }
  return merged as T;
}

/**
 * Restore the saved step counter, clamped into the valid [1, totalSteps] range
 * so a stale/out-of-range persisted value can never strand the user on a
 * non-existent step.
 */
export function clampIntakeStep(saved: number, totalSteps: number): number {
  return Math.min(Math.max(saved, 1), totalSteps);
}
