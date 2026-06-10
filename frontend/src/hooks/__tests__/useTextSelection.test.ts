/** I-6 — useTextSelection hook. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import type { RefObject } from 'react';
import { useTextSelection } from '../useTextSelection';

function fakeSelection(text: string, anchorNode: Node, collapsed = false): Selection {
  return {
    isCollapsed: collapsed,
    rangeCount: collapsed ? 0 : 1,
    anchorNode,
    toString: () => text,
    getRangeAt: () => ({
      getBoundingClientRect: () => ({ left: 10, bottom: 20, top: 5, right: 50, width: 40, height: 15 }),
    }),
  } as unknown as Selection;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
  document.body.innerHTML = '';
});

describe('useTextSelection', () => {
  it('reports text + rect for a selection inside the container', () => {
    vi.useFakeTimers();
    const container = document.createElement('div');
    const child = document.createTextNode('apostille certificate');
    container.appendChild(child);
    document.body.appendChild(container);
    vi.spyOn(window, 'getSelection').mockReturnValue(fakeSelection('apostille', child));
    const ref = { current: container } as RefObject<HTMLElement>;

    const { result } = renderHook(() => useTextSelection(ref, { debounceMs: 50 }));
    act(() => {
      document.dispatchEvent(new Event('selectionchange'));
      vi.advanceTimersByTime(60);
    });

    expect(result.current.selection?.text).toBe('apostille');
    expect(result.current.selection?.rect.left).toBe(10);
  });

  it('ignores selections outside the container', () => {
    vi.useFakeTimers();
    const container = document.createElement('div');
    document.body.appendChild(container);
    const outside = document.createTextNode('elsewhere');
    document.body.appendChild(outside);
    vi.spyOn(window, 'getSelection').mockReturnValue(fakeSelection('elsewhere', outside));
    const ref = { current: container } as RefObject<HTMLElement>;

    const { result } = renderHook(() => useTextSelection(ref, { debounceMs: 50 }));
    act(() => {
      document.dispatchEvent(new Event('selectionchange'));
      vi.advanceTimersByTime(60);
    });

    expect(result.current.selection).toBeNull();
  });

  it('clears on a collapsed selection', () => {
    vi.useFakeTimers();
    const container = document.createElement('div');
    const child = document.createTextNode('x');
    container.appendChild(child);
    document.body.appendChild(container);
    vi.spyOn(window, 'getSelection').mockReturnValue(fakeSelection('', child, true));
    const ref = { current: container } as RefObject<HTMLElement>;

    const { result } = renderHook(() => useTextSelection(ref, { debounceMs: 50 }));
    act(() => {
      document.dispatchEvent(new Event('selectionchange'));
      vi.advanceTimersByTime(60);
    });

    expect(result.current.selection).toBeNull();
  });
});
