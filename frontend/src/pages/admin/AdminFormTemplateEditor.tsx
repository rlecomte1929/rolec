/**
 * [P1-2 / Phase 2A→2B] Admin Form Template Editor.
 *
 * Three tabs:
 *  - Basic info — code, name, country, category, authority, version (Phase 2A)
 *  - Fields     — drag-and-drop FieldDefinition list (Phase 2B)
 *  - PDF        — upload to Supabase Storage `form-templates` bucket (Phase 2B)
 *
 * Trigger rules editor is still deferred to Phase 2C — for now they're shown
 * read-only inline below the basic-info tab when present.
 *
 * Save modes:
 *  - "Save changes"            — in-place PATCH with no version change
 *  - "Save as new version"     — bumps version → backend INSERTs a new row
 *                                 preserving the old; we redirect to its editor
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { Input } from '../../components/antigravity/Input';
import { Button, Card } from '../../components/antigravity';
import {
  adminFormTemplatesAPI,
  type FormTemplate,
  type FormTemplateCreate,
} from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { getAuthItem } from '../../utils/demo';
import {
  FieldDefinitionEditor,
  normalizeFields,
  withComputedPositions,
  validateFieldDefinitions,
  type FieldDefinition,
} from '../../features/platform-v2/admin/form-templates/FieldDefinitionEditor';
import {
  PdfUploadField,
  signFormTemplatePdfUrl,
} from '../../features/platform-v2/admin/form-templates/PdfUploadField';
import { AdminLayout } from './AdminLayout';

const COUNTRY_OPTIONS: Array<{ code: string; label: string }> = [
  { code: 'NO', label: 'Norway' },
  { code: 'FR', label: 'France' },
  { code: 'DE', label: 'Germany' },
  { code: 'NL', label: 'Netherlands' },
  { code: 'ES', label: 'Spain' },
  { code: 'IT', label: 'Italy' },
  { code: 'CH', label: 'Switzerland' },
  { code: 'GB', label: 'United Kingdom' },
  { code: 'US', label: 'United States' },
  { code: 'CA', label: 'Canada' },
];

const CATEGORY_OPTIONS = [
  'registration',
  'work_permit',
  'residence_permit',
  'tax',
  'family',
  'health',
  'other',
];

type EditableForm = {
  code: string;
  name: string;
  country: string;
  authority_code: string;
  authority_name: string;
  category: string;
  /** The persisted reference to the PDF in Storage. Can be:
   *   - a full http(s) URL (legacy)
   *   - a bucket path like 'UTL-2011/1.0.0.pdf' (new Phase 2B convention)
   *   - empty
   */
  original_pdf_url: string;
  version: string;
};

const EMPTY_FORM: EditableForm = {
  code: '',
  name: '',
  country: 'NO',
  authority_code: '',
  authority_name: '',
  category: '',
  original_pdf_url: '',
  version: '1.0.0',
};

type TabKey = 'basic' | 'fields' | 'pdf';
const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'basic', label: 'Basic info' },
  { key: 'fields', label: 'Fields' },
  { key: 'pdf', label: 'PDF' },
];

function templateToForm(t: FormTemplate): EditableForm {
  return {
    code: t.code,
    name: t.name,
    country: t.country,
    authority_code: t.authority_code ?? '',
    authority_name: t.authority_name ?? '',
    category: t.category ?? '',
    original_pdf_url: t.original_pdf_url ?? '',
    version: t.version,
  };
}

function formToCreate(form: EditableForm): FormTemplateCreate {
  return {
    code: form.code.trim(),
    name: form.name.trim(),
    country: form.country.trim().toUpperCase(),
    authority_code: form.authority_code.trim() || null,
    authority_name: form.authority_name.trim() || null,
    category: form.category.trim() || null,
    original_pdf_url: form.original_pdf_url.trim() || null,
    version: form.version.trim(),
    fields: [],
    trigger_rules: {},
  };
}


export const AdminFormTemplateEditor: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isNew = !id || id === 'new';

  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<EditableForm>(EMPTY_FORM);
  const [loadedVersion, setLoadedVersion] = useState<string | null>(null);
  const [fields, setFields] = useState<FieldDefinition[]>([]);
  const [triggerRules, setTriggerRules] = useState<Record<string, unknown> | unknown[]>([]);
  const [tab, setTab] = useState<TabKey>('basic');
  const [pdfSignedUrl, setPdfSignedUrl] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (isNew) return;
    setLoading(true);
    setError(null);
    try {
      const t = await adminFormTemplatesAPI.get(id);
      setForm(templateToForm(t));
      setLoadedVersion(t.version);
      setFields(normalizeFields(t.fields ?? []));
      setTriggerRules(t.trigger_rules ?? []);
      // If original_pdf_url looks like a bucket path (no scheme), sign it for preview.
      const ref = t.original_pdf_url ?? '';
      if (ref && !/^https?:\/\//i.test(ref)) {
        const signed = await signFormTemplatePdfUrl(ref);
        setPdfSignedUrl(signed);
      } else {
        setPdfSignedUrl(ref || null);
      }
    } catch (e) {
      setError((e as Error)?.message || 'Failed to load form template');
    } finally {
      setLoading(false);
    }
  }, [id, isNew]);

  useEffect(() => {
    void load();
  }, [load]);

  const update = <K extends keyof EditableForm>(k: K, v: EditableForm[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const basicValidationError = useMemo<string | null>(() => {
    if (!form.code.trim()) return 'Code is required.';
    if (!form.name.trim()) return 'Name is required.';
    if (!form.country.trim()) return 'Country is required.';
    if (form.country.trim().length !== 2)
      return 'Country must be a 2-letter ISO code (e.g. NO).';
    if (!form.version.trim()) return 'Version is required.';
    return null;
  }, [form]);

  const fieldsValidationError = useMemo(
    () => validateFieldDefinitions(fields),
    [fields],
  );

  const isVersionBump = !isNew && loadedVersion !== null && form.version.trim() !== loadedVersion;

  const save = async () => {
    if (basicValidationError) {
      setError(basicValidationError);
      setTab('basic');
      return;
    }
    if (fieldsValidationError) {
      setError(fieldsValidationError);
      setTab('fields');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload: FormTemplateCreate = {
        ...formToCreate(form),
        fields: withComputedPositions(fields) as unknown as Array<Record<string, unknown>>,
        trigger_rules: triggerRules as unknown as Record<string, unknown>,
      };
      if (isNew) {
        const created = await adminFormTemplatesAPI.create(payload);
        navigate(buildRoute('adminFormTemplatesEdit', { id: created.id }), {
          replace: true,
        });
      } else {
        const updated = await adminFormTemplatesAPI.update(id, payload);
        if (updated.id !== id) {
          navigate(buildRoute('adminFormTemplatesEdit', { id: updated.id }), {
            replace: true,
          });
        } else {
          setLoadedVersion(updated.version);
          setForm(templateToForm(updated));
          setFields(normalizeFields(updated.fields ?? []));
          setTriggerRules(updated.trigger_rules ?? []);
        }
      }
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err.response?.data?.detail || err.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const role = getAuthItem('relopass_role');
  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Form template" subtitle="Restricted">
        <div className="py-8 text-center text-slate-500">Admin only.</div>
      </AdminLayout>
    );
  }

  const title = isNew
    ? 'New form template'
    : `${form.code || 'Form template'} · v${form.version || '—'}`;

  const onPdfUploaded = (path: string, signedUrl: string | null) => {
    setForm((f) => ({ ...f, original_pdf_url: path }));
    setPdfSignedUrl(signedUrl);
  };

  // The PDF tab is meaningful only after the template has been created (we
  // need the code + version locked in to derive the storage path).
  const pdfDisabled = isNew;

  return (
    <AdminLayout
      title={title}
      subtitle={
        isNew
          ? 'Define the basic info first; the Fields and PDF tabs unlock after the first save.'
          : 'Edit basic info, fields, or attach the official PDF. Bump the version to create a new revision.'
      }
      headerRight={
        <Link to={buildRoute('adminFormTemplates')}>
          <Button variant="secondary">← Back to list</Button>
        </Link>
      }
    >
      {loading ? (
        <div className="py-12 text-center text-slate-500">Loading…</div>
      ) : (
        <div className="grid gap-6 max-w-4xl">
          {error && (
            <div className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </div>
          )}

          {/* Tab strip */}
          <div className="flex items-center gap-1 border-b border-slate-200">
            {TABS.map((t) => {
              const isActive = tab === t.key;
              const isDisabled = isNew && t.key !== 'basic';
              return (
                <Button unstyled
                  key={t.key}
                  type="button"
                  onClick={() => !isDisabled && setTab(t.key)}
                  disabled={isDisabled}
                  className={`relative px-4 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'text-[#0b2b43]'
                      : isDisabled
                        ? 'text-slate-500 cursor-not-allowed'
                        : 'text-slate-500 hover:text-slate-700'
                  }`}
                  title={isDisabled ? 'Save the template first' : undefined}
                >
                  {t.label}
                  {isActive && (
                    <span className="absolute left-0 right-0 -bottom-px h-0.5 bg-[#0b2b43]" />
                  )}
                </Button>
              );
            })}
          </div>

          {tab === 'basic' && (
            <>
              <Card padding="lg">
                <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide mb-4">
                  Basic info
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <Field label="Code" required hint="e.g. UTL-2011">
                    <Input unstyled
                      value={form.code}
                      onChange={(v) => update('code', v)}
                      className="w-full rounded border border-slate-200 px-3 py-2 text-sm font-mono"
                      placeholder="UTL-2011"
                      // eslint-disable-next-line jsx-a11y/no-autofocus -- new form: focus Code field so keyboard users can start typing immediately
                      autoFocus={isNew}
                    />
                  </Field>

                  <Field label="Version" required hint='Bump to create a new revision (e.g. "2.0.0")'>
                    <Input unstyled
                      value={form.version}
                      onChange={(v) => update('version', v)}
                      className="w-full rounded border border-slate-200 px-3 py-2 text-sm font-mono"
                      placeholder="1.0.0"
                    />
                  </Field>

                  <Field label="Name" required className="col-span-2">
                    <Input unstyled
                      value={form.name}
                      onChange={(v) => update('name', v)}
                      className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                      placeholder="Notification of move (NO)"
                    />
                  </Field>

                  <Field label="Country" required hint="ISO 3166-1 alpha-2">
                    <select
                      value={form.country}
                      onChange={(e) => update('country', e.target.value)}
                      className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                    >
                      {COUNTRY_OPTIONS.map((c) => (
                        <option key={c.code} value={c.code}>
                          {c.code} · {c.label}
                        </option>
                      ))}
                    </select>
                  </Field>

                  <Field label="Category">
                    <select
                      value={form.category}
                      onChange={(e) => update('category', e.target.value)}
                      className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                    >
                      <option value="">— none —</option>
                      {CATEGORY_OPTIONS.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </Field>

                  <Field label="Authority code" hint="e.g. UDI, OFII">
                    <Input unstyled
                      value={form.authority_code}
                      onChange={(v) => update('authority_code', v)}
                      className="w-full rounded border border-slate-200 px-3 py-2 text-sm font-mono"
                      placeholder="UDI"
                    />
                  </Field>

                  <Field label="Authority name">
                    <Input unstyled
                      value={form.authority_name}
                      onChange={(v) => update('authority_name', v)}
                      className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                      placeholder="Norwegian Directorate of Immigration"
                    />
                  </Field>
                </div>
              </Card>

              {!isNew && (
                <Card padding="lg">
                  <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide mb-2">
                    Trigger rules <span className="text-xs font-normal text-slate-500">(Phase 2C — read-only)</span>
                  </h2>
                  <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-3 max-h-64 overflow-auto">
                    {JSON.stringify(triggerRules, null, 2)}
                  </pre>
                </Card>
              )}
            </>
          )}

          {tab === 'fields' && !isNew && (
            <Card padding="lg">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
                  Fields
                </h2>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-500">
                    {fields.length} field{fields.length === 1 ? '' : 's'} · drag to reorder
                  </span>
                  <Link
                    to={buildRoute('adminFormTemplatesMap', { id: id })}
                    className="text-xs font-medium text-[#0b2b43] hover:underline focus:outline-none focus:underline"
                  >
                    Map coordinates →
                  </Link>
                </div>
              </div>
              <FieldDefinitionEditor
                value={fields}
                onChange={setFields}
                disabled={saving}
              />
              {fieldsValidationError && (
                <div className="mt-3 text-xs text-rose-600">{fieldsValidationError}</div>
              )}
            </Card>
          )}

          {tab === 'pdf' && !isNew && (
            <Card padding="lg">
              <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide mb-3">
                Official PDF
              </h2>
              <p className="text-xs text-slate-500 mb-4">
                Uploads land in the <code className="font-mono">form-templates</code> bucket at{' '}
                <code className="font-mono">{form.code || '<code>'}/{form.version || '<version>'}.pdf</code>.
                Save the template after uploading to persist the reference.
              </p>
              <PdfUploadField
                templateCode={form.code}
                version={form.version}
                currentPath={form.original_pdf_url || null}
                currentUrl={pdfSignedUrl}
                onUploaded={onPdfUploaded}
                disabled={pdfDisabled}
                disabledHint="Save the template first, then upload a PDF."
              />
            </Card>
          )}

          <div className="flex items-center gap-3">
            <Button
              onClick={save}
              disabled={saving || !!basicValidationError || !!fieldsValidationError}
              variant="primary"
            >
              {saving
                ? 'Saving…'
                : isNew
                  ? 'Create template'
                  : isVersionBump
                    ? `Save as new version (${form.version})`
                    : 'Save changes'}
            </Button>
            {!isNew && isVersionBump && (
              <span className="text-xs text-slate-500">
                Will create a new row; the current v{loadedVersion} is preserved.
              </span>
            )}
            {(basicValidationError || fieldsValidationError) && (
              <span className="text-xs text-rose-600">
                {basicValidationError || fieldsValidationError}
              </span>
            )}
          </div>
        </div>
      )}
    </AdminLayout>
  );
};

// ---------------------------------------------------------------------------
// Local Field helper — light wrapper so all rows in the form look identical.
// ---------------------------------------------------------------------------

const Field: React.FC<{
  label: string;
  required?: boolean;
  hint?: string;
  className?: string;
  children: React.ReactNode;
}> = ({ label, required, hint, className, children }) => (
  <div className={className}>
    <label className="block text-xs font-medium text-slate-600 mb-1">
      {label}
      {required && <span className="text-rose-500 ml-0.5">*</span>}
    </label>
    {children}
    {hint && <div className="mt-1 text-[11px] text-slate-500">{hint}</div>}
  </div>
);
