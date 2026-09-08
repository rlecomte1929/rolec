import {
  KeyboardEvent,
  ReactNode,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react';
import { ChevronDown, ChevronUp, Minus, Plus, X } from 'lucide-react';
import { cn } from '../../lib/utils';
import { usePdfDocument } from './usePdfDocument';
import { PdfPage } from './PdfPage';
import type { PdfViewerHandle, PdfViewerProps } from './types';

const ZOOM_LEVELS = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2] as const;
const DEFAULT_ZOOM_INDEX = 2; // 1.0x

interface PdfViewerExtendedProps extends PdfViewerProps {
  /**
   * Optional close handler — when supplied, the viewer renders an
   * X button in its toolbar and treats Esc as a close request. The
   * Sheet host (case detail Documents section, resolution UI) owns
   * the open/close state.
   */
  onClose?: () => void;
  /**
   * Per-page overlay renderer. C1-11e wires the BboxOverlay here.
   * Receives the page number + the canvas dimensions at the current
   * scale, so the overlay can size its SVG to match.
   */
  renderPageOverlay?: (page: number, size: { widthPx: number; heightPx: number }) => ReactNode;
}

/**
 * Lazy-rendered, keyboard-navigable PDF viewer.
 *
 * Layout:
 *   [ toolbar — page selector / zoom / close       ]
 *   [ scrollable column                            ]
 *   [   page 1                                     ]
 *   [   page 2                                     ]
 *   [   …                                          ]
 *
 * Pages are lazy-mounted via an IntersectionObserver so a 50-page
 * contract doesn't render every canvas up front. Once mounted, a
 * page stays mounted — re-mount churn would lose the canvas content
 * and force a re-render on every scroll-by.
 */
export function PdfViewer({
  documentUri,
  initialPage = 1,
  onPageChange,
  onWordsLoaded,
  viewerHandleRef,
  ariaLabel,
  onClose,
  renderPageOverlay,
}: PdfViewerExtendedProps): JSX.Element {
  const { document, numPages, isLoading, error } = usePdfDocument(documentUri);
  const [zoomIndex, setZoomIndex] = useState(DEFAULT_ZOOM_INDEX);
  const [mountedPages, setMountedPages] = useState<Set<number>>(() => new Set([initialPage]));
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [pageSizes, setPageSizes] = useState<Map<number, { widthPx: number; heightPx: number }>>(
    new Map(),
  );
  const scrollHostRef = useRef<HTMLDivElement | null>(null);
  const pageAnchorIds = useMemo(
    () => Array.from({ length: numPages }, (_, i) => `pdf-page-${i + 1}`),
    [numPages],
  );

  // Reset paging state when the document URI changes (re-use is rare;
  // most consumers spin up a new viewer per document).
  useEffect(() => {
    setMountedPages(new Set([initialPage]));
    setCurrentPage(initialPage);
    setPageSizes(new Map());
  }, [documentUri, initialPage]);

  // IntersectionObserver: keep `currentPage` honest as the user scrolls
  // and lazy-mount pages as they near the viewport.
  useEffect(() => {
    if (!scrollHostRef.current || numPages === 0) return;
    const host = scrollHostRef.current;
    const observer = new IntersectionObserver(
      (entries) => {
        let leadingVisible: number | null = null;
        const toMount = new Set<number>();
        entries.forEach((entry) => {
          const pageAttr = (entry.target as HTMLElement).dataset['lazyPage'];
          if (!pageAttr) return;
          const page = Number(pageAttr);
          if (entry.isIntersecting) {
            toMount.add(page);
            if (leadingVisible === null || page < leadingVisible) {
              leadingVisible = page;
            }
          }
        });
        if (toMount.size > 0) {
          setMountedPages((prev) => {
            const next = new Set(prev);
            toMount.forEach((p) => next.add(p));
            // Eagerly add neighbours so scroll-by-keyboard doesn't show
            // a render flash.
            toMount.forEach((p) => {
              if (p + 1 <= numPages) next.add(p + 1);
              if (p - 1 >= 1) next.add(p - 1);
            });
            return next;
          });
        }
        if (leadingVisible !== null && leadingVisible !== currentPage) {
          setCurrentPage(leadingVisible);
        }
      },
      {
        root: host,
        rootMargin: '200px 0px',
        threshold: 0.1,
      },
    );
    pageAnchorIds.forEach((id) => {
      const el = host.querySelector(`[data-lazy-page-id="${id}"]`);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, [pageAnchorIds, numPages, currentPage]);

  // Notify the parent whenever the visible page changes.
  useEffect(() => {
    onPageChange?.(currentPage);
  }, [currentPage, onPageChange]);

  const goToPage = useCallback(
    (page: number): void => {
      if (page < 1 || page > numPages) return;
      setMountedPages((prev) => {
        const next = new Set(prev);
        next.add(page);
        if (page + 1 <= numPages) next.add(page + 1);
        if (page - 1 >= 1) next.add(page - 1);
        return next;
      });
      // Scroll on next paint so the mounted page exists in the DOM.
      requestAnimationFrame(() => {
        const host = scrollHostRef.current;
        if (!host) return;
        const anchor = host.querySelector(`[data-lazy-page-id="pdf-page-${page}"]`);
        if (anchor) {
          (anchor as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    },
    [numPages],
  );

  useImperativeHandle(
    viewerHandleRef ?? { current: null },
    (): PdfViewerHandle => ({
      goToPage,
    }),
    [goToPage],
  );

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>): void => {
    switch (e.key) {
      case 'ArrowDown':
      case 'j':
        e.preventDefault();
        goToPage(currentPage + 1);
        break;
      case 'ArrowUp':
      case 'k':
        e.preventDefault();
        goToPage(currentPage - 1);
        break;
      case 'Escape':
        if (onClose) {
          e.preventDefault();
          onClose();
        }
        break;
      default:
        break;
    }
  };

  const zoom = ZOOM_LEVELS[zoomIndex] ?? 1;
  const canZoomOut = zoomIndex > 0;
  const canZoomIn = zoomIndex < ZOOM_LEVELS.length - 1;

  if (!documentUri) {
    return <ViewerShell ariaLabel={ariaLabel}>{noDocumentNotice}</ViewerShell>;
  }
  if (isLoading) {
    return (
      <ViewerShell ariaLabel={ariaLabel}>
        <p className="px-4 py-12 text-center text-sm text-muted-foreground" aria-busy="true">
          Loading document…
        </p>
      </ViewerShell>
    );
  }
  if (error) {
    return (
      <ViewerShell ariaLabel={ariaLabel}>
        <p role="alert" className="px-4 py-12 text-center text-sm text-destructive">
          Couldn't load document: {error.message}
        </p>
      </ViewerShell>
    );
  }
  if (!document || numPages === 0) {
    return <ViewerShell ariaLabel={ariaLabel}>{noDocumentNotice}</ViewerShell>;
  }

  return (
    <ViewerShell
      ariaLabel={ariaLabel}
      onKeyDown={handleKeyDown}
      toolbar={
        <>
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label="Previous page"
              onClick={() => goToPage(currentPage - 1)}
              disabled={currentPage <= 1}
              className={iconButtonClass}
            >
              <ChevronUp className="h-4 w-4" aria-hidden="true" />
            </button>
            <span aria-live="polite" className="text-sm tabular-nums text-foreground">
              <span className="sr-only">Showing page </span>
              {currentPage}
              <span className="text-muted-foreground"> / {numPages}</span>
            </span>
            <button
              type="button"
              aria-label="Next page"
              onClick={() => goToPage(currentPage + 1)}
              disabled={currentPage >= numPages}
              className={iconButtonClass}
            >
              <ChevronDown className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              aria-label="Zoom out"
              onClick={() => setZoomIndex((i) => Math.max(0, i - 1))}
              disabled={!canZoomOut}
              className={iconButtonClass}
            >
              <Minus className="h-4 w-4" aria-hidden="true" />
            </button>
            <span className="w-12 text-center text-sm tabular-nums text-muted-foreground">
              {Math.round(zoom * 100)}%
            </span>
            <button
              type="button"
              aria-label="Zoom in"
              onClick={() => setZoomIndex((i) => Math.min(ZOOM_LEVELS.length - 1, i + 1))}
              disabled={!canZoomIn}
              className={iconButtonClass}
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
          {onClose ? (
            <button type="button" aria-label="Close document viewer" onClick={onClose} className={iconButtonClass}>
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          ) : null}
        </>
      }
    >
      <div
        ref={scrollHostRef}
        className="flex max-h-[calc(100vh-12rem)] flex-1 flex-col items-center gap-4 overflow-y-auto bg-muted/40 p-4"
      >
        {pageAnchorIds.map((anchorId, idx) => {
          const page = idx + 1;
          const isMounted = mountedPages.has(page);
          return (
            <div
              key={anchorId}
              data-lazy-page-id={anchorId}
              data-lazy-page={page}
              className="min-h-[20rem] w-full max-w-[860px]"
            >
              {isMounted ? (
                <PdfPage
                  doc={document}
                  pageNumber={page}
                  scale={zoom}
                  anchorId={anchorId}
                  onWordsLoaded={onWordsLoaded}
                  onSize={(size) =>
                    setPageSizes((prev) => {
                      if (prev.get(page)?.widthPx === size.widthPx && prev.get(page)?.heightPx === size.heightPx) {
                        return prev;
                      }
                      const next = new Map(prev);
                      next.set(page, size);
                      return next;
                    })
                  }
                  overlay={
                    renderPageOverlay && pageSizes.get(page)
                      ? renderPageOverlay(page, pageSizes.get(page) as { widthPx: number; heightPx: number })
                      : null
                  }
                />
              ) : (
                <PagePlaceholder page={page} />
              )}
            </div>
          );
        })}
      </div>
    </ViewerShell>
  );
}

const iconButtonClass = cn(
  'inline-flex h-8 w-8 items-center justify-center rounded-md border border-border bg-card text-foreground',
  'hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40',
  'focus-visible:shadow-focus',
);

interface ViewerShellProps {
  children: ReactNode;
  ariaLabel?: string;
  toolbar?: ReactNode;
  onKeyDown?: (e: KeyboardEvent<HTMLDivElement>) => void;
}

function ViewerShell({ children, ariaLabel, toolbar, onKeyDown }: ViewerShellProps): JSX.Element {
  return (
    <section
      aria-label={ariaLabel ?? 'Document viewer'}
      tabIndex={0}
      onKeyDown={onKeyDown}
      className="flex h-full flex-col rounded-lg border border-border bg-card shadow-sm focus:outline-none focus-visible:shadow-focus"
    >
      {toolbar ? (
        <header className="flex items-center justify-between gap-4 border-b border-border bg-card px-4 py-2">
          {toolbar}
        </header>
      ) : null}
      {children}
    </section>
  );
}

function PagePlaceholder({ page }: { page: number }): JSX.Element {
  return (
    <div
      className="flex h-80 w-full items-center justify-center rounded-md border border-dashed border-border bg-card text-sm text-muted-foreground shadow-sm"
      aria-hidden="true"
    >
      Page {page} loads when scrolled into view
    </div>
  );
}

const noDocumentNotice = (
  <p className="px-4 py-12 text-center text-sm text-muted-foreground">
    No document selected. Choose a document from the case detail panel to view it here.
  </p>
);
