import { KeyboardEvent } from 'react';
import { cn } from '../../lib/utils';
import { tierToClass } from './colors';
import type { BboxHighlight } from './types';

interface BboxOverlayProps {
  /** 1-indexed page this overlay sits on. */
  page: number;
  /** Highlights for THIS page only — the parent (PdfViewer) filters. */
  highlights: BboxHighlight[];
  /** Rendered canvas width in CSS px at the current zoom. */
  pageWidthPx: number;
  /** Rendered canvas height in CSS px at the current zoom. */
  pageHeightPx: number;
}

/**
 * Bounding-box overlay layer (C1-11e).
 *
 * Renders an absolutely-positioned SVG over the pdf.js page canvas.
 * Coordinates: each highlight's bbox is in canonical 0-1000 space, so
 * the SVG uses `viewBox="0 0 1000 1000"` with `preserveAspectRatio="none"`.
 * That lets the SVG stretch to the page's exact pixel dimensions at any
 * zoom level without manual conversion — the browser maps 0-1000 →
 * 0-pageWidthPx for x and 0-pageHeightPx for y.
 *
 * Why SVG instead of canvas:
 *   - Each rect is a DOM element → click + focus + aria-label work for
 *     free, satisfying validation criterion #5 (screen-reader announce).
 *   - The flash animation runs as a CSS keyframe on the element, no
 *     per-frame imperative redraw.
 *   - The overlay sits *above* the canvas (z-stack), but uses
 *     `pointer-events: none` on the container so the user can still
 *     interact with the text layer underneath. Individual rects with
 *     onSelect re-enable pointer events on themselves.
 */
export function BboxOverlay({
  page,
  highlights,
  pageWidthPx,
  pageHeightPx,
}: BboxOverlayProps): JSX.Element | null {
  const visible = highlights.filter((h) => h.page === page);
  if (visible.length === 0) {
    return null;
  }

  return (
    <svg
      className="pointer-events-none absolute inset-0"
      width={pageWidthPx}
      height={pageHeightPx}
      viewBox="0 0 1000 1000"
      preserveAspectRatio="none"
      aria-hidden="false"
      role="group"
      aria-label={`Highlighted regions on page ${page}`}
    >
      {visible.map((h) => (
        <HighlightRect key={h.id} highlight={h} />
      ))}
    </svg>
  );
}

interface HighlightRectProps {
  highlight: BboxHighlight;
}

function HighlightRect({ highlight }: HighlightRectProps): JSX.Element {
  const { id, bbox, label, tier, flashing, onSelect } = highlight;
  const { stroke, fillClass } = tierToClass(tier);
  const x = bbox.x0;
  const y = bbox.y0;
  const w = Math.max(1, bbox.x1 - bbox.x0);
  const h = Math.max(1, bbox.y1 - bbox.y0);
  const interactive = Boolean(onSelect);

  const handleKey = (e: KeyboardEvent<SVGRectElement>): void => {
    if (!onSelect) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect(id);
    }
  };

  return (
    <rect
      x={x}
      y={y}
      width={w}
      height={h}
      vectorEffect="non-scaling-stroke"
      className={cn(
        stroke,
        fillClass,
        'fill-opacity-20 stroke-2',
        flashing && 'animate-bbox-flash',
        interactive && 'pointer-events-auto cursor-pointer',
      )}
      // SVG <rect> uses opacity via attribute, but `fill-opacity-*`
      // utilities aren't first-class in Tailwind v3; we set fill-opacity
      // through the inline style so the rest is class-driven.
      style={{ fillOpacity: 0.2 }}
      role={interactive ? 'button' : 'img'}
      aria-label={label ?? `Highlighted region on page ${highlight.page}`}
      tabIndex={interactive ? 0 : -1}
      onClick={interactive ? () => onSelect?.(id) : undefined}
      onKeyDown={interactive ? handleKey : undefined}
    />
  );
}
