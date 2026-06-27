/**
 * [P2-3] PdfPanel — renders the original form PDF on the left side of the
 * Form Editor layout. Uses an iframe so we don't need react-pdf.
 *
 * Falls back gracefully when no URL is available.
 */
import React, { useState } from 'react';

interface PdfPanelProps {
  url: string | null;
  formName: string;
}

export const PdfPanel: React.FC<PdfPanelProps> = ({ url, formName }) => {
  const [iframeError, setIframeError] = useState(false);

  if (!url) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-slate-50 border border-slate-200 rounded-lg p-6 text-center">
        <svg
          className="w-12 h-12 text-slate-300 mb-3"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
          />
        </svg>
        <p className="text-sm font-medium text-slate-500">No PDF available</p>
        <p className="text-xs text-slate-400 mt-1">
          The original form PDF hasn&apos;t been attached yet.
        </p>
      </div>
    );
  }

  if (iframeError) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-slate-50 border border-slate-200 rounded-lg p-6 text-center">
        <p className="text-sm font-medium text-slate-600 mb-3">
          Cannot display PDF inline.
        </p>
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium bg-[#0b2b43] text-white hover:bg-[#0e3a5c] transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
          Open {formName} PDF
        </a>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border border-b-0 border-slate-200 rounded-t-lg">
        <span className="text-xs font-medium text-slate-600 truncate">{formName}</span>
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="shrink-0 text-xs text-[#0b2b43] hover:underline ml-2"
        >
          Open in new tab ↗
        </a>
      </div>
      <iframe
        src={url}
        title={`${formName} PDF`}
        // SEC-FE-6: user-uploaded document rendered same-origin — sandbox without
        // allow-scripts so a malicious PDF/HTML can't execute in the app origin.
        sandbox="allow-same-origin allow-popups"
        className="flex-1 w-full border border-slate-200 rounded-b-lg"
        onError={() => setIframeError(true)}
      />
    </div>
  );
};
