/**
 * [P3-2] PdfCoordinateMapper
 *
 * Renders a PDF template and lets the admin click to assign XY coordinates
 * to each FieldDefinition. Coordinates are stored as fractions (0.0–1.0)
 * of page dimensions in PDF space (Y=0 at bottom, Y=1 at top — Y is flipped
 * vs. screen coordinates so values are ready for reportlab/the PDF fill service).
 *
 * activeFieldId is fully controlled by the parent so the page-level FieldSelector
 * and the PDF canvas stay in sync without prop-drilling wrappers.
 */
import React, { useEffect, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import type { FieldDefinition, PdfCoordinates } from './FieldDefinitionEditor';

// ─────────────────────────────────────────────────────────────────────
// pdfjs worker — use unpkg CDN to avoid Vite bundler config complexity
// ─────────────────────────────────────────────────────────────────────
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

// ─────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────

const DOT_COLOURS = [
  '#0b2b43', // brand navy
  '#e04c14', // brand orange
  '#10b981', // emerald
  '#8b5cf6', // violet
  '#ef4444', // red
  '#f59e0b', // amber
  '#06b6d4', // cyan
  '#ec4899', // pink
];

const PDF_RENDER_WIDTH = 700; // px

export function colourFor(index: number): string {
  return DOT_COLOURS[index % DOT_COLOURS.length];
}

// ─────────────────────────────────────────────────────────────────────
// PdfCoordinateMapper
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

export const PdfCoordinateMapper: React.FC<PdfCoordinateMapperProps> = ({
  pdfUrl,
  fields,
  onChange,
  activeFieldId,
  onActiveFieldIdChange,
  disabled,
}) => {
  const [numPages, setNumPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Escape cancels placement
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onActiveFieldIdChange(null);
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onActiveFieldIdChange]);

  const handlePdfClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (disabled || !activeFieldId) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const xFrac = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    // Flip Y: screen top→bottom → PDF bottom→top
    const yFrac = Math.max(0, Math.min(1, 1 - (e.clientY - rect.top) / rect.height));

    const coords: PdfCoordinates = {
      page: currentPage - 1, // 0-based
      x: Math.round(xFrac * 1000) / 1000,
      y: Math.round(yFrac * 1000) / 1000,
    };
    onChange(fields.map((f) => (f.id === activeFieldId ? { ...f, pdf_coordinates: coords } : f)));
    onActiveFieldIdChange(null);
  };

  const removeCoords = (fieldId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    onChange(fields.map((f) => (f.id === fieldId ? { ...f, pdf_coordinates: undefined } : f)));
  };

  const assignedOnPage = fields.filter((f) => f.pdf_coordinates?.page === currentPage - 1);
  const activeField = fields.find((f) => f.id === activeFieldId) ?? null;

  return (
    <div className="flex flex-col gap-3">
      {/* Placement banner */}
      {activeField && (
        <div className="flex items-center gap-2 rounded border border-[#0b2b43] bg-blue-50 px-3 py-2 text-sm text-[#0b2b43]">
          <span className="font-medium">Click on the PDF</span>
          <span>to place</span>
          <span className="font-semibold">{activeField.label || activeField.id}</span>
          <button
            type="button"
            onClick={() => onActiveFieldIdChange(null)}
            className="ml-auto text-xs text-slate-500 hover:text-slate-700"
          >
            Cancel (Esc)
          </button>
        </div>
      )}

      {/* PDF canvas */}
      <div className="relative select-none overflow-hidden rounded border border-slate-200 bg-slate-100">
        {loadError ? (
          <div className="flex items-center justify-center py-16 text-sm text-rose-600">
            Failed to load PDF: {loadError}
          </div>
        ) : (
          <div
            onClick={handlePdfClick}
            className={`relative ${activeFieldId && !disabled ? 'cursor-crosshair' : 'cursor-default'}`}
          >
            <Document
              file={pdfUrl}
              onLoadSuccess={({ numPages: n }) => { setNumPages(n); setLoadError(null); }}
              onLoadError={(err) => setLoadError(err.message)}
              loading={
                <div className="flex items-center justify-center py-16 text-sm text-slate-500">
                  Loading PDF…
                </div>
              }
            >
              <Page
                pageNumber={currentPage}
                width={PDF_RENDER_WIDTH}
                renderTextLayer={false}
                renderAnnotationLayer={false}
              />
            </Document>

            {/* Field dots overlay */}
            {assignedOnPage.map((f) => {
              const c = f.pdf_coordinates!;
              const colour = colourFor(fields.indexOf(f));
              return (
                <div
                  key={f.id}
                  style={{
                    left: `${c.x * 100}%`,
                    top: `${(1 - c.y) * 100}%`,
                    backgroundColor: colour,
                  }}
                  className="absolute z-10 -translate-x-1/2 -translate-y-1/2 rounded-full w-4 h-4 border-2 border-white shadow-md"
                  title={f.label || f.id}
                >
                  <button
                    type="button"
                    onClick={(e) => removeCoords(f.id, e)}
                    className="absolute -top-2 -right-2 rounded-full bg-white border border-slate-300 w-3 h-3 text-[8px] text-slate-600 hover:text-rose-600 flex items-center justify-center leading-none"
                    aria-label={`Remove coordinate for ${f.label || f.id}`}
                  >
                    ×
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Page navigation */}
      {numPages > 1 && (
        <div className="flex items-center justify-center gap-3 text-sm">
          <button
            type="button"
            disabled={currentPage <= 1}
            onClick={() => setCurrentPage((p) => p - 1)}
            className="rounded border border-slate-200 px-2 py-1 text-xs disabled:opacity-40 hover:bg-slate-50"
          >
            ← Prev
          </button>
          <span className="text-slate-600">Page {currentPage} of {numPages}</span>
          <button
            type="button"
            disabled={currentPage >= numPages}
            onClick={() => setCurrentPage((p) => p + 1)}
            className="rounded border border-slate-200 px-2 py-1 text-xs disabled:opacity-40 hover:bg-slate-50"
          >
            Next →
          </button>
        </div>
      )}
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
    <div className="grid gap-2">
      {fields.map((f, idx) => {
        const hasCoords = !!f.pdf_coordinates;
        const isActive = activeFieldId === f.id;
        const colour = colourFor(idx);
        return (
          <div
            key={f.id}
            className={`flex items-center gap-2 rounded border px-3 py-2 text-sm transition-colors ${
              isActive
                ? 'border-[#0b2b43] bg-blue-50'
                : 'border-slate-200 bg-white hover:border-slate-300'
            }`}
          >
            {/* Colour swatch */}
            <span
              className="inline-block w-3 h-3 rounded-full flex-shrink-0"
              style={{ backgroundColor: colour }}
            />

            {/* Label + coords */}
            <span className="flex-1 min-w-0">
              <span className="font-medium text-slate-800 truncate block">
                {f.label || f.id}
              </span>
              {f.id !== f.label && (
                <span className="text-[11px] text-slate-400 font-mono leading-tight block">
                  {f.id}
                </span>
              )}
              {hasCoords && f.pdf_coordinates && (
                <span className="text-[10px] text-slate-500 block">
                  p{f.pdf_coordinates.page + 1} · x={f.pdf_coordinates.x.toFixed(3)}{' '}
                  y={f.pdf_coordinates.y.toFixed(3)}
                </span>
              )}
            </span>

            {/* Actions */}
            <div className="flex items-center gap-1 flex-shrink-0">
              {hasCoords && (
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => onClear(f.id)}
                  className="text-[11px] text-rose-500 hover:text-rose-700 disabled:opacity-40"
                >
                  Clear
                </button>
              )}
              <button
                type="button"
                disabled={disabled}
                onClick={() => onActivate(f.id)}
                className={`rounded px-2 py-0.5 text-xs font-medium transition-colors disabled:opacity-40 ${
                  isActive
                    ? 'bg-[#0b2b43] text-white'
                    : hasCoords
                      ? 'border border-slate-300 text-slate-600 hover:border-slate-400'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                {isActive ? 'Placing…' : hasCoords ? 'Move' : 'Assign'}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
};
