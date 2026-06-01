/**
 * Public surface of the PDF viewer feature module.
 *
 * Consumers (case detail panel, resolution UI) should import only from
 * this file — the internal modules (PdfPage, usePdfDocument, toCanonical)
 * are implementation details and may move without notice.
 */
export { PdfViewer } from './PdfViewer';
export { textItemToCanonicalBbox } from './toCanonical';
export type {
  CanonicalBbox,
  PageWord,
  PageWordsPayload,
  PdfViewerHandle,
  PdfViewerHighlight,
  PdfViewerProps,
} from './types';
