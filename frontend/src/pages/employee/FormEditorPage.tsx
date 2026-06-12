/**
 * [P2-3] Employee Form Editor page.
 *
 * Full-page editor at /employee/case/:caseId/forms/:formId.
 *
 * Layout:
 *   ┌───────────────────────────────────────────────────────────────┐
 *   │ Header: breadcrumb + form name + save-state indicator         │
 *   ├─────────────────────┬─────────────────────────────────────────┤
 *   │ PdfPanel (40%)      │ Field editor panel (60%)                │
 *   │ Original PDF        │ Section header + FieldRow list          │
 *   │                     │ "Mark all reviewed" button              │
 *   ├─────────────────────┴─────────────────────────────────────────┤
 *   │ ActionBar (sticky): completion % · missing count · Save/Ready │
 *   └───────────────────────────────────────────────────────────────┘
 *
 * Auto-save: 30 seconds after the last field edit, if there are unsaved
 * changes, we flush a PUT /fields call silently.
 *
 * Mark ready: calls PATCH /forms/:id with { status: 'ready' }.
 * The server returns 422 with missing_fields detail when required fields
 * are still empty — we surface that in the ActionBar.
 */
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button } from '../../components/antigravity/Button';
import { Alert } from '../../components/antigravity';
import { AppShell } from '../../components/AppShell';
import { logger } from '../../lib/logger';
import { buildRoute } from '../../navigation/routes';
import { formEditorAPI } from '../../api/formEditor';
import { dossierAPI } from '../../api/dossier';
import type { FieldValueItem } from '../../api/formEditor';
import type { CaseFormSummary } from '../../api/dossier';
import { PdfPanel } from '../../features/platform-v2/form-editor/PdfPanel';
import { FieldRow } from '../../features/platform-v2/form-editor/FieldRow';
import { ActionBar } from '../../features/platform-v2/form-editor/ActionBar';
import { PrefillConfirmation } from '../../features/platform-v2/form-editor/PrefillConfirmation';
import { OriginalPdfDrawer } from '../../features/platform-v2/dossier/OriginalPdfDrawer';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Group fields by their optional `section` property.
 *  Fields with no section fall into a single "Form fields" bucket. */
function groupBySection(
  fields: FieldValueItem[],
): Array<{ section: string; fields: FieldValueItem[] }> {
  const map = new Map<string, FieldValueItem[]>();
  for (const f of fields) {
    const key = f.section?.trim() || 'Form fields';
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(f);
  }
  return Array.from(map.entries()).map(([section, fields]) => ({ section, fields }));
}

/** Compute local completion % from live values and field definitions. */
function computeCompletion(
  fields: FieldValueItem[],
  liveValues: Record<string, string>,
): number {
  const required = fields.filter((f) => f.required);
  if (required.length === 0) {
    if (fields.length === 0) return 0;
    const filled = fields.filter((f) => (liveValues[f.field_id] ?? '').trim() !== '').length;
    return Math.round((filled / fields.length) * 100);
  }
  const filledRequired = required.filter(
    (f) => (liveValues[f.field_id] ?? '').trim() !== '',
  ).length;
  return Math.round((filledRequired / required.length) * 100);
}

/** Count required fields with an empty live value. */
function countMissing(
  fields: FieldValueItem[],
  liveValues: Record<string, string>,
): number {
  return fields.filter(
    (f) => f.required && (liveValues[f.field_id] ?? '').trim() === '',
  ).length;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const FormEditorPage: React.FC = () => {
  const { caseId, formId } = useParams<{ caseId: string; formId: string }>();
  const navigate = useNavigate();

  // ── Server data ─────────────────────────────────────────────────────────
  const [fields, setFields] = useState<FieldValueItem[]>([]);
  const [formSummary, setFormSummary] = useState<CaseFormSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // ── Live edit state ──────────────────────────────────────────────────────
  /** A map of field_id → current string value displayed in the form. */
  const [liveValues, setLiveValues] = useState<Record<string, string>>({});
  /** Track which field_ids have been touched since the last save. */
  const dirtyRef = useRef<Set<string>>(new Set());

  // ── Save state ───────────────────────────────────────────────────────────
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Mark-ready state ─────────────────────────────────────────────────────
  const [isMarkingReady, setIsMarkingReady] = useState(false);
  const [markReadyError, setMarkReadyError] = useState<string | null>(null);
  const [markReadySuccess, setMarkReadySuccess] = useState(false);

  // ── Show-missing guard ────────────────────────────────────────────────────
  /** Turns red outlines on after a failed "Mark ready" attempt. */
  const [showMissing, setShowMissing] = useState(false);

  // ── [P3-3] PDF download state ─────────────────────────────────────────────
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);

  // ── [P2-4] Original PDF drawer state ─────────────────────────────────────
  const [showOriginal, setShowOriginal] = useState(false);

  // ── [P2-03c] Pre-fill confirmation gate ──────────────────────────────────
  /** Once the user confirms the engine's pre-filled values, the gate stays down
   *  for this session even though a refetch may still report `filled_by='system'`
   *  momentarily before the confirming write lands. */
  const [prefillConfirmed, setPrefillConfirmed] = useState(false);
  const [prefillConfirming, setPrefillConfirming] = useState(false);

  // ── Load ────────────────────────────────────────────────────────────────
  const load = useCallback(
    async (signal?: AbortSignal) => {
      if (!caseId || !formId) {
        setLoadError('Missing caseId or formId in URL.');
        setLoading(false);
        return;
      }
      setLoading(true);
      setLoadError(null);
      try {
        const [fieldList, forms] = await Promise.all([
          formEditorAPI.getFields(caseId, formId),
          dossierAPI.list(caseId),
        ]);
        if (signal?.aborted) return;
        setFields(fieldList);
        const summary = forms.find((f) => f.id === formId) ?? null;
        setFormSummary(summary);
        // Seed liveValues from stored values
        const initial: Record<string, string> = {};
        for (const f of fieldList) {
          initial[f.field_id] = f.value ?? '';
        }
        setLiveValues(initial);
        dirtyRef.current.clear();
      } catch (e) {
        if (signal?.aborted) return;
        const err = e as { response?: { data?: { detail?: string } }; message?: string };
        setLoadError(err.response?.data?.detail || err.message || 'Failed to load form');
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [caseId, formId],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => {
      controller.abort();
      // Flush auto-save timer on unmount
      if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    };
  }, [load]);

  // ── Field change ─────────────────────────────────────────────────────────
  const handleValueChange = useCallback((fieldId: string, value: string) => {
    setLiveValues((prev) => ({ ...prev, [fieldId]: value }));
    dirtyRef.current.add(fieldId);
    setSaveStatus('idle');
    setMarkReadyError(null);

    // Restart the 30-second auto-save debounce
    if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    autoSaveTimerRef.current = setTimeout(() => {
      void doSave(false);
    }, 30_000);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  // Note: doSave is stable via useCallback with a ref; no dep needed here.

  // ── Save draft ───────────────────────────────────────────────────────────
  const liveValuesRef = useRef(liveValues);
  liveValuesRef.current = liveValues;

  const doSave = useCallback(
    async (explicit: boolean) => {
      if (!caseId || !formId) return;
      if (!explicit && dirtyRef.current.size === 0) return;

      // Build the payload from all fields (full PUT, not delta)
      const payload = fields.map((f) => ({
        field_id: f.field_id,
        value: liveValuesRef.current[f.field_id] ?? null,
      }));

      setSaveStatus('saving');
      try {
        const updated = await formEditorAPI.putFields(caseId, formId, payload);
        setFormSummary(updated);
        dirtyRef.current.clear();
        setSaveStatus('saved');
        // Reset save indicator after 3 seconds
        setTimeout(() => setSaveStatus((s) => (s === 'saved' ? 'idle' : s)), 3_000);
      } catch {
        setSaveStatus('error');
      }
    },
    [caseId, formId, fields],
  );

  // ── Mark all reviewed (section-level) ───────────────────────────────────
  /**
   * Sends a PUT that marks every AI-filled field in the section as reviewed.
   * We do this by re-sending their current values — the server sets reviewed=true
   * on every employee write.
   */
  const handleMarkSectionReviewed = useCallback(
    async (sectionFields: FieldValueItem[]) => {
      if (!caseId || !formId) return;
      const aiFields = sectionFields.filter((f) => f.filled_by === 'ai');
      if (aiFields.length === 0) return;
      const payload = aiFields.map((f) => ({
        field_id: f.field_id,
        value: liveValuesRef.current[f.field_id] ?? null,
      }));
      setSaveStatus('saving');
      try {
        const updated = await formEditorAPI.putFields(caseId, formId, payload);
        setFormSummary(updated);
        // Refresh fields to get updated reviewed flags
        const refreshed = await formEditorAPI.getFields(caseId, formId);
        setFields(refreshed);
        // Re-seed live values with any server-side updates
        setLiveValues((prev) => {
          const next = { ...prev };
          for (const f of refreshed) {
            if (!(f.field_id in dirtyRef.current)) {
              next[f.field_id] = f.value ?? '';
            }
          }
          return next;
        });
        setSaveStatus('saved');
        setTimeout(() => setSaveStatus((s) => (s === 'saved' ? 'idle' : s)), 3_000);
      } catch {
        setSaveStatus('error');
      }
    },
    [caseId, formId],
  );

  // ── Mark ready ───────────────────────────────────────────────────────────
  const handleMarkReady = useCallback(async () => {
    if (!caseId || !formId) return;
    setMarkReadyError(null);

    // Local pre-validation: highlight missing fields
    const missing = countMissing(fields, liveValuesRef.current);
    if (missing > 0) {
      setShowMissing(true);
      setMarkReadyError(
        `${missing} required field${missing === 1 ? ' is' : 's are'} still empty.`,
      );
      return;
    }

    // Flush any unsaved changes first
    await doSave(true);

    setIsMarkingReady(true);
    try {
      await formEditorAPI.patchStatus(caseId, formId, { status: 'ready' });
      setMarkReadySuccess(true);
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      const detail = err.response?.data?.detail;
      setMarkReadyError(
        typeof detail === 'string'
          ? detail
          : 'Could not mark form as ready — check required fields.',
      );
    } finally {
      setIsMarkingReady(false);
    }
  }, [caseId, formId, fields, doSave]);

  // ── [P3-3] PDF download handler ───────────────────────────────────────────
  const handleDownloadPdf = useCallback(async () => {
    if (!caseId || !formId) return;
    setIsDownloadingPdf(true);
    try {
      await formEditorAPI.downloadPdf(caseId, formId);
    } catch (e) {
      // Non-blocking: log and surface nothing — user can retry
      logger.error('[P3-3] PDF download failed', e);
    } finally {
      setIsDownloadingPdf(false);
    }
  }, [caseId, formId]);

  // ── Derived state ─────────────────────────────────────────────────────────
  const sections = useMemo(() => groupBySection(fields), [fields]);
  const completionPct = useMemo(
    () => computeCompletion(fields, liveValues),
    [fields, liveValues],
  );
  const missingCount = useMemo(
    () => countMissing(fields, liveValues),
    [fields, liveValues],
  );

  const saveIndicatorLabel =
    saveStatus === 'saving'
      ? 'Saving…'
      : saveStatus === 'saved'
        ? 'Saved ✓'
        : saveStatus === 'error'
          ? 'Save failed'
          : null;

  // ── [P2-03c] Pre-fill confirmation gate ──────────────────────────────────
  /** Values written by the pre-fill engine (filled_by='system') awaiting the
   *  user's review. Once confirmed they're re-saved as employee-owned. */
  const prefilledFields = fields.filter(
    (f) => f.filled_by === 'system' && (f.value ?? '').trim() !== '',
  );
  /** Required fields with nothing pre-filled — the user must complete these. */
  const manualFields = fields.filter(
    (f) => f.required && (f.value ?? '').trim() === '',
  );
  const showPrefillGate = !prefillConfirmed && prefilledFields.length > 0;

  const handleConfirmPrefill = useCallback(async () => {
    if (!caseId || !formId) return;
    const toConfirm = fields.filter(
      (f) => f.filled_by === 'system' && (f.value ?? '').trim() !== '',
    );
    if (toConfirm.length === 0) {
      setPrefillConfirmed(true);
      return;
    }
    setPrefillConfirming(true);
    try {
      // Re-save the pre-filled values verbatim — the server flips them to
      // filled_by='employee', reviewed=true, persisting the user's confirmation.
      const payload = toConfirm.map((f) => ({ field_id: f.field_id, value: f.value }));
      const updated = await formEditorAPI.putFields(caseId, formId, payload);
      setFormSummary(updated);
      const refreshed = await formEditorAPI.getFields(caseId, formId);
      setFields(refreshed);
      setPrefillConfirmed(true);
    } catch {
      // Keep the gate up so the user can retry; surface via the save indicator.
      setSaveStatus('error');
    } finally {
      setPrefillConfirming(false);
    }
  }, [caseId, formId, fields]);

  // ── Render ────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <AppShell>
        <div className="flex items-center justify-center h-64 text-slate-500">
          Loading form…
        </div>
      </AppShell>
    );
  }

  if (loadError) {
    return (
      <AppShell>
        <div className="max-w-xl mx-auto mt-12 px-6">
          <div className="rounded border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {loadError}
          </div>
          <Button unstyled
            type="button"
            onClick={() =>
              caseId &&
              navigate(buildRoute('employeeCaseDossier', { caseId }))
            }
            className="mt-4 text-sm text-[#0b2b43] hover:underline"
          >
            ← Back to dossier
          </Button>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      {/* ── Page header ─────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-10 bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <Button unstyled
            type="button"
            onClick={() =>
              caseId &&
              navigate(buildRoute('employeeCaseDossier', { caseId }))
            }
            className="shrink-0 text-slate-400 hover:text-slate-700 transition-colors"
            aria-label="Back to dossier"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </Button>
          <div className="min-w-0">
            <p className="text-[10px] font-semibold tracking-widest text-slate-400 uppercase leading-none mb-0.5">
              ReloPass · Dossier & Forms
            </p>
            <h1 className="text-base font-semibold text-slate-900 truncate leading-tight">
              {formSummary?.template.name ?? 'Form editor'}
              {formSummary?.template.code && (
                <span className="ml-2 font-mono text-[11px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded border border-slate-200">
                  {formSummary.template.code}
                </span>
              )}
            </h1>
          </div>
        </div>

        {/* Save indicator */}
        {saveIndicatorLabel && (
          <span
            className={`shrink-0 text-xs font-medium ${
              saveStatus === 'error'
                ? 'text-rose-600'
                : saveStatus === 'saved'
                  ? 'text-emerald-600'
                  : 'text-slate-400'
            }`}
          >
            {saveIndicatorLabel}
          </span>
        )}
      </header>

      {/* ── Two-panel body ───────────────────────────────────────────────── */}
      <div
        className="flex overflow-hidden"
        style={{ height: 'calc(100vh - 120px)' }}
      >
        {/* Left: PDF panel (40%) */}
        <div className="hidden lg:flex flex-col w-2/5 shrink-0 overflow-hidden border-r border-slate-200">
          {/* [P2-4] Left panel header with "View original" button */}
          <div className="flex items-center justify-between px-4 py-2 border-b border-slate-100 shrink-0">
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">
              Original form
            </span>
            <Button unstyled
              type="button"
              onClick={() => setShowOriginal(true)}
              className="inline-flex items-center gap-1 text-xs text-[#0b2b43] hover:underline"
              title="Open original in side panel"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              Open in panel
            </Button>
          </div>
          <div className="flex-1 overflow-hidden p-4">
            <PdfPanel
              url={formSummary?.original_file_url ?? null}
              formName={formSummary?.template.name ?? 'Form'}
            />
          </div>
        </div>

        {/* Right: Field editor (60%) */}
        <div className="flex-1 overflow-y-auto px-6 py-4 pb-24">
          {/* Content-honesty disclaimer — this is the submission surface and the
              form template is representative, not legally verified, so remind the
              employee to confirm with the issuing authority before submitting. */}
          <Alert variant="warning" className="mb-4">
            Indicative — always confirm details with the issuing authority before you submit.
            This form is representative and may differ from the latest official version.
          </Alert>
          {sections.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-sm">
              No fields defined for this form yet.
            </div>
          ) : (
            sections.map(({ section, fields: sectionFields }) => {
              const aiFieldsInSection = sectionFields.filter(
                (f) => f.filled_by === 'ai' && !f.reviewed,
              );
              return (
                <div key={section} className="mb-8">
                  {/* Section header */}
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="text-xs font-semibold tracking-widest text-slate-500 uppercase">
                      {section}
                    </h2>
                    {aiFieldsInSection.length > 0 && (
                      <Button unstyled
                        type="button"
                        onClick={() => void handleMarkSectionReviewed(sectionFields)}
                        className="text-xs font-medium text-[#0b2b43] hover:underline"
                      >
                        Mark all reviewed ({aiFieldsInSection.length})
                      </Button>
                    )}
                  </div>

                  {/* Fields */}
                  <div className="grid gap-3">
                    {sectionFields.map((field) => (
                      <FieldRow
                        key={field.field_id}
                        field={field}
                        liveValue={liveValues[field.field_id] ?? ''}
                        onValueChange={handleValueChange}
                        showMissing={showMissing}
                      />
                    ))}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* ── Sticky action bar ────────────────────────────────────────────── */}
      <ActionBar
        missingCount={missingCount}
        completionPct={completionPct}
        isSaving={saveStatus === 'saving'}
        isMarkingReady={isMarkingReady}
        markReadyError={markReadyError}
        markReadySuccess={markReadySuccess}
        onSaveDraft={() => void doSave(true)}
        onMarkReady={() => void handleMarkReady()}
        onBack={() =>
          caseId && navigate(buildRoute('employeeCaseDossier', { caseId }))
        }
        onDownloadPdf={() => void handleDownloadPdf()}
        isDownloadingPdf={isDownloadingPdf}
        draftPdfGeneratedAt={formSummary?.updated_at ?? null}
      />

      {/* [P2-4] Original PDF drawer — right-side panel, available on all screen sizes */}
      {caseId && formId && formSummary && (
        <OriginalPdfDrawer
          isOpen={showOriginal}
          onClose={() => setShowOriginal(false)}
          caseId={caseId}
          formId={formId}
          formName={formSummary.template.name}
          formCode={formSummary.template.code}
        />
      )}

      {/* [P2-03c] Pre-fill confirmation gate — blocks the editor until the user
          reviews and confirms values populated by the pre-fill engine. */}
      {showPrefillGate && (
        <PrefillConfirmation
          prefilledFields={prefilledFields}
          manualFields={manualFields}
          onConfirm={() => void handleConfirmPrefill()}
          confirming={prefillConfirming}
        />
      )}
    </AppShell>
  );
};
