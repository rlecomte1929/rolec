import { useCallback, useMemo, useRef, useState } from 'react';
import type { PdfViewerHandle } from '../pdf-viewer/types';
import type { BboxHighlight } from './types';

const FLASH_DURATION_MS = 800;

interface UseBboxScrollOptions {
  highlights: BboxHighlight[];
  /**
   * Imperative handle on the underlying PdfViewer. The hook calls
   * `goToPage` so the destination page is mounted + scrolled.
   */
  viewerHandleRef: React.RefObject<PdfViewerHandle | null>;
}

interface UseBboxScrollResult {
  /** Highlights enriched with `flashing` state for the active id. */
  highlightsWithFlash: BboxHighlight[];
  /** Imperative scrollToBbox — passes through to the viewer + triggers flash. */
  scrollToBbox: (highlightId: string) => void;
  /** Id currently being flashed (or null). Useful for sibling UI. */
  flashingId: string | null;
}

/**
 * Glue hook for the C1-11e "click a value, jump to the bbox, flash it"
 * interaction. Owns:
 *   - The transient `flashing` flag on the matching highlight.
 *   - A timer that flips it off after the 800ms animation finishes.
 *   - A page-mount handoff via the viewer's `goToPage`.
 *
 * The hook does NOT modify the highlights array — it derives a new
 * memoised list with `flashing: true` set on exactly one element, so
 * consumers can pass the result straight to `<PdfViewer highlights />`
 * (or `<BboxOverlay highlights />`) without race conditions.
 */
export function useBboxScroll({ highlights, viewerHandleRef }: UseBboxScrollOptions): UseBboxScrollResult {
  const [flashingId, setFlashingId] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scrollToBbox = useCallback(
    (highlightId: string): void => {
      const target = highlights.find((h) => h.id === highlightId);
      if (!target) {
        // eslint-disable-next-line no-console
        console.warn(`[useBboxScroll] no highlight found with id="${highlightId}"`);
        return;
      }
      viewerHandleRef.current?.goToPage(target.page);
      // Re-arm the flash. If a previous flash is still in flight, the
      // old timer is cancelled so the new highlight gets a full window.
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      setFlashingId(highlightId);
      timerRef.current = setTimeout(() => {
        setFlashingId(null);
        timerRef.current = null;
      }, FLASH_DURATION_MS);
    },
    [highlights, viewerHandleRef],
  );

  const highlightsWithFlash = useMemo<BboxHighlight[]>(
    () =>
      flashingId === null
        ? highlights
        : highlights.map((h) => (h.id === flashingId ? { ...h, flashing: true } : h)),
    [highlights, flashingId],
  );

  return { highlightsWithFlash, scrollToBbox, flashingId };
}
