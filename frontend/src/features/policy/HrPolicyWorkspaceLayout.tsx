/**
 * HR Policy workspace — single operational surface: status → live → draft → preview → actions → (detail below).
 */
import React, { useState } from 'react';
import { Alert, Button, Card } from '../../components/antigravity';
import { AIQ1107_HIDE_SECTIONS } from './aiq1107Flags';
import type { HrPolicyLifecycleContext } from './hrPolicyLifecycle';
import {
  COMPARISON_SUMMARY_COPY,
  HrPolicyWorkspaceResolved,
} from './hrPolicyWorkspaceState';
import { comparisonBlockerMessage } from './comparisonBlockerCopy';
import { StarterPolicyOnboardingCard } from './StarterPolicyOnboardingCard';
import type { StarterTemplateKey } from './starterPolicyCopy';
import type { EmployeePreviewCompareModel } from './hrPolicyEmployeePreviewCompare';

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

export const HrPolicyWorkspaceLayout: React.FC<HrPolicyWorkspaceLayoutProps> = ({
  // AIQ-1600: the "What this means for employees" card (impact summary, primary
  // CTA row, per-employee compare, replacement-draft warning) was removed per
  // admin feedback. The props that only fed that card (lifecycle,
  // documentsCount, loading, reviewUnavailable, onReviewDraftReplacement,
  // onScrollToStarterBaselines, onRequestPublishPreflight, publishBusy,
  // publishDataReady, employeePreviewCompare) stay in the props type so callers
  // compile unchanged, but are no longer consumed here.
  resolved,
  starterTemplateBusy,
  starterError,
  onSelectStarterTemplate,
  onUploadDocument,
  onReviewDraft,
  onAdjustBenefits,
  onScrollToDraftReviewPanel,
  hasPublishedMatrix = false,
}) => {
  // POLICY-UI/AIQ-1078: a matrix-published company with no canonical/document
  // policy resolves to phase `no_policy`. A live policy DOES exist (the matrix,
  // shown above), so suppress the onboarding "get started" framing here — the
  // "Create a new policy version" section above is the correct add-a-version path.
  const matrixOnlyLive = resolved.phase === 'no_policy' && hasPublishedMatrix;
  const [showAllIssues, setShowAllIssues] = useState(false);
  const issueLimit = showAllIssues ? 50 : 3;
  const visibleIssues = resolved.highlightIssues.slice(0, issueLimit);

  return (
    <div className="space-y-6" data-hr-policy-workspace-layout>
      {/* AIQ-1600: the "What this means for employees" card was removed here per
          admin feedback (BUG-260718-C624). The sticky status strip + "Preview &
          compare" on the policy landing carry the at-a-glance signal; canonical
          publish stays reachable via the publish controls below. */}

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
