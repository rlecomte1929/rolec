/**
 * [AIQ-1855] Immigration form pre-fill — the dossier action that finally reaches the
 * IMM-11 pre-fill backend (shipped since IMM-11, unreachable by any user until now).
 *
 * One component, both personas: HR on the case dossier and the relocating employee on
 * their own dossier. `role` picks the endpoint tree; the backend authorises the case
 * and resolves the corridor, so this only needs the caseId.
 *
 * Honesty by construction:
 *  - The action renders ONLY when the corridor actually has a fillable AcroForm form.
 *    A portal/data-sheet corridor (e.g. Norway) returns no forms → nothing is shown.
 *  - The fill report distinguishes three states per field — filled / missing /
 *    needs-review — so a low-confidence or unmapped value is never dressed up as filled.
 *  - Field VALUES are never rendered (they are PII); only the field label + its state.
 *  - A backend refusal (403 consent / 404 no profile / 4xx) surfaces as readable copy,
 *    never a blank panel or an endless spinner.
 */
import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Download, FileText, MinusCircle } from 'lucide-react';
import { Alert, Badge, Button, Card, Select } from '../../components/antigravity';
import {
  immigrationFormsAPI,
  type AvailableForm,
  type DossierRole,
  type FormFillStatus,
  type GenerateFormResponse,
} from '../../api/dossier';

type UiState = 'filled' | 'missing' | 'needs_review';

// Backend has four statuses; the report shows three. `warning` (filled but
// low-confidence / exact-match caution) and `not_in_pdf` (vault had a value but the
// template has no matching field) both mean "a human should look" → needs-review.
function toUiState(status: FormFillStatus): UiState {
  if (status === 'filled') return 'filled';
  if (status === 'blank_missing_data') return 'missing';
  return 'needs_review';
}

const STATE_META: Record<
  UiState,
  { label: string; variant: 'success' | 'warning' | 'neutral'; Icon: typeof CheckCircle2 }
> = {
  filled: { label: 'Filled', variant: 'success', Icon: CheckCircle2 },
  needs_review: { label: 'Needs review', variant: 'warning', Icon: AlertTriangle },
  missing: { label: 'Missing', variant: 'neutral', Icon: MinusCircle },
};

function readableError(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  const message = (err as { message?: unknown })?.message;
  if (typeof message === 'string' && message.trim()) return message;
  return 'Could not generate the form. Please try again.';
}

const FillReport: React.FC<{ result: GenerateFormResponse }> = ({ result }) => {
  const { fill_report: report, download_url: downloadUrl } = result;
  const needsReview = report.warning_count + report.not_in_pdf_count;

  return (
    <div className="mt-4 border-t border-gray-100 pt-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="success">{report.filled_count} filled</Badge>
        {needsReview > 0 && <Badge variant="warning">{needsReview} need review</Badge>}
        {report.blank_count > 0 && <Badge variant="neutral">{report.blank_count} missing</Badge>}
        {downloadUrl && (
          <a
            href={downloadUrl}
            target="_blank"
            rel="noreferrer"
            className="ml-auto inline-flex items-center gap-1 text-sm font-medium text-[#1f8e8b] underline"
          >
            <Download className="h-4 w-4" aria-hidden /> Download PDF
          </a>
        )}
      </div>

      {report.fields.length > 0 && (
        <ul className="mt-3 space-y-1">
          {report.fields.map((field) => {
            const meta = STATE_META[toUiState(field.status)];
            const Icon = meta.Icon;
            return (
              <li key={field.form_field_id} className="flex items-start gap-2 text-xs">
                <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-500" aria-hidden />
                <span className="flex-1 text-slate-700">{field.label || field.form_field_id}</span>
                <Badge variant={meta.variant}>{meta.label}</Badge>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};

export const ImmigrationFormFill: React.FC<{ caseId: string; audience: DossierRole }> = ({ caseId, audience }) => {
  const [forms, setForms] = useState<AvailableForm[] | null>(null); // null = still loading
  const [selectedFormId, setSelectedFormId] = useState<string>('');
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<GenerateFormResponse | null>(null);
  const [genError, setGenError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setForms(null);
    setResult(null);
    setGenError(null);
    immigrationFormsAPI
      .available(caseId, audience)
      .then((res) => {
        if (!active) return;
        setForms(res.forms);
        setSelectedFormId(res.forms[0]?.form_id ?? '');
      })
      .catch(() => {
        // A corridor with no fillable form returns 200 + []. An error here (e.g. 422 —
        // the case has no resolvable corridor yet) means this surface does not apply to
        // the case: hide it rather than showing a broken panel.
        if (active) setForms([]);
      });
    return () => {
      active = false;
    };
  }, [caseId, audience]);

  // The action exists ONLY where there is a fillable form. Loading or none → render
  // nothing, so a data-sheet corridor never shows a dead button.
  if (!forms || forms.length === 0) return null;

  const selected = forms.find((form) => form.form_id === selectedFormId) ?? forms[0];
  if (!selected) return null; // forms is non-empty here; this narrows the type

  const onGenerate = async () => {
    setGenerating(true);
    setGenError(null);
    setResult(null);
    try {
      const res = await immigrationFormsAPI.generate(caseId, audience, selected.form_id);
      setResult(res);
    } catch (err) {
      setGenError(readableError(err));
    } finally {
      setGenerating(false);
    }
  };

  return (
    <Card className="mb-6">
      <div className="flex items-start gap-2">
        <FileText className="mt-0.5 h-5 w-5 shrink-0 text-[#1f8e8b]" aria-hidden />
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-[#0b2b43]">Pre-fill immigration forms</h3>
          <p className="mt-0.5 text-xs text-slate-500">
            Generate an official {selected.corridor_to} form, pre-filled from the immigration data on
            this case. Review every field before submitting — templates are representative, not legal advice.
          </p>

          {forms.length > 1 && (
            <div className="mt-3">
              <Select
                label="Form"
                fullWidth
                value={selected.form_id}
                onChange={(value) => {
                  setSelectedFormId(value);
                  setResult(null);
                  setGenError(null);
                }}
                options={forms.map((form) => ({ value: form.form_id, label: form.form_name }))}
              />
            </div>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Button onClick={() => void onGenerate()} disabled={generating}>
              {generating ? 'Generating…' : 'Generate pre-filled PDF'}
            </Button>
            {forms.length === 1 && <span className="text-xs text-slate-500">{selected.form_name}</span>}
          </div>

          {genError && (
            <Alert variant="warning" className="mt-3">
              {genError}
            </Alert>
          )}

          {result && <FillReport result={result} />}
        </div>
      </div>
    </Card>
  );
};
