/**
 * PassportOCRFlow — IMM-09
 *
 * Three-step flow for passport upload + OCR confirmation:
 *
 *   Step 1 — Upload
 *     Drag-and-drop or file picker (JPEG/PNG/WebP, ≤10 MB).
 *     Shows a preview thumbnail after selection.
 *     "Upload & scan" → POST /api/employee/cases/:caseId/profile/ocr-passport (multipart)
 *
 *   Step 2 — Processing
 *     Spinner with progress messages while waiting for the GPT-4o OCR call.
 *
 *   Step 3 — Confirm
 *     Two-column layout: extracted fields on the left (with confidence dot),
 *     current vault values on the right.
 *     "Save extracted data" → calls onSaved() and the extracted fields are now
 *     in the vault (the backend auto-saved them; this step just confirms).
 *     "Discard & enter manually" → calls onDiscard().
 *
 * API: POST /api/employee/cases/:caseId/profile/ocr-passport
 *   Body: multipart/form-data { file: File }
 *   Response: { extracted_fields, confidence, mrz_validation, conflicts, fields_saved }
 */

import React, { useCallback, useRef, useState } from 'react';
import { FileInput } from '../../components/antigravity/FileInput';
import { Alert, Button, Card, LoadingButton } from '../../components/antigravity';
import api from '../../api/client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface OcrExtractedFields {
  legal_first_name?: string;
  legal_last_name?: string;
  date_of_birth?: string;
  place_of_birth?: string;
  nationality?: string;
  gender?: string;
  passport_number?: string;
  passport_expiry?: string;
  passport_issue_date?: string;
  passport_country?: string;
  mrz_line1?: string;
  mrz_line2?: string;
  [key: string]: string | undefined;
}

// Structured error detail returned by the backend on 422
interface OcrErrorDetail {
  code: string;
  message: string;
  hint: string;
}

interface ConflictRecord {
  field_name: string;
  ocr_value: string;
  vault_value: string;
  vault_source: string;
}

interface MrzValidation {
  is_valid: boolean;
  error_fields?: string[];
  details?: Record<string, unknown>;
}

interface OcrResponse {
  extracted_fields: OcrExtractedFields;
  confidence: Record<string, number>;
  mrz_validation: MrzValidation | null;
  conflicts: ConflictRecord[];
  fields_saved: string[];
}

// ---------------------------------------------------------------------------
// Field display labels
// ---------------------------------------------------------------------------

const FIELD_LABELS: Record<string, string> = {
  legal_first_name: 'First name',
  legal_last_name: 'Last name',
  date_of_birth: 'Date of birth',
  place_of_birth: 'Place of birth',
  nationality: 'Nationality',
  gender: 'Gender',
  passport_number: 'Passport number',
  passport_expiry: 'Expiry date',
  passport_issue_date: 'Issue date',
  passport_country: 'Issuing country',
};

const DISPLAY_FIELDS = Object.keys(FIELD_LABELS);

// ---------------------------------------------------------------------------
// OCR error card — shown when the backend returns a 422 with a known error code
// ---------------------------------------------------------------------------

const OCR_ERROR_CONFIG: Record<
  string,
  { icon: string; title: string; tips: string[] }
> = {
  specimen_document: {
    icon: '🚫',
    title: 'Specimen document detected',
    tips: [
      'Specimen and sample passports cannot be processed.',
      'Please upload your actual, issued passport.',
    ],
  },
  no_mrz: {
    icon: '📄',
    title: 'No machine-readable zone found',
    tips: [
      'Your passport doesn\'t have the two lines of characters at the bottom (MRZ). This is normal for older passports.',
      'You can still skip this step and enter your details manually — it only takes a minute.',
    ],
  },
  not_a_passport: {
    icon: '🪪',
    title: 'This doesn\'t look like a passport',
    tips: [
      'Upload a photo of the biographical page — the page with your photo and personal details.',
      'Make sure all four corners of the page are visible.',
    ],
  },
  low_quality: {
    icon: '📷',
    title: 'Image quality too low',
    tips: [
      'Lay the passport flat on a table and take the photo directly above it.',
      'Use good lighting and avoid shadows or flash glare on the page.',
      'Make sure the text is in focus and all four corners are visible.',
    ],
  },
  partial_image: {
    icon: '✂️',
    title: 'Passport not fully visible',
    tips: [
      'The full biographical page must be visible, including the MRZ lines at the bottom.',
      'Move the camera further back so all four corners fit in the frame.',
    ],
  },
  low_confidence: {
    icon: '🔍',
    title: 'Couldn\'t read required fields',
    tips: [
      'Make sure the passport is flat and the image is sharp.',
      'Avoid shadows across the text and ensure good lighting.',
    ],
  },
};

const FALLBACK_ERROR_CONFIG = {
  icon: '⚠️',
  title: 'Scan failed',
  tips: ['Check your connection and try again, or skip this step and enter your details manually.'],
};

interface OcrErrorCardProps {
  error: OcrErrorDetail | string;
  onSkip: () => void;
}

const OcrErrorCard: React.FC<OcrErrorCardProps> = ({ error, onSkip }) => {
  const isStructured = typeof error === 'object' && error !== null;
  const code = isStructured ? (error).code : 'unknown';
  const message = isStructured ? (error).message : String(error);
  const hint = isStructured ? (error).hint : '';

  const config = OCR_ERROR_CONFIG[code] ?? FALLBACK_ERROR_CONFIG;

  return (
    <div className="rounded-xl border border-[#fecaca] bg-[#fff5f5] p-4 space-y-3">
      {/* Header */}
      <div className="flex items-start gap-3">
        <span className="text-2xl leading-none shrink-0">{config.icon}</span>
        <div>
          <p className="text-sm font-semibold text-[#7a2a2a]">{config.title}</p>
          <p className="text-sm text-[#991b1b] mt-0.5">{message}</p>
        </div>
      </div>

      {/* Tips */}
      {(config.tips.length > 0 || hint) && (
        <div className="pl-9 space-y-1.5">
          {hint && (
            <p className="text-xs text-[#7a2a2a]">{hint}</p>
          )}
          {config.tips.map((tip, i) => (
            <div key={i} className="flex items-start gap-1.5">
              <span className="text-[#f87171] text-xs mt-0.5 shrink-0">•</span>
              <p className="text-xs text-[#7a2a2a]">{tip}</p>
            </div>
          ))}
        </div>
      )}

      {/* Skip action */}
      <div className="pl-9 pt-1">
        <Button unstyled
          type="button"
          onClick={onSkip}
          className="text-xs font-medium text-[#0b2b43] underline underline-offset-2 hover:no-underline"
        >
          Skip scan — I&apos;ll enter my details manually →
        </Button>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Confidence indicator
// ---------------------------------------------------------------------------

function ConfidenceDot({ score }: { score: number | undefined }) {
  if (score === undefined) return null;
  const pct = Math.round(score * 100);
  const color = pct >= 90 ? 'bg-[#22c55e]' : pct >= 70 ? 'bg-[#f59e0b]' : 'bg-[#ef4444]';
  return (
    <span className="inline-flex items-center gap-1 ml-1.5">
      <span className={`inline-block h-2 w-2 rounded-full ${color}`} />
      <span className="text-[10px] text-[#94a3b8]">{pct}%</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Step 1: Upload
// ---------------------------------------------------------------------------

interface UploadStepProps {
  onUploaded: (result: OcrResponse) => void;
  onSkip: () => void;
  caseId: string;
}

const UploadStep: React.FC<UploadStepProps> = ({ caseId, onUploaded, onSkip }) => {
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<OcrErrorDetail | string | null>(null);

  const ALLOWED = ['image/jpeg', 'image/png', 'image/webp'];
  const MAX_MB = 10;

  const handleFile = (f: File) => {
    if (!ALLOWED.includes(f.type)) {
      setError('Only JPEG, PNG, or WebP images are accepted.');
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`File is too large. Maximum size is ${MAX_MB} MB.`);
      return;
    }
    setError(null);
    setFile(f);
    setPreview(URL.createObjectURL(f));
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
  }, []);

  const upload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const resp = await api.post<OcrResponse>(
        `/api/employee/cases/${caseId}/profile/ocr-passport`,
        form,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      onUploaded(resp.data);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      if (detail && typeof detail === 'object' && 'code' in detail) {
        // Structured error from the backend
        setError(detail as OcrErrorDetail);
      } else {
        // Plain string or unknown error
        setError({
          code: 'extraction_failed',
          message: typeof detail === 'string' ? detail : 'Upload failed. Please check your connection and try again.',
          hint: '',
        });
      }
      setUploading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload passport image"
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileRef.current?.click(); } }}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
          dragOver ? 'border-[#0b2b43] bg-[#f0f4f8]' : 'border-[#cbd5e1] bg-[#f8fafc] hover:border-[#94a3b8]'
        }`}
      >
        <FileInput
          ref={fileRef}
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
        />
        {preview ? (
          <div className="flex flex-col items-center gap-3">
            <img
              src={preview}
              alt="Passport preview"
              className="max-h-40 rounded-lg border border-[#e2e8f0] object-contain shadow-sm"
            />
            <p className="text-sm text-[#475569]">{file?.name}</p>
            <p className="text-xs text-[#94a3b8]">Click or drag to replace</p>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#e0f2fe]">
              <svg className="h-6 w-6 text-[#0369a1]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-[#374151]">
              Drop your passport photo page here, or click to browse
            </p>
            <p className="text-xs text-[#94a3b8]">JPEG, PNG, or WebP · max 10 MB</p>
          </div>
        )}
      </div>

      {error && <OcrErrorCard error={error} onSkip={onSkip} />}

      <div className="rounded-lg border border-[#fef3c7] bg-[#fffbeb] px-3 py-2.5 text-xs text-[#92400e]">
        <strong>Privacy note:</strong> The passport image is transmitted securely, processed for
        data extraction only, and stored encrypted. It is not used for facial recognition.
      </div>

      {file && (
        <div className="flex justify-end">
          <LoadingButton
            variant="primary"
            loading={uploading}
            loadingLabel="Scanning…"
            onClick={upload}
          >
            Upload & scan passport
          </LoadingButton>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Step 2: Processing
// ---------------------------------------------------------------------------

const ProcessingStep: React.FC = () => (
  <div className="py-12 text-center space-y-4">
    <div className="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-[#e2e8f0] border-t-[#0b2b43]" />
    <p className="text-sm font-medium text-[#0b2b43]">Scanning passport…</p>
    <p className="text-xs text-[#94a3b8]">
      Extracting and verifying fields · validating MRZ checksums · checking for conflicts
    </p>
  </div>
);

// ---------------------------------------------------------------------------
// Step 3: Confirm
// ---------------------------------------------------------------------------

interface ConfirmStepProps {
  result: OcrResponse;
  onSaved: () => void;
  onDiscard: () => void;
}

const ConfirmStep: React.FC<ConfirmStepProps> = ({ result, onSaved, onDiscard }) => {
  const { extracted_fields, confidence, mrz_validation, conflicts, fields_saved } = result;

  return (
    <div className="space-y-5">
      {/* MRZ validation banner */}
      {mrz_validation && (
        <div className={`rounded-lg border px-3 py-2.5 text-sm flex items-start gap-2 ${
          mrz_validation.is_valid
            ? 'border-[#bbf7d0] bg-[#f0fdf4] text-[#166534]'
            : 'border-[#fecaca] bg-[#fff5f5] text-[#7a2a2a]'
        }`}>
          <span className="text-lg leading-none">{mrz_validation.is_valid ? '✅' : '⚠️'}</span>
          <div>
            <span className="font-medium">
              MRZ checksum {mrz_validation.is_valid ? 'passed' : 'failed'}
            </span>
            {!mrz_validation.is_valid && mrz_validation.error_fields?.length ? (
              <span className="ml-1 text-xs">
                — verify: {mrz_validation.error_fields.join(', ')}
              </span>
            ) : null}
          </div>
        </div>
      )}

      {/* Conflict warnings */}
      {conflicts.length > 0 && (
        <Alert variant="warning">
          <div className="text-sm font-medium mb-1">Conflicts with existing profile data</div>
          <ul className="text-xs space-y-1">
            {conflicts.map((c) => (
              <li key={c.field_name}>
                <strong>{FIELD_LABELS[c.field_name] || c.field_name}</strong>: OCR says &quot;
                {c.ocr_value}&quot; · profile ({c.vault_source}) has &quot;{c.vault_value}&quot; — the OCR value
                was saved; you can correct it in the interview.
              </li>
            ))}
          </ul>
        </Alert>
      )}

      {/* Two-column field table */}
      <div>
        <div className="text-sm font-semibold text-[#0b2b43] mb-2">Extracted fields</div>
        <div className="rounded-lg border border-[#e2e8f0] overflow-hidden">
          <div className="grid grid-cols-[1fr_auto_1fr] bg-[#f8fafc] px-3 py-2 text-[10px] font-semibold text-[#64748b] uppercase tracking-wide border-b border-[#e2e8f0]">
            <span>Extracted (OCR)</span>
            <span className="text-center w-8">Conf.</span>
            <span className="text-right">Field</span>
          </div>
          {DISPLAY_FIELDS.map((field) => {
            const extracted = extracted_fields[field];
            const conf = confidence[field];
            if (!extracted) return null;
            return (
              <div
                key={field}
                className="grid grid-cols-[1fr_auto_1fr] items-center px-3 py-2.5 border-b border-[#f1f5f9] last:border-b-0 hover:bg-[#fafbfc]"
              >
                <span className="text-sm text-[#0f172a] font-medium">
                  {field === 'passport_number' ? '••••••••' : extracted}
                </span>
                <span className="w-8 text-center">
                  <ConfidenceDot score={conf} />
                </span>
                <span className="text-sm text-[#475569] text-right">{FIELD_LABELS[field] || field}</span>
              </div>
            );
          })}
        </div>
        <p className="text-xs text-[#94a3b8] mt-1.5">
          {fields_saved.length} field{fields_saved.length !== 1 ? 's' : ''} saved to your profile ·
          passport number is masked above for display
        </p>
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-[#e2e8f0] pt-4">
        <Button variant="outline" onClick={onDiscard}>
          Discard & enter manually
        </Button>
        <Button variant="primary" onClick={onSaved}>
          Looks good — continue to interview →
        </Button>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

type FlowStep = 'upload' | 'processing' | 'confirm';

interface PassportOCRFlowProps {
  caseId: string;
  onComplete: () => void;
  onSkip: () => void;
}

export const PassportOCRFlow: React.FC<PassportOCRFlowProps> = ({ caseId, onComplete, onSkip }) => {
  const [step, setStep] = useState<FlowStep>('upload');
  const [result, setResult] = useState<OcrResponse | null>(null);

  const handleUploaded = (res: OcrResponse) => {
    setResult(res);
    setStep('confirm');
  };

  return (
    <div className="max-w-2xl mx-auto">
      <Card padding="lg">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-5">
          <div>
            <h2 className="text-lg font-semibold text-[#0b2b43]">Scan passport (optional)</h2>
            <p className="text-sm text-[#475569] mt-0.5">
              Upload a photo of your passport data page to auto-fill common fields. This saves time
              and reduces errors. You can skip this step and enter everything manually.
            </p>
          </div>
          <div className="flex gap-1 shrink-0">
            <span className={`text-[10px] px-2 py-1 rounded-full font-medium ${
              step === 'upload' ? 'bg-[#0b2b43] text-white' : 'bg-[#e2e8f0] text-[#64748b]'
            }`}>1 Upload</span>
            <span className={`text-[10px] px-2 py-1 rounded-full font-medium ${
              step === 'confirm' ? 'bg-[#0b2b43] text-white' : 'bg-[#e2e8f0] text-[#64748b]'
            }`}>2 Confirm</span>
          </div>
        </div>

        {step === 'upload' && (
          <>
            <UploadStep caseId={caseId} onUploaded={handleUploaded} onSkip={onSkip} />
            <div className="mt-4 border-t border-[#e2e8f0] pt-4 flex justify-center">
              <Button unstyled
                type="button"
                onClick={onSkip}
                className="text-sm text-[#64748b] hover:text-[#0b2b43] font-medium"
              >
                Skip — I&apos;ll enter details manually
              </Button>
            </div>
          </>
        )}

        {step === 'processing' && <ProcessingStep />}

        {step === 'confirm' && result && (
          <ConfirmStep
            result={result}
            onSaved={onComplete}
            onDiscard={onSkip}
          />
        )}
      </Card>
    </div>
  );
};
