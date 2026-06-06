/**
 * [AIQ-174 · P3-2] PdfCoordinateMapper
 *
 * Renders a PDF template and lets the admin click to assign XY coordinates
 * to each FieldDefinition. Coordinates are stored as RAW PDF POINTS (not
 * fractions) so they flow directly into the P3-1 overlay engine
 * (backend/app/routers/cases_read.py::_generate_filled_pdf) which calls
 * reportlab.Canvas.drawString(pdf_x, pdf_y, value).
 *
 *   - pdf_x : points from page LEFT edge
 *   - pdf_y : points from page BOTTOM edge  (PDF Y-up space)
 *   - pdf_page : 1-based page index
 *
 * The Y-flip happens here: screen Y grows downward, PDF Y grows upward.
 *
 * activeFieldId is fully controlled by the parent so the page-level
 * FieldSelector and the PDF canvas stay in sync without prop-drilling.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Checkbox } from '../../../../components/antigravity/Checkbox';
import { Button } from '../../../../components/antigravity/Button';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import type { FieldDefinition } from './FieldDefinitionEditor';

pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

// ─────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────

const DOT_COLOURS = [
  '#0b2b43', // brand navy
  '#e04c14', // brand orange
  '#10b981', // emerald
  '#1f8e8b', // violet
  '#ef4444', // red
  '#f59e0b', // amber
  '#06b6d4', // cyan
  '#ec4899', // pink
];

const BASE_RENDER_WIDTH = 700; // px at zoom = 1.0
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 2.0;
const ZOOM_STEP = 0.25;
const NUDGE_PT = 1;          // arrow-key nudge in PDF points
const NUDGE_PT_FAST = 10;    // shift+arrow nudge
const DEFAULT_FONT_SIZE = 10;

export function colourFor(index: number): string {
  return DOT_COLOURS[index % DOT_COLOURS.length];
}

// ─────────────────────────────────────────────────────────────────────
// Coord math — exported for unit testing
// ─────────────────────────────────────────────────────────────────────

export interface PageScale {
  /** width of the rendered PDF canvas in CSS pixels */
  renderedWidth: number;
  /** width of the actual PDF page in PDF points */
  pdfWidth: number;
  /** height of the actual PDF page in PDF points */
  pdfHeight: number;
}

/** Convert a screen click (offset relative to the rendered canvas top-left) to PDF points. */
export function screenToPdfPoint(
  offsetX: number,
  offsetY: number,
  scale: PageScale,
): { pdf_x: number; pdf_y: number } {
  const px = scale.renderedWidth / scale.pdfWidth; // px per PDF point
  const pdf_x = offsetX / px;
  const pdf_y = scale.pdfHeight - offsetY / px; // Y-flip
  return {
    pdf_x: Math.max(0, Math.min(scale.pdfWidth, Math.round(pdf_x * 100) / 100)),
    pdf_y: Math.max(0, Math.min(scale.pdfHeight, Math.round(pdf_y * 100) / 100)),
  };
}

/** Convert PDF points back to a CSS-pixel offset for rendering a dot. */
export function pdfPointToScreen(
  pdf_x: number,
  pdf_y: number,
  scale: PageScale,
): { left: number; top: number } {
  const px = scale.renderedWidth / scale.pdfWidth;
  return {
    left: pdf_x * px,
    top: (scale.pdfHeight - pdf_y) * px, // Y-flip
  };
}

// ─────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────

export interface PdfCoordinateMapperProps {
  /** Signed URL or http URL for the template PDF */
  pdfUrl: string;
  fields: FieldDefinition[];
  onChange: (updated: FieldDefinition[]) => void;
  /** Controlled: which field ID is currently being placed */
  activeFieldId: string | null;
  onActiveFieldIdChange: (id: string | null) => void;
  disabled?: boolean;
}

interface DragState {
  fieldId: string;
  // Pointer position relative to the canvas at drag start.
  pointerId: number;
}

export const PdfCoordinateMapper: React.FC<PdfCoordinateMapperProps> = ({
  pdfUrl,
  fields,
  onChange,
  activeFieldId,
  onActiveFieldIdChange,
  disabled,
}) => {
  const [numPages, setNumPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(1); // 1-based
  const [pdfWidth, setPdfWidth] = useState<number | null>(null);
  const [pdfHeight, setPdfHeight] = useState<number | null>(null);
  const [zoom, setZoom] = useState(1.0);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [previewMode, setPreviewMode] = useState(false);
  const [drag, setDrag] = useState<DragState | null>(null);

  const canvasRef = useRef<HTMLDivElement>(null);

  // Reset per-page dimensions when changing pages
  useEffect(() => {
    setPdfWidth(null);
    setPdfHeight(null);
  }, [currentPage]);

  // Esc cancels active placement
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onActiveFieldIdChange(null);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onActiveFieldIdChange]);

  const renderedWidth = BASE_RENDER_WIDTH * zoom;

  const scale: PageScale | null = useMemo(() => {
    if (pdfWidth == null || pdfHeight == null) return null;
    return { renderedWidth, pdfWidth, pdfHeight };
  }, [renderedWidth, pdfWidth, pdfHeight]);

  // ── Placing a new field ───────────────────────────────────────────
  const handleCanvasClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (disabled || !activeFieldId || !scale || previewMode) return;
    // If the click bubbled up from an existing dot, ignore — dot has its
    // own pointer handlers for drag-to-move.
    if ((e.target as HTMLElement).closest('[data-pdf-pin]')) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const { pdf_x, pdf_y } = screenToPdfPoint(e.clientX - rect.left, e.clientY - rect.top, scale);

    onChange(
      fields.map((f) =>
        f.id === activeFieldId
          ? { ...f, pdf_x, pdf_y, pdf_page: currentPage }
          : f,
      ),
    );
    onActiveFieldIdChange(null);
  };

  // ── Drag-to-move ──────────────────────────────────────────────────
  const handlePinPointerDown = (fieldId: string) => (e: React.PointerEvent<HTMLButtonElement>) => {
    if (disabled || previewMode) return;
    // Only left button
    if (e.button !== 0) return;
    e.stopPropagation();
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag({ fieldId, pointerId: e.pointerId });
  };

  const handlePinPointerMove = (e: React.PointerEvent<HTMLButtonElement>) => {
    if (!drag || e.pointerId !== drag.pointerId || !scale || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const { pdf_x, pdf_y } = screenToPdfPoint(e.clientX - rect.left, e.clientY - rect.top, scale);
    onChange(
      fields.map((f) =>
        f.id === drag.fieldId ? { ...f, pdf_x, pdf_y, pdf_page: currentPage } : f,
      ),
    );
  };

  const handlePinPointerUp = (e: React.PointerEvent<HTMLButtonElement>) => {
    if (drag && e.pointerId === drag.pointerId) {
      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch {
        // pointer capture may already be released
      }
      setDrag(null);
    }
  };

  // ── Keyboard nudge on focused pin ─────────────────────────────────
  const handlePinKeyDown = (fieldId: string) => (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (disabled || previewMode) return;
    const field = fields.find((f) => f.id === fieldId);
    if (!field || field.pdf_x == null || field.pdf_y == null) return;
    const step = e.shiftKey ? NUDGE_PT_FAST : NUDGE_PT;
    let dx = 0;
    let dy = 0;
    if (e.key === 'ArrowLeft') dx = -step;
    else if (e.key === 'ArrowRight') dx = step;
    else if (e.key === 'ArrowUp') dy = step; // PDF Y grows upward
    else if (e.key === 'ArrowDown') dy = -step;
    else if (e.key === 'Delete' || e.key === 'Backspace') {
      e.preventDefault();
      onChange(
        fields.map((f) =>
          f.id === fieldId
            ? { ...f, pdf_x: undefined, pdf_y: undefined, pdf_page: undefined }
            : f,
        ),
      );
      return;
    } else {
      return;
    }
    e.preventDefault();
    onChange(
      fields.map((f) =>
        f.id === fieldId
          ? {
              ...f,
              pdf_x: Math.max(0, Math.min(scale?.pdfWidth ?? Infinity, (f.pdf_x ?? 0) + dx)),
              pdf_y: Math.max(0, Math.min(scale?.pdfHeight ?? Infinity, (f.pdf_y ?? 0) + dy)),
            }
          : f,
      ),
    );
  };

  // ── Helpers ───────────────────────────────────────────────────────
  const assignedOnPage = fields.filter((f) => (f.pdf_page ?? null) === currentPage);
  const activeField = fields.find((f) => f.id === activeFieldId) ?? null;

  const onPageLoadSuccess = useCallback((page: { originalWidth: number; originalHeight: number }) => {
    setPdfWidth(page.originalWidth);
    setPdfHeight(page.originalHeight);
  }, []);

  // ── Render ────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-3">
      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap rounded border border-slate-200 bg-white px-3 py-2 text-xs">
        {/* Zoom */}
        <div className="flex items-center gap-1" role="group" aria-label="Zoom">
          <Button unstyled
            type="button"
            onClick={() => setZoom((z) => Math.max(MIN_ZOOM, Math.round((z - ZOOM_STEP) * 100) / 100))}
            disabled={zoom <= MIN_ZOOM}
            className="rounded border border-slate-200 px-2 py-1 disabled:opacity-40 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
            aria-label="Zoom out"
          >
            −
          </Button>
          <span className="tabular-nums w-12 text-center text-slate-600" aria-live="polite">
            {Math.round(zoom * 100)}%
          </span>
          <Button unstyled
            type="button"
            onClick={() => setZoom((z) => Math.min(MAX_ZOOM, Math.round((z + ZOOM_STEP) * 100) / 100))}
            disabled={zoom >= MAX_ZOOM}
            className="rounded border border-slate-200 px-2 py-1 disabled:opacity-40 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
            aria-label="Zoom in"
          >
            +
          </Button>
          <Button unstyled
            type="button"
            onClick={() => setZoom(1)}
            className="ml-1 rounded border border-slate-200 px-2 py-1 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
            aria-label="Reset zoom to 100%"
          >
            Fit
          </Button>
        </div>

        {/* Page nav */}
        {numPages > 1 && (
          <div className="flex items-center gap-1 ml-2" role="group" aria-label="Page navigation">
            <Button unstyled
              type="button"
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage((p) => p - 1)}
              className="rounded border border-slate-200 px-2 py-1 disabled:opacity-40 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
              aria-label="Previous page"
            >
              ←
            </Button>
            <span className="text-slate-600 tabular-nums">
              Page {currentPage}/{numPages}
            </span>
            <Button unstyled
              type="button"
              disabled={currentPage >= numPages}
              onClick={() => setCurrentPage((p) => p + 1)}
              className="rounded border border-slate-200 px-2 py-1 disabled:opacity-40 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-[#0b2b43]"
              aria-label="Next page"
            >
              →
            </Button>
          </div>
        )}

        {/* Preview toggle */}
        <label className="flex items-center gap-1 ml-auto cursor-pointer select-none">
          <Checkbox
            checked={previewMode}
            onChange={(e) => setPreviewMode(e.target.checked)}
            className="accent-[#0b2b43] focus:ring-2 focus:ring-[#0b2b43]"
          />
          <span className="text-slate-700">Preview filled</span>
        </label>

        {/* PDF size readout (helps verify scale) */}
        {pdfWidth != null && pdfHeight != null && (
          <span className="text-[10px] text-slate-400 font-mono">
            {Math.round(pdfWidth)} × {Math.round(pdfHeight)} pt
          </span>
        )}
      </div>

      {/* Placement banner */}
      {activeField && !previewMode && (
        <div
          className="flex items-center gap-2 rounded border border-[#0b2b43] bg-blue-50 px-3 py-2 text-sm text-[#0b2b43]"
          role="status"
        >
          <span className="font-medium">Click on the PDF</span>
          <span>to place</span>
          <span className="font-semibold">{activeField.label || activeField.id}</span>
          <Button unstyled
            type="button"
            onClick={() => onActiveFieldIdChange(null)}
            className="ml-auto text-xs text-slate-500 hover:text-slate-700 focus:outline-none focus:underline"
          >
            Cancel (Esc)
          </Button>
        </div>
      )}

      {/* PDF canvas */}
      <div className="relative select-none overflow-auto rounded border border-slate-200 bg-slate-100">
        {loadError ? (
          <div className="flex items-center justify-center py-16 text-sm text-rose-600">
            Failed to load PDF: {loadError}
          </div>
        ) : (
          <div
            ref={canvasRef}
            onClick={handleCanvasClick}
            className={`relative ${
              activeFieldId && !disabled && !previewMode ? 'cursor-crosshair' : 'cursor-default'
            }`}
            style={{ width: renderedWidth }}
          >
            <Document
              file={pdfUrl}
              onLoadSuccess={({ numPages: n }: { numPages: number }) => {
                setNumPages(n);
                setLoadError(null);
              }}
              onLoadError={(err: Error) => setLoadError(err.message)}
              loading={
                <div className="flex items-center justify-center py-16 text-sm text-slate-500">
                  Loading PDF…
                </div>
              }
            >
              <Page
                pageNumber={currentPage}
                width={renderedWidth}
                renderTextLayer={false}
                renderAnnotationLayer={false}
                onLoadSuccess={onPageLoadSuccess}
              />
            </Document>

            {/* Field pins / preview overlay */}
            {scale &&
              assignedOnPage.map((f) => {
                if (f.pdf_x == null || f.pdf_y == null) return null;
                const { left, top } = pdfPointToScreen(f.pdf_x, f.pdf_y, scale);
                const colour = colourFor(fields.indexOf(f));
                const accessibleName = `${f.label || f.id} at x ${Math.round(f.pdf_x)}, y ${Math.round(
                  f.pdf_y,
                )}, page ${currentPage}`;

                if (previewMode) {
                  const fontSize = (f.pdf_font_size ?? DEFAULT_FONT_SIZE) * (scale.renderedWidth / scale.pdfWidth);
                  return (
                    <span
                      key={f.id}
                      data-pdf-preview-label
                      style={{
                        left,
                        top: top - fontSize, // align text baseline to PDF point
                        fontSize: `${fontSize}px`,
                      }}
                      className="absolute z-10 whitespace-nowrap font-sans text-black bg-yellow-100/60 px-0.5"
                    >
                      {`{${f.label || f.id}}`}
                    </span>
                  );
                }

                return (
                  <Button unstyled
                    key={f.id}
                    type="button"
                    data-pdf-pin
                    aria-label={accessibleName}
                    title={accessibleName}
                    onPointerDown={handlePinPointerDown(f.id)}
                    onPointerMove={handlePinPointerMove}
                    onPointerUp={handlePinPointerUp}
                    onKeyDown={handlePinKeyDown(f.id)}
                    style={{ left, top, backgroundColor: colour }}
                    className={`absolute z-10 -translate-x-1/2 -translate-y-1/2 rounded-full w-4 h-4 border-2 border-white shadow-md focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-[#0b2b43] ${
                      drag?.fieldId === f.id ? 'cursor-grabbing' : 'cursor-grab'
                    } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
                  />
                );
              })}
          </div>
        )}
      </div>

      {/* Help text */}
      <p className="text-[11px] text-slate-500 leading-relaxed">
        Click on the PDF to place a selected field. Drag a pin to move it. Focus a pin and
        use arrow keys to nudge (Shift+arrow = 10pt). Press Delete to clear. Coordinates are
        stored as PDF points (Y origin at page bottom) and used verbatim by the fill engine.
      </p>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────
// FieldSelector — right-panel list with assign / move / clear controls
// ─────────────────────────────────────────────────────────────────────

export interface FieldSelectorProps {
  fields: FieldDefinition[];
  activeFieldId: string | null;
  onActivate: (id: string) => void;
  onClear: (id: string) => void;
  disabled?: boolean;
}

export const FieldSelector: React.FC<FieldSelectorProps> = ({
  fields,
  activeFieldId,
  onActivate,
  onClear,
  disabled,
}) => {
  if (fields.length === 0) {
    return (
      <div className="rounded border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
        No fields defined. Add fields in the Fields tab first.
      </div>
    );
  }

  return (
    <div className="grid gap-2" role="list">
      {fields.map((f, idx) => {
        const hasCoords =
          f.pdf_x != null && f.pdf_y != null && f.pdf_page != null;
        const isActive = activeFieldId === f.id;
        const colour = colourFor(idx);
        return (
          <div
            key={f.id}
            role="listitem"
            className={`flex items-center gap-2 rounded border px-3 py-2 text-sm transition-colors ${
              isActive
                ? 'border-[#0b2b43] bg-blue-50'
                : 'border-slate-200 bg-white hover:border-slate-300'
            }`}
          >
            <span
              aria-hidden="true"
              className="inline-block w-3 h-3 rounded-full flex-shrink-0"
              style={{ backgroundColor: colour }}
            />

            <span className="flex-1 min-w-0">
              <span className="font-medium text-slate-800 truncate block">
                {f.label || f.id}
              </span>
              {f.id !== f.label && (
                <span className="text-[11px] text-slate-400 font-mono leading-tight block">
                  {f.id}
                </span>
              )}
              {hasCoords && (
                <span className="text-[10px] text-slate-500 block font-mono">
                  p{f.pdf_page} · x={Math.round((f.pdf_x ?? 0) * 10) / 10}{' '}
                  y={Math.round((f.pdf_y ?? 0) * 10) / 10}
                </span>
              )}
            </span>

            <div className="flex items-center gap-1 flex-shrink-0">
              {hasCoords && (
                <Button unstyled
                  type="button"
                  disabled={disabled}
                  onClick={() => onClear(f.id)}
                  aria-label={`Clear coordinates for ${f.label || f.id}`}
                  className="text-[11px] text-rose-500 hover:text-rose-700 disabled:opacity-40 focus:outline-none focus:underline"
                >
                  Clear
                </Button>
              )}
              <Button unstyled
                type="button"
                disabled={disabled}
                onClick={() => onActivate(f.id)}
                aria-label={
                  isActive
                    ? `Cancel placement for ${f.label || f.id}`
                    : hasCoords
                      ? `Move ${f.label || f.id}`
                      : `Assign coordinates to ${f.label || f.id}`
                }
                className={`rounded px-2 py-0.5 text-xs font-medium transition-colors disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-[#0b2b43] ${
                  isActive
                    ? 'bg-[#0b2b43] text-white'
                    : hasCoords
                      ? 'border border-slate-300 text-slate-600 hover:border-slate-400'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                {isActive ? 'Placing…' : hasCoords ? 'Move' : 'Assign'}
              </Button>
            </div>
          </div>
        );
      })}
    </div>
  );
};
