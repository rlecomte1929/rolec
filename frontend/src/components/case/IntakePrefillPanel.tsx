/**
 * IntakePrefillPanel — [W1-3b] HR reads the contract so the employee doesn't retype it.
 *
 * The employer already holds an employment contract carrying the employee's name, role,
 * salary, start date and work location, and the platform asks the employee to type all of
 * it again. This panel uploads that document, shows what was read from it with a confidence
 * per field, lets HR correct anything, and writes only on confirm.
 *
 * THE TWO-ENDPOINT SPLIT IS THE GATE, and this component must not undermine it:
 *
 *   POST .../intake-extraction/propose   OCR + extraction. Writes NOTHING.
 *   POST .../intake-extraction/confirm   The ONLY writer. Carries HR's EDITED values.
 *
 * So: nothing is posted to confirm until the button is pressed, and what is posted is
 * `values` (HR's version) rather than the proposal. Confidence is advisory — it orders
 * attention, it is never a threshold that auto-accepts or hides a field. There is no
 * confidence at which review is skipped, on the server either.
 *
 * Modelled on features/immigration/PassportOCRFlow.tsx (upload → processing → confirm), and
 * deliberately different from it in two places:
 *   * that flow hides a field with no extracted value (`if (!extracted) return null`). Here
 *     an unread field is exactly the one HR most needs to fill, so every field renders,
 *     empty and editable.
 *   * the accepted mime list is the SERVER's ALLOWED_MIME (pdf/docx/xlsx/png/jpeg), not the
 *     passport flow's image-only set — that one allows image/webp, which this endpoint rejects.
 *
 * Never renders the raw OCR text: it is document content (GDPR, CLAUDE.md).
 */
import React, { useCallback, useState } from 'react';
import { Alert, Button, Card } from '../antigravity';
import api from '../../api/client';

// The eleven flat snake_case keys the backend proposes. They are a subset of
// RECOGNISED_INTAKE_KEYS (backend/intake_draft_to_case_draft.py) — a key outside that set is
// stored and then silently ignored by the submit guard, so this list is not free-form.
const FIELD_LABELS: Record<string, string> = {
  full_name: 'Full name',
  nationality: 'Nationality (ISO)',
  job_title: 'Job title',
  salary_band: 'Salary',
  contract_type: 'Contract type',
  contract_start: 'Start date',
  target_date: 'Target move date',
  origin_city: 'Origin city',
  origin_country: 'Origin country (ISO)',
  dest_city: 'Destination city',
  dest_country: 'Destination country (ISO)',
};
const DISPLAY_FIELDS = Object.keys(FIELD_LABELS);

const DEFAULT_DOCUMENT_TYPE = 'employment_contract';
const DOCUMENT_TYPES: Array<{ value: string; label: string }> = [
  { value: DEFAULT_DOCUMENT_TYPE, label: 'Employment contract' },
  { value: 'offer_letter', label: 'Offer letter' },
];

// Mirrors backend/app/services/upload_validator.py ALLOWED_MIME + the 10 MiB cap in
// hr_intake_extraction.py. Client-side only to give a fast, clear message — the server
// re-validates regardless.
const ALLOWED_MIME = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'image/png',
  'image/jpeg',
];
const MAX_MB = 10;

export interface ProposedField {
  value: string | null;
  confidence: number;
}

export interface ProposeResponse {
  case_id: string;
  assignment_id: string;
  document_type: string;
  pages_count: number;
  fields: Record<string, ProposedField>;
  written: boolean;
}

export interface ConfirmResponse {
  case_id: string;
  assignment_id: string;
  written_fields: string[];
  skipped_fields: string[];
  provenance: string;
  intake_draft: Record<string, unknown>;
}

/** Advisory only. Mirrors the thresholds in PassportOCRFlow so the two read the same. */
export function ConfidenceDot({ score }: { score: number | undefined }) {
  if (score === undefined || score === null) return null;
  const pct = Math.round(score * 100);
  const color = pct >= 90 ? 'bg-[#22c55e]' : pct >= 70 ? 'bg-[#f59e0b]' : 'bg-[#ef4444]';
  return (
    <span className="inline-flex items-center gap-1" title={`Model confidence ${pct}%`}>
      <span className={`inline-block h-2 w-2 rounded-full ${color}`} />
      <span className="text-[10px] text-slate-500">{pct}%</span>
    </span>
  );
}

function errorDetail(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === 'string' && detail ? detail : fallback;
}

// ---------------------------------------------------------------------------
// Step 2: review + confirm. Exported so the test can drive it with a canned proposal
// rather than going through multipart upload — the same shape as PassportOCRFlow's test.
// ---------------------------------------------------------------------------

interface ConfirmStepProps {
  caseId: string;
  proposal: ProposeResponse;
  onConfirmed: (result: ConfirmResponse) => void;
  onDiscard: () => void;
}

export const ConfirmStep: React.FC<ConfirmStepProps> = ({
  caseId,
  proposal,
  onConfirmed,
  onDiscard,
}) => {
  // Local state IS the proposal until HR presses confirm. Every field is seeded, including
  // the ones that came back null — those render as empty inputs, not as absent rows.
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(DISPLAY_FIELDS.map((f) => [f, proposal.fields?.[f]?.value ?? ''])),
  );
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const readCount = DISPLAY_FIELDS.filter((f) => (proposal.fields?.[f]?.value ?? '') !== '').length;

  const confirmAndSave = useCallback(async () => {
    setSaving(true);
    setSaveError(null);
    try {
      // The ONLY write in this flow, and it sends `values` — HR's edited version — not the
      // proposal. Blank fields are dropped server-side rather than written as empty strings,
      // so an unanswered field leaves any existing employee answer alone.
      const resp = await api.post<ConfirmResponse>(
        `/api/hr/cases/${caseId}/intake-extraction/confirm`,
        { fields: values },
      );
      onConfirmed(resp.data);
    } catch (err: unknown) {
      setSaveError(errorDetail(err, 'Could not save the intake details. Please try again.'));
    } finally {
      setSaving(false);
    }
  }, [caseId, values, onConfirmed]);

  return (
    <div className="space-y-4">
      <div className="text-xs text-[#64748b]">
        Read {readCount} of {DISPLAY_FIELDS.length} fields from {proposal.pages_count || 0} page
        {proposal.pages_count === 1 ? '' : 's'}. Nothing has been saved yet.
      </div>

      <div className="rounded-lg border border-[#e2e8f0] overflow-hidden">
        <div className="grid grid-cols-[1fr_2fr_auto] bg-[#f8fafc] px-3 py-2 text-[10px] font-semibold text-[#64748b] uppercase tracking-wide border-b border-[#e2e8f0]">
          <span>Field</span>
          <span>Value</span>
          <span className="text-right w-14">Conf.</span>
        </div>
        {DISPLAY_FIELDS.map((field) => (
          <div
            key={field}
            className="grid grid-cols-[1fr_2fr_auto] items-center gap-2 px-3 py-2.5 border-b border-[#f1f5f9] last:border-b-0 hover:bg-[#fafbfc]"
          >
            <span className="text-sm text-[#475569]">{FIELD_LABELS[field]}</span>
            <input
              aria-label={FIELD_LABELS[field]}
              type="text"
              value={values[field] ?? ''}
              placeholder="Not found — add it if you know it"
              onChange={(e) => setValues((v) => ({ ...v, [field]: e.target.value }))}
              className="w-full rounded border border-[#e2e8f0] px-2 py-1 text-sm text-[#0f172a] font-medium focus:border-[#1f8e8b] focus:outline-none"
            />
            <span className="w-14 text-right">
              <ConfidenceDot score={proposal.fields?.[field]?.confidence} />
            </span>
          </div>
        ))}
      </div>

      <p className="text-xs text-slate-500">
        Confidence is how directly the document stated a value — a hint for what to
        double-check, not an approval. Correct anything that is wrong, then confirm.
      </p>

      {saveError && <Alert variant="error">{saveError}</Alert>}

      <div className="flex items-center justify-between gap-3 border-t border-[#e2e8f0] pt-4">
        <Button variant="outline" onClick={onDiscard} disabled={saving}>
          Discard
        </Button>
        <Button variant="primary" onClick={confirmAndSave} disabled={saving}>
          {saving ? 'Saving…' : 'Confirm & prefill intake →'}
        </Button>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Panel
// ---------------------------------------------------------------------------

type Step = 'upload' | 'processing' | 'confirm' | 'done';

export interface IntakePrefillPanelProps {
  /**
   * The RELOCATION case id, not the assignment PK. The endpoints resolve through
   * `_require_case_access` → `db.get_relocation_case`, so an assignment id 404s. The
   * command-center payload carries both as `caseId` and `id` respectively; the same
   * mix-up is already called out for the immigration endpoints on that page.
   */
  caseId: string;
}

export const IntakePrefillPanel: React.FC<IntakePrefillPanelProps> = ({ caseId }) => {
  const [step, setStep] = useState<Step>('upload');
  const [documentType, setDocumentType] = useState(DEFAULT_DOCUMENT_TYPE);
  const [file, setFile] = useState<File | null>(null);
  const [proposal, setProposal] = useState<ProposeResponse | null>(null);
  const [result, setResult] = useState<ConfirmResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFile = (f: File) => {
    if (f.type && !ALLOWED_MIME.includes(f.type)) {
      setError('Accepted formats: PDF, Word, Excel, PNG or JPEG.');
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`File is too large. Maximum size is ${MAX_MB} MB.`);
      return;
    }
    setError(null);
    setFile(f);
  };

  const propose = useCallback(async () => {
    if (!file) return;
    setStep('processing');
    setError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('document_type', documentType);
      // Reads the document. Writes nothing — the response is a proposal.
      const resp = await api.post<ProposeResponse>(
        `/api/hr/cases/${caseId}/intake-extraction/propose`,
        form,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      );
      setProposal(resp.data);
      setStep('confirm');
    } catch (err: unknown) {
      setError(errorDetail(err, 'Could not read that document. Try another file, or enter the intake by hand.'));
      setStep('upload');
    }
  }, [caseId, file, documentType]);

  const reset = () => {
    setFile(null);
    setProposal(null);
    setError(null);
    setStep('upload');
  };

  return (
    <Card padding="lg" className="border border-[#e2e8f0]">
      <div className="mb-4">
        <div className="text-sm font-semibold text-[#0b2b43]">Prefill intake from a document</div>
        <p className="text-xs text-slate-500 mt-0.5">
          Upload the employment contract or offer letter. You review every field before
          anything is saved.
        </p>
      </div>

      {error && (
        <div className="mb-3">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      {step === 'upload' && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs text-[#64748b]" htmlFor="intake-prefill-doctype">
              Document type
            </label>
            <select
              id="intake-prefill-doctype"
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value)}
              className="rounded border border-[#e2e8f0] px-2 py-1 text-sm text-[#0f172a] focus:border-[#1f8e8b] focus:outline-none"
            >
              {DOCUMENT_TYPES.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>
          <input
            aria-label="Contract or offer letter"
            type="file"
            accept={ALLOWED_MIME.join(',')}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
            }}
            className="block w-full text-sm text-[#475569] file:mr-3 file:rounded file:border-0 file:bg-[#0b2b43] file:px-3 file:py-1.5 file:text-sm file:text-white hover:file:bg-[#13405f]"
          />
          {file && <div className="text-xs text-[#64748b]">Selected: {file.name}</div>}
          <div className="flex justify-end">
            <Button variant="primary" onClick={propose} disabled={!file}>
              Read document →
            </Button>
          </div>
        </div>
      )}

      {step === 'processing' && (
        <div className="py-6 text-center text-sm text-[#64748b]">
          Reading the document… this usually takes a few seconds.
        </div>
      )}

      {step === 'confirm' && proposal && (
        <ConfirmStep
          caseId={caseId}
          proposal={proposal}
          onConfirmed={(r) => {
            setResult(r);
            setStep('done');
          }}
          onDiscard={reset}
        />
      )}

      {step === 'done' && result && (
        <div className="space-y-3">
          <Alert variant="success">
            Intake prefilled — {result.written_fields.length} field
            {result.written_fields.length === 1 ? '' : 's'} saved.
          </Alert>
          <div className="text-xs text-[#64748b]">
            Saved: {result.written_fields.map((f) => FIELD_LABELS[f] || f).join(', ') || '—'}
          </div>
          {result.skipped_fields.length > 0 && (
            <div className="text-xs text-slate-500">
              Left blank: {result.skipped_fields.map((f) => FIELD_LABELS[f] || f).join(', ')}
            </div>
          )}
          <div className="flex justify-end">
            <Button variant="outline" onClick={reset}>
              Upload another document
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
};

export default IntakePrefillPanel;
