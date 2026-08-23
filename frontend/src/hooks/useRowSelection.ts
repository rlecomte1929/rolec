/**
 * useRowSelection — the row-selection closure that six admin pages had each written
 * out by hand (AdminAssignments, AdminVettingQueue, AdminUsers, AdminCompanies,
 * HrTeamList, AdminContentReviewPage, AdminReviewQueuePage).
 *
 * Two behaviours are baked in on purpose, because getting either wrong is how a bulk
 * action does something the user did not see it do:
 *
 *   1. SELECT ALL MEANS "ALL THE ROWS YOU CAN SEE". It is derived from the visible
 *      (filtered) rows, never from the unfiltered set. AdminVettingQueue:145 does this
 *      deliberately; a select-all over hidden rows is how you approve a supplier you
 *      never looked at.
 *   2. CHANGING A FILTER CLEARS THE SELECTION (`syncTo`). Otherwise a row selected
 *      under one filter stays selected, invisibly, and rides along on the next action.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';

export interface RowSelection<T> {
  /** The currently selected ids. */
  selectedIds: Set<string>;
  /** The visible rows that are selected — what a bulk action should operate on. */
  selectedRows: T[];
  /** True when every visible row is selected (drives the header checkbox). */
  allVisibleSelected: boolean;
  isSelected: (id: string) => boolean;
  toggle: (id: string) => void;
  /** Select or clear ALL VISIBLE rows. */
  toggleAll: (checked: boolean) => void;
  clear: () => void;
}

/**
 * @param visibleRows the rows currently rendered — already filtered.
 * @param getId       stable id for a row.
 * @param syncTo      when this string changes, the selection is cleared. Pass a
 *                    serialisation of the active filters.
 */
export function useRowSelection<T>(
  visibleRows: T[],
  getId: (row: T) => string,
  syncTo?: string,
): RowSelection<T> {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Filters changed -> the visible set changed -> a stale selection would act on rows
  // the user can no longer see.
  useEffect(() => {
    setSelectedIds(new Set());
  }, [syncTo]);

  const toggle = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleAll = useCallback(
    (checked: boolean) => {
      setSelectedIds(checked ? new Set(visibleRows.map(getId)) : new Set());
    },
    [visibleRows, getId],
  );

  const clear = useCallback(() => setSelectedIds(new Set()), []);

  const selectedRows = useMemo(
    () => visibleRows.filter((r) => selectedIds.has(getId(r))),
    [visibleRows, selectedIds, getId],
  );

  const allVisibleSelected =
    visibleRows.length > 0 && visibleRows.every((r) => selectedIds.has(getId(r)));

  const isSelected = useCallback((id: string) => selectedIds.has(id), [selectedIds]);

  return { selectedIds, selectedRows, allVisibleSelected, isSelected, toggle, toggleAll, clear };
}

export default useRowSelection;
