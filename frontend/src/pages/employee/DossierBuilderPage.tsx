/**
 * [P3-4] Dossier Builder — 3-step wizard.
 *
 * Step 1 — Form selector: pick forms from the case's dossier.
 * Step 2 — Reorder + options: drag-to-reorder with @dnd-kit/sortable, toggle cover page.
 * Step 3 — Download: call POST /api/cases/{caseId}/dossiers, then GET .../zip.
 *
 * The builder is self-contained and navigates back to the dossier list on completion
 * or cancellation.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { restrictToVerticalAxis } from '@dnd-kit/modifiers';
import { GripVertical, CheckSquare, Square, ChevronRight, ChevronLeft, Download, Loader2, X, FileText } from 'lucide-react';
import { Button } from '../../components/antigravity/Button';
import { assertSafeUrl } from '../../utils/assertSafeUrl';
import { AppShell } from '../../components/AppShell';
import { dossierAPI, dossierPackageAPI, type CaseFormSummary } from '../../api/dossier';
import { buildRoute } from '../../navigation/routes';

// ---------------------------------------------------------------------------
// Types & helpers
// ---------------------------------------------------------------------------

type Step = 1 | 2 | 3;

const STEP_LABELS: Record<Step, string> = {
  1: 'Select forms',
  2: 'Order & preview',
  3: 'Export',
};

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    not_started: 'Not started',
    auto_filled: 'AI-filled',
    in_progress: 'In progress',
    pending_doc: 'Pending doc',
    ready: 'Ready',
    submitted: 'Submitted',
    approved: 'Approved',
    rejected: 'Rejected',
  };
  return map[status] ?? status;
}

function statusColor(status: string): string {
  if (status === 'ready' || status === 'approved') return 'text-emerald-600 bg-emerald-50 border-emerald-200';
  if (status === 'submitted') return 'text-blue-600 bg-blue-50 border-blue-200';
  if (status === 'rejected') return 'text-red-600 bg-red-50 border-red-200';
  if (status === 'auto_filled') return 'text-accent-600 bg-accent-50 border-accent-200';
  return 'text-slate-500 bg-slate-50 border-slate-200';
}

// ---------------------------------------------------------------------------
// SortableFormRow — one draggable row in Step 2
// ---------------------------------------------------------------------------

interface SortableFormRowProps {
  form: CaseFormSummary;
  index: number;
}

function SortableFormRow({ form, index }: SortableFormRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: form.id });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 50 : undefined,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-3 p-3 rounded-lg border bg-white ${isDragging ? 'shadow-lg border-[#0b2b43]/30' : 'border-slate-200 shadow-sm'}`}
    >
      {/* Drag handle */}
      <Button unstyled
        type="button"
        {...attributes}
        {...listeners}
        className="touch-none text-slate-300 hover:text-slate-500 cursor-grab active:cursor-grabbing flex-none"
        aria-label="Drag to reorder"
      >
        <GripVertical className="h-4 w-4" />
      </Button>

      {/* Position index */}
      <span className="flex-none w-5 text-center text-xs font-semibold text-slate-400">{index + 1}</span>

      {/* Form info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 min-w-0">
          {form.is_adhoc && (
            <span className="flex-none inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
              Custom
            </span>
          )}
          <span className="text-sm font-medium text-slate-800 truncate">{form.template.name}</span>
        </div>
        <div className="text-xs text-slate-500 mt-0.5">
          {(form.is_adhoc ? (form.template.authority_name ?? 'Ad-hoc document') : form.template.code)} · {form.person.name ?? form.person.kind}
        </div>
      </div>

      {/* Status */}
      <span className={`text-[11px] font-semibold px-2 py-0.5 rounded border flex-none ${statusColor(form.status)}`}>
        {statusLabel(form.status)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 1 — Form selection grid (with filter tabs + not-ready warning)
// ---------------------------------------------------------------------------

type Step1FilterKey = 'all' | 'ready' | 'in_progress';

const STEP1_FILTER_TABS: Array<{ key: Step1FilterKey; label: string }> = [
  { key: 'all', label: 'All' },
  { key: 'ready', label: 'Ready' },
  { key: 'in_progress', label: 'In progress' },
];

function step1Matches(form: CaseFormSummary, key: Step1FilterKey): boolean {
  if (key === 'all') return true;
  if (key === 'ready') return form.status === 'ready' || form.status === 'approved' || form.status === 'submitted';
  if (key === 'in_progress') return form.status === 'in_progress' || form.status === 'auto_filled' || form.status === 'not_started' || form.status === 'pending_doc';
  return true;
}

interface Step1Props {
  forms: CaseFormSummary[];
  selectedIds: Set<string>;
  onToggle: (id: string) => void;
}

function Step1({ forms, selectedIds, onToggle }: Step1Props) {
  const [filterTab, setFilterTab] = useState<Step1FilterKey>('ready');

  const filteredForms = forms.filter((f) => step1Matches(f, filterTab));

  // Warning: any selected form that is not ready/approved/submitted
  const hasUnreadySelected = forms.some(
    (f) => selectedIds.has(f.id) && f.status !== 'ready' && f.status !== 'approved' && f.status !== 'submitted',
  );

  if (forms.length === 0) {
    return (
      <div className="text-center py-12 text-slate-500 text-sm">
        No forms found for this case.
      </div>
    );
  }

  const tabCounts: Record<Step1FilterKey, number> = {
    all: forms.length,
    ready: forms.filter((f) => step1Matches(f, 'ready')).length,
    in_progress: forms.filter((f) => step1Matches(f, 'in_progress')).length,
  };

  return (
    <div className="space-y-4">
      {/* Filter tabs */}
      <div className="flex items-center gap-1 border-b border-slate-200">
        {STEP1_FILTER_TABS.map((tab) => {
          const isActive = filterTab === tab.key;
          return (
            <Button unstyled
              key={tab.key}
              type="button"
              onClick={() => setFilterTab(tab.key)}
              className={`relative px-3 py-1.5 text-sm font-medium transition-colors ${
                isActive ? 'text-[#0b2b43]' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {tab.label}
              <span
                className={`ml-1.5 inline-flex items-center justify-center min-w-[16px] h-[16px] px-1 rounded-full text-[10px] font-semibold ${
                  isActive ? 'bg-[#0b2b43] text-white' : 'bg-slate-100 text-slate-500'
                }`}
              >
                {tabCounts[tab.key]}
              </span>
              {isActive && <span className="absolute left-0 right-0 -bottom-px h-0.5 bg-[#0b2b43]" />}
            </Button>
          );
        })}
      </div>

      {/* Warning banner */}
      {hasUnreadySelected && (
        <div className="flex items-start gap-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 flex-none" aria-hidden="true">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <span>One or more selected forms are not yet ready. They will be included in the dossier but may be incomplete.</span>
        </div>
      )}

      {/* Form list */}
      {filteredForms.length === 0 ? (
        <div className="text-center py-8 text-slate-500 text-sm">No forms match this filter.</div>
      ) : (
        <div className="space-y-2">
          {filteredForms.map((form) => {
            const selected = selectedIds.has(form.id);
            return (
              <Button unstyled
                key={form.id}
                type="button"
                onClick={() => onToggle(form.id)}
                className={`w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-colors ${
                  selected
                    ? 'border-[#0b2b43]/40 bg-[#0b2b43]/5'
                    : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                }`}
              >
                {selected ? (
                  <CheckSquare className="h-4 w-4 text-[#0b2b43] flex-none" />
                ) : (
                  <Square className="h-4 w-4 text-slate-300 flex-none" />
                )}

                <FileText className="h-4 w-4 text-slate-400 flex-none" />

                {/* Form code badge — "Custom" for ad-hoc forms */}
                {form.is_adhoc ? (
                  <span className="flex-none inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                    Custom
                  </span>
                ) : (
                  <span className="flex-none inline-flex items-center px-1.5 py-0.5 rounded font-mono text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                    {form.template.code}
                  </span>
                )}

                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-slate-800 truncate">{form.template.name}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {form.person.name ?? form.person.kind}
                    {form.template.authority_code ? ` · ${form.template.authority_code}` : ''}
                  </div>
                </div>

                {/* Completion pct */}
                <span className="text-[11px] text-slate-400 flex-none">{form.completion_pct}%</span>

                <span className={`text-[11px] font-semibold px-2 py-0.5 rounded border flex-none ${statusColor(form.status)}`}>
                  {statusLabel(form.status)}
                </span>
              </Button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 2 — Drag-to-reorder + options
// ---------------------------------------------------------------------------

interface Step2Props {
  orderedForms: CaseFormSummary[];
  onReorder: (forms: CaseFormSummary[]) => void;
  coverPage: boolean;
  onCoverPageChange: (v: boolean) => void;
}

function Step2({ orderedForms, onReorder, coverPage, onCoverPageChange }: Step2Props) {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIndex = orderedForms.findIndex((f) => f.id === active.id);
      const newIndex = orderedForms.findIndex((f) => f.id === over.id);
      onReorder(arrayMove(orderedForms, oldIndex, newIndex));
    }
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Left: drag-to-reorder list + options */}
      <div className="space-y-5">
        {/* Drag-to-reorder list */}
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
            Drag to set order in the dossier
          </p>
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            modifiers={[restrictToVerticalAxis]}
            onDragEnd={handleDragEnd}
          >
            <SortableContext items={orderedForms.map((f) => f.id)} strategy={verticalListSortingStrategy}>
              <div className="space-y-2">
                {orderedForms.map((form, i) => (
                  <SortableFormRow key={form.id} form={form} index={i} />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        </div>

        {/* Cover page toggle */}
        <div className="border border-slate-200 rounded-lg p-4 bg-slate-50">
          <label className="flex items-center gap-3 cursor-pointer">
            <Button unstyled
              type="button"
              role="checkbox"
              aria-checked={coverPage}
              onClick={() => onCoverPageChange(!coverPage)}
              className="flex-none"
            >
              {coverPage ? (
                <CheckSquare className="h-5 w-5 text-[#0b2b43]" />
              ) : (
                <Square className="h-5 w-5 text-slate-300" />
              )}
            </Button>
            <div>
              <div className="text-sm font-medium text-slate-800">Include cover page</div>
              <div className="text-xs text-slate-500 mt-0.5">
                Adds a ReloPass cover page with case details and generation date.
              </div>
            </div>
          </label>
        </div>
      </div>

      {/* Right: preview placeholder */}
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 px-6 py-12 text-center">
        <FileText className="h-8 w-8 text-slate-300 mb-3" />
        <p className="text-sm font-medium text-slate-500">Preview</p>
        <p className="text-xs text-slate-400 mt-1">Preview will be available after building</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step 3 — Build & export
// ---------------------------------------------------------------------------

interface Step3Props {
  caseId: string;
  orderedForms: CaseFormSummary[];
  coverPage: boolean;
  onDone: () => void;
}

interface DossierResult {
  id: string;
  name: string;
  pdf_url: string | null;
}

function Step3({ caseId, orderedForms, coverPage, onDone }: Step3Props) {
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DossierResult | null>(null);

  const packageName = useMemo(
    () => `Dossier ${new Date().toISOString().slice(0, 10)}`,
    [],
  );

  const build = useCallback(async () => {
    setBuilding(true);
    setError(null);
    try {
      const pkg = await dossierPackageAPI.create(caseId, {
        name: packageName,
        form_ids: orderedForms.map((f) => f.id),
        cover_page: coverPage,
      });
      setResult({ id: pkg.id, name: pkg.name, pdf_url: pkg.pdf_url });
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err.response?.data?.detail || err.message || 'Failed to build dossier');
    } finally {
      setBuilding(false);
    }
  }, [caseId, orderedForms, coverPage, packageName]);

  const handleDownloadZip = useCallback(() => {
    if (!result) return;
    const zipUrl = dossierPackageAPI.getZipUrl(caseId, result.id);
    // Trigger download by creating a temporary anchor
    const a = document.createElement('a');
    a.href = zipUrl;
    a.download = `${result.name}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }, [caseId, result]);

  const handlePrint = useCallback(() => {
    if (!result?.pdf_url) return;
    window.open(assertSafeUrl(result.pdf_url), '_blank', 'noopener,noreferrer');
  }, [result]);

  const handleDownloadPdf = useCallback(() => {
    if (!result?.pdf_url) return;
    window.open(assertSafeUrl(result.pdf_url), '_blank', 'noopener,noreferrer');
  }, [result]);

  return (
    <div className="space-y-6">
      {/* Summary of what's in the package */}
      <div className="border border-slate-200 rounded-lg p-4">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Package contents</p>
        <ul className="space-y-1">
          {orderedForms.map((form, i) => (
            <li key={form.id} className="flex items-center gap-2 text-sm text-slate-700">
              <span className="text-slate-400 font-medium w-5 text-right">{i + 1}.</span>
              <span className="font-mono text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded border border-slate-200 flex-none">{form.template.code}</span>
              <span className="truncate">{form.template.name}</span>
            </li>
          ))}
        </ul>
        {coverPage && (
          <p className="mt-2 text-xs text-slate-500 italic">+ Cover page</p>
        )}
      </div>

      {/* Build button (shown when not yet built) */}
      {!result && !building && (
        <Button unstyled
          type="button"
          onClick={() => void build()}
          className="inline-flex items-center gap-2 rounded-lg bg-[#0b2b43] px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[#08213a] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43]/50"
        >
          Build dossier
        </Button>
      )}

      {/* Building state */}
      {building && (
        <div className="flex items-center gap-3 text-sm text-slate-600">
          <Loader2 className="h-4 w-4 animate-spin text-[#0b2b43]" />
          Building your dossier package…
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
          {error}
          <Button unstyled
            type="button"
            onClick={() => void build()}
            className="ml-3 underline font-medium"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Success: package info + download buttons */}
      {result && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm text-emerald-700 font-medium">
            <CheckSquare className="h-4 w-4" />
            Dossier package created successfully.
          </div>

          {/* Package name + timestamp */}
          <div>
            <p className="text-sm font-semibold text-slate-800">{result.name}</p>
            <p className="text-xs text-slate-500 mt-0.5">Last generated: just now</p>
          </div>

          {/* Prominent download / print buttons */}
          <div className="flex flex-wrap gap-3">
            <Button unstyled
              type="button"
              onClick={handleDownloadPdf}
              disabled={!result.pdf_url}
              className="inline-flex items-center gap-2 rounded-lg bg-[#0b2b43] px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[#08213a] transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43]/50"
            >
              <Download className="h-4 w-4" />
              Download PDF
            </Button>

            <Button unstyled
              type="button"
              onClick={() => handleDownloadZip()}
              data-testid="download-zip-btn"
              className="inline-flex items-center gap-2 rounded-lg border border-[#0b2b43] px-5 py-2.5 text-sm font-semibold text-[#0b2b43] bg-white shadow-sm hover:bg-[#0b2b43]/5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43]/50"
            >
              <Download className="h-4 w-4" />
              Download ZIP
            </Button>

            <Button unstyled
              type="button"
              onClick={handlePrint}
              disabled={!result.pdf_url}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-5 py-2.5 text-sm font-semibold text-slate-700 bg-white shadow-sm hover:bg-slate-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <polyline points="6 9 6 2 18 2 18 9" />
                <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
                <rect x="6" y="14" width="12" height="8" />
              </svg>
              Print
            </Button>
          </div>

          {/* Done link */}
          <div className="pt-1">
            <Button unstyled
              type="button"
              onClick={onDone}
              className="text-sm text-slate-500 hover:text-slate-700 underline"
            >
              Back to my dossier
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DossierBuilderPage — orchestrates the 3 steps
// ---------------------------------------------------------------------------

export const DossierBuilderPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();

  const [forms, setForms] = useState<CaseFormSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [step, setStep] = useState<Step>(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [orderedForms, setOrderedForms] = useState<CaseFormSummary[]>([]);
  const [coverPage, setCoverPage] = useState(true);

  // Load case forms
  useEffect(() => {
    if (!caseId) return;
    setLoading(true);
    dossierAPI
      .list(caseId)
      .then((rows) => {
        setForms(rows);
        setLoading(false);
      })
      .catch((e: { response?: { data?: { detail?: string } }; message?: string }) => {
        setLoadError(e.response?.data?.detail || e.message || 'Failed to load forms');
        setLoading(false);
      });
  }, [caseId]);

  // Keep orderedForms in sync with selectedIds (only when transitioning 1→2)
  const toggleForm = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const goToStep2 = useCallback(() => {
    // Build ordered list from current forms in their natural order
    const selected = forms.filter((f) => selectedIds.has(f.id));
    setOrderedForms(selected);
    setStep(2);
  }, [forms, selectedIds]);

  const backToStep1 = useCallback(() => setStep(1), []);
  const goToStep3 = useCallback(() => setStep(3), []);
  const backToStep2 = useCallback(() => setStep(2), []);

  const handleDone = useCallback(() => {
    if (!caseId) return;
    navigate(buildRoute('employeeCaseDossier', { caseId }));
  }, [caseId, navigate]);

  const canAdvanceStep1 = selectedIds.size > 0;
  const canAdvanceStep2 = orderedForms.length > 0;

  const stepList: Step[] = [1, 2, 3];

  // Completion %
  const completionPct = useMemo(() => {
    if (forms.length === 0) return 0;
    const sel = forms.filter((f) => selectedIds.has(f.id));
    if (sel.length === 0) return 0;
    const sum = sel.reduce((acc, f) => acc + (f.completion_pct || 0), 0);
    return Math.round(sum / sel.length);
  }, [forms, selectedIds]);

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <p className="text-[10px] font-semibold tracking-widest text-slate-400 uppercase mb-1">
              ReloPass · Dossier Builder
            </p>
            <h1 className="text-2xl font-semibold text-slate-900">Build dossier package</h1>
            <p className="text-sm text-slate-500 mt-1">
              Select forms, arrange them, and download a ZIP of PDFs.
            </p>
          </div>
          <Button unstyled
            type="button"
            onClick={handleDone}
            aria-label="Close builder"
            className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Step indicator */}
        <nav aria-label="Builder steps" className="flex items-center gap-0 mb-8">
          {stepList.map((s, i) => (
            <React.Fragment key={s}>
              <div
                className={`flex items-center gap-2 ${step >= s ? 'text-[#0b2b43]' : 'text-slate-400'}`}
              >
                <div
                  className={`w-6 h-6 rounded-full text-[11px] font-semibold flex items-center justify-center border-2 ${
                    step > s
                      ? 'bg-[#0b2b43] border-[#0b2b43] text-white'
                      : step === s
                        ? 'border-[#0b2b43] text-[#0b2b43] bg-white'
                        : 'border-slate-300 text-slate-400 bg-white'
                  }`}
                >
                  {step > s ? '✓' : s}
                </div>
                <span className="text-xs font-medium hidden sm:block">{STEP_LABELS[s]}</span>
              </div>
              {i < stepList.length - 1 && (
                <div className={`flex-1 h-px mx-2 ${step > s ? 'bg-[#0b2b43]' : 'bg-slate-200'}`} />
              )}
            </React.Fragment>
          ))}
        </nav>

        {/* Content area */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          {loading ? (
            <div className="flex items-center gap-3 py-8 justify-center text-slate-500 text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading forms…
            </div>
          ) : loadError ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
              {loadError}
            </div>
          ) : (
            <>
              {step === 1 && (
                <>
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-base font-semibold text-slate-800">Select forms to include</h2>
                    {selectedIds.size > 0 && (
                      <span className="text-xs text-slate-500">
                        {selectedIds.size} selected · avg {completionPct}% complete
                      </span>
                    )}
                  </div>
                  <Step1 forms={forms} selectedIds={selectedIds} onToggle={toggleForm} />
                </>
              )}

              {step === 2 && (
                <>
                  <h2 className="text-base font-semibold text-slate-800 mb-4">Arrange forms & set options</h2>
                  <Step2
                    orderedForms={orderedForms}
                    onReorder={setOrderedForms}
                    coverPage={coverPage}
                    onCoverPageChange={setCoverPage}
                  />
                </>
              )}

              {step === 3 && caseId && (
                <>
                  <h2 className="text-base font-semibold text-slate-800 mb-4">Download your dossier</h2>
                  <Step3
                    caseId={caseId}
                    orderedForms={orderedForms}
                    coverPage={coverPage}
                    onDone={handleDone}
                  />
                </>
              )}
            </>
          )}
        </div>

        {/* Navigation footer */}
        {!loading && !loadError && step !== 3 && (
          <div className="flex items-center justify-between mt-5">
            {/* Back */}
            {step === 1 ? (
              <Button unstyled
                type="button"
                onClick={handleDone}
                className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700"
              >
                <ChevronLeft className="h-4 w-4" />
                Cancel
              </Button>
            ) : (
              <Button unstyled
                type="button"
                onClick={step === 2 ? backToStep1 : backToStep2}
                className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700"
              >
                <ChevronLeft className="h-4 w-4" />
                Back
              </Button>
            )}

            {/* Next */}
            <Button unstyled
              type="button"
              disabled={step === 1 ? !canAdvanceStep1 : !canAdvanceStep2}
              onClick={step === 1 ? goToStep2 : goToStep3}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#0b2b43] px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-[#08213a] transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43]/50"
            >
              {step === 1 ? 'Order & preview' : 'Export'}
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>
    </AppShell>
  );
};

export default DossierBuilderPage;
