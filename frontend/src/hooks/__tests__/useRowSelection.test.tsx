/**
 * useRowSelection — the two behaviours that stop a bulk action doing something the
 * user did not see it do. Both surfaces that use this hook (the feedback console and
 * the review queue) rely on them, so they are pinned here rather than duplicated.
 */
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useRowSelection } from '../useRowSelection';

interface Row { id: string; country: string }

const ALL: Row[] = [
  { id: 'a', country: 'IE' },
  { id: 'b', country: 'IE' },
  { id: 'c', country: 'NO' },
];
const getId = (r: Row) => r.id;

describe('useRowSelection', () => {
  it('toggles a single row on and off', () => {
    const { result } = renderHook(() => useRowSelection(ALL, getId));
    act(() => result.current.toggle('a'));
    expect(result.current.selectedRows.map(getId)).toEqual(['a']);
    act(() => result.current.toggle('a'));
    expect(result.current.selectedRows).toEqual([]);
  });

  it('select-all covers ONLY the visible rows, never the unfiltered set', () => {
    // The caller passes the FILTERED list. Selecting over the full set is how you
    // approve something you never looked at.
    const visible = ALL.filter((r) => r.country === 'IE');
    const { result } = renderHook(() => useRowSelection(visible, getId));
    act(() => result.current.toggleAll(true));
    expect(result.current.selectedRows.map(getId)).toEqual(['a', 'b']);
    expect(result.current.selectedRows.map(getId)).not.toContain('c');
  });

  it('reports allVisibleSelected only when every visible row is picked', () => {
    const { result } = renderHook(() => useRowSelection(ALL, getId));
    expect(result.current.allVisibleSelected).toBe(false);
    act(() => result.current.toggle('a'));
    expect(result.current.allVisibleSelected).toBe(false);
    act(() => result.current.toggleAll(true));
    expect(result.current.allVisibleSelected).toBe(true);
  });

  it('is false for an empty list rather than vacuously true', () => {
    const { result } = renderHook(() => useRowSelection([] as Row[], getId));
    expect(result.current.allVisibleSelected).toBe(false);
  });

  it('CLEARS the selection when the filter signature changes', () => {
    // Otherwise a row selected under one filter stays selected invisibly and rides
    // along on the next bulk action.
    const { result, rerender } = renderHook(
      ({ rows, sig }: { rows: Row[]; sig: string }) => useRowSelection(rows, getId, sig),
      { initialProps: { rows: ALL, sig: 'country=all' } },
    );
    act(() => result.current.toggleAll(true));
    expect(result.current.selectedRows).toHaveLength(3);

    rerender({ rows: ALL.filter((r) => r.country === 'NO'), sig: 'country=NO' });
    expect(result.current.selectedRows).toEqual([]);
  });

  it('keeps the selection when the rows change but the filter does not', () => {
    const { result, rerender } = renderHook(
      ({ rows, sig }: { rows: Row[]; sig: string }) => useRowSelection(rows, getId, sig),
      { initialProps: { rows: ALL, sig: 'stable' } },
    );
    act(() => result.current.toggle('a'));
    rerender({ rows: [...ALL], sig: 'stable' });
    expect(result.current.selectedRows.map(getId)).toEqual(['a']);
  });

  it('drops a selected row from selectedRows once it is no longer visible', () => {
    // Belt and braces: even if a caller forgets syncTo, a bulk action must never
    // operate on a row the user cannot see.
    const { result, rerender } = renderHook(
      ({ rows }: { rows: Row[] }) => useRowSelection(rows, getId),
      { initialProps: { rows: ALL } },
    );
    act(() => result.current.toggleAll(true));
    rerender({ rows: ALL.filter((r) => r.id === 'c') });
    expect(result.current.selectedRows.map(getId)).toEqual(['c']);
  });

  it('clear() empties the selection', () => {
    const { result } = renderHook(() => useRowSelection(ALL, getId));
    act(() => result.current.toggleAll(true));
    act(() => result.current.clear());
    expect(result.current.selectedRows).toEqual([]);
  });
});
