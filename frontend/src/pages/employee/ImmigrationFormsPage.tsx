/**
 * ImmigrationFormsPage — form-fill Phase 1 (System B, IMM-11).
 * Route: /employee/case/:caseId/immigration/forms   (flag: VITE_ENABLE_IMMIGRATION_FORMS)
 *
 * The employee sees the real government visa form(s) available for their corridor, generates a
 * pre-filled copy from their own case data, sees exactly which fields were filled (and from
 * where), and downloads the filled PDF. Values come only from real case data — a field that can't
 * be sourced is shown blank for the employee to complete, never guessed. Not legally verified.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Alert, Badge, Button, Card, Skeleton } from '../../components/antigravity';
import {
  immigrationFormsAPI,
  type AvailableForm,
  type FillReport,
  type FillReportField,
  type FillFieldStatus,
} from '../../api/immigrationForms';

type LoadState = 'loading' | 'ready' | 'error';

const STATUS_META: Record<FillFieldStatus, { label: string; variant: 'success' | 'warning' | 'error' | 'neutral' }> = {
  filled: { label: 'Filled', variant: 'success' },
  warning: { label: 'Check this', variant: 'warning' },
  blank_missing_data: { label: "You'll add this", variant: 'neutral' },
  not_in_pdf: { label: 'Not on this form', variant: 'error' },
};

function readDetail(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return typeof detail === 'string' && detail ? detail : fallback;
}

export const ImmigrationFormsPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();

  const [state, setState] = useState<LoadState>('loading');
  const [error, setError] = useState<string | null>(null);
  const [forms, setForms] = useState<AvailableForm[]>([]);

  const [generating, setGenerating] = useState<Record<string, boolean>>({});
  const [reports, setReports] = useState<Record<string, FillReport>>({});
  const [genErrors, setGenErrors] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    if (!caseId) {
      setError('No case ID in the URL.');
      setState('error');
      return;
    }
    setState('loading');
    setError(null);
    try {
      const res = await immigrationFormsAPI.getAvailableForms(caseId);
      setForms(res.forms);
      setState('ready');
    } catch (err) {
      setError(readDetail(err, 'Could not load your visa forms. Please try again.'));
      setState('error');
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  const generate = useCallback(
    async (formId: string) => {
      if (!caseId) return;
      setGenerating((g) => ({ ...g, [formId]: true }));
      setGenErrors((e) => {
        const next = { ...e };
        delete next[formId];
        return next;
      });
      try {
        const res = await immigrationFormsAPI.generateForm(caseId, formId);
        setReports((r) => ({ ...r, [formId]: res.fill_report }));
      } catch (err) {
        setGenErrors((e) => ({ ...e, [formId]: readDetail(err, 'Could not generate this form right now.') }));
      } finally {
        setGenerating((g) => ({ ...g, [formId]: false }));
      }
    },
    [caseId],
  );

  return (
    <AppShell
      title="Auto-fill your visa forms"
      subtitle="Generate a pre-filled copy of your official visa form from the details you've already given."
    >
      {state === 'loading' && (
        <div className="space-y-3 max-w-2xl">
          <Skeleton height="90px" />
          <Skeleton height="90px" />
        </div>
      )}

      {state === 'error' && (
        <div className="max-w-lg">
          <Alert variant="error" className="mb-4">{error}</Alert>
          <Button variant="outline" onClick={() => void load()}>Try again</Button>
        </div>
      )}

      {state === 'ready' && forms.length === 0 && (
        <div className="max-w-2xl">
          <Alert variant="info" title="No form to fill for this destination">
            The visa steps for your destination use an online portal or a prepared data sheet rather
            than a fillable government form, so there is nothing to auto-fill here.
          </Alert>
        </div>
      )}

      {state === 'ready' && forms.length > 0 && (
        <div className="space-y-4 max-w-2xl">
          <Alert variant="info" title="How this works">
            We fill each field from the details already on your case. Any field we cannot source is
            left blank for you to complete — we never guess. Check every value against your own
            documents before you submit; this is a draft to help you, not a legally verified application.
          </Alert>

          {forms.map((form) => (
            <FormCard
              key={form.form_id}
              form={form}
              generating={Boolean(generating[form.form_id])}
              report={reports[form.form_id]}
              error={genErrors[form.form_id]}
              onGenerate={() => void generate(form.form_id)}
            />
          ))}
        </div>
      )}
    </AppShell>
  );
};

interface FormCardProps {
  form: AvailableForm;
  generating: boolean;
  report: FillReport | undefined;
  error: string | undefined;
  onGenerate: () => void;
}

const FormCard: React.FC<FormCardProps> = ({ form, generating, report, error, onGenerate }) => (
  <Card padding="lg">
    <div className="flex items-start justify-between gap-4">
      <div>
        <h3 className="text-base font-semibold text-[#0b2b43]">{form.form_name}</h3>
        <p className="text-xs text-slate-500 mt-0.5">
          {form.field_count} field{form.field_count === 1 ? '' : 's'} · {form.corridor_to} · {form.visa_type}
        </p>
      </div>
      <Button variant="primary" onClick={onGenerate} disabled={generating}>
        {generating ? 'Filling…' : report ? 'Re-generate' : 'Pre-fill this form'}
      </Button>
    </div>

    {error && <Alert variant="warning" className="mt-4">{error}</Alert>}

    {report && (
      <div className="mt-5 border-t border-slate-200 pt-4">
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <Badge variant="success">{report.filled_count} filled</Badge>
          {report.blank_count > 0 && <Badge variant="neutral">{report.blank_count} to complete</Badge>}
          {report.warning_count > 0 && <Badge variant="warning">{report.warning_count} to check</Badge>}
          {report.not_in_pdf_count > 0 && <Badge variant="error">{report.not_in_pdf_count} not on form</Badge>}
          {report.download_url && (
            <a
              href={report.download_url}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto inline-flex items-center rounded-lg bg-[#0b2b43] px-3 py-1.5 text-sm font-medium text-white hover:bg-[#14405f]"
            >
              Download filled PDF
            </a>
          )}
        </div>

        <ul className="divide-y divide-slate-100">
          {report.fields.map((field) => (
            <FieldLine key={field.form_field_id} field={field} />
          ))}
        </ul>
      </div>
    )}
  </Card>
);

const FieldLine: React.FC<{ field: FillReportField }> = ({ field }) => {
  const meta = STATUS_META[field.status];
  return (
    <li className="flex items-start justify-between gap-3 py-2">
      <div className="min-w-0">
        <p className="text-sm text-[#0b2b43]">{field.label || field.form_field_id}</p>
        {field.value ? (
          <p className="text-sm text-slate-600 truncate">{field.value}</p>
        ) : (
          <p className="text-xs text-slate-500 italic">not provided yet</p>
        )}
        {field.warning && <p className="text-xs text-amber-700 mt-0.5">{field.warning}</p>}
      </div>
      <Badge variant={meta.variant} size="sm">{meta.label}</Badge>
    </li>
  );
};
