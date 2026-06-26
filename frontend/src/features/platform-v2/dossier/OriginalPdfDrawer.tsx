/**
 * [P2-4] OriginalPdfDrawer — right-side drawer showing the blank template PDF.
 *
 * - Opens as a non-blocking right-side panel so the user can reference the
 *   original form while filling fields in the Form Editor or Dossier list.
 * - Lazy-fetches the signed URL only when first opened (not on mount).
 * - Reuses PdfPanel (iframe viewer) so both surfaces share the same renderer.
 * - Includes a "Download original" button that triggers a browser download.
 * - Closes on Escape or the × button.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '../../../components/antigravity/Button';
import { PdfPanel } from '../form-editor/PdfPanel';
import { formEditorAPI } from '../../../api/formEditor';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface OriginalPdfDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  /** ID of the case — needed for the signed URL API call. */
  caseId: string;
  /** ID of the case form — needed for the signed URL API call. */
  formId: string;
  /** Display name shown in the drawer header. */
  formName: string;
  /** Optional form code shown as a chip in admin/internal contexts. */
  formCode?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const OriginalPdfDrawer: React.FC<OriginalPdfDrawerProps> = ({
  isOpen,
  onClose,
  caseId,
  formId,
  formName,
  formCode,
}) => {
  const [signedUrl, setSignedUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false); // only fetch once per open
  const [isDownloading, setIsDownloading] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);

  // ── Lazy-fetch the signed URL the first time the drawer opens ────────────
  useEffect(() => {
    if (!isOpen || hasLoaded) return;
    setIsLoading(true);
    formEditorAPI
      .getOriginalUrl(caseId, formId)
      .then((url) => {
        setSignedUrl(url);
        setHasLoaded(true);
      })
      .catch(() => {
        setSignedUrl(null);
        setHasLoaded(true);
      })
      .finally(() => setIsLoading(false));
  }, [isOpen, hasLoaded, caseId, formId]);

  // ── Reset fetch state when the drawer closes so re-open gets a fresh URL ─
  useEffect(() => {
    if (!isOpen) {
      setHasLoaded(false);
      setSignedUrl(null);
    }
  }, [isOpen]);

  // ── Close on Escape ───────────────────────────────────────────────────────
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose();
    },
    [isOpen, onClose],
  );
  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // ── Download original ─────────────────────────────────────────────────────
  const handleDownload = useCallback(async () => {
    if (!signedUrl) return;
    setIsDownloading(true);
    try {
      const response = await fetch(signedUrl);
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = `${formCode ? `${formCode}_` : ''}original.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      setTimeout(() => URL.revokeObjectURL(objectUrl), 10_000);
    } catch {
      // Non-fatal — user can use the browser's own download from the iframe
    } finally {
      setIsDownloading(false);
    }
  }, [signedUrl, formCode]);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      {/* Backdrop — click to close */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/20"
          aria-hidden="true"
          onClick={onClose}
        />
      )}

      {/* Drawer panel */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Original PDF: ${formName}`}
        className={[
          'fixed top-0 right-0 bottom-0 z-50 flex flex-col',
          'w-full max-w-lg bg-white shadow-2xl border-l border-slate-200',
          'transition-transform duration-300 ease-in-out',
          isOpen ? 'translate-x-0' : 'translate-x-full',
        ].join(' ')}
      >
        {/* ── Header ── */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-200 shrink-0">
          {formCode && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-[#0b2b43] text-white tracking-wide">
              {formCode}
            </span>
          )}
          <span className="flex-1 text-sm font-semibold text-slate-800 truncate">
            {formName}
          </span>

          {/* Download button */}
          {signedUrl && (
            <Button unstyled
              type="button"
              onClick={handleDownload}
              disabled={isDownloading}
              className={[
                'inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium',
                'bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors',
                'disabled:opacity-50 disabled:cursor-not-allowed',
              ].join(' ')}
              title="Download original blank form PDF"
            >
              {isDownloading ? (
                <>
                  <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Downloading…
                </>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Download original
                </>
              )}
            </Button>
          )}

          {/* Close button */}
          <Button unstyled
            type="button"
            onClick={onClose}
            className="ml-1 p-1.5 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
            aria-label="Close original PDF panel"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </Button>
        </div>

        {/* ── PDF viewer body ── */}
        <div className="flex-1 overflow-hidden p-4">
          {isLoading ? (
            <div className="h-full flex items-center justify-center">
              <div className="flex flex-col items-center gap-3 text-slate-400">
                <svg className="animate-spin w-8 h-8" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <span className="text-sm">Loading original PDF…</span>
              </div>
            </div>
          ) : (
            <PdfPanel url={signedUrl} formName={formName} />
          )}
        </div>
      </div>
    </>
  );
};
