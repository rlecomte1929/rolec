/**
 * ImmigrationStatusPanel — IMM-13
 *
 * HR-facing single-glance view of immigration status for a case.
 * Renders inside HrCommandCenterCaseDetail alongside PendingRfqsPanel.
 *
 * Sections:
 *  1. Document checklist — required documents with status badges
 *  2. Risk flags         — severity-coded alerts with recommended actions
 *  3. Interview progress — employee's profile-collection completion %
 *  4. Quick actions      — view profile, generate form (Phase 3), find vendor
 *
 * Privacy: does NOT display passport_number or date_of_birth.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { hrAPI } from '../../api/client';
import { MilestoneTracker } from '../immigration/MilestoneTracker';
import type { ImmigrationContext } from './immigrationContext';

// ── Types ────────────────────────────────────────────────────────────────────

type Requirement = {
  document_type: string;
  document_name: string;
  is_required: boolean;
  freshness_days: number | null;
  requires_apostille: boolean;
  apostille_countries: string[];
  requires_translation: boolean;
  translation_languages: string[];
  typical_processing_days: number | null;
  book_early_flag: boolean;
  book_early_reason: string | null;
  form_url: string | null;
};

type RiskFlag = {
  flag_type: string;
  severity: 'critical' | 'warning' | 'info';
  title: string;
  description: string;
  recommended_action: string;
  deadline: string | null;
};

type ImmigrationData = {
  corridor_from: string;
  corridor_to: string;
  visa_type: string;
  document_count: number;
  estimated_timeline_days: number;
  requirements: Requirement[];
  risk_flags: RiskFlag[];
  // IMM-15: case context for vendor RFQ pre-fill
  employee_nationality?: string | null;
  has_dependents?: boolean;
  dependents_count?: number;
};

type InterviewStatus = {
  has_session: boolean;
  completion_pct: number;
  is_complete: boolean;
  started_at: string | null;
  last_active_at: string | null;
  completed_at: string | null;
};

interface Props {
  caseId: string;
  /** Case expected move date (ISO) — drives the milestone timeline. */
  moveDate?: string | null;
  /** IMM-15: receives the case's immigration context to pre-load the vendor RFQ */
  onFindVendor: (ctx: ImmigrationContext) => void;
  onViewProfile: () => void;
}

// ── Severity styling ─────────────────────────────────────────────────────────

const SEVERITY_STYLE: Record<RiskFlag['severity'], { card: string; badge: string; label: string }> = {
  critical: {
    card: 'border-[#fecaca] bg-[#fff5f5]',
    badge: 'bg-[#fee2e2] text-[#b91c1c]',
    label: 'Critical',
  },
  warning: {
    card: 'border-[#fde68a] bg-[#fffbeb]',
    badge: 'bg-[#fef3c7] text-[#92400e]',
    label: 'Warning',
  },
  info: {
    card: 'border-[#bfdbfe] bg-[#eff6ff]',
    badge: 'bg-[#dbeafe] text-[#1d4ed8]',
    label: 'Info',
  },
};

// ── Sub-components ────────────────────────────────────────────────────────────

const DocStatusBadge: React.FC<{ collected: boolean }> = ({ collected }) =>
  collected ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-[#f0fdf4] border border-[#bbf7d0] px-2 py-0.5 text-xs font-medium text-[#15803d]">
      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
      Provided
    </span>
  ) : (
    <span className="inline-flex items-center rounded-full bg-[#f8fafc] border border-[#e2e8f0] px-2 py-0.5 text-xs font-medium text-[#64748b]">
      Not started
    </span>
  );

// ── Main component ────────────────────────────────────────────────────────────

export const ImmigrationStatusPanel: React.FC<Props> = ({
  caseId,
  moveDate,
  onFindVendor,
  onViewProfile,
}) => {
  const [immData, setImmData] = useState<ImmigrationData | null>(null);
  const [interview, setInterview] = useState<InterviewStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    setError('');
    Promise.all([
      hrAPI.getImmigrationRequirements(caseId),
      hrAPI.getImmigrationInterviewStatus(caseId),
    ])
      .then(([imm, iv]) => {
        setImmData(imm);
        setInterview(iv);
      })
      .catch(() => setError('Failed to load immigration data.'))
      .finally(() => setLoading(false));
  }, [caseId]);

  useEffect(() => {
    load();
  }, [load]);

  // IMM-15: snapshot the case's immigration context for a vendor RFQ pre-fill.
  // move_date is injected by the parent (sourced from the case record).
  const buildImmigrationContext = (): ImmigrationContext => ({
    visa_type: immData?.visa_type,
    corridor_from: immData?.corridor_from,
    corridor_to: immData?.corridor_to,
    employee_nationality: immData?.employee_nationality ?? undefined,
    has_dependents: immData?.has_dependents,
    dependents_count: immData?.dependents_count,
    risk_flags: immData?.risk_flags?.map((f) => ({ flag_type: f.flag_type, title: f.title })),
  });

  // ── Loading / error / empty states ─────────────────────────────────────────

  if (loading) {
    return (
      <div className="py-6 text-center text-sm text-[#94a3b8]">
        Loading immigration status…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-[#fecaca] bg-[#fff5f5] px-4 py-3 text-sm text-[#b91c1c]">
        {error}
        <button
          type="button"
          onClick={load}
          className="ml-3 underline hover:no-underline"
        >
          Retry
        </button>
      </div>
    );
  }

  const noData = !immData || immData.requirements.length === 0;

  if (noData) {
    return (
      <div className="space-y-4">
        <div className="rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-4 py-6 text-center">
          <p className="text-sm font-medium text-[#64748b]">Immigration setup not started</p>
          <p className="mt-1 text-xs text-[#94a3b8]">
            No immigration requirements have been generated for this case yet.
          </p>
        </div>
        <QuickActions onFindVendor={() => onFindVendor(buildImmigrationContext())} onViewProfile={onViewProfile} />
      </div>
    );
  }

  const criticalCount = immData.risk_flags.filter((f) => f.severity === 'critical').length;
  const warningCount  = immData.risk_flags.filter((f) => f.severity === 'warning').length;
  const interviewPct  = interview?.completion_pct ?? 0;

  return (
    <div className="space-y-5">

      {/* ── Summary chips ──────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-2 text-xs">
        <span className="rounded-full border border-[#e2e8f0] bg-[#f8fafc] px-3 py-1 text-[#374151]">
          {immData.corridor_from} → {immData.corridor_to}
        </span>
        <span className="rounded-full border border-[#e2e8f0] bg-[#f8fafc] px-3 py-1 text-[#374151]">
          {immData.visa_type.replace(/_/g, ' ')}
        </span>
        <span className="rounded-full border border-[#e2e8f0] bg-[#f8fafc] px-3 py-1 text-[#374151]">
          ~{immData.estimated_timeline_days}d processing
        </span>
        {criticalCount > 0 && (
          <span className="rounded-full border border-[#fecaca] bg-[#fee2e2] px-3 py-1 font-medium text-[#b91c1c]">
            {criticalCount} critical flag{criticalCount > 1 ? 's' : ''}
          </span>
        )}
        {warningCount > 0 && (
          <span className="rounded-full border border-[#fde68a] bg-[#fef3c7] px-3 py-1 font-medium text-[#92400e]">
            {warningCount} warning{warningCount > 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* ── 1. Document checklist ───────────────────────────────────────────── */}
      <section>
        <div className="text-xs font-semibold uppercase tracking-wide text-[#94a3b8] mb-2">
          Document checklist ({immData.document_count})
        </div>
        <ul className="space-y-2">
          {immData.requirements.map((req) => (
            <li
              key={req.document_type}
              className="flex items-start justify-between gap-3 rounded-lg border border-[#e2e8f0] bg-white px-3 py-2.5"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-[#0b2b43] leading-snug">
                    {req.document_name}
                  </span>
                  {req.requires_apostille && (
                    <span className="rounded-full border border-[#a5b4fc] bg-[#eef2ff] px-2 py-0.5 text-xs text-[#4338ca]">
                      Apostille
                    </span>
                  )}
                  {req.requires_translation && (
                    <span className="rounded-full border border-[#d2eceb] bg-[#ebf7f6] px-2 py-0.5 text-xs text-[#1f8e8b]">
                      Translation
                    </span>
                  )}
                  {req.book_early_flag && (
                    <span className="rounded-full border border-[#fde68a] bg-[#fef3c7] px-2 py-0.5 text-xs text-[#92400e]">
                      Book early
                    </span>
                  )}
                </div>
                <div className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-[#94a3b8]">
                  {req.freshness_days != null && (
                    <span>Valid ≤{req.freshness_days}d</span>
                  )}
                  {req.typical_processing_days != null && (
                    <span>~{req.typical_processing_days}d processing</span>
                  )}
                  {req.book_early_reason && (
                    <span className="text-[#92400e]">{req.book_early_reason}</span>
                  )}
                </div>
              </div>
              <div className="shrink-0 mt-0.5">
                {/* Status derived from profile existence — Phase 2 will track per-document */}
                <DocStatusBadge collected={false} />
              </div>
            </li>
          ))}
        </ul>
      </section>

      {/* ── 2. Risk flags ──────────────────────────────────────────────────── */}
      {immData.risk_flags.length > 0 && (
        <section>
          <div className="text-xs font-semibold uppercase tracking-wide text-[#94a3b8] mb-2">
            Risk flags
          </div>
          <div className="space-y-2">
            {immData.risk_flags.map((flag, i) => {
              const s = SEVERITY_STYLE[flag.severity];
              return (
                <div
                  key={`${flag.flag_type}-${i}`}
                  className={`rounded-lg border px-3 py-3 ${s.card}`}
                >
                  <div className="flex items-start gap-2">
                    <span className={`shrink-0 mt-0.5 rounded-full px-2 py-0.5 text-xs font-semibold ${s.badge}`}>
                      {s.label}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-[#0b2b43]">{flag.title}</p>
                      <p className="mt-0.5 text-xs text-[#4b5563] leading-relaxed">{flag.description}</p>
                      {flag.recommended_action && (
                        <p className="mt-1 text-xs font-medium text-[#374151]">
                          → {flag.recommended_action}
                        </p>
                      )}
                      {flag.deadline && (
                        <p className="mt-1 text-xs text-[#64748b]">
                          Deadline: {new Date(flag.deadline).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── IMM-14: Application milestone timeline ───────────────────────────── */}
      <MilestoneTracker
        caseId={caseId}
        moveDate={moveDate}
        corridorFrom={immData.corridor_from}
        corridorTo={immData.corridor_to}
      />

      {/* ── 3. Interview progress ───────────────────────────────────────────── */}
      <section>
        <div className="text-xs font-semibold uppercase tracking-wide text-[#94a3b8] mb-2">
          Employee interview progress
        </div>
        <div className="rounded-lg border border-[#e2e8f0] bg-white px-4 py-3">
          {!interview?.has_session ? (
            <p className="text-sm text-[#94a3b8]">Interview not started by employee yet.</p>
          ) : (
            <>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-[#374151]">
                  {interview.is_complete ? 'Interview complete' : 'In progress'}
                </span>
                <span className="text-sm font-semibold text-[#0b2b43]">
                  {Math.round(interviewPct)}%
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-[#e2e8f0]">
                <div
                  className={`h-2 rounded-full transition-all ${
                    interview.is_complete ? 'bg-[#22c55e]' : 'bg-[#3b82f6]'
                  }`}
                  style={{ width: `${Math.min(100, Math.round(interviewPct))}%` }}
                />
              </div>
              {interview.last_active_at && (
                <p className="mt-1.5 text-xs text-[#94a3b8]">
                  Last active: {new Date(interview.last_active_at).toLocaleDateString()}
                </p>
              )}
            </>
          )}
        </div>
      </section>

      {/* ── 4. Quick actions ────────────────────────────────────────────────── */}
      <QuickActions onFindVendor={() => onFindVendor(buildImmigrationContext())} onViewProfile={onViewProfile} />
    </div>
  );
};

// ── Quick actions sub-component ──────────────────────────────────────────────

const QuickActions: React.FC<{
  onFindVendor: () => void;
  onViewProfile: () => void;
}> = ({ onFindVendor, onViewProfile }) => (
  <div className="flex flex-wrap gap-2">
    <button
      type="button"
      onClick={onViewProfile}
      className="rounded-lg border border-[#e2e8f0] bg-white px-3 py-1.5 text-xs font-medium text-[#374151] hover:bg-[#f8fafc] transition-colors"
    >
      View employee data
    </button>
    <button
      type="button"
      disabled
      title="Form generation available in Phase 3"
      className="rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-3 py-1.5 text-xs font-medium text-[#94a3b8] cursor-not-allowed"
    >
      Generate pre-filled form
      <span className="ml-1.5 rounded-full bg-[#f1f5f9] px-1.5 py-0.5 text-[10px] font-normal text-[#94a3b8]">
        Phase 3
      </span>
    </button>
    <button
      type="button"
      onClick={onFindVendor}
      className="flex items-center gap-1.5 rounded-lg border border-[#0b2b43] bg-white px-3 py-1.5 text-xs font-medium text-[#0b2b43] hover:bg-[#f8fafc] transition-colors"
    >
      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
      Find immigration vendor
    </button>
  </div>
);
