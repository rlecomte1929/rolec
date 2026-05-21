/**
 * [P1-2B] PdfUploadField — upload an official form PDF to Supabase Storage.
 *
 * Storage bucket: `form-templates` (migration 20260521040000).
 * Path convention: <template_code>/<version>.pdf
 *
 * On successful upload the parent gets the public URL via `onUploaded`, which
 * the AdminFormTemplateEditor persists as `original_pdf_url` on the next save.
 *
 * Read access goes through signed URLs (bucket is private). We generate a
 * 1-hour signed URL for the "View PDF" link so the editor preview works
 * without making the whole bucket public.
 */
import React, { useCallback, useState } from 'react';
import { supabase } from '../../../../api/supabase';

const MAX_BYTES = 10 * 1024 * 1024;   // 10 MB
const BUCKET = 'form-templates';

export interface PdfUploadFieldProps {
  /** Form template code, used as the storage path prefix */
  templateCode: string;
  /** Template version, used as the filename stem */
  version: string;
  /** Current URL (signed or public) for "View PDF". Null when nothing uploaded yet. */
  currentUrl: string | null;
  /** Storage path of the currently-attached PDF (relative to bucket). Null if none. */
  currentPath: string | null;
  /** Called with the new storage path after a successful upload. */
  onUploaded: (path: string, signedUrl: string | null) => void;
  /** Disabled state for the whole field (e.g. when the template hasn't been created yet). */
  disabled?: boolean;
  /** Reason to show when disabled. */
  disabledHint?: string;
}

type UploadState =
  | { kind: 'idle' }
  | { kind: 'uploading' }
  | { kind: 'error'; message: string }
  | { kind: 'success' };

/** Build the path under the bucket: e.g. 'UTL-2011/1.0.0.pdf' */
function storagePathFor(templateCode: string, version: string): string {
  // Slashes and other characters that confuse Storage keys are unlikely in code
  // (it's already validated as ^[A-Z0-9\-]+ by ops convention) but cheap to guard.
  const cleanCode = templateCode.replace(/\//g, '_').replace(/\s/g, '_');
  const cleanVer  = version.replace(/\//g, '_').replace(/\s/g, '_');
  return `${cleanCode}/${cleanVer}.pdf`;
}

export const PdfUploadField: React.FC<PdfUploadFieldProps> = ({
  templateCode,
  version,
  currentUrl,
  currentPath,
  onUploaded,
  disabled,
  disabledHint,
}) => {
  const [state, setState] = useState<UploadState>({ kind: 'idle' });
  const [dragOver, setDragOver] = useState(false);

  const upload = useCallback(async (file: File) => {
    if (!templateCode.trim() || !version.trim()) {
      setState({ kind: 'error', message: 'Save the template (code + version) first, then upload a PDF.' });
      return;
    }
    if (file.type !== 'application/pdf') {
      setState({ kind: 'error', message: 'File must be a PDF.' });
      return;
    }
    if (file.size > MAX_BYTES) {
      setState({ kind: 'error', message: `PDF exceeds 10 MB (got ${(file.size / 1024 / 1024).toFixed(1)} MB).` });
      return;
    }

    setState({ kind: 'uploading' });
    const path = storagePathFor(templateCode, version);
    try {
      const { error: uploadError } = await supabase.storage
        .from(BUCKET)
        .upload(path, file, { upsert: true, contentType: 'application/pdf' });
      if (uploadError) {
        setState({ kind: 'error', message: uploadError.message || 'Upload failed.' });
        return;
      }

      // Generate a signed URL (1 hour) for the preview link
      const { data: signed, error: signError } = await supabase.storage
        .from(BUCKET)
        .createSignedUrl(path, 60 * 60);
      if (signError) {
        // Upload succeeded but we couldn't sign — still tell the parent the path.
        onUploaded(path, null);
        setState({ kind: 'success' });
        return;
      }

      onUploaded(path, signed?.signedUrl ?? null);
      setState({ kind: 'success' });
    } catch (e) {
      setState({ kind: 'error', message: (e as Error)?.message || 'Upload failed.' });
    }
  }, [templateCode, version, onUploaded]);

  const onFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void upload(file);
    // Reset so the same file can be picked again after a retry
    e.target.value = '';
  };

  const onDrop = (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (disabled) return;
    const file = e.dataTransfer.files?.[0];
    if (file) void upload(file);
  };

  const inputId = `pdf-upload-${templateCode || 'new'}`;

  if (disabled) {
    return (
      <div className="rounded border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
        {disabledHint || 'PDF upload available after saving the template.'}
      </div>
    );
  }

  return (
    <div className="grid gap-3">
      <label
        htmlFor={inputId}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`block cursor-pointer rounded border-2 border-dashed px-4 py-6 text-center transition-colors ${
          dragOver
            ? 'border-blue-300 bg-blue-50'
            : 'border-slate-200 bg-slate-50 hover:border-slate-300'
        }`}
      >
        <input
          id={inputId}
          type="file"
          accept="application/pdf"
          onChange={onFileSelect}
          className="sr-only"
        />
        <p className="text-sm font-medium text-slate-700">
          {state.kind === 'uploading'
            ? 'Uploading…'
            : currentPath
              ? 'Drop a new PDF here, or click to replace'
              : 'Drop a PDF here, or click to upload'}
        </p>
        <p className="text-xs text-slate-500 mt-1">PDF only · max 10 MB</p>
      </label>

      {state.kind === 'error' && (
        <div className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {state.message}
        </div>
      )}

      {currentPath && state.kind !== 'uploading' && (
        <div className="flex items-center gap-3 text-xs text-slate-600">
          <span>Attached: <code className="font-mono text-slate-700">{currentPath}</code></span>
          {currentUrl && (
            <a
              href={currentUrl}
              target="_blank"
              rel="noreferrer"
              className="text-[#0b2b43] hover:underline"
            >
              View PDF →
            </a>
          )}
        </div>
      )}

      {state.kind === 'success' && (
        <div className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
          Uploaded — don't forget to save the template to persist the URL.
        </div>
      )}
    </div>
  );
};

// Helper exposed for callers that need to sign a stored path on-demand
// (e.g. when loading an existing template that already has original_pdf_url
// pointing at a Storage path).
export async function signFormTemplatePdfUrl(
  storagePath: string,
  expiresSeconds: number = 3600,
): Promise<string | null> {
  if (!storagePath) return null;
  try {
    const { data, error } = await supabase.storage
      .from(BUCKET)
      .createSignedUrl(storagePath, expiresSeconds);
    if (error) return null;
    return data?.signedUrl ?? null;
  } catch {
    return null;
  }
}
