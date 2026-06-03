/**
 * Pure functions for converting between pdf.js native coordinates and
 * the canonical 0–1000 / top-left-origin space the rest of the app
 * uses (Architecture Report §2.2).
 *
 * Why a separate module: this is the part most likely to be wrong, and
 * keeping it pure + dependency-free makes it easy to unit-test against
 * sample Mistral / Azure DI outputs.
 *
 * pdf.js convention:
 *   - Origin is bottom-left.
 *   - Page size comes from viewport.width / viewport.height at scale=1.
 *   - A TextItem's transform is a 6-vector [a, b, c, d, e, f] where
 *     (e, f) is the lower-left origin of the glyph and (a, d) gives
 *     the un-rotated width/height. We only need (e, f), the glyph
 *     height (item.height), and a width approximation (item.width).
 */

import type { CanonicalBbox } from './types';

export interface RawTextItem {
  /** [a, b, c, d, e, f] homogeneous transform from pdf.js. */
  transform: number[];
  /** Glyph height in pdf.js native space. */
  height: number;
  /** Glyph width in pdf.js native space. */
  width: number;
  str: string;
}

export interface RawPageSize {
  width: number;
  height: number;
}

/**
 * Convert one pdf.js TextItem to a canonical-space bbox.
 *
 * Implementation notes:
 *   - pdf.js's TextItem origin is the BOTTOM-LEFT of the glyph.
 *   - We flip y because canonical space has y growing downward.
 *   - We round to the nearest integer 0–1000 — a 1/1000 step at A4
 *     width = 0.21 mm, well below any extraction precision.
 *   - The clamp guards against degenerate fixtures (item slightly off
 *     the page) so the overlay never escapes its viewBox.
 */
export function textItemToCanonicalBbox(
  item: RawTextItem,
  pageSize: RawPageSize,
): CanonicalBbox {
  const { width: pw, height: ph } = pageSize;
  if (pw <= 0 || ph <= 0) {
    return { x0: 0, y0: 0, x1: 0, y1: 0 };
  }

  const nativeLeftX = item.transform[4] ?? 0;
  const nativeBottomY = item.transform[5] ?? 0;
  const nativeRightX = nativeLeftX + (item.width ?? 0);
  const nativeTopY = nativeBottomY + (item.height ?? 0);

  // Flip y: canonical_y = (page_height - native_y) / page_height * 1000.
  const canonicalY0 = ((ph - nativeTopY) / ph) * 1000;
  const canonicalY1 = ((ph - nativeBottomY) / ph) * 1000;

  return {
    x0: clamp(Math.round((nativeLeftX / pw) * 1000)),
    y0: clamp(Math.round(canonicalY0)),
    x1: clamp(Math.round((nativeRightX / pw) * 1000)),
    y1: clamp(Math.round(canonicalY1)),
  };
}

function clamp(v: number): number {
  if (Number.isNaN(v) || v < 0) return 0;
  if (v > 1000) return 1000;
  return v;
}
