/**
 * [P1-05c] FormDocuments — supporting-document upload + list for a single
 * dossier form. Rendered inside the expanded CaseFormCard.
 *
 * V1: upload to the case-documents bucket (scoped to case_id + form_id via the
 * backend), list uploaded files with a signed download link, and delete.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { formDocumentsAPI, type FormDocument } from '../../../api/dossier';
import { logger } from '../../../lib/logger';

export interface FormDocumentsProps {
  caseId: string;
  formId: string;
}

function formatSize(bytes: number | null): string {
  if (!bytes && bytes !== 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const FormDocuments: React.FC<FormDocumentsProps> = ({ caseId, formId }) => {
  const [docs, setDocs] = useState<FormDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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
      if (file) {
        setBusy(true);
        setError(null);
        try {
          await formDocumentsAPI.upload(caseId, formId, file);
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

  return (
    <div className="rounded border border-slate-200 px-3 py-2">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Supporting documents
        </span>
        <label
          className={`text-sm font-medium cursor-pointer text-[#0b2b43] hover:underline ${
            busy ? 'opacity-50 pointer-events-none' : ''
          }`}
        >
          {busy ? 'Working…' : '+ Upload'}
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            onChange={(e) => void handleFile(e)}
            disabled={busy}
            aria-label="Upload supporting document"
          />
        </label>
      </div>

      {error && (
        <div className="mb-2 rounded border border-rose-200 bg-rose-50 px-2 py-1 text-xs text-rose-700">
          {error}
        </div>
      )}

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
