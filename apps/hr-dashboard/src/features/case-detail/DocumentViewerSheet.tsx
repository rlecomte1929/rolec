import { Sheet } from '../../components/Sheet';
import { PdfViewer } from '../pdf-viewer';
import type { CaseDocument } from './types';

interface DocumentViewerSheetProps {
  document: CaseDocument | null;
  open: boolean;
  onClose: () => void;
}

/**
 * Sheet host for the C1-11d PdfViewer.
 *
 * The bbox-overlay (C1-11e) plugs in here once the case detail exposes
 * a per-document highlight list (no such list is part of C1-11c — it
 * lands when the Resolution UI or ExtractedField inspector consumes
 * the viewer via the same Sheet). For now, the viewer renders without
 * an overlay; the `renderPageOverlay` slot is available for future
 * consumers without re-architecting this component.
 */
export function DocumentViewerSheet({
  document,
  open,
  onClose,
}: DocumentViewerSheetProps): JSX.Element | null {
  if (!document) return null;
  const title = document.filename;
  const description = document.document_type_label ?? document.document_type_code;

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      widthClassName="w-full md:w-[72vw] lg:w-[68vw] xl:w-[60vw]"
    >
      {document.document_uri ? (
        <PdfViewer
          documentUri={document.document_uri}
          ariaLabel={`Document viewer for ${title}`}
          onClose={onClose}
        />
      ) : (
        <p className="px-4 py-12 text-center text-sm text-muted-foreground">
          This document has no signed URL yet. Backend will issue one once the document is
          finalised by the extractor pipeline.
        </p>
      )}
    </Sheet>
  );
}
