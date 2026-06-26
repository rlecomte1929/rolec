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
import { useNavigate } from 'react-router-dom';
import { Button } from '../../../components/antigravity/Button';
import { Badge, Card, StalenessBadge, isSourceStale } from '../../../components/antigravity';
import { logger } from '../../../lib/logger';
import type { CaseFormStatus, CaseFormSummary } from '../../../api/dossier';
import { buildRoute } from '../../../navigation/routes';
import { formEditorAPI } from '../../../api/formEditor';
import { OriginalPdfDrawer } from './OriginalPdfDrawer';
import { FormDocuments } from './FormDocuments';

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

type BadgeVariant = 'success' | 'warning' | 'error' | 'info' | 'neutral';

// [AIQ-1250] A 100%-filled form must never read "Action needed". When an
// `auto_filled` form has all fields filled, refine the badge: no required
// supporting docs → "Ready to submit" (green); docs required → "Upload documents
// to complete" (yellow). Every other status / partially-filled form is unchanged.
// Note: the card sees which docs are *required* (template.required_documents) but
// not which are *uploaded* (lazy-fetched in FormDocuments), so "docs required" is
// the proxy for the upload-docs state.
function effectiveBadge(
  form: CaseFormSummary,
  filledFields: number,
  totalFields: number,
): { label: string; variant: BadgeVariant } {
  const dStatus = displayStatus(form);
  const allFieldsFilled = totalFields > 0 && filledFields >= totalFields;
  if (dStatus === 'auto_filled' && allFieldsFilled) {
    const requiresDocs = (form.template.required_documents?.length ?? 0) > 0;
    return requiresDocs
      ? { label: 'Upload documents to complete', variant: 'warning' }
      : { label: 'Ready to submit', variant: 'success' };
  }
  return { label: STATUS_LABEL[dStatus], variant: STATUS_BADGE_VARIANT[dStatus] };
}

function statusBannerCopy(form: CaseFormSummary): { tone: string; text: string } {
  const { fields_summary, blocker_form_code, deadline_trigger } = form;
  const status = displayStatus(form);
  const aiFilled = fields_summary.filled_by_ai;
  const missing = fields_summary.missing_required;

  switch (status) {
    case 'auto_filled': {
      // [AIQ-1250] Keep the expanded banner consistent with the refined badge:
      // when every field is filled, this form isn't "action needed" anymore.
      const total = fields_summary.total;
      const filled = fields_summary.filled_by_ai + fields_summary.filled_by_human;
      if (total > 0 && filled >= total) {
        return (form.template.required_documents?.length ?? 0) > 0
          ? {
              tone: 'bg-amber-50 border-amber-200 text-amber-900',
              text: 'All fields complete · upload the required supporting documents to finish.',
            }
          : {
              tone: 'bg-emerald-50 border-emerald-200 text-emerald-900',
              text: 'All fields complete · ready to submit.',
            };
      }
      return {
        tone: 'bg-amber-50 border-amber-200 text-amber-900',
        text:
          aiFilled > 0
            ? `Ready for your review — ${aiFilled} field${aiFilled === 1 ? '' : 's'} pre-filled, ${missing} need${missing === 1 ? 's' : ''} your input.`
            : 'Action needed — review and complete the remaining fields.',
      };
    }
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
        text: form.rejection_reason
          ? `⚠ Returned by ${form.template.authority_name ?? 'authority'}: ${form.rejection_reason}. Open form to correct and resubmit.`
          : 'Rejected — check the response for required changes.',
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
  const [isDownloadingPdf, setIsDownloadingPdf] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);
  const navigate = useNavigate();

  const canDownloadPdf =
    form.status !== 'not_started' && displayStatus(form) !== 'blocked';

  const handleDownloadPdf = async () => {
    if (!canDownloadPdf || isDownloadingPdf) return;
    setIsDownloadingPdf(true);
    try {
      await formEditorAPI.downloadPdf(form.case_id, form.id);
    } catch (e) {
      logger.error('[P3-3] PDF download failed', e);
    } finally {
      setIsDownloadingPdf(false);
    }
  };

  const banner = statusBannerCopy(form);
  const chip = deadlineChip(form.deadline);
  const dStatus = displayStatus(form);
  const totalFields = form.fields_summary.total;
  const filledFields =
    form.fields_summary.filled_by_ai + form.fields_summary.filled_by_human;
  const progressPct =
    totalFields > 0 ? Math.round((filledFields / totalFields) * 100) : form.completion_pct;
  // [AIQ-1250] Refined badge — never "Action needed" at 100% filled.
  const badge = effectiveBadge(form, filledFields, totalFields);

  return (
    <Card padding="lg" className="hover:shadow-sm transition-shadow">
      <Button unstyled
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
            {/* EMP-7: label the bar as "filled" so it can't read as "done" — a form can be
                100% filled (incl. AI-filled fields) yet still show "Action needed" (needs review).
                The % measures field population; the status badge measures readiness. */}
            <span className="text-xs font-medium text-slate-700">{progressPct}% filled</span>
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
          <Badge variant={badge.variant}>{badge.label}</Badge>
          <svg
            className={`w-4 h-4 text-slate-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </Button>

      {expanded && (
        <div className="mt-4 grid gap-3">
          <div className={`rounded border px-3 py-2 text-sm ${banner.tone}`}>{banner.text}</div>

          {/* [WS1] Content-honesty notice — this form set is representative
              scaffolding until an authorised human verifies it against the
              issuing authority. Shown for anything not 'verified' so we never
              imply unverified immigration guidance is authoritative. */}
          {form.template.verification_status !== 'verified' && !form.is_adhoc && (
            <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 flex items-start gap-2">
              <svg className="w-3.5 h-3.5 mt-0.5 shrink-0 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
              <span>
                Indicative guidance to help you prepare — confirm the current
                requirements with{' '}
                <span className="font-medium">
                  {form.template.authority_name ?? 'the issuing authority'}
                </span>{' '}
                before you submit.
              </span>
            </div>
          )}

          {/* [P1-05] Which roadmap step this form belongs to + the official
              Tier-1 source URL. V1 has no submission proxy — the employee
              clicks through to the official authority page to complete it. */}
          {(form.roadmap_step_title || form.template.source_url) && (
            <div className="flex items-center gap-x-4 gap-y-1 flex-wrap text-xs">
              {form.roadmap_step_title && (
                <span className="inline-flex items-center gap-1 text-slate-500">
                  <svg className="w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                  Roadmap step:{' '}
                  <span className="font-medium text-slate-700">{form.roadmap_step_title}</span>
                </span>
              )}
              {form.template.source_url && (
                <a
                  href={form.template.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-medium text-[#0b2b43] hover:underline"
                >
                  Official source
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M14 5h5m0 0v5m0-5L10 14M9 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-3" />
                  </svg>
                </a>
              )}
              {/* [P1-05d] Source freshness from source_pages.last_fetched_at.
                  When the source is older than its tier threshold (P2-08) the
                  passive date is replaced by the StalenessBadge advisory below. */}
              {form.template.source_url &&
                form.template.source_last_verified &&
                !isSourceStale(form.template.source_last_verified) && (
                  <span className="text-slate-400" title="When we last checked the official source page">
                    Last verified · {new Date(form.template.source_last_verified).toLocaleDateString()}
                  </span>
                )}
            </div>
          )}

          {/* [P2-08c] Stale-source advisory — additive, renders only when the
              official source hasn't been verified within its tier threshold. */}
          <StalenessBadge
            lastVerified={form.template.source_last_verified}
            sourceUrl={form.template.source_url}
          />

          <div className="flex items-center gap-3 flex-wrap">
            {/* [P2-3] Open form editor — disabled for blocked/submitted/approved */}
            {dStatus === 'blocked' || dStatus === 'submitted' || dStatus === 'approved' ? (
              <Button unstyled
                type="button"
                disabled
                title={
                  dStatus === 'blocked'
                    ? `Blocked — ${form.blocker_form_code ?? 'another form'} must be submitted first`
                    : 'Form already submitted'
                }
                className="px-3 py-1.5 rounded text-sm font-medium bg-[#0b2b43] text-white opacity-40 cursor-not-allowed"
              >
                Open form
              </Button>
            ) : (
              <Button unstyled
                type="button"
                onClick={() =>
                  navigate(buildRoute('employeeCaseFormEditor', { caseId: form.case_id, formId: form.id }))
                }
                className="px-3 py-1.5 rounded text-sm font-medium bg-[#0b2b43] text-white hover:bg-[#0e3a5c] transition-colors"
              >
                Open form
              </Button>
            )}
            {/* [P3-3] Download filled PDF */}
            {canDownloadPdf ? (
              <div className="flex flex-col items-start">
                <Button unstyled
                  type="button"
                  onClick={() => void handleDownloadPdf()}
                  disabled={isDownloadingPdf}
                  className="text-sm text-[#0b2b43] hover:underline disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                >
                  {isDownloadingPdf ? (
                    <>
                      <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      Generating…
                    </>
                  ) : (
                    'Download PDF'
                  )}
                </Button>
                {form.draft_pdf_url && !isDownloadingPdf && (
                  <span className="text-[10px] text-slate-400 mt-0.5">
                    Last generated: {new Date(form.updated_at).toLocaleString()}
                  </span>
                )}
              </div>
            ) : null}
            {/* [P2-4] "View original" — opens OriginalPdfDrawer with signed URL */}
            <Button unstyled
              type="button"
              onClick={() => setShowOriginal(true)}
              className="text-sm text-[#0b2b43] hover:underline"
            >
              View original PDF
            </Button>
            <span className="text-xs text-slate-400 ml-auto">
              v{form.template.version} · updated{' '}
              {form.updated_at ? new Date(form.updated_at).toLocaleDateString() : '—'}
            </span>
          </div>

          {/* [P1-05c] Supporting documents upload + list (not for ad-hoc forms,
              which are themselves a single uploaded document). */}
          {!form.is_adhoc && (
            <FormDocuments
              caseId={form.case_id}
              formId={form.id}
              requiredDocuments={form.template.required_documents}
            />
          )}
        </div>
      )}

      {/* [P2-4] Original PDF drawer — rendered outside the card scroll area */}
      <OriginalPdfDrawer
        isOpen={showOriginal}
        onClose={() => setShowOriginal(false)}
        caseId={form.case_id}
        formId={form.id}
        formName={form.template.name}
        formCode={form.template.code}
      />
    </Card>
  );
};
