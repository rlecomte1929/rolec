/**
 * CaseDocumentsPanel — immigration document upload + list (BL-OCR.4 / AIQ-750).
 *
 * One reusable panel mounted on two surfaces:
 *  - Employee immigration checklist (canUpload) — drag-and-drop upload widget.
 *  - HR immigration case detail (read-only) — document list with OCR status.
 *
 * Backend: POST/GET /api/immigration/cases/{caseId}/documents (immigrationDocumentsAPI).
 * While any document is pending/processing the list polls so the OCR status
 * badge advances to done/failed without a manual refresh.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Badge } from '../antigravity/Badge';
import { Button } from '../antigravity/Button';
import {
  immigrationDocumentsAPI,
  IMMIGRATION_DOC_MAX_BYTES,
  IMMIGRATION_DOC_ACCEPT,
  type ImmigrationDocument,
  type ImmigrationOcrStatus,
} from '../../api/immigrationDocuments';

const STATUS_META: Record<
  ImmigrationOcrStatus,
  { label: string; variant: 'neutral' | 'info' | 'success' | 'error' }
> = {
  pending: { label: 'AI extraction: pending', variant: 'neutral' },
  processing: { label: 'AI extraction: processing', variant: 'info' },
  done: { label: 'Extracted ✓', variant: 'success' },
  failed: { label: 'Extraction failed', variant: 'error' },
};

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function validateFile(file: File): string | null {
  if (!IMMIGRATION_DOC_ACCEPT.includes(file.type)) {
    return 'Unsupported file type. Upload a PDF or an image (PNG, JPEG, WEBP, TIFF).';
  }
  if (file.size > IMMIGRATION_DOC_MAX_BYTES) {
    return 'File is too large. The maximum size is 20 MB.';
  }
  return null;
}

export interface CaseDocumentsPanelProps {
  caseId: string;
  /** Show the upload widget (employee / assigned uploader surfaces). */
  canUpload?: boolean;
}

export function CaseDocumentsPanel({ caseId, canUpload = false }: CaseDocumentsPanelProps) {
  const [documents, setDocuments] = useState<ImmigrationDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const docs = await immigrationDocumentsAPI.list(caseId);
      setDocuments(docs);
      setError(null);
    } catch {
      setError('Could not load documents. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  // Poll while any document is still being processed so badges advance.
  const hasInFlight = documents.some(
    (d) => d.ocr_status === 'pending' || d.ocr_status === 'processing',
  );
  useEffect(() => {
    if (!hasInFlight) return;
    const t = setInterval(() => void load(), 5000);
    return () => clearInterval(t);
  }, [hasInFlight, load]);

  const handleUpload = useCallback(
    async (file: File) => {
      const validationError = validateFile(file);
      if (validationError) {
        setUploadError(validationError);
        return;
      }
      setUploadError(null);
      setUploading(true);
      setProgress(0);
      try {
        await immigrationDocumentsAPI.upload(caseId, file, setProgress);
        await load();
      } catch {
        setUploadError("Upload failed. Please try again — your file wasn't saved.");
      } finally {
        setUploading(false);
        setProgress(0);
      }
    },
    [caseId, load],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) void handleUpload(file);
    },
    [handleUpload],
  );

  return (
    <div>
      {canUpload && (
        <div className="mb-5">
          <div
            role="button"
            tabIndex={0}
            aria-label="Upload a document"
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click();
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            className={`rounded-xl border-2 border-dashed p-6 text-center cursor-pointer transition-colors ${
              dragOver ? 'border-[#0b2b43] bg-slate-50' : 'border-slate-200 hover:border-slate-300'
            }`}
          >
            <p className="text-sm font-medium text-slate-900">
              Drag a document here, or click to browse
            </p>
            <p className="mt-1 text-xs text-slate-500">
              PDF or image (PNG, JPEG, WEBP, TIFF) · up to 20 MB
            </p>
            {uploading && (
              <div className="mt-3">
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full bg-[#0b2b43] transition-all"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <p className="mt-1 text-xs text-slate-500">Uploading… {progress}%</p>
              </div>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept={IMMIGRATION_DOC_ACCEPT.join(',')}
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void handleUpload(file);
              e.target.value = '';
            }}
          />
          {uploadError && (
            <p role="alert" className="mt-2 text-xs text-red-500">
              {uploadError}
            </p>
          )}
        </div>
      )}

      {loading ? (
        <p className="py-8 text-center text-sm text-slate-500">Loading documents…</p>
      ) : error ? (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
          <Button unstyled onClick={() => void load()} className="ml-2 underline">
            Retry
          </Button>
        </div>
      ) : documents.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-500">
          No documents uploaded yet.
        </p>
      ) : (
        <ul className="space-y-2">
          {documents.map((doc) => {
            const meta = STATUS_META[doc.ocr_status];
            const isExpandable =
              doc.ocr_status === 'done' && doc.ocr_result && Object.keys(doc.ocr_result).length > 0;
            const isOpen = expanded === doc.document_id;
            return (
              <li
                key={doc.document_id}
                className="rounded-lg border border-slate-200 bg-white px-4 py-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900">{doc.file_name}</p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {formatBytes(doc.file_size_bytes)}
                      {doc.uploaded_at &&
                        ` · ${new Date(doc.uploaded_at).toLocaleDateString()}`}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge variant={meta.variant} size="sm">
                      {meta.label}
                    </Badge>
                    {isExpandable && (
                      <Button
                        unstyled
                        type="button"
                        onClick={() => setExpanded(isOpen ? null : doc.document_id)}
                        aria-expanded={isOpen}
                        className="text-xs font-medium text-accent-600 hover:text-accent-800"
                      >
                        {isOpen ? 'Hide' : 'View fields'}
                      </Button>
                    )}
                  </div>
                </div>
                {isOpen && isExpandable && (
                  <dl className="mt-3 grid grid-cols-1 gap-1 border-t border-slate-100 pt-3 sm:grid-cols-2">
                    {Object.entries(doc.ocr_result as Record<string, unknown>).map(([k, v]) => (
                      <div key={k} className="flex gap-2 text-xs">
                        <dt className="font-medium text-slate-500">{k}:</dt>
                        <dd className="truncate text-slate-800">
                          {typeof v === 'object' ? JSON.stringify(v) : String(v as string | number | boolean | bigint)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default CaseDocumentsPanel;
