/**
 * Category grouping for the Draft vs Live diff views (matrix + canonical).
 *
 * Slice 3a of the HR Policy IA simplification fixed the "long flat green-
 * block list" complaint by collapsing diff rows into per-category folds.
 * Both PolicyDiffView and CanonicalPolicyDiffView render their three
 * change types (changed / added / removed) through CollapsibleCategory
 * here so HR sees `▸ Compensation & allowances (12)` instead of 41 rows
 * scrolling off screen.
 *
 * Open by default when the section has 5 or fewer rows total — small
 * sections aren't worth a click. Larger sections stay collapsed.
 */
import React, { useState } from 'react';
import { Button } from '../../components/antigravity/Button';
import { POLICY_CONFIG_CATEGORIES } from '../policy-config/constants';

const CATEGORY_LABEL = new Map(POLICY_CONFIG_CATEGORIES.map((c) => [c.key, c.label]));

const FALLBACK_CATEGORY_KEY = '__uncategorized__';
const FALLBACK_CATEGORY_LABEL = 'Other';

export type CategoryGroup<T> = {
  key: string;
  label: string;
  rows: T[];
};

/**
 * Bucket rows by their category key, ordered to match the canonical
 * POLICY_CONFIG_CATEGORIES sequence, with anything unrecognized
 * appended at the end under "Other". Empty buckets are dropped.
 */
export function groupByCategory<T>(
  rows: T[],
  getCategoryKey: (row: T) => string | null | undefined
): CategoryGroup<T>[] {
  const buckets = new Map<string, T[]>();
  for (const row of rows) {
    const key = (getCategoryKey(row) || '').trim() || FALLBACK_CATEGORY_KEY;
    const list = buckets.get(key) ?? [];
    list.push(row);
    buckets.set(key, list);
  }
  const out: CategoryGroup<T>[] = [];
  // Canonical order first
  for (const { key, label } of POLICY_CONFIG_CATEGORIES) {
    const list = buckets.get(key);
    if (list && list.length) out.push({ key, label, rows: list });
    buckets.delete(key);
  }
  // Then anything else, alphabetically by key
  const trailing = Array.from(buckets.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  for (const [key, list] of trailing) {
    out.push({
      key,
      label: key === FALLBACK_CATEGORY_KEY ? FALLBACK_CATEGORY_LABEL : (CATEGORY_LABEL.get(key) ?? key),
      rows: list,
    });
  }
  return out;
}

const SMALL_SECTION_THRESHOLD = 5;

/** Returns true if the section is small enough that auto-expanding is the
 * better default than burying the content behind another click. */
export function shouldDefaultOpen(totalRowsInSection: number): boolean {
  return totalRowsInSection > 0 && totalRowsInSection <= SMALL_SECTION_THRESHOLD;
}

type CollapsibleCategoryProps<T> = {
  group: CategoryGroup<T>;
  /** Render a single row inside the expanded body. */
  renderRow: (row: T, index: number) => React.ReactNode;
  /** Force the section open on first render. Defaults to false (collapsed). */
  defaultOpen?: boolean;
  /** Visual accent ring matching the change-type color (emerald/amber/red).
   *  Used as a left border on the summary so HR can scan change types
   *  even with everything collapsed. */
  accentClassName?: string;
  /** data-testid for tests + automation. */
  testId?: string;
};

export function CollapsibleCategory<T>({
  group,
  renderRow,
  defaultOpen = false,
  accentClassName,
  testId,
}: CollapsibleCategoryProps<T>): React.ReactElement {
  const [open, setOpen] = useState<boolean>(defaultOpen);
  return (
    <div
      className={`rounded-md border border-slate-200 bg-white ${accentClassName ?? ''}`}
      data-testid={testId}
    >
      <Button unstyled
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full flex items-center justify-between gap-3 px-3 py-2 text-left hover:bg-slate-50 rounded-md"
      >
        <span className="flex items-center gap-2 min-w-0">
          <span className="text-slate-500 w-3 text-center" aria-hidden>
            {open ? '▾' : '▸'}
          </span>
          <span className="text-sm font-medium text-[#0b2b43] truncate">{group.label}</span>
          <span className="text-xs text-slate-500">({group.rows.length})</span>
        </span>
      </Button>
      {open && (
        <ul className="space-y-2 px-3 pb-3 pt-1">
          {group.rows.map((row, i) => (
            <React.Fragment key={i}>{renderRow(row, i)}</React.Fragment>
          ))}
        </ul>
      )}
    </div>
  );
}
