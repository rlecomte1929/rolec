/**
 * Public surface of the bbox-overlay feature module (C1-11e).
 *
 * The overlay is meant to compose with PdfViewer (C1-11d) via its
 * `renderPageOverlay` slot. The recommended pattern:
 *
 *   const viewerHandleRef = useRef<PdfViewerHandle | null>(null);
 *   const { highlightsWithFlash, scrollToBbox } = useBboxScroll({
 *     highlights,
 *     viewerHandleRef,
 *   });
 *
 *   <PdfViewer
 *     documentUri={uri}
 *     viewerHandleRef={viewerHandleRef}
 *     renderPageOverlay={(page, size) => (
 *       <BboxOverlay
 *         page={page}
 *         highlights={highlightsWithFlash}
 *         pageWidthPx={size.widthPx}
 *         pageHeightPx={size.heightPx}
 *       />
 *     )}
 *   />
 *
 * The consumer then calls `scrollToBbox(highlightId)` from wherever
 * the user clicks an extracted value (CandidateCard, contradiction
 * detail row, search results).
 */
export { BboxOverlay } from './BboxOverlay';
export { useBboxScroll } from './useBboxScroll';
export { TIER_CLASSES, tierToClass } from './colors';
export type { BboxHighlight, HighlightTier } from './types';
