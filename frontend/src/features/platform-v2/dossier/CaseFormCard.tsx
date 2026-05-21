/**
 * [P1-5] CaseFormCard — single row in the Dossier & Forms list.
 *
 * Collapsed by default. Clicking the header expands to reveal the status
 * banner + action buttons.
 *
 * Visual style uses antigravity primitives for consistency with the rest of
 * the new Phase 1 admin/employee surfaces.
 */
import React, { useState } from 'react';
import { Badge, Card } from '../../../components/antigravity';
import type { CaseFormStatus, CaseFormSummary } from '../../../api/dossier';

// ---------------------------------------------------------------------------
// Status → label + colour + banner copy
//
// `blocked` is NOT a value in the document_status enum (P1-1). It's a UI-only
// state derived from `blocker_form_id` being set on a form that hasn't been
// submitted/approved yet. `displayStatus()` produces the union type below.
// ---------------------------------------------------------------------------

type DisplayStatus = CaseFormStatus | 'blocked';

function displayStatus(form: CaseFormSummary): DisplayStatus {
  if (
    form.blocker_form_id &&
    form.status !== 'submitted' &&
    form.status !== 'approved' &&
    form.status !== 'rejected'
  ) {
    return 'blocked';
  }
  return form.status;
}

const STATUS_LABEL: Record<DisplayStatus, string> = {
  not_started: 'Not started',
  auto_filled: 'Action needed',
  in_progress: 'In progress',
  pending_doc: 'Waiting on doc',
  ready: 'Ready to submit',
  blocked: 'Blocked',
  submitted: 'Submitted',
  approved: 'Approved',
  rejected: 'Rejected',
};

// antigravity `Badge` variant: 'success' | 'warning' | 'error' | 'info' | 'neutral'
const STATUS_BADGE_VARIANT: Record<DisplayStatus, 'success' | 'warning' | 'error' | 'info' | 'neutral'> = {
  not_started: 'neutral',
  auto_filled: 'warning',
  in_progress: 'info',
  pending_doc: 'neutral',
  ready: 'success',
  blocked: 'error',
  submitted: 'info',
  approved: 'success',
  rejected: 'error',
};

function statusBannerCopy(form: CaseFormSummary): { tone: string; text: string } {
  const { fields_summary, blocker_form_code, deadline_trigger } = form;
  const status = displayStatus(form);
  const aiFilled = fields_summary.filled_by_ai;
  const missing = fields_summary.missing_required;

  switch (status) {
    case 'auto_filled':
      return {
        tone: 'bg-amber-50 border-amber-200 text-amber-900',
        text:
          aiFilled > 0
            ? `Ready for your review — ${aiFilled} field${aiFilled === 1 ? '' : 's'} pre-filled, ${missing} need${missing === 1 ? 's' : ''} your input.`
            : 'Action needed — review and complete the remaining fields.',
      };
    case 'pending_doc':
      return {
        tone: 'bg-orange-50 border-orange-200 text-orange-900',
        text: 'Waiting on a document upload before this form can be completed.',
      };
    case 'blocked':
      return {
        tone: 'bg-rose-50 border-rose-200 text-rose-900',
        text: blocker_form_code
          ? `Blocked — needs ${blocker_form_code} to be submitted first.`
          : 'Blocked — needs another form completed first.',
      };
    case 'ready':
      return {
        tone: 'bg-emerald-50 border-emerald-200 text-emerald-900',
        text: deadline_trigger
          ? `Pre-filled · ready once you ${humaniseTrigger(deadline_trigger)}.`
          : 'Pre-filled · ready to submit.',
      };
    case 'in_progress':
      return {
        tone: 'bg-blue-50 border-blue-200 text-blue-900',
        text: `In progress — ${form.completion_pct}% complete.`,
      };
    case 'submitted':
      return {
        tone: 'bg-blue-50 border-blue-200 text-blue-900',
        text: form.receipt_ref
          ? `Submitted · receipt ${form.receipt_ref}.`
          : 'Submitted — awaiting authority response.',
      };
    case 'approved':
      return {
        tone: 'bg-emerald-50 border-emerald-200 text-emerald-900',
        text: 'Approved by the authority.',
      };
    case 'rejected':
      return {
        tone: 'bg-rose-50 border-rose-200 text-rose-900',
        text: 'Rejected — check the response for required changes.',
      };
    case 'not_started':
    default:
      return {
        tone: 'bg-slate-50 border-slate-200 text-slate-700',
        text: 'Not started.',
      };
  }
}

function humaniseTrigger(trigger: string): string {
  // 'within_7_days_of_arrival' → 'arrive in Norway'
  // 'after_d_number_approved' → 'have your D-number'
  // Fallback: the raw symbol
  return trigger.replace(/_/g, ' ');
}

function personLabel(form: CaseFormSummary): string {
  const { kind, name } = form.person;
  const displayName = name && name.trim() ? name : kindFallback(kind);
  return kind === 'employee' ? displayName : `${capitalise(kind)} · ${displayName}`;
}

function kindFallback(kind: string): string {
  return kind === 'employee' ? 'Employee' : (capitalise(kind) || 'Family member');
}

function capitalise(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

function deadlineChip(deadline: string | null): { tone: string; text: string } | null {
  if (!deadline) return null;
  const due = new Date(deadline);
  if (Number.isNaN(due.getTime())) return null;
  const now = new Date();
  const diffDays = Math.ceil((due.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
  const label = due.toLocaleDateString();
  if (diffDays < 0) {
    return { tone: 'bg-rose-100 text-rose-700 border-rose-200', text: `Overdue · ${label}` };
  }
  if (diffDays <= 7) {
    return { tone: 'bg-amber-100 text-amber-700 border-amber-200', text: `${diffDays}d · ${label}` };
  }
  return { tone: 'bg-slate-100 text-slate-600 border-slate-200', text: label };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface CaseFormCardProps {
  form: CaseFormSummary;
}

export const CaseFormCard: React.FC<CaseFormCardProps> = ({ form }) => {
  const [expanded, setExpanded] = useState(false);

  const banner = statusBannerCopy(form);
  const chip = deadlineChip(form.deadline);
  const dStatus = displayStatus(form);
  const totalFields = form.fields_summary.total;
  const filledFields =
    form.fields_summary.filled_by_ai + form.fields_summary.filled_by_human;
  const progressPct =
    totalFields > 0 ? Math.round((filledFields / totalFields) * 100) : form.completion_pct;

  return (
    <Card padding="lg" className="hover:shadow-sm transition-shadow">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="w-full text-left grid grid-cols-12 items-center gap-3"
      >
        {/* Left: code badge + name + person */}
        <div className="col-span-5 flex items-start gap-2 min-w-0">
          <span className="shrink-0 inline-flex items-center px-2 py-0.5 rounded font-mono text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            {form.template.code}
          </span>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-slate-900 truncate">{form.template.name}</div>
            <div className="text-xs text-slate-500 truncate">
              {personLabel(form)}
              {form.template.authority_code && ` · ${form.template.authority_code}`}
            </div>
          </div>
        </div>

        {/* Middle: progress bar + counts */}
        <div className="col-span-4">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-slate-500">
              {filledFields} of {totalFields} field{totalFields === 1 ? '' : 's'}
              {form.fields_summary.missing_required > 0 &&
                ` · ${form.fields_summary.missing_required} need${form.fields_summary.missing_required === 1 ? 's' : ''} input`}
            </span>
            <span className="text-xs font-medium text-slate-700">{progressPct}%</span>
          </div>
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                dStatus === 'blocked'
                  ? 'bg-rose-400'
                  : dStatus === 'ready' || dStatus === 'approved'
                    ? 'bg-emerald-500'
                    : 'bg-blue-500'
              }`}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>

        {/* Right: status badge + deadline chip + chevron */}
        <div className="col-span-3 flex items-center justify-end gap-2">
          {chip && (
            <span className={`hidden md:inline-flex items-center px-2 py-0.5 rounded border text-[11px] font-medium ${chip.tone}`}>
              {chip.text}
            </span>
          )}
          <Badge variant={STATUS_BADGE_VARIANT[dStatus]}>{STATUS_LABEL[dStatus]}</Badge>
          <svg
            className={`w-4 h-4 text-slate-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {expanded && (
        <div className="mt-4 grid gap-3">
          <div className={`rounded border px-3 py-2 text-sm ${banner.tone}`}>{banner.text}</div>
          <div className="flex items-center gap-3 flex-wrap">
            <button
              type="button"
              disabled
              title="Form editor lands in P2-3 — coming soon"
              className="px-3 py-1.5 rounded text-sm font-medium bg-[#0b2b43] text-white opacity-50 cursor-not-allowed"
            >
              Open form
            </button>
            {form.template.id && form.original_file_url && (
              <a
                href={form.original_file_url}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-[#0b2b43] hover:underline"
              >
                View original PDF
              </a>
            )}
            <span className="text-xs text-slate-400 ml-auto">
              v{form.template.version} · updated{' '}
              {form.updated_at ? new Date(form.updated_at).toLocaleDateString() : '—'}
            </span>
          </div>
        </div>
      )}
    </Card>
  );
};
