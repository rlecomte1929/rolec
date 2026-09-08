/**
 * Per-table column-state persistence (order + widths).
 *
 * State key: `dataTable:${tableId}:v1`. Bumping the suffix invalidates
 * everyone's stored layout on a breaking change (e.g. a column renamed).
 *
 * Storage is localStorage by design — no backend round-trip on every drag.
 * If we ever need cross-device sync we add a server endpoint without
 * changing this contract.
 */

const VERSION = 'v1';

export interface ColumnLayout {
  /** Ordered list of column ids — drives <th> sequence. */
  order: string[];
  /** Per-column pixel widths. Missing entries fall back to the column's defaultWidth. */
  widths: Record<string, number>;
}

function keyFor(tableId: string): string {
  return `dataTable:${tableId}:${VERSION}`;
}

export function loadLayout(tableId: string): ColumnLayout | null {
  if (typeof window === 'undefined' || !window.localStorage) return null;
  try {
    const raw = window.localStorage.getItem(keyFor(tableId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (
      parsed &&
      typeof parsed === 'object' &&
      'order' in parsed &&
      'widths' in parsed &&
      Array.isArray((parsed as ColumnLayout).order)
    ) {
      return parsed as ColumnLayout;
    }
    return null;
  } catch {
    return null;
  }
}

export function saveLayout(tableId: string, layout: ColumnLayout): void {
  if (typeof window === 'undefined' || !window.localStorage) return;
  try {
    window.localStorage.setItem(keyFor(tableId), JSON.stringify(layout));
  } catch {
    /* ignore (quota errors, private mode, etc.) */
  }
}

export function resetLayout(tableId: string): void {
  if (typeof window === 'undefined' || !window.localStorage) return;
  try {
    window.localStorage.removeItem(keyFor(tableId));
  } catch {
    /* ignore */
  }
}
