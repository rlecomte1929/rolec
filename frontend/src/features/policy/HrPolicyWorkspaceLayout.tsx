/**
 * HR Policy workspace — single operational surface: status → live → draft → preview → actions → (detail below).
 */
import React, { useState } from 'react';
import { Alert, Button, Card } from '../../components/antigravity';
import { AIQ1107_HIDE_SECTIONS } from './aiq1107Flags';
import type { HrPolicyLifecycleContext } from './hrPolicyLifecycle';
import {
  COMPARISON_SUMMARY_COPY,
  HR_POLICY_WORKSPACE_COPY,
  HrPolicyWorkspaceResolved,
  deriveHrPolicyPrimaryAction,
} from './hrPolicyWorkspaceState';
import { publishImpactSentence } from './policyWorkflowCopy';
import { comparisonBlockerMessage } from './comparisonBlockerCopy';
import { StarterPolicyOnboardingCard } from './StarterPolicyOnboardingCard';
import type { StarterTemplateKey } from './starterPolicyCopy';
import type { EmployeePreviewCompareModel } from './hrPolicyEmployeePreviewCompare';
import { COMPARISON_TIER_HEADLINE } from './hrPolicyEmployeePreviewCompare';

export type HrPolicyWorkspaceLayoutProps = {
  resolved: HrPolicyWorkspaceResolved;
  lifecycle: HrPolicyLifecycleContext;
  documentsCount: number;
  loading: boolean;
  /**
   * POLICY-UI/AIQ-1078: true when a compensation-matrix policy is published
   * (GET /api/hr/policy-config/published). The workspace `phase` is derived
   * only from the canonical/document policy (company_policies), so a
   * matrix-only company resolves to `no_policy` and would otherwise render the
   * onboarding "get started" empty-state even though a live policy exists.
   */
  hasPublishedMatrix?: boolean;
  /** True after policy-review fetch failed (normalized may still load). */
  reviewUnavailable?: boolean;
  starterTemplateBusy: StarterTemplateKey | null;
  starterError: string | null;
  onSelectStarterTemplate: (key: StarterTemplateKey) => void | Promise<void>;
  onUploadDocument: () => void;
  onReviewDraft: () => void;
  onReviewDraftReplacement?: () => void;
  /** Scroll to standard baseline card (no-policy primary path). */
  onScrollToStarterBaselines?: () => void;
  onAdjustBenefits: () => void;
  /** Opens publish preflight modal (parent runs publish on confirm). */
  onRequestPublishPreflight?: () => void;
  publishBusy?: boolean;
  /** When false, Publish policy stays disabled (e.g. data still loading). */
  publishDataReady?: boolean;
  /** Side-by-side employee view; null when no company policy row. */
  employeePreviewCompare: EmployeePreviewCompareModel | null;
  onScrollToDraftReviewPanel?: () => void;
};

function Badge({
  children,
  tone = 'neutral',
}: {
  children: React.ReactNode;
  tone?: 'neutral' | 'success' | 'warning' | 'danger';
}) {
  const cls =
    tone === 'success'
      ? 'bg-emerald-50 text-emerald-900 border-emerald-200'
      : tone === 'warning'
        ? 'bg-amber-50 text-amber-900 border-amber-200'
        : tone === 'danger'
          ? 'bg-red-50 text-red-900 border-red-200'
          : 'bg-slate-100 text-slate-800 border-slate-200';
  return <span className={`text-xs font-medium px-2 py-0.5 rounded border ${cls}`}>{children}</span>;
}

function formatEntitlementRow(row: Record<string, unknown>): string {
  const rawSk = row.service_key ?? row.canonical_service_key ?? row.benefit_key;
  const sk = typeof rawSk === 'string' ? rawSk : null;
  const rawLabel = row.label ?? row.summary ?? row.service_label;
  const label = typeof rawLabel === 'string' ? rawLabel : sk;
  const rawCap = row.numeric_max ?? row.max_value ?? row.standard_value;
  const cap: string | number | null =
    typeof rawCap === 'number' || typeof rawCap === 'string' ? rawCap : null;
  const cur = typeof row.currency === 'string' ? row.currency : 'USD';
  const parts = [label, cap != null ? `${cur} ${cap}` : null].filter((v): v is string => v != null && v !== '');
  return parts.join(' · ') || (sk ?? 'Benefit');
}

function EmployeeViewComparePanels({
  model,
  loading,
}: {
  model: EmployeePreviewCompareModel;
  loading: boolean;
}) {
  const Panel = ({
    label,
    panel,
    testId,
  }: {
    label: string;
    panel: EmployeePreviewCompareModel['current'];
    testId: string;
  }) => (
    <div
      className="rounded-lg border border-[#e5e7eb] bg-white p-4 min-h-[140px]"
      data-testid={testId}
    >
      <div className="text-xs font-semibold uppercase tracking-wide text-[#64748b] mb-2">{label}</div>
      <div className="flex flex-wrap gap-2 mb-2">
        <Badge tone={panel.policyVisibleToEmployees ? 'success' : 'neutral'}>
          {panel.policyVisibleToEmployees ? 'Visible to employees' : 'Not visible to employees yet'}
        </Badge>
        <Badge
          tone={
            panel.tier === 'full' ? 'success' : panel.tier === 'partial' ? 'warning' : 'neutral'
          }
        >
          {COMPARISON_TIER_HEADLINE[panel.tier]}
        </Badge>
      </div>
      <p className="text-xs text-[#6b7280] mb-2">{panel.visibilityLine}</p>
      <p className="text-sm text-[#374151] mb-2">{panel.summaryLine}</p>
      <p className="text-xs text-[#4b5563] mb-2">{panel.tierBody}</p>
      {panel.previewRows.length > 0 ? (
        <ul className="space-y-1 text-sm text-[#374151] border-t border-[#f3f4f6] pt-2 mt-2">
          {panel.previewRows.map((row, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-[#9ca3af]">•</span>
              <span>{formatEntitlementRow(row)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-[#9ca3af] italic mt-1">No sample rows shown.</p>
      )}
    </div>
  );

  if (loading) {
    return (
      <div
        className="grid md:grid-cols-2 gap-4 animate-pulse"
        data-testid="hr-policy-employee-compare-loading"
        aria-busy="true"
      >
        <div className="h-48 rounded-lg bg-slate-100 border border-slate-200" />
        <div className="h-48 rounded-lg bg-slate-100 border border-slate-200" />
      </div>
    );
  }

  return (
    <div
      className={`grid gap-4 ${model.showFuturePanel ? 'md:grid-cols-2' : 'md:grid-cols-1 max-w-xl'}`}
      data-testid="hr-policy-employee-compare"
    >
      <Panel label="Current employee view" panel={model.current} testId="hr-policy-panel-current-employee" />
      {model.showFuturePanel && model.future && (
        <Panel label="If you publish this draft" panel={model.future} testId="hr-policy-panel-if-publish" />
      )}
    </div>
  );
}

export const HrPolicyWorkspaceLayout: React.FC<HrPolicyWorkspaceLayoutProps> = ({
  resolved,
  lifecycle,
  documentsCount,
  loading,
  reviewUnavailable = false,
  starterTemplateBusy,
  starterError,
  onSelectStarterTemplate,
  onUploadDocument,
  onReviewDraft,
  onReviewDraftReplacement,
  onScrollToStarterBaselines,
  onAdjustBenefits,
  onRequestPublishPreflight,
  publishBusy = false,
  publishDataReady = true,
  employeePreviewCompare,
  onScrollToDraftReviewPanel,
  hasPublishedMatrix = false,
}) => {
  // POLICY-UI/AIQ-1078: a matrix-published company with no canonical/document
  // policy resolves to phase `no_policy`. A live policy DOES exist (the matrix,
  // shown above), so suppress the onboarding "get started" framing here — the
  // "Create a new policy version" section above is the correct add-a-version path.
  const matrixOnlyLive = resolved.phase === 'no_policy' && hasPublishedMatrix;
  const copy = matrixOnlyLive
    ? {
        headline: 'Your compensation matrix is live',
        subline:
          'Employees already see your published matrix policy (shown above). There’s no separate document-based policy version here yet — use “Create a new policy version” above only if you want to add one.',
      }
    : HR_POLICY_WORKSPACE_COPY[resolved.phase];
  const primaryAction = deriveHrPolicyPrimaryAction(resolved);
  const [showAllIssues, setShowAllIssues] = useState(false);
  const issueLimit = showAllIssues ? 50 : 3;
  const visibleIssues = resolved.highlightIssues.slice(0, issueLimit);


  const renderPrimaryCta = () => {
    switch (primaryAction) {
      case 'start_baseline_or_upload':
        return (
          <Button
            onClick={onScrollToStarterBaselines ?? onUploadDocument}
            disabled={starterTemplateBusy !== null}
          >
            Choose a standard baseline
          </Button>
        );
      case 'review_draft':
        return (
          <Button onClick={onReviewDraft} disabled={loading}>
            Review draft
          </Button>
        );
      case 'publish':
        return (
          <Button
            onClick={() => onRequestPublishPreflight?.()}
            disabled={publishBusy || loading || !publishDataReady || !onRequestPublishPreflight}
          >
            {publishBusy ? 'Publishing…' : 'Publish policy'}
          </Button>
        );
      case 'review_replacement_draft':
        return (
          <Button onClick={onReviewDraftReplacement ?? onReviewDraft} disabled={loading}>
            Review new draft
          </Button>
        );
      case 'adjust_values':
      default:
        return (
          <Button onClick={onAdjustBenefits} disabled={loading}>
            Adjust policy values
          </Button>
        );
    }
  };

  return (
    <div className="space-y-6" data-hr-policy-workspace-layout>
      {/* A — Status + next step.
          Slice 3c collapses the previous 5-in-1 into one tight module
          that answers the only question HR opens this card to ask:
          "if I publish right now, what changes for employees?"
          The detail surfaces (per-employee compare, visibility rules)
          stay one click away via <details>. */}
      <Card padding="lg" className="border-[#0b2b43]/12">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-[#0b2b43]">What this means for employees</h2>
            <p className="text-sm text-[#4b5563] mt-1 max-w-3xl">{copy.headline}</p>
          </div>
          {loading && (
            <span className="text-sm text-[#6b7280]" role="status" aria-live="polite">
              Updating…
            </span>
          )}
        </div>

        {/* Phase-aware impact summary — derived from existing fields,
            no new API call. The number-laden version
            ("change 12 caps, add 1 benefit, no impact for DE/FR") needs
            a per-jurisdiction breakdown from the backend; that's queued
            as a follow-up. For now, lean on the existing copy + a
            count-based hint from highlightIssues. */}
        {!loading && (
          <p className="text-sm text-[#374151] mt-3 leading-relaxed">
            <strong className="text-[#0b2b43]">If you publish right now:</strong>{' '}
            {publishImpactSentence(resolved, lifecycle)}
          </p>
        )}

        {resolved.phase === 'no_policy' && documentsCount > 0 && (
          <p className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 mt-3">
            You have {documentsCount} uploaded file{documentsCount === 1 ? '' : 's'}—finish processing in{' '}
            <strong>Documents &amp; processing</strong> above, then return here.
          </p>
        )}

        {reviewUnavailable && resolved.phase !== 'no_policy' && (
          <Alert variant="info" className="mt-3">
            The detailed policy review summary could not be loaded. You can still use the benefit table and publish
            controls below—try refreshing if this persists.
          </Alert>
        )}

        {resolved.hasUnpublishedDraftAhead && lifecycle.draftReplacement && (
          <div data-testid="hr-policy-replacement-warning" className="mt-3">
            <Alert variant="warning">
              <div className="space-y-1">
                <strong className="text-[#92400e]">{lifecycle.draftReplacement.title}</strong>
                {lifecycle.draftReplacement.versionLabel && (
                  <span className="text-xs text-[#78350f] ml-2">({lifecycle.draftReplacement.versionLabel})</span>
                )}
                <p className="text-sm text-[#78350f] mt-1">{lifecycle.draftReplacement.body}</p>
              </div>
            </Alert>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-3">
          {/* AIQ-1078: when the matrix is already live, the no_policy onboarding
              CTAs ("Start from a baseline" / "Upload company policy") duplicate
              the "Create a new policy version" section above and re-introduce the
              misleading first-run framing — suppress them here. */}
          {!matrixOnlyLive && renderPrimaryCta()}
          {!matrixOnlyLive && primaryAction === 'start_baseline_or_upload' && (
            <Button variant="outline" onClick={onUploadDocument} disabled={starterTemplateBusy !== null}>
              Upload company policy
            </Button>
          )}
          {primaryAction === 'review_draft' && (
            <Button variant="outline" onClick={onUploadDocument}>
              Upload a different file
            </Button>
          )}
          {primaryAction === 'publish' && (
            <Button variant="outline" onClick={onAdjustBenefits} disabled={loading}>
              Adjust benefits first
            </Button>
          )}
          {primaryAction === 'review_replacement_draft' && (
            <>
              <Button variant="outline" onClick={onAdjustBenefits} disabled={loading}>
                Adjust live policy
              </Button>
              <Button variant="outline" onClick={onUploadDocument}>
                Upload another file
              </Button>
            </>
          )}
          {primaryAction === 'adjust_values' && (
            <Button variant="outline" onClick={onUploadDocument} disabled={loading}>
              Upload newer policy
            </Button>
          )}
        </div>

        {/* Per-employee compare → audit case, hidden by default. */}
        {employeePreviewCompare && (
          <details className="mt-4 border border-[#e5e7eb] rounded-lg bg-[#fafbfc]">
            <summary className="cursor-pointer list-none px-4 py-2.5 text-sm font-medium text-[#0b2b43] [&::-webkit-details-marker]:hidden">
              ▸ Show what each employee would see (today vs if you publish)
            </summary>
            <div className="px-4 pb-4">
              <EmployeeViewComparePanels model={employeePreviewCompare} loading={loading} />
            </div>
          </details>
        )}

        {/* Visibility rules + version-history hint → reference content,
            hidden by default. The headline + impact sentence above
            already tell HR what they need to act. */}
        <details className="mt-3">
          <summary className="cursor-pointer list-none text-xs text-[#64748b] hover:text-[#0b2b43] [&::-webkit-details-marker]:hidden">
            ▸ How visibility works
          </summary>
          <div className="mt-2 border-t border-[#e5e7eb] pt-3">
            <ul className="text-xs text-[#64748b] space-y-1 list-disc list-inside">
              {lifecycle.employeeVisibilityLines.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
            {lifecycle.templateUploadHint && (
              <p className="text-xs text-[#4b5563] mt-2">{lifecycle.templateUploadHint}</p>
            )}
            <p className="text-xs text-[#9ca3af] mt-2">{lifecycle.versionHistoryHint}</p>
          </div>
        </details>
      </Card>

      {/* Starter onboarding (no policy) — primary path. AIQ-1078: hidden when a
          matrix policy is already live (the "Create a new policy version"
          section above is the correct add-a-version entry point in that case). */}
      {resolved.phase === 'no_policy' && !matrixOnlyLive && (
        <div id="hr-policy-starter-onboarding" className="scroll-mt-4">
          <StarterPolicyOnboardingCard
            error={starterError}
            busyTemplateKey={starterTemplateBusy}
            onSelectTemplate={onSelectStarterTemplate}
            onUploadDocument={onUploadDocument}
          />
        </div>
      )}

      {starterError && resolved.phase !== 'no_policy' && <Alert variant="error">{starterError}</Alert>}

      {/* B — Live policy detail */}
      {(resolved.phase === 'published' || resolved.publishedVersionNumber != null) && (
        <Card padding="lg">
          <h3 className="text-sm font-semibold text-[#0b2b43] mb-2">Active policy (live)</h3>
          {resolved.publishedTitle || resolved.publishedVersionNumber != null ? (
            <div className="text-sm text-[#374151] space-y-1">
              <div>
                <span className="text-[#6b7280]">Title: </span>
                {resolved.publishedTitle || '—'}
              </div>
              {resolved.publishedVersionNumber != null && (
                <div>
                  <span className="text-[#6b7280]">Live version: </span>
                  {resolved.publishedVersionNumber}
                </div>
              )}
              <div className="mt-3">
                <span className="text-[#6b7280] block mb-1">Cost comparison (published)</span>
                <p className="text-[#374151]">{COMPARISON_SUMMARY_COPY[resolved.comparisonSummary]}</p>
                {resolved.comparisonBlockers.length > 0 && (
                  <ul className="list-disc list-inside text-xs text-[#6b7280] mt-2">
                    {/* TASK-004: render an HR-facing message, never the raw
                        internal blocker code (e.g. MISSING_COMPARISON_CATEGORY:shipment). */}
                    {resolved.comparisonBlockers.slice(0, 6).map((b) => (
                      <li key={b}>{comparisonBlockerMessage(b)}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-[#6b7280]">No published version yet.</p>
          )}
        </Card>
      )}

      {/* C — Working draft (compact; full checklist in Policy draft review below) */}
      {(resolved.phase === 'draft_not_publishable' ||
        resolved.phase === 'ready_to_publish' ||
        resolved.hasUnpublishedDraftAhead) && (
        <Card padding="lg" id="hr-policy-draft-panel" className="scroll-mt-4">
          <h3 className="text-sm font-semibold text-[#0b2b43] mb-2">
            {resolved.hasUnpublishedDraftAhead ? 'Replacement draft (not live)' : 'Working draft'}
          </h3>
          <div className="text-sm text-[#4b5563] space-y-2">
            {resolved.draftVersionNumber != null && (
              <div>
                <span className="text-[#6b7280]">Working version: </span>
                {resolved.draftVersionNumber}
              </div>
            )}
            <div>
              <span className="text-[#6b7280]">Benefit rules: </span>
              {resolved.benefitRuleCount}
              <span className="text-[#6b7280] ml-3">Exclusions: </span>
              {resolved.exclusionCount}
            </div>
          </div>

          {resolved.highlightIssues.length > 0 && (
            <div className="mt-3">
              <div className="text-xs font-medium text-[#6b7280] mb-1">
                Open items ({resolved.highlightIssues.length}) — first {Math.min(3, resolved.highlightIssues.length)}
              </div>
              <ul className="list-disc list-inside text-sm text-[#374151] space-y-1">
                {visibleIssues.map((it, idx) => (
                  <li key={idx}>{it.message}</li>
                ))}
              </ul>
              {resolved.highlightIssues.length > 3 && (
                <Button unstyled
                  type="button"
                  className="text-xs text-[#059669] hover:underline mt-2"
                  onClick={() => setShowAllIssues(!showAllIssues)}
                >
                  {showAllIssues ? 'Show fewer' : `Show all (${resolved.highlightIssues.length})`}
                </Button>
              )}
              {onScrollToDraftReviewPanel && (
                <Button unstyled
                  type="button"
                  className="block text-xs text-[#0b2b43] font-medium hover:underline mt-2"
                  onClick={onScrollToDraftReviewPanel}
                >
                  Open full draft review ↓
                </Button>
              )}
            </div>
          )}

          {resolved.draftRuleCandidatesCount > 0 && (
            <p className="text-xs text-[#6b7280] mt-3">
              {resolved.draftRuleCandidatesCount} item{resolved.draftRuleCandidatesCount === 1 ? '' : 's'} pulled from
              your document before they became rules — expand in{' '}
              <strong>Policy draft review</strong> below if needed.
            </p>
          )}

          {resolved.hasUnpublishedDraftAhead && (
            <p className="text-xs text-[#6b7280] mt-3">
              When ready, use <strong>Publish version</strong> in publish controls below to make this draft live.
            </p>
          )}
        </Card>
      )}

      {/* D — Secondary actions only (primary is in at-a-glance) */}
      {/* AIQ-1107: hidden (reversible via aiq1107Flags) */}
      {!AIQ1107_HIDE_SECTIONS && resolved.phase !== 'no_policy' && (
        <Card padding="lg" className="border-dashed border-[#cbd5e1] bg-[#f8fafc]">
          <h3 className="text-sm font-semibold text-[#0b2b43] mb-2">More actions</h3>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={onUploadDocument}>
              Documents &amp; upload
            </Button>
            <Button variant="outline" size="sm" onClick={onReviewDraft}>
              Jump to benefit table
            </Button>
            {resolved.phase === 'published' && (
              <Button variant="outline" size="sm" onClick={onAdjustBenefits}>
                Edit benefits
              </Button>
            )}
          </div>
        </Card>
      )}
    </div>
  );
};
