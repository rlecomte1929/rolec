import React, { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Circle,
  CircleDot,
} from 'lucide-react';
import { Button } from '../../../components/antigravity';
import type { RelocationPlanPhaseTaskDTO } from '../../../types/relocationPlanView';
import { ownerLabel, taskStatusLabel } from '../../relocation-plan-employee/relocationPlanLabels';
import {
  relocationTaskCtaDefaultButtonLabel,
  resolveRelocationTaskCtaTarget,
  type RelocationPlanCtaNavigateContext,
} from './relocationTaskCtaMap';
import { isRelocationTaskBlocked, relocationTaskBlockerExplanation } from './taskBlockerCopy';

function formatDue(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = iso.slice(0, 10);
  return d || null;
}

function TaskStatusIcon({
  status,
  isBlockedRow,
}: {
  status: RelocationPlanPhaseTaskDTO['status'];
  isBlockedRow: boolean;
}) {
  const iconClass = 'size-5 shrink-0';
  if (status === 'completed' || status === 'not_applicable') {
    return (
      <CheckCircle2
        className={`${iconClass} text-[#1f8e8b]`}
        aria-hidden
        strokeWidth={2}
      />
    );
  }
  if (status === 'blocked' || isBlockedRow) {
    return (
      <AlertTriangle
        className={`${iconClass} text-amber-600`}
        aria-hidden
        strokeWidth={2}
      />
    );
  }
  if (status === 'in_progress') {
    return (
      <CircleDot className={`${iconClass} text-[#0b2b43]`} aria-hidden strokeWidth={2} />
    );
  }
  return <Circle className={`${iconClass} text-[#cbd5e1]`} aria-hidden strokeWidth={2} />;
}

function cardSurfaceClass(task: RelocationPlanPhaseTaskDTO, highlightSuggested: boolean | undefined): string {
  const done = task.status === 'completed' || task.status === 'not_applicable';
  const blocked = isRelocationTaskBlocked(task);
  let border = 'border-[#e2e8f0]';
  if (highlightSuggested && !done) {
    border = 'border-[#0b2b43]/40 ring-1 ring-[#0b2b43]/10';
  } else if (blocked) {
    border = 'border-amber-200/90';
  } else if (done) {
    border = 'border-[#e2e8f0] bg-[#fafcfb]';
  }
  return `rounded-xl border ${border} bg-white overflow-hidden transition-[border-color,box-shadow,background-color] duration-200`;
}

export interface RelocationTaskCardNotesProps {
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  disabled?: boolean;
}

export interface RelocationTaskCardProps {
  task: RelocationPlanPhaseTaskDTO;
  ctaContext: RelocationPlanCtaNavigateContext;
  highlightSuggested?: boolean;
  onCta: (cta: RelocationPlanPhaseTaskDTO['cta']) => void;
  notes?: RelocationTaskCardNotesProps | null;
}

/**
 * Phased plan task row: compact summary, inline expand for details and a single primary CTA.
 */
export const RelocationTaskCard: React.FC<RelocationTaskCardProps> = ({
  task,
  ctaContext,
  highlightSuggested,
  onCta,
  notes,
}) => {
  const [expanded, setExpanded] = useState(false);
  const prevStatusRef = useRef(task.status);

  const due = formatDue(task.due_date);
  const target = resolveRelocationTaskCtaTarget(ctaContext, task.cta);
  const primaryLabel = relocationTaskCtaDefaultButtonLabel(task.cta, target);
  const isBlockedRow = isRelocationTaskBlocked(task);
  const done = task.status === 'completed' || task.status === 'not_applicable';
  const showNotesUi = Boolean(task.notes_enabled && notes);
  const blockerExplanation = relocationTaskBlockerExplanation(task);

  const showPrimaryCta = !done && !isBlockedRow;

  useEffect(() => {
    const prev = prevStatusRef.current;
    const wasIncomplete = prev !== 'completed' && prev !== 'not_applicable';
    const nowDone = task.status === 'completed' || task.status === 'not_applicable';
    if (wasIncomplete && nowDone && expanded) {
      const id = window.setTimeout(() => setExpanded(false), 1000);
      prevStatusRef.current = task.status;
      return () => window.clearTimeout(id);
    }
    prevStatusRef.current = task.status;
  }, [task.status, expanded]);

  const hasDetailSections =
    Boolean(task.why_this_matters) ||
    Boolean(task.instructions?.length) ||
    Boolean(task.required_inputs?.length) ||
    Boolean(blockerExplanation) ||
    showNotesUi;

  const showExpandedFooter = showPrimaryCta || (!done && isBlockedRow);
  const showExpandedShell = expanded && (hasDetailSections || showExpandedFooter || done);

  const ownerText = ownerLabel(task.owner);

  return (
    <div className={cardSurfaceClass(task, highlightSuggested)}>
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
        aria-label={`${task.title}. ${taskStatusLabel(task.status)}${ownerText ? `. ${ownerText}` : ''}${
          due
            ? `. ${
                task.is_overdue && !done
                  ? `Overdue ${due}`
                  : task.is_due_soon && !done
                    ? `Due soon ${due}`
                    : `Due ${due}`
              }`
            : ''
        }. ${expanded ? 'Collapse details' : 'Expand details'}`}
        className={`w-full text-left px-4 py-3.5 min-h-[56px] flex gap-3 items-start transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0b2b43] focus-visible:ring-inset ${
          done
            ? 'opacity-[0.92] hover:bg-[#fafcfb]'
            : 'hover:bg-[#fafbfc]/90'
        }`}
      >
        <span className="pt-0.5" aria-hidden>
          <TaskStatusIcon status={task.status} isBlockedRow={isBlockedRow} />
        </span>
        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span
              className={`font-medium text-base leading-snug ${
                done ? 'text-[#64748b] line-through decoration-[#94a3b8]' : 'text-[#0b2b43]'
              }`}
            >
              {task.title}
            </span>
            {task.priority === 'critical' && !done ? (
              <span className="text-[11px] font-medium text-[#0b2b43]/80 bg-[#f1f5f9] border border-[#e2e8f0] px-2 py-0.5 rounded-full">
                Priority
              </span>
            ) : null}
          </div>
          <p className="text-xs text-[#64748b] flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5">
            <span>{ownerText}</span>
            {due ? (
              <>
                <span className="text-[#cbd5e1]" aria-hidden>
                  ·
                </span>
                <span
                  className={
                    task.is_overdue && !done
                      ? 'text-red-700 font-medium'
                      : task.is_due_soon && !done
                        ? 'text-amber-800 font-medium'
                        : undefined
                  }
                >
                  {task.is_overdue && !done
                    ? `Overdue · ${due}`
                    : task.is_due_soon && !done
                      ? `Due soon · ${due}`
                      : `Due ${due}`}
                </span>
              </>
            ) : null}
          </p>
          {isBlockedRow && blockerExplanation ? (
            <p className="text-xs text-amber-900/90 leading-snug line-clamp-2 pr-1">{blockerExplanation}</p>
          ) : null}
        </div>
        <span className="text-xs text-[#94a3b8] shrink-0 pt-1" aria-hidden>
          {expanded ? 'Hide' : 'Details'}
        </span>
      </button>

      {showExpandedShell ? (
        <div className="px-4 pb-4 pt-0 border-t border-[#f1f5f9] bg-[#fafbfc]/70">
          {task.why_this_matters ? (
            <div className="mt-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-[#94a3b8]">Why this matters</p>
              <p className="text-sm text-[#475569] mt-1 leading-relaxed">{task.why_this_matters}</p>
            </div>
          ) : null}

          {task.instructions?.length ? (
            <div className="mt-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-[#94a3b8]">Steps</p>
              <ul className="mt-1.5 text-sm text-[#475569] list-disc pl-5 space-y-1">
                {task.instructions.map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {task.required_inputs?.length ? (
            <div className="mt-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-[#94a3b8]">Required</p>
              <ul className="mt-1.5 text-xs text-[#64748b] space-y-1">
                {task.required_inputs.map((ri) => (
                  <li key={ri.key} className="flex gap-2">
                    <span className={ri.present ? 'text-[#1f8e8b]' : 'text-[#cbd5e1]'} aria-hidden>
                      {ri.present ? '✓' : '○'}
                    </span>
                    <span>{ri.label}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {blockerExplanation ? (
            <p className="mt-3 text-xs text-[#92400e] bg-amber-50/80 border border-amber-100 rounded-lg px-3 py-2 flex gap-2 items-start">
              <Ban className="size-3.5 shrink-0 mt-0.5 text-amber-700" aria-hidden />
              <span>{blockerExplanation}</span>
            </p>
          ) : null}

          {showNotesUi && notes ? (
            <label className="block mt-3 text-sm">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-[#94a3b8]">Notes</span>
              <textarea
                className="mt-1.5 w-full min-h-[72px] rounded-lg border border-[#e2e8f0] px-2 py-1.5 text-sm text-[#334155] bg-white"
                value={notes.value}
                onChange={(e) => notes.onChange(e.target.value)}
                onBlur={notes.onBlur}
                disabled={notes.disabled}
                placeholder="Short context for you or HR…"
              />
            </label>
          ) : null}

          {showPrimaryCta ? (
            <Button
              variant="primary"
              size="md"
              fullWidth
              className="mt-4 min-h-[48px] transition-opacity duration-200"
              onClick={() => onCta(task.cta)}
            >
              {primaryLabel}
            </Button>
          ) : !done && isBlockedRow ? (
            <p className="mt-4 text-xs text-[#64748b]">
              This step can&apos;t be completed here until the blockers above are cleared.
            </p>
          ) : null}

          {done && !hasDetailSections && !showExpandedFooter ? (
            <p className="mt-3 text-xs text-[#94a3b8]">This step is complete.</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
};
