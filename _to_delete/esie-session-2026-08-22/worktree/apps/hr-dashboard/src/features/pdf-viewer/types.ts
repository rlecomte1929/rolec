/**
 * Types for the PDF viewer + the contract it exposes to consumers
 * (case detail panel, resolution UI).
 *
 * Coordinate convention (Architecture Report §2.2): all bboxes shared
 * across the app are in canonical 0–1000 space with the origin in the
 * TOP-LEFT (y grows downward, the standard screen convention). The
 * pdf.js native space has its origin in the BOTTOM-LEFT and uses raw
 * device units; the conversion happens in `toCanonical.ts`.
 *
 * Mistral and Azure Document Intelligence already publish their bboxes
 * in the canonical space (per the C1-04 / C1-05 contract), so the
 * overlay never needs to know which OCR engine produced a given bbox.
 */

/**
 * One bbox in canonical 0–1000 space.
 * x0/y0 = top-left corner; x1/y1 = bottom-right corner.
 * Always 0 ≤ x0 ≤ x1 ≤ 1000 and 0 ≤ y0 ≤ y1 ≤ 1000.
 */
export interface CanonicalBbox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

/** One word emitted by the viewer's text-layer pipeline. */
export interface PageWord {
  text: string;
  bbox: CanonicalBbox;
}

/** Words for one page, surfaced via the onWordsLoaded callback. */
export interface PageWordsPayload {
  page: number;
  words: PageWord[];
  /** Raw pdf.js page size, exposed so consumers can sanity-check the conversion. */
  rawPageWidth: number;
  rawPageHeight: number;
}

/**
 * Optional bbox highlights to render on top of the page canvas.
 * The C1-11e overlay consumes this prop; the viewer never reads the
 * contents, it just hands the slice for the current page down.
 */
export interface PdfViewerHighlight {
  /** Stable id so React keys and scrollToBbox have a referent. */
  id: string;
  page: number;
  bbox: CanonicalBbox;
  /** Color tier — see bbox-overlay/colors.ts. */
  tier?: 'primary' | 'secondary' | 'tertiary';
  /** Aria-label announced to screen readers. */
  label?: string;
  /** Render flash animation when true. Parent flips back after ~800ms. */
  flashing?: boolean;
}

export interface PdfViewerProps {
  /**
   * URL to the PDF. Required — there's no internal upload path here.
   * Render an empty state outside the viewer if you don't have a URL yet.
   */
  documentUri: string;
  /** 1-indexed. Defaults to 1. */
  initialPage?: number;
  /** Called whenever the user (or scrollToBbox) changes the current page. */
  onPageChange?: (page: number) => void;
  /**
   * Fires once per page as text is extracted. C1-11e overlays consume
   * these to anchor click-to-bbox interactions, and the case detail
   * panel uses them to highlight the source of an extracted value.
   */
  onWordsLoaded?: (payload: PageWordsPayload) => void;
  /** Highlights to render on top of the page canvases. */
  highlights?: PdfViewerHighlight[];
  /**
   * Optional ref-style handle for imperative scrollToBbox calls from
   * a parent (resolution UI, candidate card).
   */
  viewerHandleRef?: React.RefObject<PdfViewerHandle | null>;
  /** Optional aria-label for the viewer region. */
  ariaLabel?: string;
}

/**
 * Imperative handle the parent gets when it passes `viewerHandleRef`.
 *
 * `goToPage` is the primitive — it mounts neighbours so the j/k flow
 * stays smooth and scrolls the destination into view. The C1-11e
 * `useBboxScroll` hook wraps this with `scrollToBbox(highlightId)`
 * that drives the flash animation as well.
 */
export interface PdfViewerHandle {
  /** Programmatic page change. 1-indexed; clamped. */
  goToPage: (page: number) => void;
}
