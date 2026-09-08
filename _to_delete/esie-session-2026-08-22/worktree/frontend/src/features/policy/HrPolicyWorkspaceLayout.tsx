/**
 * HR Policy workspace — single operational surface: status → live → draft → preview → actions → (detail below).
 */
import React, { useState } from 'react';
import { Button, Card } from '../../components/antigravity';
import { AIQ1107_HIDE_SECTIONS } from './aiq1107Flags';
import type { HrPolicyLifecycleContext } from './hrPolicyLifecycle';
import {
  COMPARISON_SUMMARY_COPY,
  HrPolicyWorkspaceResolved,
} from './hrPolicyWorkspaceState';
import { comparisonBlockerMessage } from './comparisonBlockerCopy';
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
  onUploadDocument: () => void;
  onReviewDraft: () => void;
  onReviewDraftReplacement?: () => void;
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
  // AIQ-1600 / AIQ-1588: several props (lifecycle, documentsCount, loading,
  // reviewUnavailable, onReviewDraftReplacement, onScrollToStarterBaselines,
  // onRequestPublishPreflight, publishBusy, publishDataReady,
  // employeePreviewCompare, hasPublishedMatrix, and the starter-baseline props)
  // stay in the props type so callers compile unchanged, but are no longer
  // consumed here — the "What this means" card and the starter-baseline card
  // both moved out (the latter up to HrPolicyPageV2, AIQ-1588).
  resolved,
  onUploadDocument,
  onReviewDraft,
  onAdjustBenefits,
  onScrollToDraftReviewPanel,
}) => {
  const [showAllIssues, setShowAllIssues] = useState(false);
  const issueLimit = showAllIssues ? 50 : 3;
  const visibleIssues = resolved.highlightIssues.slice(0, issueLimit);

  return (
    <div className="space-y-6" data-hr-policy-workspace-layout>
      {/* AIQ-1600: the "What this means for employees" card was removed here per
          admin feedback (BUG-260718-C624). The sticky status strip + "Preview &
          compare" on the policy landing carry the at-a-glance signal; canonical
          publish stays reachable via the publish controls below. */}

      {/* AIQ-1588: the starter-baseline onboarding card moved up to
          HrPolicyPageV2 (one consolidated, config-matrix-seeding entry point,
          high on the page for first-time HR). */}

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
