/**
 * [P2-3 / P3-3] ActionBar — sticky bottom bar for the Form Editor.
 *
 * Shows:
 *   - "X fields need your input" counter (required fields with empty value)
 *   - "Download PDF" button → triggers P3-1 endpoint
 *   - "Save draft" button → flushes pending changes immediately
 *   - "Mark ready" button → PATCH status to 'ready'; handles 422 inline
 */
import React from 'react';
import { Button } from '../../../components/antigravity/Button';
interface ActionBarProps {
  missingCount: number;
  completionPct: number;
  isSaving: boolean;
  isMarkingReady: boolean;
  markReadyError: string | null;
  onSaveDraft: () => void;
  onMarkReady: () => void;
  /** Navigate back (called on successful Mark ready) */
  onBack: () => void;
  markReadySuccess: boolean;
  /** [P3-3] PDF download */
  onDownloadPdf?: () => void;
  isDownloadingPdf?: boolean;
  /** ISO date of last generated draft PDF — shown as "Last generated: X" */
  draftPdfGeneratedAt?: string | null;
}

// Spinner SVG shared between buttons
const Spinner: React.FC<{ className?: string }> = ({ className }) => (
  <svg className={`animate-spin w-3.5 h-3.5 ${className ?? ''}`} fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
  </svg>
);

export const ActionBar: React.FC<ActionBarProps> = ({
  missingCount,
  completionPct,
  isSaving,
  isMarkingReady,
  markReadyError,
  onSaveDraft,
  onMarkReady,
  onBack,
  markReadySuccess,
  onDownloadPdf,
  isDownloadingPdf = false,
  draftPdfGeneratedAt,
}) => {
  return (
    <div className="sticky bottom-0 z-20 bg-white border-t border-slate-200 shadow-[0_-2px_8px_rgba(0,0,0,0.06)]">
      {markReadyError && (
        <div className="px-6 py-2 bg-rose-50 border-b border-rose-200 text-sm text-rose-700">
          {markReadyError}
        </div>
      )}
      {markReadySuccess && (
        <div className="px-6 py-2 bg-emerald-50 border-b border-emerald-200 text-sm text-emerald-700 flex items-center justify-between">
          <span>Form marked as ready to submit.</span>
          <Button unstyled
            type="button"
            onClick={onBack}
            className="text-sm font-medium text-emerald-700 hover:underline"
          >
            Back to dossier →
          </Button>
        </div>
      )}
      <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
        {/* Left: completion + missing */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-24 h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-blue-500 transition-all"
                style={{ width: `${completionPct}%` }}
              />
            </div>
            <span className="text-xs font-medium text-slate-600">{completionPct}%</span>
          </div>
          {missingCount > 0 && (
            <span className="text-xs text-rose-600 font-medium">
              {missingCount} field{missingCount === 1 ? '' : 's'} need{missingCount === 1 ? 's' : ''} input
            </span>
          )}
          {missingCount === 0 && (
            <span className="text-xs text-emerald-600 font-medium">All required fields filled</span>
          )}
        </div>

        {/* Right: buttons */}
        <div className="flex items-center gap-2">
          {/* [P3-3] Download PDF */}
          {onDownloadPdf && (
            <div className="flex flex-col items-end">
              <Button unstyled
                type="button"
                onClick={onDownloadPdf}
                disabled={isDownloadingPdf}
                className="px-3 py-1.5 rounded text-sm font-medium border border-slate-300 text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isDownloadingPdf ? (
                  <span className="flex items-center gap-1.5">
                    <Spinner className="text-slate-500" />
                    Generating…
                  </span>
                ) : (
                  'Download PDF'
                )}
              </Button>
              {draftPdfGeneratedAt && !isDownloadingPdf && (
                <span className="text-[10px] text-slate-500 mt-0.5">
                  Last generated: {new Date(draftPdfGeneratedAt).toLocaleString()}
                </span>
              )}
            </div>
          )}

          <Button unstyled
            type="button"
            onClick={onSaveDraft}
            disabled={isSaving}
            className="px-3 py-1.5 rounded text-sm font-medium border border-slate-300 text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSaving ? (
              <span className="flex items-center gap-1.5">
                <Spinner className="text-slate-500" />
                Saving…
              </span>
            ) : (
              'Save draft'
            )}
          </Button>
          <Button unstyled
            type="button"
            onClick={onMarkReady}
            disabled={isMarkingReady || markReadySuccess}
            title={missingCount > 0 ? `${missingCount} required field${missingCount === 1 ? '' : 's'} still empty` : undefined}
            className="px-3 py-1.5 rounded text-sm font-medium bg-[#0b2b43] text-white hover:bg-[#0e3a5c] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isMarkingReady ? (
              <span className="flex items-center gap-1.5">
                <Spinner className="text-white" />
                Marking ready…
              </span>
            ) : markReadySuccess ? (
              '✓ Ready'
            ) : (
              'Mark ready'
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};
