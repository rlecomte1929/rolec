/**
 * Redesigned employee roadmap — renders the plan-view (milestone-backed) journey
 * in the approved template: dark hero + mini phase-timeline, "what you can do now",
 * an HR/partner-handled banner, and collapsible phase sections with rich rows.
 * Pure presentation; data + handlers are passed in by EmployeeCaseRoadmapPage.
 */
import React, { useMemo, useState } from 'react';
import {
  Check, Circle, Lock, Loader2, Sparkles, Flag, FileText, ChevronUp, ChevronDown,
  Clock, ArrowRight, ExternalLink,
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

function StatusIcon({ task }: { task: RelocationPlanPhaseTaskDTO }) {
  const { tone } = rowStatus(task);
  const base = 'flex h-6 w-6 shrink-0 items-center justify-center rounded-full';
  if (task.status === 'completed') return <span className={`${base} bg-emerald-100 text-emerald-600`}><Check size={14} /></span>;
  if (tone === 'wait') return <span className={`${base} bg-amber-50 text-amber-500`}><Lock size={13} /></span>;
  if (task.status === 'in_progress') return <span className={`${base} bg-sky-50 text-sky-500`}><Loader2 size={13} /></span>;
  if (tone === 'ready') return <span className={`${base} bg-teal-50 text-teal-500`}><Circle size={13} /></span>;
  return <span className={`${base} bg-slate-100 text-slate-400`}><Clock size={13} /></span>;
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
          <div className="text-[11px] uppercase tracking-wide text-white/60">Overall progress</div>
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
            <span className="ml-2 text-slate-400">
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
  task, titles, onCta, confidence,
}: { task: RelocationPlanPhaseTaskDTO; titles: Record<string, string>; onCta: (t: RelocationPlanPhaseTaskDTO) => void; confidence?: StepConfidence }) {
  const st = rowStatus(task);
  const blocked = resolveBlockedBy(task, titles);
  const docs = docCount(task);
  const done = task.status === 'completed';
  const actionable = st.tone === 'ready' || (st.tone === 'progress' && (task.owner === 'employee' || task.owner === 'joint'));

  return (
    <div className={`flex items-start gap-3 border-l-2 py-3 pl-3 ${actionable ? 'border-teal-400' : 'border-transparent'}`}>
      <StatusIcon task={task} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className={`text-[14px] font-semibold ${done ? 'text-slate-400 line-through' : 'text-[#0b2b43]'}`}>
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
          className={`mt-1 text-[11.5px] text-slate-400${task.due_date_is_suggested ? ' italic' : ''}`}
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
  phase, titles, onCta, defaultOpen, confidenceByTitle,
}: { phase: RelocationPlanPhaseDTO; titles: Record<string, string>; onCta: (t: RelocationPlanPhaseTaskDTO) => void; defaultOpen: boolean; confidenceByTitle?: ConfidenceByTitle }) {
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
            <span className="text-[12px] text-slate-400">{phase.task_counts.completed} of {phase.task_counts.total} done</span>
          </div>
          <div className="mt-1.5 flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-teal-500" style={{ width: `${pct}%` }} />
            </div>
            <span className="text-[11.5px] font-medium text-slate-500">{pct}%</span>
          </div>
        </div>
        {open ? <ChevronUp size={18} className="text-slate-400" /> : <ChevronDown size={18} className="text-slate-400" />}
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
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Root ─────────────────────────────────────────────────────────────────────

export const RoadmapTemplate: React.FC<RoadmapTemplateProps> = ({
  data, header, caseId, onCta, validated, validatedAt, validating, onValidate, confidenceByTitle,
}) => {
  const titles = useMemo(() => titlesByCode(data.phases), [data.phases]);
  const actionable = useMemo(() => actionableTasks(data.phases, 3), [data.phases]);
  const hrHandled = useMemo(() => hrHandledTasks(data.phases), [data.phases]);
  const activeIdx = data.phases.findIndex((p) => p.status === 'active');

  return (
    <div className="space-y-4">
      <Hero data={data} header={header} validated={validated} validatedAt={validatedAt} />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 text-[13px] font-semibold">
          <span className="rounded-md bg-[#0b2b43] px-3 py-1.5 text-white">Checklist</span>
          <span className="px-3 py-1.5 text-slate-400" title="Coming soon">Timeline</span>
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
            <Clock size={16} className="mt-0.5 text-slate-400" />
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
          />
        ))}
      </div>

      {/* Validate footer — validated status now shown in the hero (AIQ-1278). */}
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
