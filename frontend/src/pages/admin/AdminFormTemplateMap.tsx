/**
 * [P3-2] AdminFormTemplateMap
 *
 * Admin page at /admin/form-templates/:id/map for assigning PDF field
 * coordinates. Two-column layout: PDF on the left, field list on the right.
 *
 * activeFieldId is managed here and passed down to both PdfCoordinateMapper
 * (canvas click handler) and FieldSelector (assign/move/clear buttons) so
 * they stay in sync without extra bridge components.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { AdminLayout } from './AdminLayout';
import { Button } from '../../components/antigravity';
import {
  adminFormTemplatesAPI,
  type FormTemplate,
} from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { getAuthItem } from '../../utils/demo';
import { signFormTemplatePdfUrl } from '../../features/platform-v2/admin/form-templates/PdfUploadField';
import {
  PdfCoordinateMapper,
  FieldSelector,
} from '../../features/platform-v2/admin/form-templates/PdfCoordinateMapper';
import {
  withComputedPositions,
  type FieldDefinition,
} from '../../features/platform-v2/admin/form-templates/FieldDefinitionEditor';

// ─────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────

function asFiniteNumber(v: unknown): number | undefined {
  return typeof v === 'number' && Number.isFinite(v) ? v : undefined;
}

function errorToString(err: unknown, fallback = 'An error occurred'): string {
  if (!err) return fallback;
  if (typeof err === 'string') return err || fallback;
  if (Array.isArray(err)) {
    return err
      .map((e) => (typeof e === 'object' && e && 'msg' in e ? String((e as { msg: string }).msg) : String(e)))
      .join('; ') || fallback;
  }
  if (typeof err === 'object' && 'message' in err) return String((err as { message: string }).message) || fallback;
  return fallback;
}

function normalizeFields(raw: Array<Record<string, unknown>>): FieldDefinition[] {
  return (raw || []).map((r, i) => ({
    id: typeof r.id === 'string' ? r.id : '',
    label: typeof r.label === 'string' ? r.label : '',
    type: ((r.type as FieldDefinition['type']) ?? 'text'),
    required: r.required === true,
    prefill_source: typeof r.prefill_source === 'string' ? r.prefill_source : undefined,
    requires_original: r.requires_original === true,
    position: typeof r.position === 'number' ? r.position : i + 1,
    options: Array.isArray(r.options) ? (r.options as string[]) : undefined,
    pdf_x: asFiniteNumber(r.pdf_x),
    pdf_y: asFiniteNumber(r.pdf_y),
    pdf_page: asFiniteNumber(r.pdf_page),
    pdf_font_size: asFiniteNumber(r.pdf_font_size),
  }));
}

// ─────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────

export const AdminFormTemplateMap: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const [template, setTemplate] = useState<FormTemplate | null>(null);
  const [fields, setFields] = useState<FieldDefinition[]>([]);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [activeFieldId, setActiveFieldId] = useState<string | null>(null);

  // ── Load ─────────────────────────────────────────────────────────
  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const t = await adminFormTemplatesAPI.get(id);
      setTemplate(t);
      setFields(normalizeFields(t.fields ?? []));
      const ref = t.original_pdf_url ?? '';
      if (!ref) {
        setPdfUrl(null);
      } else if (/^https?:\/\//i.test(ref)) {
        setPdfUrl(ref);
      } else {
        const signed = await signFormTemplatePdfUrl(ref);
        setPdfUrl(signed);
      }
    } catch (e) {
      const err = e as { response?: { data?: { detail?: unknown } }; message?: string };
      setError(errorToString(err.response?.data?.detail ?? err.message, 'Failed to load template'));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  // ── Field changes from mapper ─────────────────────────────────────
  const handleFieldsChange = useCallback((updated: FieldDefinition[]) => {
    setFields(updated);
    setSaveSuccess(false);
  }, []);

  // ── FieldSelector actions ─────────────────────────────────────────
  const handleActivate = useCallback((fieldId: string) => {
    // Toggle: activating an already-active field deselects it
    setActiveFieldId((prev) => (prev === fieldId ? null : fieldId));
  }, []);

  const handleClear = useCallback((fieldId: string) => {
    setFields((prev) =>
      prev.map((f) =>
        f.id === fieldId
          ? { ...f, pdf_x: undefined, pdf_y: undefined, pdf_page: undefined }
          : f,
      ),
    );
    setSaveSuccess(false);
  }, []);

  // ── Save ─────────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!id || !template) return;
    setSaving(true);
    setError(null);
    setSaveSuccess(false);
    try {
      await adminFormTemplatesAPI.update(id, {
        code: template.code,
        name: template.name,
        country: template.country,
        authority_code: template.authority_code ?? null,
        authority_name: template.authority_name ?? null,
        category: template.category ?? null,
        original_pdf_url: template.original_pdf_url ?? null,
        version: template.version,
        fields: withComputedPositions(fields) as unknown as Array<Record<string, unknown>>,
        trigger_rules: (template.trigger_rules ?? {}),
      });
      setSaveSuccess(true);
    } catch (e) {
      const err = e as { response?: { data?: { detail?: unknown } }; message?: string };
      setError(errorToString(err.response?.data?.detail ?? err.message, 'Save failed'));
    } finally {
      setSaving(false);
    }
  };

  // ── Access guard ─────────────────────────────────────────────────
  const role = getAuthItem('relopass_role');
  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="PDF Coordinate Map" subtitle="Restricted">
        <div className="py-8 text-center text-slate-500">Admin only.</div>
      </AdminLayout>
    );
  }

  const title = template
    ? `Map fields — ${template.code} · v${template.version}`
    : 'Map fields';

  const assignedCount = fields.filter(
    (f) => f.pdf_x != null && f.pdf_y != null && f.pdf_page != null,
  ).length;

  return (
    <AdminLayout
      title={title}
      subtitle="Click on the PDF to place each field. Coordinates are stored as PDF points (origin at the page's bottom-left) and consumed verbatim by the overlay engine."
      headerRight={
        <Link
          to={id ? buildRoute('adminFormTemplatesEdit', { id }) : buildRoute('adminFormTemplates')}
        >
          <Button variant="secondary">← Back to editor</Button>
        </Link>
      }
    >
      {loading ? (
        <div className="py-12 text-center text-slate-500">Loading…</div>
      ) : (
        <div className="flex flex-col gap-4">
          {/* Error / success */}
          {error && (
            <div className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </div>
          )}
          {saveSuccess && (
            <div className="rounded border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              Coordinates saved successfully.
            </div>
          )}

          {/* No PDF uploaded */}
          {!pdfUrl && (
            <div className="rounded border border-amber-200 bg-amber-50 px-4 py-6 text-center text-sm text-amber-800">
              <p className="font-medium mb-1">No PDF uploaded for this template.</p>
              <p>
                Go to the{' '}
                <Link
                  to={id ? buildRoute('adminFormTemplatesEdit', { id }) : '#'}
                  className="underline"
                >
                  PDF tab
                </Link>{' '}
                in the template editor and upload the official form PDF first.
              </p>
            </div>
          )}

          {/* Main layout */}
          {pdfUrl && (
            <div className="grid grid-cols-[1fr_300px] gap-6 items-start">
              {/* Left — PDF mapper */}
              <PdfCoordinateMapper
                pdfUrl={pdfUrl}
                fields={fields}
                onChange={handleFieldsChange}
                activeFieldId={activeFieldId}
                onActiveFieldIdChange={setActiveFieldId}
                disabled={saving}
              />

              {/* Right — Field selector + save */}
              <div className="flex flex-col gap-4 sticky top-4">
                <div className="rounded border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wide">
                      Fields
                    </h2>
                    <span className="text-xs text-slate-500">
                      {assignedCount}/{fields.length} placed
                    </span>
                  </div>
                  <FieldSelector
                    fields={fields}
                    activeFieldId={activeFieldId}
                    onActivate={handleActivate}
                    onClear={handleClear}
                    disabled={saving}
                  />
                </div>

                <Button onClick={handleSave} disabled={saving} variant="primary">
                  {saving ? 'Saving…' : 'Save coordinates'}
                </Button>

                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Coordinates are stored as raw PDF points (1 pt ≈ 1/72 in). The
                  Y-axis origin is at the page's bottom-left, matching the PDF
                  spec. The overlay engine writes values directly at these
                  coordinates on top of the original PDF.
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </AdminLayout>
  );
};
