/**
 * ImmigrationCasePage — MVG-6A/6C
 *
 * HR view of an existing immigration case: status timeline, key dates,
 * and a 7-day deadline warning.
 * Route: /hr/immigration/:immigrationCaseId
 */

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { Badge, Button, Card } from '../../components/antigravity';
import { buildRoute } from '../../navigation/routes';
import { CaseDocumentsPanel } from '../../components/case/CaseDocumentsPanel';
import api from '../../api/client';

// ── Types ────────────────────────────────────────────────────────────────────

type ImmigrationStatus =
  | 'initiated'
  | 'documents_collected'
  | 'submitted'
  | 'under_review'
  | 'decision'
  | 'granted';

interface ImmigrationCase {
  id: string;
  case_id: string;
  corridor_from: string;
  corridor_to: string;
  permit_type: string;
  partner_name: string | null;
  expected_submission_date: string | null;
  expected_grant_date: string | null;
  permit_expiry_date: string | null;
  status: ImmigrationStatus;
  created_at: string;
}

// ── Constants ────────────────────────────────────────────────────────────────

const TIMELINE_STAGES: { key: ImmigrationStatus; label: string }[] = [
  { key: 'initiated',           label: 'Application Initiated' },
  { key: 'documents_collected', label: 'Documents Collected' },
  { key: 'submitted',           label: 'Submitted' },
  { key: 'under_review',        label: 'Under Review' },
  { key: 'decision',            label: 'Decision' },
  { key: 'granted',             label: 'Granted' },
];

const PERMIT_LABELS: Record<string, string> = {
  eu_blue_card: 'EU Blue Card',
  work_permit: 'Work Permit',
  skilled_worker_visa: 'Skilled Worker Visa',
  eea_registration: 'EEA Registration',
  other: 'Other',
};

function daysBetween(dateStr: string): number {
  const target = new Date(dateStr);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  target.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  });
}

// ── Component ────────────────────────────────────────────────────────────────

export const ImmigrationCasePage: React.FC = () => {
  const { immigrationCaseId } = useParams<{ immigrationCaseId: string }>();
  const navigate = useNavigate();

  const immCaseQuery = useQuery({
    queryKey: ['hr', 'immigration-case', immigrationCaseId],
    queryFn: async () => {
      const res = await api.get(`/api/hr/immigration/cases/${immigrationCaseId}`);
      return res.data as ImmigrationCase;
    },
    enabled: !!immigrationCaseId,
  });
  const immCase: ImmigrationCase | null = immCaseQuery.data ?? null;
  // Preserve original: with no id the page stays in its loading state.
  const loading = !immigrationCaseId || immCaseQuery.isLoading;
  const error = immCaseQuery.isError ? 'Could not load immigration case.' : null;

  if (loading) {
    return (
      <AppShell title="Immigration case">
        <p className="text-[#94a3b8] p-8">Loading…</p>
      </AppShell>
    );
  }

  if (error || !immCase) {
    return (
      <AppShell title="Immigration case">
        <div className="p-8">
          <p className="text-[#fca5a5]">{error ?? 'Case not found.'}</p>
          <Button className="mt-4" variant="ghost" onClick={() => navigate(-1)}>
            Go back
          </Button>
        </div>
      </AppShell>
    );
  }

  // ── Deadline warning logic ────────────────────────────────────────────────

  const earlyStages: ImmigrationStatus[] = ['initiated', 'documents_collected'];
  const isEarlyStage = earlyStages.includes(immCase.status);
  const daysUntilSubmission = immCase.expected_submission_date
    ? daysBetween(immCase.expected_submission_date)
    : null;
  const showWarning =
    isEarlyStage &&
    daysUntilSubmission !== null &&
    daysUntilSubmission <= 7;

  // ── Timeline position ─────────────────────────────────────────────────────

  const currentIdx = TIMELINE_STAGES.findIndex((s) => s.key === immCase.status);

  return (
    <AppShell title="Immigration case — status">
      <div className="max-w-2xl mx-auto py-8 px-4">

        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-[#f1f5f9]">
              Immigration case
            </h1>
            <p className="text-[#94a3b8] text-sm mt-1">
              {immCase.corridor_from} → {immCase.corridor_to} ·{' '}
              {PERMIT_LABELS[immCase.permit_type] ?? immCase.permit_type}
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(buildRoute('hrCommandCenter'))}
          >
            ← Command center
          </Button>
        </div>

        {/* 7-day warning */}
        {showWarning && (
          <div
            role="alert"
            className="mb-6 rounded-lg bg-[#451a03] border border-[#92400e] text-[#fcd34d] px-4 py-3 text-sm flex items-start gap-2"
          >
            <span>⚠️</span>
            <span>
              Submission expected in{' '}
              <strong>{daysUntilSubmission} day{daysUntilSubmission !== 1 ? 's' : ''}</strong>{' '}
              — documents not yet collected. Follow up with employee.
            </span>
          </div>
        )}

        {/* Timeline */}
        <Card className="p-6 mb-6">
          <h2 className="text-sm font-semibold text-[#94a3b8] uppercase tracking-wider mb-6">
            Permit pipeline
          </h2>
          <ol className="relative border-l border-[#334155] space-y-0">
            {TIMELINE_STAGES.map((stage, idx) => {
              const isCompleted = idx < currentIdx;
              const isCurrent = idx === currentIdx;
              const isFuture = idx > currentIdx;

              return (
                <li key={stage.key} className="ml-4 pb-6 last:pb-0">
                  {/* Dot */}
                  <span
                    className={[
                      'absolute -left-2 flex items-center justify-center w-4 h-4 rounded-full ring-2',
                      isCompleted
                        ? 'bg-[#22c55e] ring-[#14532d]'
                        : isCurrent
                        ? 'bg-[#3b82f6] ring-[#1e3a5f]'
                        : 'bg-[#1e293b] ring-[#334155]',
                    ].join(' ')}
                    aria-hidden="true"
                  />
                  <div className="flex items-center gap-3">
                    <span
                      className={[
                        'text-sm font-medium',
                        isCurrent
                          ? 'text-[#f1f5f9]'
                          : isCompleted
                          ? 'text-[#86efac]'
                          : 'text-[#475569]',
                      ].join(' ')}
                    >
                      {stage.label}
                    </span>
                    {isCurrent && (
                      <Badge variant="info" size="sm">
                        Current
                      </Badge>
                    )}
                    {isCompleted && (
                      <span className="text-xs text-[#4ade80]">✓</span>
                    )}
                    {isFuture && (
                      <span className="text-xs text-[#334155]">Pending</span>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        </Card>

        {/* Key dates */}
        <Card className="p-6 mb-6">
          <h2 className="text-sm font-semibold text-[#94a3b8] uppercase tracking-wider mb-4">
            Key dates
          </h2>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-[#64748b]">Expected submission</dt>
              <dd className="text-[#f1f5f9] font-medium mt-0.5">
                {formatDate(immCase.expected_submission_date)}
              </dd>
            </div>
            <div>
              <dt className="text-[#64748b]">Expected grant</dt>
              <dd className="text-[#f1f5f9] font-medium mt-0.5">
                {formatDate(immCase.expected_grant_date)}
              </dd>
            </div>
            {immCase.permit_expiry_date && (
              <div>
                <dt className="text-[#64748b]">Permit expiry</dt>
                <dd className="text-[#f1f5f9] font-medium mt-0.5">
                  {formatDate(immCase.permit_expiry_date)}
                </dd>
              </div>
            )}
            <div>
              <dt className="text-[#64748b]">Immigration partner</dt>
              <dd className="text-[#f1f5f9] font-medium mt-0.5">
                {immCase.partner_name ?? '—'}
              </dd>
            </div>
          </dl>
        </Card>

        {/* BL-OCR.4 / AIQ-750 — uploaded documents + AI extraction status */}
        <Card className="p-6 mb-6">
          <h2 className="text-sm font-semibold text-[#94a3b8] uppercase tracking-wider mb-4">
            Documents
          </h2>
          <CaseDocumentsPanel caseId={immCase.case_id} />
        </Card>

        {/* Actions */}
        <div className="flex gap-3">
          <Button
            variant="ghost"
            onClick={() =>
              navigate(
                buildRoute('employeeCaseImmigrationChecklist', {
                  caseId: immCase.case_id,
                }),
              )
            }
          >
            View employee checklist
          </Button>
          <Button
            variant="ghost"
            onClick={() => navigate(buildRoute('hrImmigrationCreate'))}
          >
            + New immigration case
          </Button>
        </div>
      </div>
    </AppShell>
  );
};
