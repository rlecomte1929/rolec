import { useEffect, useState } from 'react';
import * as pdfjs from 'pdfjs-dist';
// Vite resolves this to a URL string for the bundled worker file.
// pdfjs-dist 4.x ships the worker as an ESM module — we register that
// URL once, at module-load time, with the global pdf.js worker config.
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import type { PDFDocumentProxy } from 'pdfjs-dist';

// Register the worker once per module. pdf.js will throw if anyone
// calls getDocument() before this runs, so it lives at the top of the
// module rather than inside the hook.
pdfjs.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

interface UsePdfDocumentResult {
  document: PDFDocumentProxy | null;
  numPages: number;
  isLoading: boolean;
  error: Error | null;
}

/**
 * Loads a PDF off the network and returns the pdf.js document handle.
 *
 * Lifecycle:
 *   - Triggers on `documentUri` change.
 *   - Aborts in flight loads when the URI changes again, so React
 *     strict-mode double-mount + fast prop changes don't leak handles.
 *   - Calls `.destroy()` on the document when unmounting (pdf.js
 *     mandates this — the worker holds the parsed tree until you do).
 */
export function usePdfDocument(documentUri: string | null): UsePdfDocumentResult {
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!documentUri) {
      setDocument(null);
      setNumPages(0);
      setError(null);
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    const task = pdfjs.getDocument({ url: documentUri });
    task.promise
      .then((doc) => {
        if (cancelled) {
          void doc.destroy();
          return;
        }
        setDocument(doc);
        setNumPages(doc.numPages);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err : new Error(String(err)));
        setIsLoading(false);
      });

    return () => {
      cancelled = true;
      // Cancel the load. Destroy any document that was returned.
      void task.destroy();
    };
  }, [documentUri]);

  // Ensure the active document is destroyed on unmount (the load-cancel
  // effect handles in-flight loads; this handles the steady-state doc).
  useEffect(() => {
    return () => {
      if (document) {
        void document.destroy();
      }
    };
  }, [document]);

  return { document, numPages, isLoading, error };
}
