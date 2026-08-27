/**
 * Redesigned employee roadmap — renders the plan-view (milestone-backed) journey
 * in the approved template: dark hero + mini phase-timeline, "what you can do now",
 * an HR/partner-handled banner, and collapsible phase sections with rich rows.
 * Pure presentation; data + handlers are passed in by EmployeeCaseRoadmapPage.
 */
import React, { useMemo, useState, useEffect, useId, useRef } from 'react';
import {
  Check, Circle, Lock, Loader2, Sparkles, Flag, FileText, ChevronUp, ChevronDown,
  Clock, ArrowRight, ExternalLink, Info,
} from 'lucide-react';
import { CountryFlag } from '../../../components/antigravity/CountryFlag';
import { getCountryName } from '../../../utils/countries';
import { ownerLabel } from '../relocationPlanLabels';
import { RoadmapActions } from '../../platform-v2/roadmap/RoadmapActions';
import { ConfidenceBadge } from '../../platform-v2/roadmap/ConfidenceBadge';
import { resolveConfidenceLevel, type StepConfidence } from '../../platform-v2/roadmap/confidence.tokens';
import { deriveCanonicalProgress } from '../../employee-journey/caseStage';
import type {
  RelocationPlanViewResponseDTO,
  RelocationPlanPhaseDTO,
  RelocationPlanPhaseTaskDTO,
  RelocationPlanTaskStatusWire,
} from '../../../types/relocationPlanView';
import {
  phaseIcon, titlesByCode, actionableTasks, hrHandledTasks, resolveBlockedBy,
  rowStatus, formatDue, docCount, daysUntil, normalizeStepTitle, type RowTone,
} from './roadmapTemplateHelpers';

/** Confidence keyed by normalised task title, supplied by the page from /roadmap/tracks. */
export type ConfidenceByTitle = Record<string, StepConfidence>;

export interface RoadmapHeaderMeta {
  originCity?: string;
  destCity?: string;
  destCountry?: string;
  employeeName?: string;
  role?: string;
  targetMoveDate?: string;
}

export interface RoadmapTemplateProps {
  data: RelocationPlanViewResponseDTO;
  header: RoadmapHeaderMeta | null;
  caseId: string;
  onCta: (task: RelocationPlanPhaseTaskDTO) => void;
  validated: boolean;
  validatedAt: string | null;
  validating: boolean;
  onValidate: () => void;
  /** [AIQ-806] Per-task confidence matched from the /roadmap/tracks projection. */
  confidenceByTitle?: ConfidenceByTitle;
  /**
   * [AIQ-1526] HR hasn't approved this plan yet. The employee may EXPLORE the roadmap
   * freely — only ACTING on it waits, because HR can still send the plan back for
   * regeneration and work done against a superseded plan is wasted.
   *
   * This only reflects the truth; the enforcement is server-side (409 from
   * assert_roadmap_released). A disabled button is not a security control.
   */
  pendingReview?: boolean;
  /**
   * [AIQ-2057] Tick a step off. Absent → the plan renders read-only exactly as before,
   * which is what every non-employee surface wants.
   */
  onToggleComplete?: (task: RelocationPlanPhaseTaskDTO) => void;
  /** Optimistic statuses to render instead of the fetched ones, keyed by task_id. */
  statusOverrides?: Record<string, RelocationPlanTaskStatusWire>;
  /** Tasks with a write in flight — their control is disabled and shows a spinner. */
  savingTaskIds?: Set<string>;
}

const TONE_CHIP: Record<RowTone, string> = {
  done: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  progress: 'bg-sky-50 text-sky-700 ring-sky-200',
  ready: 'bg-teal-50 text-teal-700 ring-teal-200',
  wait: 'bg-amber-50 text-amber-700 ring-amber-200',
  muted: 'bg-slate-100 text-slate-500 ring-slate-200',
};

function Chip({ tone, children }: { tone: RowTone; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${TONE_CHIP[tone]}`}>
      {children}
    </span>
  );
}

/**
 * [AIQ-2057] Whose step is this to tick?
 *
 * Only the employee's own work, and only once HR has released the plan. An HR- or
 * provider-owned milestone is somebody else's to close — letting the employee mark it done
 * would put a false completion in front of the person actually responsible for it. And while
 * `pendingReview` holds, the server refuses the write anyway (`assert_roadmap_released` 409s),
 * so offering the control would only manufacture an error.
 */
export function canEmployeeToggle(
  task: RelocationPlanPhaseTaskDTO,
  pendingReview: boolean,
): boolean {
  if (pendingReview) return false;
  return task.owner === 'employee' || task.owner === 'joint';
}

function StatusIcon({ task }: { task: RelocationPlanPhaseTaskDTO }) {
  const { tone } = rowStatus(task);
  const base = 'flex h-6 w-6 shrink-0 items-center justify-center rounded-full';
  if (task.status === 'completed') return <span className={`${base} bg-emerald-100 text-emerald-600`}><Check size={14} /></span>;
  if (tone === 'wait') return <span className={`${base} bg-amber-50 text-amber-500`}><Lock size={13} /></span>;
  if (task.status === 'in_progress') return <span className={`${base} bg-sky-50 text-sky-500`}><Loader2 size={13} /></span>;
  if (tone === 'ready') return <span className={`${base} bg-teal-50 text-teal-500`}><Circle size={13} /></span>;
  return <span className={`${base} bg-slate-100 text-slate-500`}><Clock size={13} /></span>;
}

function OwnerPill({ owner }: { owner: RelocationPlanPhaseTaskDTO['owner'] }) {
  const label = ownerLabel(owner);
  const tone = owner === 'hr' ? 'bg-sky-50 text-sky-700'
    : owner === 'provider' ? 'bg-slate-100 text-slate-600'
    : owner === 'joint' ? 'bg-amber-50 text-amber-700'
    : 'bg-teal-50 text-teal-700';
  return <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${tone}`}>{label}</span>;
}

// ── Hero ─────────────────────────────────────────────────────────────────────

/**
 * AIQ-1548: a small accessible info tooltip (hover, focus, or click to open; Escape or an
 * outside click to close). Reuses the in-repo ConfidenceBadge role="tooltip" pattern rather
 * than adding a dependency — the codebase has no shared design-system Tooltip component.
 */
function InfoTooltip({ label, text }: { label: string; text: string }) {
  const [open, setOpen] = useState(false);
  const tipId = useId();
  const wrapRef = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    const onDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDown);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onDown);
    };
  }, [open]);
  return (
    <span ref={wrapRef} className="relative inline-flex">
      <button
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-describedby={open ? tipId : undefined}
        onClick={() => setOpen((o) => !o)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full text-white/60 transition-colors hover:text-white focus:text-white focus:outline-none"
      >
        <Info size={12} aria-hidden="true" />
      </button>
      {open && (
        <span
          id={tipId}
          role="tooltip"
          className="absolute right-0 top-[calc(100%+6px)] z-20 w-max max-w-[260px] rounded-md bg-slate-900 px-2.5 py-2 text-left text-[11.5px] font-normal normal-case leading-snug text-white shadow-lg ring-1 ring-white/10"
        >
          {text}
        </span>
      )}
    </span>
  );
}

function Hero({ data, header, validated, validatedAt }: { data: RelocationPlanViewResponseDTO; header: RoadmapHeaderMeta | null; validated: boolean; validatedAt: string | null }) {
  // One canonical progress definition (shared with the dashboard / Tasks page).
  const { completed, total, pct, blocked, readyNow } = deriveCanonicalProgress(data.summary);
  const cities = header?.originCity && header?.destCity ? `${header.originCity} to ${header.destCity}` : 'Your relocation';
  const move = header?.targetMoveDate ? new Date(header.targetMoveDate) : null;
  const moveLabel = move ? move.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : null;
  const days = daysUntil(header?.targetMoveDate);
  const arriving = moveLabel ? `arriving ${moveLabel}${days && days > 0 ? ` · ${days} days` : ''}` : null;
  const sub = [header?.employeeName, header?.role, arriving].filter(Boolean).join(' · ');
  const activeIdx = data.phases.findIndex((p) => p.status === 'active');

  return (
    <div className="rounded-2xl bg-gradient-to-br from-[#0b2b43] via-[#103e54] to-[#176f6b] px-6 py-5 text-white shadow-lg">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-widest text-white/60">Your relocation</div>
          <h1 className="mt-1 flex items-center gap-2 text-2xl font-bold">
            {cities}
            {header?.destCountry && <CountryFlag country={getCountryName(header.destCountry)} className="text-base opacity-90" />}
          </h1>
          {sub && <div className="mt-1 text-[13px] text-white/70">{sub}</div>}
          {/* AIQ-1278: validated status surfaced in the hero (moved up from the footer). */}
          {validated && (
            <div className="mt-2 inline-flex items-center gap-1 rounded-full bg-teal-400/20 px-2.5 py-0.5 text-[11.5px] font-medium text-teal-100 ring-1 ring-teal-300/40">
              <Check size={12} /> Roadmap validated{validatedAt ? ` · ${new Date(validatedAt).toLocaleDateString()}` : ''}
            </div>
          )}
        </div>
        <div className="text-right">
          {/* AIQ-1548: label the metric + tooltip its scope, so this task-completion % isn't
              confused with the dossier fields-filled % shown on other pages. */}
          <div className="flex items-center justify-end text-[11px] uppercase tracking-wide text-white/60">
            Overall case progress
            <InfoTooltip
              label="What does overall case progress measure?"
              text="The share of your relocation tasks completed across every phase of your case — it rises as you and your HR team finish tasks, so it starts at 0%. Other pages (like your Dossier) may show a different number that tracks how much of your intake forms you've filled in."
            />
          </div>
          <div className="text-3xl font-bold leading-none">{pct}%</div>
          <div className="mt-0.5 text-[12px] text-white/70">{completed} of {total} tasks done</div>
          {blocked > 0 && (
            <div className="mt-0.5 text-[12px] text-white/70">
              {readyNow} ready now · {blocked} waiting on earlier steps
            </div>
          )}
        </div>
      </div>

      {/* mini phase-timeline */}
      <div className="mt-5">
        <div className="flex items-end justify-between">
          {data.phases.map((p, i) => {
            const Icon = phaseIcon(p.phase_key);
            const isDone = p.status === 'completed';
            const isActive = p.status === 'active';
            const reached = isDone || isActive || i < activeIdx;
            return (
              <div key={p.phase_key} className="flex flex-1 flex-col items-center text-center">
                <span
                  className={`flex h-9 w-9 items-center justify-center rounded-full ring-2 ${
                    isActive ? 'bg-white text-[#0b2b43] ring-white'
                    : reached ? 'bg-teal-400/90 text-white ring-teal-300'
                    : 'bg-white/10 text-white/50 ring-white/20'
                  }`}
                >
                  <Icon size={16} />
                </span>
                <div className={`mt-2 text-[11.5px] font-medium ${reached ? 'text-white' : 'text-white/50'}`}>{p.title}</div>
                <div className="text-[10.5px] text-white/50">
                  {p.task_counts.completed}/{p.task_counts.total}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── "What you can do now" ────────────────────────────────────────────────────

function ActionCard({ task, onCta }: { task: RelocationPlanPhaseTaskDTO; onCta: (t: RelocationPlanPhaseTaskDTO) => void }) {
  return (
    <div className="flex flex-1 flex-col rounded-xl border border-slate-200 bg-white p-3.5">
      <div className="mb-2 flex items-center gap-2">
        <span title={task.due_date_is_suggested ? 'Auto-estimated from your move date' : undefined}>
          <Chip tone={task.is_overdue ? 'wait' : 'ready'}>{formatDue(task)}</Chip>
        </span>
        {task.priority === 'critical' && <Flag size={13} className="text-rose-500" />}
      </div>
      <div className="text-[14.5px] font-semibold text-[#0b2b43]">{task.title}</div>
      <div className="mt-2 flex items-center gap-2 text-[12px] text-slate-500">
        <OwnerPill owner={task.owner} />
        {task.estimated_effort && <span>· {task.estimated_effort}</span>}
      </div>
      <button
        type="button"
        onClick={() => onCta(task)}
        className="mt-3 inline-flex items-center justify-center gap-1.5 rounded-lg bg-[#0b2b43] px-3 py-2 text-[13px] font-semibold text-white hover:bg-[#103e54]"
      >
        {task.status === 'in_progress' ? 'Continue' : 'Start now'} <ArrowRight size={14} />
      </button>
    </div>
  );
}

// ── Phase section + rows ─────────────────────────────────────────────────────

/** [AIQ-806] Collapsible "Show source" disclosure for a confident, sourced task. */
function SourceDisclosure({ confidence }: { confidence: StepConfidence }) {
  const [open, setOpen] = useState(false);
  if (!confidence.sourceUrl) return null;
  return (
    <div className="mt-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-[11.5px] font-medium text-teal-700 hover:underline"
        aria-expanded={open}
      >
        {open ? 'Hide source' : 'Show source'}
      </button>
      {open && (
        <div className="mt-1 rounded-lg bg-slate-50 px-2.5 py-2 text-[11.5px] text-slate-600">
          <a
            href={confidence.sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-medium text-teal-700 hover:underline"
          >
            <ExternalLink size={11} /> Official source
          </a>
          {confidence.sourceFetchedAt && (
            <span className="ml-2 text-slate-500">
              Verified {new Date(confidence.sourceFetchedAt).toLocaleDateString()}
            </span>
          )}
          {confidence.sourceExcerpt && <p className="mt-1 text-slate-500">{confidence.sourceExcerpt}</p>}
        </div>
      )}
    </div>
  );
}

function TaskRow({
  task, titles, onCta, confidence, onToggleComplete, saving, pendingReview,
}: {
  task: RelocationPlanPhaseTaskDTO;
  titles: Record<string, string>;
  onCta: (t: RelocationPlanPhaseTaskDTO) => void;
  confidence?: StepConfidence;
  onToggleComplete?: (t: RelocationPlanPhaseTaskDTO) => void;
  saving?: boolean;
  pendingReview?: boolean;
}) {
  const st = rowStatus(task);
  const blocked = resolveBlockedBy(task, titles);
  const docs = docCount(task);
  const done = task.status === 'completed';
  const actionable = st.tone === 'ready' || (st.tone === 'progress' && (task.owner === 'employee' || task.owner === 'joint'));
  const tickable = Boolean(onToggleComplete) && canEmployeeToggle(task, Boolean(pendingReview));

  return (
    <div className={`flex items-start gap-3 border-l-2 py-3 pl-3 ${actionable ? 'border-teal-400' : 'border-transparent'}`}>
      {tickable ? (
        <button
          type="button"
          onClick={() => onToggleComplete?.(task)}
          disabled={saving}
          aria-pressed={done}
          aria-label={done ? `Mark “${task.title}” as not done` : `Mark “${task.title}” as done`}
          title={done ? 'Mark as not done' : 'Mark as done'}
          className="shrink-0 rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-1 disabled:opacity-60"
        >
          <StatusIcon task={task} />
        </button>
      ) : (
        <StatusIcon task={task} />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className={`text-[14px] font-semibold ${done ? 'text-slate-500 line-through' : 'text-[#0b2b43]'}`}>
            {task.title}
          </span>
          {confidence && <ConfidenceBadge level={resolveConfidenceLevel(confidence)} size="sm" />}
          {task.priority === 'critical' && !done && (
            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-rose-500"><Flag size={11} /> Critical</span>
          )}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-slate-500">
          <OwnerPill owner={task.owner} />
          {task.estimated_effort && <span>{task.estimated_effort}</span>}
          {docs && (
            <span className="inline-flex items-center gap-1"><FileText size={12} /> {docs.present} of {docs.total} docs</span>
          )}
          {blocked && (
            <span className="inline-flex items-center gap-1 text-amber-600"><Lock size={11} /> Waiting on: {blocked}</span>
          )}
        </div>
        {confidence && <SourceDisclosure confidence={confidence} />}
      </div>
      <div className="shrink-0 text-right">
        <Chip tone={st.tone}>{st.label}</Chip>
        <div
          className={`mt-1 text-[11.5px] text-slate-500${task.due_date_is_suggested ? ' italic' : ''}`}
          title={task.due_date_is_suggested ? 'Auto-estimated from your move date' : undefined}
        >
          {formatDue(task)}
        </div>
        {actionable && (
          <button
            type="button"
            onClick={() => onCta(task)}
            className="mt-1.5 text-[12px] font-semibold text-teal-700 hover:underline"
          >
            {task.status === 'in_progress' ? 'Continue' : 'Start'} →
          </button>
        )}
      </div>
    </div>
  );
}

function PhaseSection({
  phase, titles, onCta, defaultOpen, confidenceByTitle, onToggleComplete, savingTaskIds, pendingReview,
}: {
  phase: RelocationPlanPhaseDTO;
  titles: Record<string, string>;
  onCta: (t: RelocationPlanPhaseTaskDTO) => void;
  defaultOpen: boolean;
  confidenceByTitle?: ConfidenceByTitle;
  onToggleComplete?: (t: RelocationPlanPhaseTaskDTO) => void;
  savingTaskIds?: Set<string>;
  pendingReview?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const pct = Math.round((phase.completion_ratio ?? 0) * 100);
  const Icon = phaseIcon(phase.phase_key);
  const active = phase.status === 'active';

  return (
    <div className="rounded-2xl border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left"
        aria-expanded={open}
      >
        <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${active ? 'bg-teal-600 text-white' : 'bg-[#0b2b43] text-white'}`}>
          <Icon size={17} />
        </span>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-[15.5px] font-bold text-[#0b2b43]">{phase.title}</h3>
            <span className="text-[12px] text-slate-500">{phase.task_counts.completed} of {phase.task_counts.total} done</span>
          </div>
          <div className="mt-1.5 flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-teal-500" style={{ width: `${pct}%` }} />
            </div>
            <span className="text-[11.5px] font-medium text-slate-500">{pct}%</span>
          </div>
        </div>
        {open ? <ChevronUp size={18} className="text-slate-500" /> : <ChevronDown size={18} className="text-slate-500" />}
      </button>
      {open && (
        <div className="px-4 pb-3">
          {phase.tasks.map((t) => (
            <TaskRow
              key={t.task_id}
              task={t}
              titles={titles}
              onCta={onCta}
              confidence={confidenceByTitle?.[normalizeStepTitle(t.title)]}
              onToggleComplete={onToggleComplete}
              saving={savingTaskIds?.has(t.task_id)}
              pendingReview={pendingReview}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Root ─────────────────────────────────────────────────────────────────────

/**
 * [AIQ-2057] Overlay optimistic statuses on a fetched plan, recomputing the derived counts.
 *
 * Returns the SAME object when there is nothing to override, so the memo chain downstream
 * (`titlesByCode`, `actionableTasks`, …) keeps its identity and nothing re-renders for a
 * read-only surface that never passes overrides at all.
 */
export function applyStatusOverrides(
  view: RelocationPlanViewResponseDTO,
  overrides: Record<string, RelocationPlanTaskStatusWire> | undefined,
): RelocationPlanViewResponseDTO {
  if (!overrides || Object.keys(overrides).length === 0) return view;

  let touched = false;
  const phases = view.phases.map((phase) => {
    const tasks = phase.tasks.map((t) => {
      const next = overrides[t.task_id];
      if (!next || next === t.status) return t;
      touched = true;
      return { ...t, status: next };
    });
    if (tasks === phase.tasks) return phase;
    const completed = tasks.filter((t) => t.status === 'completed').length;
    const total = tasks.length;
    return {
      ...phase,
      tasks,
      task_counts: { ...phase.task_counts, completed, total },
      completion_ratio: total > 0 ? completed / total : phase.completion_ratio,
    };
  });
  if (!touched) return view;

  const all = phases.flatMap((p) => p.tasks);
  const completedTasks = all.filter((t) => t.status === 'completed').length;
  const blockedTasks = all.filter((t) => t.status === 'blocked').length;
  return {
    ...view,
    phases,
    summary: {
      ...view.summary,
      completed_tasks: completedTasks,
      total_tasks: all.length,
      blocked_tasks: blockedTasks,
      // `deriveCanonicalProgress` reads the RATIO for the headline percentage and the COUNT
      // for the "x of y done" line beside it. Updating one and not the other puts two
      // disagreeing numbers in the same hero.
      completion_ratio: all.length > 0 ? completedTasks / all.length : view.summary.completion_ratio,
    },
  };
}


export const RoadmapTemplate: React.FC<RoadmapTemplateProps> = ({
  data: fetched, header, caseId, onCta, validated, validatedAt, validating, onValidate, confidenceByTitle,
  pendingReview = false,
  onToggleComplete, statusOverrides, savingTaskIds,
}) => {
  // [AIQ-2057] Apply the optimistic ticks over the fetched plan, so the whole view — row
  // status, phase counters, the hero percentage — moves together the moment the employee
  // clicks. Recomputing the counters here rather than only restyling the row is what stops
  // "3 of 8 done" disagreeing with the ticks directly beneath it.
  const data = useMemo(
    () => applyStatusOverrides(fetched, statusOverrides),
    [fetched, statusOverrides],
  );
  const titles = useMemo(() => titlesByCode(data.phases), [data.phases]);
  const actionable = useMemo(() => actionableTasks(data.phases, 3), [data.phases]);
  const hrHandled = useMemo(() => hrHandledTasks(data.phases), [data.phases]);
  const activeIdx = data.phases.findIndex((p) => p.status === 'active');

  return (
    <div className="space-y-4">
      <Hero data={data} header={header} validated={validated} validatedAt={validatedAt} />

      {/* [AIQ-1606] "Under HR review" is a non-blocking, informational tag. HR is reviewing
          the plan in parallel, but the employee is never blocked — they can start any task
          right away. Say that plainly so the banner reassures rather than gates. */}
      {pendingReview && (
        <div
          role="status"
          className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4"
        >
          <Clock size={18} className="mt-0.5 flex-none text-amber-600" aria-hidden="true" />
          <div>
            <div className="text-[14px] font-semibold text-[#0b2b43]">
              Your HR team is reviewing this plan
            </div>
            <div className="mt-0.5 text-[12.5px] leading-relaxed text-slate-600">
              You don&rsquo;t need to wait — start any task below whenever you&rsquo;re ready.
              HR is reviewing in the background and will confirm your plan shortly.
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 text-[13px] font-semibold">
          <span className="rounded-md bg-[#0b2b43] px-3 py-1.5 text-white">Checklist</span>
          <span className="px-3 py-1.5 text-slate-500" title="Coming soon">Timeline</span>
        </div>
        <RoadmapActions caseId={caseId} />
      </div>

      {/* What you can do now */}
      {actionable.length > 0 && (
        <div className="rounded-2xl border border-teal-100 bg-teal-50/40 p-4">
          <div className="mb-3 flex items-center gap-2">
            <Sparkles size={16} className="text-teal-600" />
            <h2 className="text-[15px] font-bold text-[#0b2b43]">What you can do now</h2>
            <span className="rounded-full bg-teal-100 px-2 py-0.5 text-[11px] font-semibold text-teal-700">{actionable.length} ready</span>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            {actionable.map((t) => (
              <ActionCard key={t.task_id} task={t} onCta={onCta} />
            ))}
          </div>
        </div>
      )}

      {/* HR & partners handling */}
      {hrHandled.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3">
          <div className="flex items-start gap-3">
            <Clock size={16} className="mt-0.5 text-slate-500" />
            <div>
              <div className="text-[13.5px] font-semibold text-[#0b2b43]">
                HR &amp; partners are handling {hrHandled.length} step{hrHandled.length === 1 ? '' : 's'} for you
              </div>
              <div className="text-[12px] text-slate-500">{hrHandled.map((t) => t.title).join(' · ')}</div>
            </div>
          </div>
          <span className="text-[12px] font-semibold text-teal-700">Nothing needed from you</span>
        </div>
      )}

      {/* Phases */}
      <div className="space-y-3">
        {data.phases.map((p, i) => (
          <PhaseSection
            key={p.phase_key}
            phase={p}
            titles={titles}
            onCta={onCta}
            defaultOpen={p.status === 'active' || (activeIdx === -1 && i === 0)}
            confidenceByTitle={confidenceByTitle}
            onToggleComplete={onToggleComplete}
            savingTaskIds={savingTaskIds}
            pendingReview={pendingReview}
          />
        ))}
      </div>

      {/* Validate footer — validated status now shown in the hero (AIQ-1278).
          [AIQ-1606] Shown even while HR is reviewing: the review tag is non-blocking, so the
          employee can validate & start whenever they're ready. The banner (top) explains the
          parallel HR review. */}
      {!validated && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-4">
          <div>
            <div className="text-[14px] font-semibold text-[#0b2b43]">Ready to begin?</div>
            <div className="text-[12.5px] text-slate-500">Confirm your plan to start tasks and lock in deadlines. You can still adjust later.</div>
          </div>
          <button
            type="button"
            onClick={onValidate}
            disabled={validating}
            className="inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2.5 text-[14px] font-semibold text-white hover:bg-teal-700 disabled:opacity-60"
          >
            <Check size={16} /> {validating ? 'Validating…' : 'Validate & start tasks'}
          </button>
        </div>
      )}
    </div>
  );
};
