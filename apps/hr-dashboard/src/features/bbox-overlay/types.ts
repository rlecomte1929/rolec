/**
 * Bbox-overlay public contract.
 *
 * The overlay is a thin SVG layer that snaps onto a PdfPage. It does
 * not own state — the parent (case detail panel, resolution UI) keeps
 * a list of `BboxHighlight` and toggles `flashing` to trigger the
 * 800ms attention animation.
 *
 * One overlay per page. The parent filters the highlight list by
 * page before passing it in.
 */

import type { CanonicalBbox } from '../pdf-viewer/types';

/**
 * Color tier for the highlight stroke + fill.
 *
 * `primary`   — the currently-selected source. Strong accent.
 * `secondary` — peer candidates in the same contradiction (so the
 *               HR reviewer can compare A vs B at a glance).
 * `tertiary`  — supporting context (e.g. the canonical entity's
 *               other appearances in the same document).
 *
 * Tiers map to the design system's secondary / primary / muted ramps,
 * so a deuteranope reviewer still sees three distinguishable bands
 * even at low saturation.
 */
export type HighlightTier = 'primary' | 'secondary' | 'tertiary';

export interface BboxHighlight {
  /** Stable id for React keys + scrollToBbox lookup. */
  id: string;
  /** 1-indexed page within the document. */
  page: number;
  /** Canonical 0–1000 bbox. */
  bbox: CanonicalBbox;
  /** Optional aria-label announced when the highlight is focused. */
  label?: string;
  /** Color tier — defaults to 'secondary'. */
  tier?: HighlightTier;
  /**
   * When true, the rect runs the 800ms flash animation. The parent
   * flips this back to `false` once the animation completes (handle
   * via useBboxScroll).
   */
  flashing?: boolean;
  /** Optional click handler — overrides the default scroll behaviour. */
  onSelect?: (highlightId: string) => void;
}
