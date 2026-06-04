/**
 * [P1-05c + checklist] FormDocuments — required-document checklist + supporting
 * document upload/list for a single dossier form. Rendered in the expanded
 * CaseFormCard.
 *
 * - Checklist: one row per required supporting document (derived server-side
 *   from the template fields that require an original). An item is "provided"
 *   when an uploaded document carries its doc_key.
 * - Upload: per-checklist-item (tags the upload with that doc_key) or general.
 * - List: all uploaded documents with a signed download link + delete.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { formDocumentsAPI, type FormDocument } from '../../../api/dossier';
import { logger } from '../../../lib/logger';

export interface RequiredDocument {
  key: string;
  label: string;
}

export interface FormDocumentsProps {
  caseId: string;
  formId: string;
  requiredDocuments?: RequiredDocument[];
}

function formatSize(bytes: number | null): string {
  if (!bytes && bytes !== 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const FormDocuments: React.FC<FormDocumentsProps> = ({
  caseId,
  formId,
  requiredDocuments = [],
}) => {
  const [docs, setDocs] = useState<FormDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  // doc_key to tag the next file selection with (null = general attachment).
  const pendingDocKey = useRef<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setDocs(await formDocumentsAPI.list(caseId, formId));
      setError(null);
    } catch (e) {
      logger.error('[P1-05c] failed to load form documents', e);
      setError('Could not load documents.');
    } finally {
      setLoading(false);
    }
  }, [caseId, formId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleFile = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      const docKey = pendingDocKey.current;
      pendingDocKey.current = null;
      if (file) {
        setBusy(true);
        setError(null);
        try {
          await formDocumentsAPI.upload(caseId, formId, file, docKey);
          await load();
        } catch (err) {
          const ex = err as { response?: { data?: { detail?: string } }; message?: string };
          setError(ex.response?.data?.detail || ex.message || 'Upload failed.');
        } finally {
          setBusy(false);
        }
      }
      if (inputRef.current) inputRef.current.value = ''; // allow re-uploading the same file
    },
    [caseId, formId, load],
  );

  const pickFile = useCallback((docKey: string | null) => {
    pendingDocKey.current = docKey;
    inputRef.current?.click();
  }, []);

  const handleDelete = useCallback(
    async (documentId: string) => {
      setBusy(true);
      setError(null);
      try {
        await formDocumentsAPI.remove(caseId, formId, documentId);
        await load();
      } catch (err) {
        const ex = err as { response?: { data?: { detail?: string } }; message?: string };
        setError(ex.response?.data?.detail || ex.message || 'Delete failed.');
      } finally {
        setBusy(false);
      }
    },
    [caseId, formId, load],
  );

  const providedKeys = useMemo(
    () => new Set(docs.map((d) => d.doc_key).filter((k): k is string => !!k)),
    [docs],
  );
  const labelForKey = useMemo(() => {
    const m = new Map<string, string>();
    requiredDocuments.forEach((r) => m.set(r.key, r.label));
    return m;
  }, [requiredDocuments]);

  return (
    <div className="rounded border border-slate-200 px-3 py-2">
      {/* Single hidden input, reused for every upload affordance. */}
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        onChange={(e) => void handleFile(e)}
        disabled={busy}
        aria-label="Upload supporting document"
      />

      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Supporting documents
        </span>
        <button
          type="button"
          onClick={() => pickFile(null)}
          disabled={busy}
          className={`text-sm font-medium text-[#0b2b43] hover:underline ${busy ? 'opacity-50' : ''}`}
        >
          {busy ? 'Working…' : '+ Upload'}
        </button>
      </div>

      {error && (
        <div className="mb-2 rounded border border-rose-200 bg-rose-50 px-2 py-1 text-xs text-rose-700">
          {error}
        </div>
      )}

      {/* Required-document checklist */}
      {requiredDocuments.length > 0 && (
        <ul className="mb-2 flex flex-col gap-1" data-testid="required-doc-checklist">
          {requiredDocuments.map((req) => {
            const provided = providedKeys.has(req.key);
            return (
              <li key={req.key} className="flex items-center gap-2 text-sm">
                <span
                  className={`shrink-0 inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] ${
                    provided ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-400'
                  }`}
                  aria-hidden="true"
                >
                  {provided ? '✓' : '○'}
                </span>
                <span className={provided ? 'text-slate-700' : 'text-slate-600'}>{req.label}</span>
                {!provided && (
                  <button
                    type="button"
                    onClick={() => pickFile(req.key)}
                    disabled={busy}
                    className="ml-auto shrink-0 text-xs text-[#0b2b43] hover:underline disabled:opacity-50"
                  >
                    Upload
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {/* Uploaded documents */}
      {loading ? (
        <p className="text-xs text-slate-400">Loading documents…</p>
      ) : docs.length === 0 ? (
        <p className="text-xs text-slate-400">No documents uploaded yet.</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {docs.map((d) => (
            <li key={d.id} className="flex items-center gap-2 text-sm">
              {d.download_url ? (
                <a
                  href={d.download_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[#0b2b43] hover:underline truncate"
                >
                  {d.file_name}
                </a>
              ) : (
                <span className="text-slate-700 truncate">{d.file_name}</span>
              )}
              {d.doc_key && labelForKey.has(d.doc_key) && (
                <span className="shrink-0 rounded bg-emerald-50 px-1.5 text-[10px] text-emerald-700 border border-emerald-200">
                  {labelForKey.get(d.doc_key)}
                </span>
              )}
              {d.size_bytes != null && (
                <span className="text-[11px] text-slate-400 shrink-0">{formatSize(d.size_bytes)}</span>
              )}
              <button
                type="button"
                onClick={() => void handleDelete(d.id)}
                disabled={busy}
                className="ml-auto shrink-0 text-xs text-slate-400 hover:text-rose-600 disabled:opacity-50"
                aria-label={`Delete ${d.file_name}`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default FormDocuments;
