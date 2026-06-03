import { ReactNode, useEffect, useRef, useState } from 'react';
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist';
import type { TextItem } from 'pdfjs-dist/types/src/display/api';
import { textItemToCanonicalBbox } from './toCanonical';
import type { PageWord, PageWordsPayload } from './types';
import { cn } from '../../lib/utils';

interface PdfPageProps {
  doc: PDFDocumentProxy;
  pageNumber: number;
  /** Display scale, where 1 = 100% of the page's natural size at 96 DPI. */
  scale: number;
  /**
   * Fires once after the page renders + its text content extracts.
   * Parent uses this to thread words back to consumers.
   */
  onWordsLoaded?: (payload: PageWordsPayload) => void;
  /** Stable anchor id used by scrollToBbox (C1-11e). */
  anchorId: string;
  /**
   * Optional overlay surface stacked over the canvas. C1-11d renders
   * `null` here; C1-11e passes a BboxOverlay layered on top using the
   * `pageWidthPx`/`pageHeightPx` consumers receive via `onSize`.
   */
  overlay?: ReactNode;
  /**
   * Reports the rendered canvas dimensions in px. C1-11e's overlay
   * uses these to size its absolutely-positioned SVG layer to match
   * the visible canvas at the current zoom.
   */
  onSize?: (size: { widthPx: number; heightPx: number }) => void;
}

/**
 * Single-page renderer.
 *
 * Why this is its own component:
 *   - Each page owns one canvas + one text-layer and emits its own
 *     onWordsLoaded.
 *   - Cancelling and re-rendering on zoom change is local to the page
 *     — no ripple to siblings.
 *
 * Lazy rendering: the PdfViewer shell mounts pages only as they enter
 * the viewport, so by the time PdfPage exists in the tree it's visible.
 */
export function PdfPage({
  doc,
  pageNumber,
  scale,
  onWordsLoaded,
  anchorId,
  overlay,
  onSize,
}: PdfPageProps): JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [renderedSize, setRenderedSize] = useState<{ widthPx: number; heightPx: number } | null>(
    null,
  );
  const [isRendering, setIsRendering] = useState(true);
  const [renderError, setRenderError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let renderTask: ReturnType<PDFPageProxy['render']> | null = null;
    let pageHandle: PDFPageProxy | null = null;
    setIsRendering(true);
    setRenderError(null);

    void (async () => {
      try {
        pageHandle = await doc.getPage(pageNumber);
        if (cancelled || !pageHandle) return;

        const viewport = pageHandle.getViewport({ scale });
        const rawViewport = pageHandle.getViewport({ scale: 1 });
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          setRenderError('Could not acquire 2D rendering context.');
          setIsRendering(false);
          return;
        }
        // Match canvas backing buffer to viewport at chosen scale.
        const widthPx = Math.floor(viewport.width);
        const heightPx = Math.floor(viewport.height);
        canvas.width = widthPx;
        canvas.height = heightPx;
        canvas.style.width = `${widthPx}px`;
        canvas.style.height = `${heightPx}px`;

        renderTask = pageHandle.render({ canvasContext: ctx, viewport });
        await renderTask.promise;
        if (cancelled) return;

        setRenderedSize({ widthPx, heightPx });
        onSize?.({ widthPx, heightPx });
        setIsRendering(false);

        // Text extraction. Independent of canvas render so a slow
        // text layer doesn't delay first paint.
        try {
          const textContent = await pageHandle.getTextContent();
          if (cancelled) return;
          const words: PageWord[] = textContent.items
            .filter((it): it is TextItem => 'str' in it)
            .map((it) => ({
              text: it.str,
              bbox: textItemToCanonicalBbox(
                {
                  transform: it.transform as number[],
                  width: it.width,
                  height: it.height,
                  str: it.str,
                },
                { width: rawViewport.width, height: rawViewport.height },
              ),
            }))
            .filter((w) => w.text.trim().length > 0);
          onWordsLoaded?.({
            page: pageNumber,
            words,
            rawPageWidth: rawViewport.width,
            rawPageHeight: rawViewport.height,
          });
        } catch (textErr) {
          // Text extraction failure is non-fatal — canvas already
          // rendered, we just lose the overlay anchors for this page.
          // eslint-disable-next-line no-console
          console.warn(`[PdfPage] text extraction failed for page ${pageNumber}`, textErr);
        }
      } catch (err) {
        if (cancelled) return;
        setRenderError(err instanceof Error ? err.message : String(err));
        setIsRendering(false);
      }
    })();

    return () => {
      cancelled = true;
      if (renderTask) {
        try {
          renderTask.cancel();
        } catch {
          /* ignore: pdf.js throws if the task already finished */
        }
      }
      if (pageHandle) {
        pageHandle.cleanup();
      }
    };
  }, [doc, pageNumber, scale, onWordsLoaded, onSize]);

  return (
    <div
      id={anchorId}
      className="relative inline-block rounded-md border border-border bg-card shadow-sm"
      data-page={pageNumber}
    >
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={`PDF page ${pageNumber}`}
        className={cn('block', isRendering && 'opacity-50')}
      />
      {renderedSize ? overlay ?? null : null}
      {isRendering ? (
        <p
          className="absolute inset-0 flex items-center justify-center text-sm text-muted-foreground"
          aria-busy="true"
        >
          Rendering page {pageNumber}…
        </p>
      ) : null}
      {renderError ? (
        <p
          role="alert"
          className="absolute inset-0 flex items-center justify-center text-sm text-destructive"
        >
          Couldn't render page {pageNumber}: {renderError}
        </p>
      ) : null}
    </div>
  );
}
