/**
 * useTextSelection (I-6) — surfaces the current text selection (text + screen
 * rect) when it falls inside an opt-in container, so a feature can offer an
 * "explain this term" affordance without listening app-wide.
 *
 * Debounced on `selectionchange`; clears when the selection collapses, is empty,
 * or lands outside the container.
 */
import { useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';

export interface TextSelection {
  /** Trimmed selected text. */
  text: string;
  /** Viewport rect of the selection range (for popover anchoring). */
  rect: DOMRect;
}

export interface UseTextSelectionResult {
  selection: TextSelection | null;
  clear: () => void;
}

/** Max characters worth treating as a "term" to explain (avoid whole-page grabs). */
const MAX_TERM_LENGTH = 200;

export function useTextSelection(
  containerRef: RefObject<HTMLElement>,
  { debounceMs = 200 }: { debounceMs?: number } = {},
): UseTextSelectionResult {
  const [selection, setSelection] = useState<TextSelection | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    const onSelectionChange = () => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        const sel = typeof window !== 'undefined' ? window.getSelection() : null;
        if (!sel || sel.isCollapsed || sel.rangeCount === 0) {
          setSelection(null);
          return;
        }
        const text = sel.toString().trim();
        if (!text || text.length > MAX_TERM_LENGTH) {
          setSelection(null);
          return;
        }
        const container = containerRef.current;
        const anchor = sel.anchorNode;
        if (!container || !anchor || !container.contains(anchor)) {
          setSelection(null);
          return;
        }
        const rect = sel.getRangeAt(0).getBoundingClientRect();
        setSelection({ text, rect });
      }, debounceMs);
    };

    document.addEventListener('selectionchange', onSelectionChange);
    return () => {
      document.removeEventListener('selectionchange', onSelectionChange);
      if (timer.current) clearTimeout(timer.current);
    };
  }, [containerRef, debounceMs]);

  return { selection, clear: () => setSelection(null) };
}
