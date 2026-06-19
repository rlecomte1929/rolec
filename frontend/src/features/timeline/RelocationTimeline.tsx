/**
 * RelocationTimeline — AIQ-3-C / AIQ-3-D
 *
 * Visual vertical timeline replacing the accordion-list RelocationTaskTracker on
 * the employee dashboard. Desktop: 2-column layout (40% list, 60% sticky detail
 * panel). Mobile (< 1024px): single-column timeline + bottom-sheet for task detail.
 *
 * Data: GET /api/relocation-plans/{id}/view (phased plan endpoint).
 * Edits: PATCH /api/cases/{caseId}/timeline/milestones/{id}.
 *
 * Design decisions (approved by Romain 2026-05-13):
 *   Q1 - Phase grouping: from API phases (not milestone_type prefix inference).
 *   Q2 - HR tasks: shown view-only to employees (greyed, no edit controls).
 *   Q3 - "Mark done": auto-sets actual_date=today, no confirmation dialog.
 *   Q4 - Mobile detail: bottom sheet slide-up (implemented in AIQ-3-D).
 *
 * Mobile layout (AIQ-3-D):
 *   - Single column — full-width timeline list, no right panel.
 *   - Tapping a task row opens a bottom sheet (fixed, slides up 200ms ease-out).
 *   - Bottom sheet max-height 85vh with internal scroll; backdrop dims the list.
 *   - Filter tabs scroll horizontally (overflow-x: auto) without wrapping.
 *   - All touch targets ≥ 44px; text min 14px (text-sm = 14px in Tailwind).
 *   - No JS breakpoint detection — sheet is always rendered, hidden via lg:hidden.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Input } from '../../components/antigravity/Input';
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Circle,
  CircleDot,
  Diamond,
  TriangleAlert,
  X,
} from 'lucide-react';
import { Button, Card, LoadingButton } from '../../components/antigravity';
import { fetchRelocationPlanView } from '../../api/relocationPlanView';
import { timelineAPI } from '../../api/client';
import { getApiErrorMessage, getClientTransportErrorMessage } from '../../utils/apiDetail';
import type {
  RelocationPlanPhaseDTO,
  RelocationPlanPhaseTaskDTO,
  RelocationPlanViewResponseDTO,
} from '../../types/relocationPlanView';

// ─── Types ────────────────────────────────────────────────────────────────────

export type RelocationTimelineRole = 'hr' | 'employee';
export type RelocationTimelineFilter = 'all' | 'overdue' | 'blocked' | 'in_progress' | 'done';

export interface RelocationTimelineProps {
  /** Used to fetch plan data and milestone updates. */
  assignmentId: string;
  /**
   * Controls edit permissions.
   *   employee (default): can edit status + notes only.
   *   hr: can edit all fields (target_date, owner, criticality).
   */
  role?: RelocationTimelineRole;
  /**
   * Role query param forwarded to GET /api/relocation-plans/{id}/view.
   * Defaults to match `role` prop.
   */
  planViewRole?: 'employee' | 'hr';
  /** If true, ensures default milestones are created on first load. */
  ensureDefaults?: boolean;
  /** Card title. Default: 'Relocation plan'. */
  title?: string;
  /** Hide the card's own h3 when embedded under a parent section heading. */
  hideMainTitle?: boolean;
  /** Fired when user clicks a task row (useful for external deep-linking). */
  onMilestoneSelect?: (milestoneId: string) => void;
}

// ─── Visual state derivation ──────────────────────────────────────────────────

type VisualStatus = 'done' | 'skipped' | 'in_progress' | 'blocked' | 'overdue' | 'pending';

function deriveVisualStatus(task: RelocationPlanPhaseTaskDTO): VisualStatus {
  const s = task.status;
  if (s === 'completed') return 'done';
  if (s === 'not_applicable') return 'skipped';
  // Overdue supersedes in_progress per spec.
  if (task.is_overdue) return 'overdue';
  if (s === 'blocked') return 'blocked';
  if (s === 'in_progress') return 'in_progress';
  return 'pending';
}

/** Map API status string to PATCH vocabulary accepted by the milestone endpoint. */
function apiStatusToPatch(apiStatus: string): string {
  switch (apiStatus) {
    case 'not_started': return 'pending';
    case 'in_progress': return 'in_progress';
    case 'completed': return 'done';
    case 'blocked': return 'blocked';
    case 'not_applicable': return 'skipped';
    default: return 'pending';
  }
}

/** Map PATCH vocabulary back to display label. */
function patchStatusLabel(s: string): string {
  switch (s) {
    case 'pending': return 'Not started';
    case 'in_progress': return 'In progress';
    case 'done': return 'Done';
    case 'blocked': return 'Blocked';
    case 'skipped': return 'Skipped';
    default: return s;
  }
}

function isTaskComplete(task: RelocationPlanPhaseTaskDTO): boolean {
  return task.status === 'completed' || task.status === 'not_applicable';
}

// ─── Visual token maps ────────────────────────────────────────────────────────

const VISUAL: Record<
  VisualStatus,
  {
    /** Applied to the circular dot icon — must meet ≥ 3:1 (graphical object). */
    dotClass: string;
    /**
     * Applied to the inline status badge in the detail panel.
     * Uses lighter background + darker text for ≥ 4.5:1 (text-xs body text).
     */
    badgeClass: string;
    accentClass: string;
    textClass: string;
    label: string;
  }
> = {
  done: {
    // emerald-700 bg, white icon → 5.48:1 ✅
    dotClass: 'bg-emerald-700 text-white',
    // emerald-800 on emerald-50 → 7.29:1 ✅
    badgeClass: 'bg-emerald-50 text-emerald-800',
    accentClass: 'border-l-2 border-emerald-600',
    // slate-500 on white → 4.76:1 ✅ (was slate-400 at 2.56:1 — fixed)
    textClass: 'text-slate-500',
    label: 'Done',
  },
  skipped: {
    // slate-500 on slate-200 → 3.86:1 ✅
    dotClass: 'bg-slate-200 text-slate-500',
    // slate-600 on slate-100 → 6.92:1 ✅
    badgeClass: 'bg-slate-100 text-slate-600',
    accentClass: 'border-l-2 border-slate-300',
    // slate-500 on white → 4.76:1 ✅ (was slate-400 — fixed)
    textClass: 'text-slate-500',
    label: 'Skipped',
  },
  in_progress: {
    // sky-600 on sky-100 → 3.57:1 ✅ (graphical object)
    dotClass: 'bg-sky-100 text-sky-600 border border-sky-400',
    // sky-800 on sky-50 → 7.09:1 ✅
    badgeClass: 'bg-sky-50 text-sky-800',
    accentClass: 'border-l-2 border-sky-500',
    textClass: 'text-slate-900',
    label: 'In progress',
  },
  blocked: {
    // amber-700 on amber-100 → 4.51:1 ✅ (was amber-600 at 2.86:1 — fixed)
    dotClass: 'bg-amber-100 text-amber-700 border border-amber-400',
    // amber-800 on amber-50 → 6.84:1 ✅
    badgeClass: 'bg-amber-50 text-amber-800',
    accentClass: 'border-l-2 border-amber-500',
    textClass: 'text-slate-900',
    label: 'Blocked',
  },
  overdue: {
    // red-600 on red-100 → 3.95:1 ✅ (graphical object)
    dotClass: 'bg-red-100 text-red-600 border border-red-400',
    // red-700 on red-50 → 5.91:1 ✅
    badgeClass: 'bg-red-50 text-red-700',
    accentClass: 'border-l-2 border-red-500',
    textClass: 'text-red-700',
    label: 'Overdue',
  },
  pending: {
    // slate-500 on white → 4.76:1 ✅ (was slate-300 at 1.48:1 — fixed)
    dotClass: 'bg-white text-slate-500 border border-slate-500',
    // slate-600 on slate-50 → 6.92:1 ✅
    badgeClass: 'bg-slate-50 text-slate-600',
    accentClass: '',
    textClass: 'text-slate-700',
    label: 'Not started',
  },
};

const OWNER_CHIP: Record<string, { label: string; chipClass: string }> = {
  employee: { label: 'Employee', chipClass: 'bg-amber-50 text-amber-800 border border-amber-200' },
  hr: { label: 'HR', chipClass: 'bg-sky-50 text-sky-800 border border-sky-200' },
  joint: { label: 'Joint', chipClass: 'bg-slate-100 text-slate-600 border border-slate-200' },
  provider: { label: 'Provider', chipClass: 'bg-accent-50 text-accent-700 border border-accent-200' },
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function TimelineDot({ status }: { status: VisualStatus }) {
  const v = VISUAL[status];
  const iconClass = 'size-3';

  const icon = (() => {
    switch (status) {
      case 'done': return <CheckCircle2 className={iconClass} strokeWidth={2.5} aria-hidden />;
      case 'skipped': return <Circle className={iconClass} aria-hidden />;
      case 'in_progress': return <CircleDot className={iconClass} aria-hidden />;
      case 'blocked': return <Ban className={iconClass} aria-hidden />;
      case 'overdue': return <TriangleAlert className={iconClass} aria-hidden />;
      case 'pending': return <Circle className={iconClass} aria-hidden />;
    }
  })();

  return (
    <span
      className={`relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${v.dotClass}`}
      aria-hidden
    >
      {icon}
    </span>
  );
}

function OwnerChip({ owner }: { owner: string }) {
  const chip = OWNER_CHIP[owner] ?? OWNER_CHIP.joint;
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${chip.chipClass}`}>
      {chip.label}
    </span>
  );
}

// ─── Filter helpers ───────────────────────────────────────────────────────────

function taskMatchesFilter(task: RelocationPlanPhaseTaskDTO, filter: RelocationTimelineFilter): boolean {
  const visual = deriveVisualStatus(task);
  switch (filter) {
    case 'all': return true;
    case 'overdue': return visual === 'overdue';
    case 'blocked': return visual === 'blocked';
    case 'in_progress': return visual === 'in_progress';
    case 'done': return visual === 'done' || visual === 'skipped';
  }
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function SkeletonTimeline() {
  return (
    <div className="animate-pulse space-y-3" aria-hidden>
      {[80, 60, 90, 50, 70].map((w, i) => (
        <div key={i} className="flex items-center gap-3">
          <div className="h-6 w-6 shrink-0 rounded-full bg-slate-200" />
          <div className={`h-4 rounded bg-slate-200`} style={{ width: `${w}%` }} />
        </div>
      ))}
    </div>
  );
}

// ─── Next-focus callout ───────────────────────────────────────────────────────

function NextFocusCallout({
  task,
  phaseTitle,
  onSelect,
}: {
  task: RelocationPlanPhaseTaskDTO;
  phaseTitle: string;
  onSelect: () => void;
}) {
  const visual = deriveVisualStatus(task);
  const isOverdue = visual === 'overdue';
  const isCritical = task.priority === 'critical';

  const bg = isOverdue
    ? 'bg-red-50 border border-red-200'
    : isCritical
      ? 'bg-amber-50 border border-amber-200'
      : 'bg-sky-50 border border-sky-200';

  const iconClass = isOverdue ? 'text-red-600' : isCritical ? 'text-amber-600' : 'text-sky-600';
  const headingClass = isOverdue ? 'text-red-800' : isCritical ? 'text-amber-800' : 'text-sky-800';
  const subClass = isOverdue ? 'text-red-700' : isCritical ? 'text-amber-700' : 'text-sky-700';

  const ownerText = OWNER_CHIP[task.owner]?.label ?? 'Joint';
  const dueLine = task.due_date
    ? isOverdue
      ? `Overdue since ${task.due_date}`
      : `Due ${task.due_date}`
    : null;

  return (
    // role="alert" must NOT be on interactive elements — removed. The callout is
    // announced on first render via the surrounding aria-live="polite" region in
    // the loading state; here it is a standard button.
    <Button unstyled
      type="button"
      onClick={onSelect}
      className={`w-full text-left rounded-xl px-4 py-3 flex gap-3 items-start ${bg} focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43] focus-visible:ring-offset-2`}
      aria-label={`Next focus: ${task.title}. ${dueLine ?? ''}. Click to view details.`}
    >
      <AlertTriangle className={`mt-0.5 size-5 shrink-0 ${iconClass}`} aria-hidden />
      <div className="min-w-0">
        <p className={`text-sm font-semibold ${headingClass}`}>
          Next focus: {task.title}
        </p>
        <p className={`text-xs mt-0.5 ${subClass}`}>
          {[dueLine, ownerText, phaseTitle].filter(Boolean).join(' · ')}
        </p>
      </div>
    </Button>
  );
}

// ─── Detail panel content (shared between desktop panel + mobile bottom sheet) ─

interface DetailPanelContentProps {
  task: RelocationPlanPhaseTaskDTO;
  caseId: string | null;
  role: RelocationTimelineRole;
  /** Prefix for form element IDs — avoids duplicates when rendered in two places. */
  idPrefix: string;
  onSaved: () => void;
}

function DetailPanelContent({ task, caseId, role, idPrefix, onSaved }: DetailPanelContentProps) {
  const [statusDraft, setStatusDraft] = useState(() => apiStatusToPatch(task.status));
  const [noteDraft, setNoteDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);
  const prevTaskId = useRef<string | null>(null);

  // Sync drafts when selected task changes.
  useEffect(() => {
    if (task.task_id === prevTaskId.current) return;
    prevTaskId.current = task.task_id;
    setStatusDraft(apiStatusToPatch(task.status));
    setNoteDraft('');
    setSaveError(null);
    setSavedFlash(false);
  }, [task]);

  const canEditTargetDate = role === 'hr';
  const canSkip = role === 'hr';
  const isHrOwned = task.owner === 'hr';
  const panelCanEdit = role === 'hr' || !isHrOwned;

  const visual = deriveVisualStatus(task);
  const v = VISUAL[visual];
  const done = isTaskComplete(task);

  const handleSave = useCallback(async () => {
    if (!caseId) return;
    setSaving(true);
    setSaveError(null);
    try {
      const patch: Record<string, unknown> = { status: statusDraft };
      if (noteDraft.trim()) patch.notes = noteDraft.trim();
      await timelineAPI.updateMilestone(caseId, task.task_id, patch);
      setSavedFlash(true);
      window.setTimeout(() => setSavedFlash(false), 2000);
      onSaved();
    } catch (err: unknown) {
      const transport = getClientTransportErrorMessage(err);
      const msg = transport ?? getApiErrorMessage(err, (err as Error)?.message ?? '');
      setSaveError(msg.trim() ? msg : 'Save failed');
    } finally {
      setSaving(false);
    }
  }, [caseId, statusDraft, noteDraft, task.task_id, onSaved]);

  const handleMarkDone = useCallback(async () => {
    if (!caseId) return;
    setSaving(true);
    setSaveError(null);
    try {
      const today = new Date().toISOString().slice(0, 10);
      await timelineAPI.updateMilestone(caseId, task.task_id, { status: 'done', actual_date: today });
      setSavedFlash(true);
      window.setTimeout(() => setSavedFlash(false), 2000);
      onSaved();
    } catch (err: unknown) {
      const transport = getClientTransportErrorMessage(err);
      const msg = transport ?? getApiErrorMessage(err, (err as Error)?.message ?? '');
      setSaveError(msg.trim() ? msg : 'Save failed');
    } finally {
      setSaving(false);
    }
  }, [caseId, task.task_id, onSaved]);

  const handleSkip = useCallback(async () => {
    if (!caseId) return;
    setSaving(true);
    setSaveError(null);
    try {
      await timelineAPI.updateMilestone(caseId, task.task_id, { status: 'skipped' });
      onSaved();
    } catch (err: unknown) {
      const transport = getClientTransportErrorMessage(err);
      const msg = transport ?? getApiErrorMessage(err, (err as Error)?.message ?? '');
      setSaveError(msg.trim() ? msg : 'Save failed');
    } finally {
      setSaving(false);
    }
  }, [caseId, task.task_id, onSaved]);

  return (
    <>
      {/* Header section */}
      <div className={`px-4 pt-4 pb-3 border-b border-slate-100 ${done ? 'bg-slate-50/70' : 'bg-white'}`}>
        <div className="flex items-start justify-between gap-2 flex-wrap">
          {/* Use badgeClass (not dotClass) — darker text/lighter bg meets ≥ 4.5:1 for text-xs */}
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${v.badgeClass}`}
            aria-label={`Status: ${v.label}`}
          >
            <TimelineDot status={visual} />
            <span>{v.label}</span>
          </span>
          <OwnerChip owner={task.owner} />
        </div>
        {/* h4: heading hierarchy — Card already uses h3 for the panel title */}
        <h4 className={`mt-2 text-base font-semibold leading-snug ${done ? 'text-slate-500 line-through' : 'text-[#0b2b43]'}`}>
          {task.title}
        </h4>
        {task.priority === 'critical' && !done && (
          <span className="mt-1 inline-flex items-center gap-1 text-[11px] font-medium text-red-700">
            <Diamond className="size-3" aria-hidden /> Critical path
          </span>
        )}
        {task.due_date && (
          <p className={`text-xs mt-1 ${visual === 'overdue' ? 'text-red-700 font-medium' : 'text-slate-500'}`}>
            {visual === 'overdue' ? `Overdue since ${task.due_date}` : `Due ${task.due_date}`}
          </p>
        )}
        {done && (
          <p className="text-xs text-slate-400 mt-0.5">Completed</p>
        )}
      </div>

      {/* Body section */}
      <div className="px-4 py-4 space-y-4">
        {task.why_this_matters && (
          <p className="text-sm text-slate-600 leading-relaxed">{task.why_this_matters}</p>
        )}

        {/* Step-by-step instructions — sent by backend, previously ignored */}
        {Array.isArray(task.instructions) && task.instructions.length > 0 && (
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-400 mb-1.5">
              How to complete this step
            </p>
            <ol className="space-y-1.5">
              {(task.instructions as string[]).map((step, i) => (
                <li key={i} className="flex gap-2.5 text-sm text-slate-600">
                  <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[#1f8e8b]/10 text-[10px] font-semibold text-[#1f8e8b]">
                    {i + 1}
                  </span>
                  <span className="leading-snug">{step}</span>
                </li>
              ))}
            </ol>
          </div>
        )}

        {/* Required inputs checklist — shows what's already provided vs. still needed */}
        {Array.isArray(task.required_inputs) && task.required_inputs.length > 0 && (
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-400 mb-1.5">
              What's needed
            </p>
            <ul className="space-y-1">
              {(task.required_inputs as { label: string; present: boolean }[]).map((inp, i) => (
                <li key={i} className="flex items-center gap-2 text-sm">
                  {inp.present ? (
                    <svg className="h-3.5 w-3.5 shrink-0 text-emerald-500" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                      <circle cx="7" cy="7" r="6.5" className="fill-emerald-50 stroke-emerald-300" strokeWidth="1" />
                      <path d="M4 7l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  ) : (
                    <svg className="h-3.5 w-3.5 shrink-0 text-amber-400" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                      <circle cx="7" cy="7" r="6.5" className="fill-amber-50 stroke-amber-300" strokeWidth="1" />
                      <path d="M7 4v3M7 9.5h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                    </svg>
                  )}
                  <span className={inp.present ? 'text-slate-500 line-through' : 'text-slate-700'}>
                    {inp.label}
                  </span>
                  {!inp.present && (
                    <span className="ml-auto text-[10px] font-medium text-amber-600 bg-amber-50 rounded px-1.5 py-0.5">
                      Missing
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* CTA button — backend sends type + label; target is not yet wired so we
            show the button only when the label is present and link to the dossier
            as a sensible fallback until backend populates cta.target per-task. */}
        {task.cta?.label && !isHrOwned && (
          <a
            href={task.cta.target ?? '#'}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#0b2b43] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#0b2b43]/90 transition-colors"
          >
            {task.cta.label}
            <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none" aria-hidden="true">
              <path d="M2.5 6h7M6.5 3.5l3 2.5-3 2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </a>
        )}

        {/* Blocked-by details — previously only showed generic "Blocked" badge */}
        {task.status === 'blocked' && Array.isArray(task.blocked_by) && task.blocked_by.length > 0 && (
          <div className="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2.5">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-amber-600 mb-1">
              Waiting on
            </p>
            <ul className="space-y-0.5">
              {(task.blocked_by as string[]).map((dep, i) => (
                <li key={i} className="text-xs text-amber-700">
                  {dep.replace(/_/g, ' ')}
                </li>
              ))}
            </ul>
          </div>
        )}

        {isHrOwned && role === 'employee' && (
          <p className="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
            HR is handling this step. No action required from you.
          </p>
        )}

        {panelCanEdit && (
          <div>
            <label
              htmlFor={`${idPrefix}-status`}
              className="block text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1"
            >
              Status
            </label>
            <select
              id={`${idPrefix}-status`}
              value={statusDraft}
              onChange={(e) => setStatusDraft(e.target.value)}
              disabled={saving}
              className="w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm text-[#0b2b43] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43] focus-visible:ring-offset-2"
            >
              {['pending', 'in_progress', 'blocked', 'done', 'skipped'].map((s) => (
                <option key={s} value={s}>{patchStatusLabel(s)}</option>
              ))}
            </select>
          </div>
        )}

        {canEditTargetDate && (
          <div>
            <label
              htmlFor={`${idPrefix}-date`}
              className="block text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1"
            >
              Due date
            </label>
            <Input unstyled
              id={`${idPrefix}-date`}
              type="date"
              defaultValue={task.due_date ?? ''}
              disabled={saving}
              className="w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm text-[#0b2b43] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43] focus-visible:ring-offset-2"
            />
          </div>
        )}

        {panelCanEdit && (
          <div>
            <label
              htmlFor={`${idPrefix}-notes`}
              className="block text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1"
            >
              Notes{statusDraft === 'blocked' ? ' / Block reason' : ''}
            </label>
            <textarea
              id={`${idPrefix}-notes`}
              value={noteDraft}
              onChange={(e) => setNoteDraft(e.target.value)}
              disabled={saving}
              rows={3}
              placeholder={
                statusDraft === 'blocked'
                  ? "What's blocking this? Add context for your HR team"
                  : 'Optional note…'
              }
              className="w-full rounded-lg border border-slate-200 bg-white px-2 py-2 text-sm text-[#334155] placeholder:text-slate-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43] focus-visible:ring-offset-2 resize-none"
            />
          </div>
        )}

        {saveError && (
          <p className="text-xs text-red-600" role="alert">{saveError}</p>
        )}
        {savedFlash && (
          <p className="text-xs text-emerald-600" aria-live="polite">Saved ✓</p>
        )}

        {panelCanEdit && (
          <div className="flex flex-wrap gap-2 pt-1">
            <LoadingButton
              loading={saving}
              onClick={() => void handleSave()}
              variant="primary"
              size="sm"
            >
              Save notes
            </LoadingButton>
            {!done && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => void handleMarkDone()}
                disabled={saving}
                aria-label="Mark this task done"
              >
                Mark done ✓
              </Button>
            )}
            {canSkip && !done && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void handleSkip()}
                disabled={saving}
              >
                Skip
              </Button>
            )}
          </div>
        )}
      </div>
    </>
  );
}

// ─── Desktop detail panel wrapper ─────────────────────────────────────────────

interface DetailPanelProps {
  task: RelocationPlanPhaseTaskDTO | null;
  caseId: string | null;
  role: RelocationTimelineRole;
  onSaved: () => void;
}

function DetailPanel({ task, caseId, role, onSaved }: DetailPanelProps) {
  if (!task) {
    return (
      <div className="hidden lg:flex h-full min-h-[200px] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-6">
        <p className="text-sm text-slate-400 text-center">Select a task to view and edit details</p>
      </div>
    );
  }
  return (
    <div className="hidden lg:block sticky top-4 rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <DetailPanelContent
        task={task}
        caseId={caseId}
        role={role}
        idPrefix="dp"
        onSaved={onSaved}
      />
    </div>
  );
}

// ─── Mobile bottom sheet ──────────────────────────────────────────────────────

interface BottomSheetProps {
  open: boolean;
  task: RelocationPlanPhaseTaskDTO | null;
  caseId: string | null;
  role: RelocationTimelineRole;
  onClose: () => void;
  onSaved: () => void;
}

const FOCUSABLE_SELECTORS =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function BottomSheet({ open, task, caseId, role, onClose, onSaved }: BottomSheetProps) {
  const sheetRef = useRef<HTMLDivElement>(null);

  // Close on Escape key.
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // Move focus into sheet when it opens.
  useEffect(() => {
    if (open && sheetRef.current) {
      const first = sheetRef.current.querySelector<HTMLElement>(FOCUSABLE_SELECTORS);
      first?.focus();
    }
  }, [open, task]);

  // Focus trap — keep Tab / Shift+Tab inside the dialog while it is open.
  // WCAG 2.4.3 Focus Order + APG modal dialog pattern.
  useEffect(() => {
    if (!open) return;
    const trapFocus = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !sheetRef.current) return;
      const focusable = Array.from(
        sheetRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTORS)
      ).filter((el) => !el.closest('[aria-hidden="true"]'));
      if (focusable.length === 0) { e.preventDefault(); return; }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', trapFocus);
    return () => document.removeEventListener('keydown', trapFocus);
  }, [open]);

  // Prevent body scroll while sheet is open.
  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  return (
    // Outer: lg:hidden so it never appears on desktop
    <div className={`lg:hidden`} aria-hidden={!open}>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-black/30 transition-opacity duration-200 ${
          open ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
        aria-hidden
      />

      {/* Sheet */}
      <div
        ref={sheetRef}
        role="dialog"
        aria-modal="true"
        aria-label={task ? `Task details: ${task.title}` : 'Task details'}
        className={`fixed inset-x-0 bottom-0 z-50 max-h-[85vh] flex flex-col rounded-t-2xl border-t border-slate-200 bg-white shadow-2xl transition-transform duration-200 ease-out ${
          open ? 'translate-y-0' : 'translate-y-full'
        }`}
      >
        {/* Drag handle + close */}
        <div className="flex items-center justify-between px-4 pt-3 pb-2 shrink-0">
          <div className="mx-auto w-10 h-1 rounded-full bg-slate-300" aria-hidden />
          <Button unstyled
            type="button"
            onClick={onClose}
            className="absolute right-4 top-3 p-2 rounded-lg text-slate-500 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43]"
            aria-label="Close task details"
          >
            <X className="size-5" aria-hidden />
          </Button>
        </div>

        {/* Scrollable content */}
        <div className="overflow-y-auto flex-1 pb-safe">
          {task ? (
            <DetailPanelContent
              task={task}
              caseId={caseId}
              role={role}
              idPrefix="bs"
              onSaved={() => { onSaved(); onClose(); }}
            />
          ) : (
            <p className="text-sm text-slate-400 text-center py-8">
              Select a task to view details
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Task row ─────────────────────────────────────────────────────────────────

function TaskRow({
  task,
  selected,
  isLast,
  onSelect,
}: {
  task: RelocationPlanPhaseTaskDTO;
  selected: boolean;
  isLast: boolean;
  onSelect: () => void;
}) {
  const visual = deriveVisualStatus(task);
  const v = VISUAL[visual];
  const done = isTaskComplete(task);

  return (
    <li className="relative flex gap-3">
      {/* Vertical connector line */}
      {!isLast && (
        <span
          className="absolute left-3 top-6 bottom-0 w-[2px] bg-slate-200 -z-0"
          aria-hidden
        />
      )}

      <span className="relative z-10 pt-0.5 shrink-0">
        <TimelineDot status={visual} />
      </span>

      <Button unstyled
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        aria-label={`${task.title}. ${v.label}${task.due_date ? `. Due ${task.due_date}` : ''}. ${selected ? 'Selected' : 'Click to view details'}`}
        className={`flex-1 min-w-0 text-left rounded-lg px-3 py-2 min-h-[44px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43] focus-visible:ring-offset-2 ${
          selected
            ? 'bg-[#0b2b43]/5 border border-[#0b2b43]/15'
            : 'hover:bg-slate-50 border border-transparent'
        } ${v.accentClass}`}
      >
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 min-w-0">
          <span className={`text-sm font-medium leading-snug truncate ${done ? 'line-through text-slate-400' : v.textClass}`}>
            {task.title}
          </span>
          <OwnerChip owner={task.owner} />
          {task.priority === 'critical' && !done && (
            <span aria-label="Critical path" className="text-red-700" title="Critical path">
              <Diamond className="size-3" aria-hidden />
            </span>
          )}
        </div>
        {(task.due_date || visual === 'overdue') && (
          <p className={`text-xs mt-0.5 ${visual === 'overdue' ? 'text-red-700 font-medium' : 'text-slate-500'}`}>
            {visual === 'overdue'
              ? `Overdue · ${task.due_date}`
              : `Due ${task.due_date}`}
          </p>
        )}
        {visual === 'blocked' && (
          <p className="text-xs text-amber-800 mt-0.5">Blocked</p>
        )}
      </Button>
    </li>
  );
}

// ─── Phase header ─────────────────────────────────────────────────────────────

function PhaseHeader({ phase }: { phase: RelocationPlanPhaseDTO }) {
  const phaseDone = phase.status === 'completed';
  const phaseBlocked = phase.status === 'blocked';

  return (
    <li className="relative flex gap-3 items-center" aria-label={`Phase: ${phase.title}`}>
      {/* Phase dot — slightly larger */}
      <span
        className={`relative z-10 flex h-3 w-3 shrink-0 mx-1.5 rounded-full ring-2 ring-white ${
          phaseDone
            ? 'bg-emerald-500'
            : phaseBlocked
              ? 'bg-amber-400'
              : phase.status === 'active'
                ? 'bg-[#0b2b43]'
                : 'bg-slate-300'
        }`}
        aria-hidden
      />
      <div className="flex-1 flex items-center gap-2 min-w-0 py-1 border-b border-slate-100">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500 truncate">
          {phase.title}
        </span>
        {phase.task_counts.total > 0 && (
          // slate-500 on white → 4.76:1 ✅ (was slate-400 at 2.56:1)
          <span className="text-[10px] text-slate-500 shrink-0">
            {phase.task_counts.completed}/{phase.task_counts.total}
          </span>
        )}
      </div>
    </li>
  );
}

// ─── Empty states ─────────────────────────────────────────────────────────────

function EmptyNoMilestones({ role, onEnsure }: { role: RelocationTimelineRole; onEnsure?: () => void }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50/50 p-8 text-center">
      <p className="text-2xl mb-2">📋</p>
      <p className="text-sm font-medium text-slate-700">No relocation plan yet.</p>
      <p className="text-sm text-slate-500 mt-1">Your HR team will set up your task list shortly.</p>
      {role === 'hr' && onEnsure && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onEnsure}>
          Create default plan
        </Button>
      )}
    </div>
  );
}

function EmptyFilterNoResults() {
  return (
    <div className="rounded-xl border border-dashed border-slate-200 px-4 py-6 text-center">
      <p className="text-sm text-slate-500">No tasks match this filter.</p>
    </div>
  );
}

function EmptyAllDone() {
  return (
    <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-8 text-center">
      <p className="text-2xl mb-2">✅</p>
      <p className="text-sm font-semibold text-emerald-800">All tasks complete — great work!</p>
      <p className="text-sm text-emerald-700 mt-1">Your relocation plan is fully checked off.</p>
    </div>
  );
}

// ─── Filter tabs ──────────────────────────────────────────────────────────────

interface FilterTabsProps {
  active: RelocationTimelineFilter;
  counts: Record<RelocationTimelineFilter, number>;
  onChange: (f: RelocationTimelineFilter) => void;
}

const FILTER_TABS: Array<{ key: RelocationTimelineFilter; label: string }> = [
  { key: 'all', label: 'Total' },
  { key: 'overdue', label: 'Overdue' },
  { key: 'blocked', label: 'Blocked' },
  { key: 'in_progress', label: 'In Progress' },
  { key: 'done', label: 'Done' },
];

function FilterTabs({ active, counts, onChange }: FilterTabsProps) {
  return (
    <div
      role="tablist"
      aria-label="Filter tasks"
      className="flex gap-1 overflow-x-auto scrollbar-none -mx-1 px-1 pb-0.5"
    >
      {FILTER_TABS.map((tab) => {
        const isActive = active === tab.key;
        const count = counts[tab.key];
        return (
          <Button unstyled
            key={tab.key}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.key)}
            className={`flex shrink-0 items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43] focus-visible:ring-offset-1 ${
              isActive
                ? 'bg-[#0b2b43] text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            {tab.label}
            <span
              className={`inline-flex items-center justify-center min-w-[18px] h-[18px] rounded-full text-[10px] font-semibold px-1 ${
                isActive ? 'bg-white/20 text-white' : 'bg-white text-slate-500'
              }`}
            >
              {count}
            </span>
          </Button>
        );
      })}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export const RelocationTimeline: React.FC<RelocationTimelineProps> = ({
  assignmentId,
  role = 'employee',
  planViewRole,
  ensureDefaults = false,
  title = 'Relocation plan',
  hideMainTitle = false,
  onMilestoneSelect,
}) => {
  const [data, setData] = useState<RelocationPlanViewResponseDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<RelocationTimelineFilter>('all');
  const [bottomSheetOpen, setBottomSheetOpen] = useState(false);

  const effectiveViewRole = planViewRole ?? role;

  const load = useCallback(
    async (opts?: { forceEnsure?: boolean }) => {
      if (!assignmentId) return;
      setLoading(true);
      setError(null);
      try {
        const view = await fetchRelocationPlanView(assignmentId, { role: effectiveViewRole });

        // Optionally ensure defaults on first empty load.
        if (view.summary.total_tasks === 0 && (ensureDefaults || opts?.forceEnsure)) {
          await import('../../api/client').then(({ timelineAPI: tAPI }) =>
            tAPI.getByAssignment(assignmentId, { ensureDefaults: true, includeLinks: false })
          );
          const refreshed = await fetchRelocationPlanView(assignmentId, { role: effectiveViewRole });
          setData(refreshed);
        } else {
          setData(view);
        }

        // Auto-select: prefer next_action task, else first non-done task.
        setSelectedId((prev) => {
          const allTasks = view.phases?.flatMap((p) => p.tasks) ?? [];
          if (view.next_action?.task_id && allTasks.some((t) => t.task_id === view.next_action!.task_id)) {
            return view.next_action.task_id;
          }
          if (prev && allTasks.some((t) => t.task_id === prev)) return prev;
          const firstIncomplete = allTasks.find((t) => !isTaskComplete(t));
          return firstIncomplete?.task_id ?? allTasks[0]?.task_id ?? null;
        });
      } catch (err: unknown) {
        const transport = getClientTransportErrorMessage(err);
        const msg = transport ?? getApiErrorMessage(err, (err as Error)?.message ?? '');
        setError(msg.trim() ? msg : 'Failed to load your relocation plan');
        setData(null);
      } finally {
        setLoading(false);
      }
    },
    [assignmentId, effectiveViewRole, ensureDefaults]
  );

  useEffect(() => {
    void load();
  }, [load]);

  // Flatten all tasks for counts + next-focus.
  const allTasks = useMemo(
    () => data?.phases?.flatMap((p) => p.tasks) ?? [],
    [data]
  );

  // Compute filter counts.
  const filterCounts = useMemo((): Record<RelocationTimelineFilter, number> => {
    const counts: Record<RelocationTimelineFilter, number> = {
      all: allTasks.length,
      overdue: 0,
      blocked: 0,
      in_progress: 0,
      done: 0,
    };
    for (const t of allTasks) {
      const v = deriveVisualStatus(t);
      if (v === 'overdue') counts.overdue++;
      if (v === 'blocked') counts.blocked++;
      if (v === 'in_progress') counts.in_progress++;
      if (v === 'done' || v === 'skipped') counts.done++;
    }
    return counts;
  }, [allTasks]);

  // Next focus task: first overdue, then critical non-done, then first non-done.
  const nextFocusTask = useMemo((): { task: RelocationPlanPhaseTaskDTO; phaseTitle: string } | null => {
    if (!data?.phases) return null;
    for (const ph of data.phases) {
      for (const t of ph.tasks) {
        if (isTaskComplete(t)) continue;
        const v = deriveVisualStatus(t);
        if (v === 'overdue' || t.priority === 'critical') {
          return { task: t, phaseTitle: ph.title };
        }
      }
    }
    return null;
  }, [data]);

  const selectedTask = useMemo(
    () => allTasks.find((t) => t.task_id === selectedId) ?? null,
    [allTasks, selectedId]
  );

  const handleSelect = useCallback(
    (taskId: string) => {
      setSelectedId(taskId);
      setBottomSheetOpen(true);
      onMilestoneSelect?.(taskId);
    },
    [onMilestoneSelect]
  );

  const allComplete = allTasks.length > 0 && allTasks.every(isTaskComplete);

  // ── Render: error ──────────────────────────────────────────────────────────
  if (error) {
    return (
      <Card padding="lg">
        <p className="text-sm text-red-600 flex gap-2 items-center" role="alert">
          <AlertTriangle className="size-4 shrink-0" aria-hidden /> {error}
        </p>
        <Button variant="outline" size="sm" className="mt-3" onClick={() => void load()}>
          Retry
        </Button>
      </Card>
    );
  }

  // ── Render: loading ────────────────────────────────────────────────────────
  if (loading && !data) {
    return (
      <Card padding="lg">
        {!hideMainTitle && (
          <h3 className="text-base font-semibold text-[#0b2b43] mb-4">{title}</h3>
        )}
        <div role="status" aria-live="polite" aria-busy="true">
          <span className="sr-only">Loading plan tasks…</span>
          <SkeletonTimeline />
        </div>
      </Card>
    );
  }

  // ── Render: empty — no milestones ─────────────────────────────────────────
  if (!loading && (!data || allTasks.length === 0)) {
    return (
      <Card padding="lg">
        {!hideMainTitle && (
          <h3 className="text-base font-semibold text-[#0b2b43] mb-4">{title}</h3>
        )}
        <EmptyNoMilestones role={role} onEnsure={() => void load({ forceEnsure: true })} />
      </Card>
    );
  }

  // ── Build filtered phases ──────────────────────────────────────────────────
  const filteredPhases: Array<{ phase: RelocationPlanPhaseDTO; tasks: RelocationPlanPhaseTaskDTO[] }> =
    (data?.phases ?? [])
      .map((phase) => ({
        phase,
        tasks: phase.tasks.filter((t) => taskMatchesFilter(t, filter)),
      }))
      .filter((p) => p.tasks.length > 0);

  const hasFilterResults = filteredPhases.some((p) => p.tasks.length > 0);

  return (
    <>
      <Card padding="lg">
        {/* Card header */}
        {!hideMainTitle && (
          <div className="mb-1">
            <h3 className="text-base font-semibold text-[#0b2b43]">{title}</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Shared operational checklist — HR and employee view the same tasks; ownership shows who drives each step.
            </p>
          </div>
        )}

        {/* Next focus callout */}
        {nextFocusTask && (
          <div className="mt-3">
            <NextFocusCallout
              task={nextFocusTask.task}
              phaseTitle={nextFocusTask.phaseTitle}
              onSelect={() => handleSelect(nextFocusTask.task.task_id)}
            />
          </div>
        )}

        {/* Filter tabs */}
        <div className="mt-3">
          <FilterTabs active={filter} counts={filterCounts} onChange={setFilter} />
        </div>

        {/* All done state */}
        {allComplete && filter === 'all' ? (
          <div className="mt-4">
            <EmptyAllDone />
          </div>
        ) : !hasFilterResults ? (
          <div className="mt-4">
            <EmptyFilterNoResults />
          </div>
        ) : (
          /* Two-column layout */
          <div className="mt-4 lg:grid lg:grid-cols-[40%_60%] lg:gap-6 items-start">
            {/* LEFT: timeline list */}
            <div className="overflow-y-auto max-h-[70vh] pr-1">
              <ul
                role="list"
                aria-label="Relocation milestones"
                className="relative space-y-1 pl-3"
              >
                {filteredPhases.map(({ phase, tasks }) => (
                  <React.Fragment key={phase.phase_key}>
                    <PhaseHeader phase={phase} />
                    {tasks.map((task, idx) => (
                      <TaskRow
                        key={task.task_id}
                        task={task}
                        selected={selectedId === task.task_id}
                        isLast={idx === tasks.length - 1}
                        onSelect={() => handleSelect(task.task_id)}
                      />
                    ))}
                  </React.Fragment>
                ))}
              </ul>
            </div>

            {/* RIGHT: detail panel (desktop only) */}
            <DetailPanel
              task={selectedTask}
              caseId={data?.case_id ?? null}
              role={role}
              onSaved={() => void load()}
            />
          </div>
        )}
      </Card>

      {/* Mobile bottom sheet — rendered outside Card so fixed positioning works correctly */}
      <BottomSheet
        open={bottomSheetOpen}
        task={selectedTask}
        caseId={data?.case_id ?? null}
        role={role}
        onClose={() => setBottomSheetOpen(false)}
        onSaved={() => void load()}
      />
    </>
  );
};

export default RelocationTimeline;
