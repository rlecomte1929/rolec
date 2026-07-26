import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { getAuthItem } from '../utils/demo';
import { getCountryName } from '../utils/countries';
import { Card, Button } from '../components/antigravity';
import { RiskBadge } from '../components/command-center/RiskBadge';
import { hrAPI } from '../api/client';
import { buildRoute } from '../navigation/routes';
import { safeNavigate } from '../navigation/safeNavigate';
import { ExceptionFlagsPanel } from '../components/case/ExceptionFlagsPanel';
import { RoadmapReviewPanel } from '../components/case/RoadmapReviewPanel';
import { statusLabel } from '../lib/statusLabel';
import { HrCaseTasksPanel } from '../components/case/HrCaseTasksPanel';
import { VendorBrowsePanel } from '../components/case/VendorBrowsePanel';
import type { ImmigrationContext } from '../components/case/immigrationContext';
import { PendingRfqsPanel } from '../components/case/PendingRfqsPanel';
import { ImmigrationStatusPanel } from '../components/case/ImmigrationStatusPanel';
import { AdvisorsPanel } from '../components/case/AdvisorsPanel';
import { AssignmentExceptionsPanel } from '../components/case/AssignmentExceptionsPanel';
import { PetRequirementsSection } from '../components/case/PetRequirementsSection';
import { CaseAuditTimeline } from '../components/case/CaseAuditTimeline';
import { CaseNotesPanel } from '../components/case/CaseNotesPanel';
import { CasePredictionCard } from '../components/case/CasePredictionCard';
import { CaseSummaryCard } from '../components/case/CaseSummaryCard';
import { EscalateCaseModal } from '../components/case/EscalateCaseModal';
import { ReassignCaseModal } from '../components/case/ReassignCaseModal';
import { AIRecommendationCard } from '../features/ai-oversight/AIRecommendationCard';
import { CoordinatorChatPanel } from '../features/coordinator/CoordinatorChatPanel';
import { isCoordinatorEnabled } from '../featureFlags';

/**
 * Corridor label for the case-identity header (BRAND-4). The command-center
 * case payload carries only a destination (no origin field), so we render
 * "Relocating to <dest>" when a destination exists, and an intentional
 * "Corridor not set" when it doesn't — never a bare "-" or "tbd"
 * (coordinated with BRAND-5). If an origin is added to the payload later,
 * this is the single place to switch to the "<origin> → <dest>" form.
 */
function corridorLabel(destCity?: string, destCountry?: string): string {
  // [AIQ-1336] City-level destination ("Amsterdam, Netherlands") for parity with the
  // case summary; falls back to country-only, then city-only, then a neutral label.
  const city = destCity?.trim();
  const country = destCountry?.trim() ? getCountryName(destCountry.trim()) : undefined;
  const dest = city && country ? `${city}, ${country}` : country || city;
  return dest ? `Relocating to ${dest}` : 'Corridor not set';
}

type CaseDetail = {
  id: string;
  /** AIQ-1479: relocation case id (distinct from the assignment PK `id`); used to key the
   *  immigration panel's case-scoped reads. */
  caseId?: string | null;
  employeeIdentifier: string;
  destCountry?: string;
  destCity?: string;
  status: string;
  riskStatus: string;
  budgetLimit?: number;
  budgetEstimated?: number;
  expectedStartDate?: string;
  tasksTotal: number;
  tasksDone: number;
  tasksOverdue: number;
  phases: Array<{ phase: string; tasks: Array<{ title: string; status: string; due_date?: string }> }>;
  events: Array<{ event_type: string; description?: string; created_at: string }>;
};

export const HrCommandCenterCaseDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const role = getAuthItem('relopass_role');
  useEffect(() => {
    if (role && role !== 'HR' && role !== 'ADMIN') {
      safeNavigate(navigate, 'landing');
    }
  }, [role, navigate]);

  const detailQuery = useQuery({
    queryKey: ['hr', 'cc-case-detail', id],
    enabled: !!id,
    queryFn: () => hrAPI.getCommandCenterCaseDetail(id as string),
  });
  const detail: CaseDetail | null = detailQuery.data ?? null;
  const isLoading = detailQuery.isLoading;

  // Preserve the 401 → landing redirect from the detail read.
  useEffect(() => {
    const status = (detailQuery.error as { response?: { status?: number } } | null)?.response?.status;
    if (detailQuery.isError && status === 401) safeNavigate(navigate, 'landing');
  }, [detailQuery.isError, detailQuery.error, navigate]);

  // Vendor browse panel + RFQ modal
  const [vendorPanelOpen, setVendorPanelOpen] = useState(false);
  const [vendorPanelInitialCategory, setVendorPanelInitialCategory] = useState('');
  // IMM-15: immigration context captured when the vendor flow is opened from the
  // immigration panel; flows into VendorBrowsePanel and the RFQ modal.
  const [vendorImmigrationContext, setVendorImmigrationContext] = useState<ImmigrationContext | null>(null);
  // BUG-260706-4DE4: allow deep-linking straight to the vendor browse (e.g. the
  // "Find immigration vendor" action on /hr/requirements) via ?openVendors=immigration.
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    if (searchParams.get('openVendors') === 'immigration') {
      setVendorPanelInitialCategory('Immigration/visa');
      setVendorPanelOpen(true);
      const next = new URLSearchParams(searchParams);
      next.delete('openVendors');
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);
  // NAV-HR-2: case-level escalate — the one case action missing from this view
  // (approve/reject already live in the exception panels below).
  const [escalateOpen, setEscalateOpen] = useState(false);
  const [escalateSuccessMsg, setEscalateSuccessMsg] = useState('');
  // AIQ-1136: case-level reassign — HR hands a case to another HR in the company.
  const [reassignOpen, setReassignOpen] = useState(false);
  const [reassignSuccessMsg, setReassignSuccessMsg] = useState('');

  const budgetStatus = (): 'Within' | 'Approaching' | 'Exceeded' | null => {
    if (!detail?.budgetLimit || detail.budgetEstimated == null) return null;
    const pct = (detail.budgetEstimated / detail.budgetLimit) * 100;
    if (pct > 100) return 'Exceeded';
    if (pct >= 90) return 'Approaching';
    return 'Within';
  };

  if (isLoading) {
    return (
      <AppShell section="Case detail" title="Loading…">
        <div className="text-sm text-[#6b7280] py-8">Loading...</div>
      </AppShell>
    );
  }
  if (!detail) {
    return (
      <AppShell section="Case detail" title="Case not found">
        <div className="text-sm text-[#6b7280] py-8">Case not found or not visible.</div>
        <Button variant="outline" onClick={() => navigate(buildRoute('hrCommandCenter'))}>
          Back to Command Center
        </Button>
      </AppShell>
    );
  }

  const bStatus = budgetStatus();

  return (
    <AppShell
      section="Case detail"
      // AIQ-1479: give the page a navigable parent crumb back to the command center and a
      // subtitle that says what this page is for (the reporter was "lost" arriving here).
      parent={{ label: 'Mobility command center', href: buildRoute('hrCommandCenter') }}
      title={detail.employeeIdentifier}
      subtitle={`${corridorLabel(detail.destCity, detail.destCountry)} · Everything for this case — immigration advisors & status, vendors, policy exceptions and notes.`}
    >
      <div className="space-y-6">
        {/* BRAND-4: the case leads with identity — employee name/email (H1) +
            corridor (subtitle) + 'Case detail' demoted to the breadcrumb eyebrow
            above. This row carries the case state (status pill) and the primary
            cross-link. (The payload has no display-name/origin field, so the H1
            falls back to the email and the corridor shows destination only.) */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <RiskBadge status={detail.riskStatus as 'green' | 'yellow' | 'red'} showLabel />
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={() => setEscalateOpen(true)}>
              Escalate case
            </Button>
            <Button variant="outline" onClick={() => setReassignOpen(true)}>
              Reassign case
            </Button>
            <Button variant="outline" onClick={() => navigate(buildRoute('hrAssignmentReview', { id: detail.id }))}>
              Open in Employee Dashboard
            </Button>
          </div>
        </div>

        {/* ── AIQ-1605: roadmap validation surface on the page HR actually reaches from
             the command center. The approve / request-changes panel previously lived only
             on /hr/cases/:caseId (HrCaseSummary), so an HR user arriving here saw no
             validation request. Mounted high on purpose — it is the most time-sensitive
             action when a roadmap is awaiting sign-off. Keyed on the relocation case id
             (detail.caseId), same id-space as the roadmap-review endpoints; falls back to
             the assignment PK when absent (mirrors the immigration panels below). ── */}
        <RoadmapReviewPanel caseId={detail.caseId ?? detail.id} />

        {/* ── AIQ-1136 slice 3: EU AI Act Art. 14 oversight on the AI risk verdict.
            The risk status is an AI-derived recommendation shown above as a passive
            badge; this card gives "override" a concrete target by forcing HR to
            accept / override / reject it. Only surfaces while the verdict is
            load-bearing (yellow/red) — a green case needs no oversight prompt. ── */}
        {(detail.riskStatus === 'yellow' || detail.riskStatus === 'red') && (
          <AIRecommendationCard
            recommendationId={`case_risk_v1:${detail.id}`}
            feature="case_risk"
            title="AI risk assessment"
            rationale={
              <>
                The platform flagged this case as{' '}
                <strong>{detail.riskStatus === 'red' ? 'high risk' : 'needs attention'}</strong>
                {' '}based on intake completeness, blocking exceptions, and overdue tasks.
                Accept to confirm, or override with your own judgement.
              </>
            }
            aiOutput={{
              assignment_id: detail.id,
              risk_status: detail.riskStatus,
              tasks_total: detail.tasksTotal,
              tasks_done: detail.tasksDone,
              tasks_overdue: detail.tasksOverdue,
              source_version: 'case_risk_v1',
            }}
          />
        )}

        {/* ── Exception flags (P3/B6): blockers + warnings from immigration check ── */}
        <ExceptionFlagsPanel caseId={detail.id} />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Timeline / Phases */}
          <Card padding="lg">
            <div className="text-sm font-semibold text-[#0b2b43] mb-3">Phase progression</div>
            <div className="space-y-3">
              {detail.phases.length === 0 ? (
                <div className="text-sm text-[#94a3b8]">No phases defined yet.</div>
              ) : (
                detail.phases.map((ph) => (
                  <div key={ph.phase} className="border-l-2 border-[#e2e8f0] pl-4">
                    <div className="text-sm font-medium text-[#4b5563]">{ph.phase}</div>
                    <ul className="mt-1 space-y-1 text-sm text-[#6b7280]">
                      {ph.tasks.map((t, i) => (
                        <li key={i} className="flex items-center gap-2">
                          <span className={t.status === 'overdue' ? 'text-[#ef4444] font-medium' : ''}>
                            {t.title}
                          </span>
                          <span className="text-xs text-[#94a3b8]">{statusLabel(t.status)}</span>
                          {t.due_date && <span className="text-xs">· {t.due_date}</span>}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))
              )}
            </div>
          </Card>

          {/* Task completion */}
          <Card padding="lg">
            <div className="text-sm font-semibold text-[#0b2b43] mb-3">Task completion</div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-semibold text-[#0b2b43]">
                {detail.tasksTotal ? Math.round((detail.tasksDone / detail.tasksTotal) * 100) : 0}%
              </span>
              <span className="text-sm text-[#6b7280]">
                {detail.tasksDone} of {detail.tasksTotal} completed
              </span>
            </div>
            {detail.tasksOverdue > 0 && (
              <div className="mt-2 text-sm text-[#ef4444] font-medium">
                {detail.tasksOverdue} overdue task(s)
              </div>
            )}
          </Card>

          {/* [Parker-A] Predicted time to completion — self-hides until the
              prediction canary + a trained model are available. */}
          <CasePredictionCard caseId={detail.id} />

          {/* AIQ-1697: AI case summary — status / blockers / next actions / cost
              variance from the case-summary Edge Function (PII-safe). */}
          <CaseSummaryCard caseId={detail.id} />

          {/* Budget */}
          <Card padding="lg">
            <div className="text-sm font-semibold text-[#0b2b43] mb-3">Budget overview</div>
            <div className="space-y-2 text-sm">
              <div>Limit: {detail.budgetLimit != null ? detail.budgetLimit : '-'}</div>
              <div>Estimated: {detail.budgetEstimated != null ? detail.budgetEstimated : '-'}</div>
              {bStatus && (
                <div className={`font-medium ${bStatus === 'Exceeded' ? 'text-[#ef4444]' : bStatus === 'Approaching' ? 'text-[#eab308]' : 'text-[#22c55e]'}`}>
                  Status: {bStatus}
                </div>
              )}
            </div>
            {/* AIQ-280: link out to the per-category estimate view. The
                rich table lives at /hr/cases/:caseId/estimate so we don't
                bloat this already-dense detail page with another panel. */}
            <Button
              variant="outline"
              className="mt-3 text-xs"
              onClick={() => navigate(buildRoute('hrCaseEstimate', { caseId: detail.id }))}
            >
              View detailed estimate
            </Button>
          </Card>

          {/* Activity log */}
          <Card padding="lg" className="lg:col-span-2">
            <div className="text-sm font-semibold text-[#0b2b43] mb-3">Activity log</div>
            {detail.events.length === 0 ? (
              <div className="text-sm text-[#94a3b8]">No events yet.</div>
            ) : (
              <ul className="space-y-3">
                {detail.events.map((e, i) => (
                  <li key={i} className="flex gap-3 text-sm">
                    <span className="text-[#94a3b8] shrink-0">
                      {e.created_at ? new Date(e.created_at).toLocaleString() : '-'}
                    </span>
                    <span className="font-medium text-[#4b5563]">{e.event_type}</span>
                    {e.description && <span className="text-[#6b7280]">{e.description}</span>}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        {/* ── Employee Tasks (AIQ-34-C) — polls every 8s ── */}
        <HrCaseTasksPanel caseId={detail.id} />

        {/* ── GAP 4 / AIQ-1479: Immigration advisors first — the actionable "contacts +
            ratings" section is the most useful thing here, so it leads the immigration
            cluster (was below the status panel). ── */}
        <AdvisorsPanel
          destinationCountry={detail.destCountry}
        />

        {/* ── IMM-13: Immigration status panel ── */}
        <Card padding="lg" className="border border-[#e2e8f0]">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-sm font-semibold text-[#0b2b43]">Immigration status</div>
              <p className="text-xs text-[#94a3b8] mt-0.5">Documents, risk flags and employee interview progress</p>
            </div>
          </div>
          <ImmigrationStatusPanel
            // AIQ-1479: pass the relocation case id (the command-center detail returns both
            // the assignment PK `id` and the relocation `caseId`). The immigration endpoints
            // key on the relocation case id; passing the assignment PK made them fail to
            // resolve → spurious "empty / error" state. Fall back to id when caseId is absent.
            caseId={detail.caseId ?? detail.id}
            moveDate={detail.expectedStartDate ?? null}
            onFindVendor={(ctx) => {
              // move_date isn't part of the immigration profile — source it from the case
              setVendorImmigrationContext({ ...ctx, move_date: detail.expectedStartDate });
              setVendorPanelInitialCategory('Immigration/visa');
              setVendorPanelOpen(true);
            }}
            onViewProfile={() => {
              navigate(buildRoute('hrAssignmentReview', { id: detail.id }));
            }}
          />
        </Card>

        {/* ── AIQ-160-E: Pet import requirements for destination country ── */}
        <PetRequirementsSection
          caseId={detail.id}
          destCountry={detail.destCountry}
        />

        {/* ── GAP 7: Assignment-level policy exception requests ── */}
        <AssignmentExceptionsPanel assignmentId={detail.id} />

        {/* ── NAV-HR-2-FU: internal HR notes on the case ── */}
        <CaseNotesPanel caseId={detail.id} />

        {/* ── AIQ-1414 Phase 4: Mobility Coordinator chat (flag-gated) ── */}
        {isCoordinatorEnabled() && <CoordinatorChatPanel caseId={detail.id} />}

        {/* ── NAV-HR-3: chronological HR-action audit trail (from audit_logs) ── */}
        <CaseAuditTimeline caseId={detail.id} />

        {/* ── AIQ-40-D: Vendor RFQs (sent by HR, tracked here) ── */}
        <Card padding="lg" className="border border-[#e2e8f0]">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-sm font-semibold text-[#0b2b43]">Vendor quote requests</div>
              <p className="text-xs text-[#94a3b8] mt-0.5">RFQs you&apos;ve sent to vendors for this case</p>
            </div>
            <Button unstyled
              type="button"
              onClick={() => { setVendorPanelInitialCategory(''); setVendorPanelOpen(true); }}
              className="flex items-center gap-1.5 rounded-lg border border-[#0b2b43] bg-white px-3 py-1.5 text-xs font-medium text-[#0b2b43] hover:bg-[#f8fafc] transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              Find a vendor
            </Button>
          </div>
          {/* [AIQ-1703] The employee's canonical RFQs (rfqs) are keyed on the CASE id, not the
              assignment PK. `detail.id` is the assignment PK; `detail.caseId` is the relocation
              case id (same id-space the RFQ carries). Passing detail.id read nothing → HR saw no
              RFQ. Fall back to detail.id for legacy rows that pre-date the split. */}
          <PendingRfqsPanel caseId={detail.caseId ?? detail.id} />
        </Card>

        <Button variant="outline" onClick={() => navigate(buildRoute('hrCommandCenter'))}>
          Back to Command Center
        </Button>
      </div>

      {/* ── AIQ-40-B: Vendor browse slide-over ── */}
      <VendorBrowsePanel
        isOpen={vendorPanelOpen}
        onClose={() => { setVendorPanelOpen(false); setVendorPanelInitialCategory(''); setVendorImmigrationContext(null); }}
        destCountry={detail.destCountry}
        initialCategory={vendorPanelInitialCategory}
        immigrationContext={vendorImmigrationContext}
      />

      {/* ── NAV-HR-2: case-level escalate ── */}
      {escalateSuccessMsg && (
        <div className="fixed bottom-6 right-6 z-50 rounded-xl border border-[#bbf7d0] bg-[#f0fdf4] px-5 py-3 shadow-lg text-sm text-[#166534] font-medium">
          ✓ {escalateSuccessMsg}
          <Button unstyled type="button" aria-label="Dismiss notification" onClick={() => setEscalateSuccessMsg('')} className="ml-3 text-[#16a34a] hover:text-[#166534]">✕</Button>
        </div>
      )}
      <EscalateCaseModal
        open={escalateOpen}
        onClose={() => setEscalateOpen(false)}
        caseId={detail.id}
        caseLabel={detail.employeeIdentifier}
        onSuccess={() => {
          setEscalateOpen(false);
          setEscalateSuccessMsg('Case escalated — the specialist has been notified.');
        }}
      />

      {/* ── AIQ-1136: case-level reassign ── */}
      {reassignSuccessMsg && (
        <div className="fixed bottom-6 right-6 z-50 rounded-xl border border-[#bbf7d0] bg-[#f0fdf4] px-5 py-3 shadow-lg text-sm text-[#166534] font-medium">
          ✓ {reassignSuccessMsg}
          <Button unstyled type="button" aria-label="Dismiss notification" onClick={() => setReassignSuccessMsg('')} className="ml-3 text-[#16a34a] hover:text-[#166534]">✕</Button>
        </div>
      )}
      <ReassignCaseModal
        open={reassignOpen}
        onClose={() => setReassignOpen(false)}
        caseId={detail.id}
        caseLabel={detail.employeeIdentifier}
        onSuccess={() => {
          setReassignOpen(false);
          setReassignSuccessMsg('Case reassigned — the new owner now sees it in their command center.');
          void detailQuery.refetch();
        }}
      />
    </AppShell>
  );
};
