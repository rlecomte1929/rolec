/**
 * adminSidebarLayout — per-admin customisation of the Admin sidebar section.
 *
 * Lets an admin reorder tabs, move them between sub-groups, and rename groups. The
 * override is stored in localStorage (per browser), mirroring the existing
 * `platform_sidebar_collapsed` / `platform_sidebar_sections_v1` pattern in
 * PlatformShellSidebar. It is reconciled against the code-defined items on every load
 * so it survives tabs being added/removed in code.
 *
 * Model: an ordered list of { id, group }. Order drives both position and (via the
 * existing group-boundary renderer) the sub-group headings. Groups are kept contiguous
 * by the editor (each dragged item adopts its new neighbour's group), so a group is
 * always a single run — which is what makes rename map cleanly.
 */

export type AdminLayoutEntry = { id: string; group: string };

const LAYOUT_KEY = 'admin_sidebar_layout_v1';

export function readAdminLayout(): AdminLayoutEntry[] | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(LAYOUT_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return null;
    const entries = parsed.filter(
      (e): e is AdminLayoutEntry =>
        !!e &&
        typeof e === 'object' &&
        typeof (e as { id?: unknown }).id === 'string' &&
        typeof (e as { group?: unknown }).group === 'string',
    );
    return entries.length ? entries : null;
  } catch {
    return null;
  }
}

export function writeAdminLayout(entries: AdminLayoutEntry[]): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(LAYOUT_KEY, JSON.stringify(entries));
  } catch {
    /* ignore */
  }
}

export function clearAdminLayout(): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(LAYOUT_KEY);
  } catch {
    /* ignore */
  }
}

/**
 * Reconcile a stored override against the current code-defined items so it survives
 * code changes: keep the stored order for ids that still exist, drop unknown ids, and
 * append any new code items (absent from the override) at the end with their code group.
 * With `stored === null` this returns the plain code default (identical to today).
 */
export function reconcileAdminLayout<T extends { id: string; group?: string }>(
  codeItems: readonly T[],
  stored: AdminLayoutEntry[] | null,
): AdminLayoutEntry[] {
  const codeById = new Map(codeItems.map((i) => [i.id, i]));
  const seen = new Set<string>();
  const out: AdminLayoutEntry[] = [];
  if (stored) {
    for (const e of stored) {
      if (seen.has(e.id) || !codeById.has(e.id)) continue;
      seen.add(e.id);
      out.push({ id: e.id, group: e.group });
    }
  }
  for (const i of codeItems) {
    if (seen.has(i.id)) continue;
    seen.add(i.id);
    out.push({ id: i.id, group: i.group ?? '' });
  }
  return out;
}

/** Order + regroup the code items per the reconciled layout (used by the live nav). */
export function applyAdminLayout<T extends { id: string; group?: string }>(
  codeItems: readonly T[],
  layout: AdminLayoutEntry[],
): T[] {
  const codeById = new Map(codeItems.map((i) => [i.id, i]));
  const out: T[] = [];
  for (const e of layout) {
    const item = codeById.get(e.id);
    if (item) out.push({ ...item, group: e.group });
  }
  return out;
}
