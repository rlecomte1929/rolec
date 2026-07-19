/**
 * AIQ-1628: guard against browser passive-autofill residue on a controlled
 * password field.
 *
 * The sign-in password `<input>` is React-controlled (`value={password}`), but a
 * browser's passive autofill can drop a value straight into the DOM *without*
 * firing React's onChange — so `password` state stays "" while the field visually
 * holds a stale password (e.g. the previous persona's, at the dual-persona
 * test-drive switch). Because the field never re-renders (state didn't change),
 * the residue lingers, and the next keystroke *concatenates* onto it
 * (`STALEpass` + `NEWpw` → `STALEpassNEWpw`) — a login that fails looking like a
 * "wrong password". The form also submits `password` *state*, so a desynced
 * autofill can submit an empty password too.
 *
 * Fix: when the controlled state is EMPTY but the DOM input still holds a value,
 * that value is untracked stale residue — clear it so the user types into a clean
 * field. A password-MANAGER fill that the user chose fires onChange (state is
 * non-empty), so this leaves managed fills untouched — we don't break legitimate
 * autofill, we only drop residue React never saw.
 *
 * Returns true iff residue was cleared (useful for tests).
 */
export function clearAutofillResidueIfStale(
  stateValue: string,
  input: HTMLInputElement | null | undefined,
): boolean {
  if (!input) return false;
  if (stateValue) return false; // user/manager-chosen value is tracked in state — keep it
  if (!input.value) return false; // already clean
  input.value = ''; // stale residue React never tracked — clear before the user types
  return true;
}
