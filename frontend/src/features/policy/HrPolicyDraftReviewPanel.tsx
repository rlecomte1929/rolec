/**
 * Read-first HR draft review: document summary, readiness, signals, publishable rules, blockers, employee preview.
 * Data: GET /api/hr/policy-review (+ normalized version context for “live” state).
 */
import React, { useMemo } from 'react';
import { Card } from '../../components/antigravity';
import { AIQ1107_HIDE_SECTIONS } from './aiq1107Flags';
import type { HrPolicyWorkspaceResolved } from './hrPolicyWorkspaceState';
import {
  confidencePercent,
  employeeComparisonVisibilityLabel,
  type ReadinessSlice,
  formatDocumentTypeLabel,
  formatIssueTierLabel,
  formatPolicyScopeLabel,
  formatProcessingStatusLabel,
  formatPublishabilityAssessment,
  formatReadinessIssueForDisplay,
} from './hrPolicyReviewFormatters';

export type HrPolicyDraftReviewPanelProps = {
  policyReview: Record<string, unknown> | null;
  workspaceResolved: HrPolicyWorkspaceResolved;
  /** Latest version status from normalized payload (e.g. draft vs published). */
  /** Reserved — was used by the dropped "Working version status: Draft"
   *  hint in the Review-status banner (see slice 3b). Kept on the props
   *  contract so call sites don't need to change. */
  versionStatus?: string;
  reviewLoading?: boolean;
};

type GroupedPolicyItem = { title?: string; summary?: string; source_ref?: string; canonical_key?: string; business_display?: string; grouped_item_id?: string; merged_draft_candidate_count?: number; [key: string]: unknown };
type ClauseCandidate = { clause_id?: string; confidence?: number; intent_category?: string; raw_text_preview?: string; service_match_candidate_benefit_key?: string; [key: string]: unknown };
type MissingStructureItem = { field?: string; issue?: string; [key: string]: unknown };
type EntitlementPreviewRow = { benefit_key?: string; benefit_rule_id?: string; [key: string]: unknown };
type DraftRuleCandidate = { candidate_category?: string; candidate_service_key?: string; clause_id?: string; confidence?: number; publishability_assessment?: string; source_excerpt?: string; [key: string]: unknown };

function pickReadiness(review: Record<string, unknown> | null): Record<string, unknown> | null {
  if (!review?.readiness || typeof review.readiness !== 'object') return null;
  return review.readiness as Record<string, unknown>;
}

function bannerToneClasses(tone: 'neutral' | 'warning' | 'success' | 'danger'): string {
  switch (tone) {
    case 'success':
      return 'bg-emerald-50 border-emerald-200 text-emerald-950';
    case 'warning':
      return 'bg-amber-50 border-amber-200 text-amber-950';
    case 'danger':
      return 'bg-red-50 border-red-200 text-red-950';
    default:
      return 'bg-slate-50 border-slate-200 text-slate-900';
  }
}

function TraceAmount(line: { amount_value?: string | number; currency?: string; amount_unit?: string } | null | undefined): string {
  if (!line) return '—';
  const v = line.amount_value;
  const c = line.currency;
  const u = line.amount_unit;
  const parts: string[] = [];
  if (v != null && v !== '') parts.push(`${c ? `${String(c)} ` : ''}${v}${u ? ` ${u}` : ''}`.trim());
  if (!parts.length) return '—';
  return parts.join(' ');
}

export const HrPolicyDraftReviewPanel: React.FC<HrPolicyDraftReviewPanelProps> = ({
  policyReview,
  workspaceResolved,
  versionStatus: _versionStatus,
  reviewLoading,
}) => {
  const readiness = pickReadiness(policyReview);
  const employeeVis = (policyReview?.employee_visibility || null) as Record<string, unknown> | null;
  const comparisonRule = (readiness?.comparison_rule_readiness || null) as Record<string, unknown> | null;
  const employeeSeesPublished = employeeVis?.employee_sees_published_policy_matrix === true;
  const comparisonReadyStrict = comparisonRule?.comparison_ready_strict as boolean | undefined;
  const comparisonReadinessStatus = (readiness?.comparison_readiness as ReadinessSlice | undefined)?.status;

  const visibility = useMemo(
    () =>
      employeeComparisonVisibilityLabel({
        employeeSeesPublished,
        comparisonReadinessStatus,
        comparisonReadyStrict,
      }),
    [employeeSeesPublished, comparisonReadinessStatus, comparisonReadyStrict]
  );

  const sourceDoc = (policyReview?.source_document || null) as { filename?: string; [key: string]: unknown } | null;
  const detected = (policyReview?.detected_classification || null) as Record<string, unknown> | null;
  const layer1 = (sourceDoc?.layer1 as Record<string, unknown> | undefined)?.classification as
    | Record<string, unknown>
    | undefined;

  const docFilename = sourceDoc?.filename != null ? String(sourceDoc.filename) : null;
  const docType =
    layer1?.detected_document_type ?? detected?.detected_document_type ?? sourceDoc?.detected_document_type;
  const docScope = layer1?.detected_policy_scope ?? detected?.detected_policy_scope ?? sourceDoc?.detected_policy_scope;
  const normDraftMeta =
    policyReview?.normalization_draft && typeof policyReview.normalization_draft === 'object'
      ? (policyReview.normalization_draft as { document_metadata?: { processing_status?: string } }).document_metadata
      : undefined;
  const processing = detected?.processing_status ?? sourceDoc?.processing_status ?? normDraftMeta?.processing_status;

  const clauseCandidates = useMemo<ClauseCandidate[]>(() => {
    const raw = policyReview?.clause_candidates;
    return Array.isArray(raw) ? (raw as ClauseCandidate[]) : [];
  }, [policyReview?.clause_candidates]);

  const draftRuleCandidates = useMemo<DraftRuleCandidate[]>(() => {
    const raw = policyReview?.draft_rule_candidates;
    return Array.isArray(raw) ? (raw as DraftRuleCandidate[]) : [];
  }, [policyReview?.draft_rule_candidates]);

  const groupedPolicyItems = useMemo<GroupedPolicyItem[]>(() => {
    const raw = policyReview?.grouped_policy_items;
    return Array.isArray(raw) ? (raw as GroupedPolicyItem[]) : [];
  }, [policyReview?.grouped_policy_items]);

  const comparisonSubrules = useMemo(() => {
    const raw = policyReview?.comparison_subrules;
    return Array.isArray(raw) ? (raw as Array<Record<string, unknown>>) : [];
  }, [policyReview?.comparison_subrules]);

  const issues = useMemo(() => {
    const raw = policyReview?.issues;
    return Array.isArray(raw) ? (raw as Array<Record<string, unknown>>) : [];
  }, [policyReview?.issues]);

  const missingStructure = useMemo<MissingStructureItem[]>(() => {
    const raw = policyReview?.missing_structure;
    return Array.isArray(raw) ? (raw as MissingStructureItem[]) : [];
  }, [policyReview?.missing_structure]);

  const entitlementPreview = useMemo<EntitlementPreviewRow[]>(() => {
    const raw = policyReview?.entitlement_effective_preview;
    return Array.isArray(raw) ? (raw as EntitlementPreviewRow[]) : [];
  }, [policyReview?.entitlement_effective_preview]);

  const supportId =
    policyReview && typeof policyReview.support === 'object' && policyReview.support
      ? String((policyReview.support as { request_id?: string }).request_id || '').trim()
      : '';

  // Slice 2 of the IA simplification gates the doc-only blocks. Matrix-only
  // deployments (no PDF uploaded, baseline created from a template) used to
  // see "No file linked", "No clause highlights or pre-rule items" — all dead
  // pixels. These blocks now collapse entirely when the underlying signals
  // are absent. Document-imported deployments still see them.
  const hasSourceDocument = Boolean(
    sourceDoc && (docFilename || docType || docScope || processing)
  );
  const hasExtractedSignals =
    clauseCandidates.length > 0 ||
    draftRuleCandidates.length > 0 ||
    groupedPolicyItems.length > 0;

  if (workspaceResolved.phase === 'no_policy') {
    return null;
  }

  return (
    <div className="space-y-6" id="hr-policy-draft-review">
      {reviewLoading && (
        <div className="rounded-lg border border-[#e5e7eb] p-4 animate-pulse space-y-3" role="status" aria-live="polite">
          <div className="h-4 bg-slate-200 rounded w-1/3" />
          <div className="h-20 bg-slate-100 rounded" />
          <div className="h-20 bg-slate-100 rounded" />
        </div>
      )}

      {/* What to fix before going live — promoted to top so the action list
          ranks above descriptive blocks. */}
      {/* AIQ-1107: hidden (reversible via aiq1107Flags) */}
      {!AIQ1107_HIDE_SECTIONS && (
      <Card padding="lg">
        <h3 className="text-sm font-semibold text-[#0b2b43] mb-2">Pre-publish checklist</h3>
        <p className="text-xs text-[#6b7280] mb-3">
          Plain-language items from readiness checks. Use them together with the workspace banner above.
        </p>
        {missingStructure.length > 0 && (
          <ul className="list-disc list-inside text-sm text-[#374151] space-y-1 mb-4">
            {missingStructure.map((m, i) => (
              <li key={i}>{String(m.issue || m.field || 'Structure gap')}</li>
            ))}
          </ul>
        )}
        {issues.length > 0 ? (
          <ul className="space-y-2">
            {issues.slice(0, 40).map((it, i) => (
              <li key={i} className="text-sm border-l-2 border-amber-300 pl-3 py-0.5">
                <span className="text-xs text-[#6b7280]">{formatIssueTierLabel(it.tier)}: </span>
                <span className="text-[#111827]">{formatReadinessIssueForDisplay(it)}</span>
              </li>
            ))}
          </ul>
        ) : (
          !missingStructure.length && (
            <p className="text-sm text-[#6b7280]">All checks passed — your policy is ready to publish.</p>
          )
        )}
      </Card>
      )}

      {/* Slice 3d wraps the doc-only blocks (Document summary + Extracted
          policy signals) in one shared <details>. Both are reference
          surfaces — useful for the audit case but noise during the fast
          "fix + publish" path. The disclosure only renders when at
          least one of them has data (matrix-only deployments collapse
          this section away entirely). */}
      {/* AIQ-1107: hidden (reversible via aiq1107Flags) */}
      {!AIQ1107_HIDE_SECTIONS && (hasSourceDocument || hasExtractedSignals) && (
      <details className="rounded-xl border border-[#e2e8f0] bg-white shadow-sm">
        <summary className="cursor-pointer list-none px-5 py-4 [&::-webkit-details-marker]:hidden">
          <div className="flex items-center justify-between gap-3">
            <span className="text-base font-semibold text-[#0b2b43]">
              ▸ See document-extraction signals
            </span>
            <span className="text-xs text-[#64748b]">
              {hasSourceDocument && 'source document'}
              {hasSourceDocument && hasExtractedSignals && ' · '}
              {hasExtractedSignals && 'extracted clauses'}
            </span>
          </div>
        </summary>
        <div className="px-5 pb-5 space-y-6">
      {/* 1 — Document summary (only when a source document is attached) */}
      {hasSourceDocument && (
      <Card padding="lg">
        <h3 className="text-sm font-semibold text-[#0b2b43] mb-3">Document summary</h3>
        <dl className="grid gap-3 sm:grid-cols-2 text-sm">
          <div>
            <dt className="text-[#6b7280]">Source document</dt>
            <dd className="text-[#111827] mt-0.5">
              {docFilename || 'No file linked (for example, a baseline created without an upload)'}
            </dd>
          </div>
          <div>
            <dt className="text-[#6b7280]">Detected type</dt>
            <dd className="text-[#111827] mt-0.5">{formatDocumentTypeLabel(docType)}</dd>
          </div>
          <div>
            <dt className="text-[#6b7280]">Detected scope</dt>
            <dd className="text-[#111827] mt-0.5">{formatPolicyScopeLabel(docScope)}</dd>
          </div>
          <div>
            <dt className="text-[#6b7280]">Processing status</dt>
            <dd className="text-[#111827] mt-0.5">{formatProcessingStatusLabel(processing)}</dd>
          </div>
        </dl>
        {supportId && (
          <div className="mt-4 pt-3 border-t border-[#e5e7eb] text-[11px] text-[#9ca3af] font-mono">
            Support reference: {supportId}
          </div>
        )}
      </Card>
      )}

      {/* Slice 3b removed the "Review status banner" here — its title +
          body restated information already shown in the workspace card
          ("What this means for employees") and the sticky status strip
          at the top of the page. The Draft-vs-Live distinction stays
          visible via the publishable-row tags below. */}

      {/* 3 — Extracted policy signals (only when extraction produced something) */}
      {hasExtractedSignals && (
      <Card padding="lg">
        <h3 className="text-sm font-semibold text-[#0b2b43] mb-2">Extracted policy signals</h3>
        <p className="text-xs text-[#6b7280] mb-4">
          Highlights from your file before they became benefit rows. Use them to confirm wording, then finish rules in
          the publishable section below.
        </p>

        {groupedPolicyItems.length > 0 && (
          <div className="mb-6">
            <div className="text-xs font-medium text-[#374151] mb-2">
              Grouped policy items ({groupedPolicyItems.length})
            </div>
            <p className="text-xs text-[#6b7280] mb-2 max-w-3xl">
              One row per business topic for HR review (tiers and variants stay nested). Atomic comparison pieces are
              derived separately when needed — see technical count below.
            </p>
            <div className="space-y-2 max-h-72 overflow-y-auto border border-[#e5e7eb] rounded-md divide-y divide-[#f3f4f6]">
              {groupedPolicyItems.slice(0, 40).map((g, i) => {
                const title = String(g.title || 'Policy item');
                const summary = String(g.summary || '').trim() || '—';
                const ref = g.source_ref != null && String(g.source_ref).trim() ? String(g.source_ref) : null;
                const ck = g.canonical_key != null ? String(g.canonical_key) : null;
                const merged = g.merged_draft_candidate_count;
                const display = g.business_display as Record<string, unknown> | undefined;
                const chips = Array.isArray(display?.variant_chips)
                  ? (display.variant_chips as string[]).slice(0, 8)
                  : [];
                const tierLines = Array.isArray(display?.tier_lines)
                  ? (display.tier_lines as string[]).slice(0, 8)
                  : [];
                return (
                  <div key={String(g.grouped_item_id ?? i)} className="p-3 text-sm bg-white">
                    <div className="flex flex-wrap gap-2 text-xs text-[#6b7280] mb-1">
                      {ck && (
                        <span className="px-1.5 py-0.5 rounded bg-slate-100 font-mono text-[10px]">{ck}</span>
                      )}
                      {ref && <span>Ref {ref}</span>}
                      {typeof merged === 'number' && merged > 1 && (
                        <span className="text-amber-800 bg-amber-50 px-1.5 py-0.5 rounded">
                          Merged {merged} draft rows
                        </span>
                      )}
                    </div>
                    <div className="text-sm font-medium text-[#0b2b43]">{title}</div>
                    <div className="text-[#374151] whitespace-pre-wrap text-xs leading-snug mt-1">{summary}</div>
                    {chips.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {chips.map((c) => (
                          <span
                            key={c}
                            className="text-[10px] px-1.5 py-0.5 rounded-full bg-[#f1f5f9] text-[#334155]"
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    )}
                    {tierLines.length > 0 && (
                      <ul className="mt-2 text-xs text-[#374151] list-disc list-inside">
                        {tierLines.map((line) => (
                          <li key={line}>{line}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}
            </div>
            {comparisonSubrules.length > 0 && (
              <p className="text-[11px] text-[#9ca3af] mt-2">
                Comparison engine subrules (derived): {comparisonSubrules.length} atomic piece
                {comparisonSubrules.length === 1 ? '' : 's'} — not shown as primary HR rows.
              </p>
            )}
          </div>
        )}

        {clauseCandidates.length > 0 && (
          <div className="mb-6">
            <div className="text-xs font-medium text-[#374151] mb-2">Clause highlights ({clauseCandidates.length})</div>
            <div className="space-y-2 max-h-72 overflow-y-auto border border-[#e5e7eb] rounded-md divide-y divide-[#f3f4f6]">
              {clauseCandidates.slice(0, 40).map((c, i) => {
                const excerpt = String(c.raw_text_preview || '').trim() || '—';
                const svc = c.service_match_candidate_benefit_key;
                const conf = confidencePercent(c.confidence);
                return (
                  <div key={String(c.clause_id ?? i)} className="p-3 text-sm bg-white">
                    <div className="flex flex-wrap gap-2 text-xs text-[#6b7280] mb-1">
                      {c.intent_category != null && (
                        <span className="px-1.5 py-0.5 rounded bg-slate-100">{String(c.intent_category)}</span>
                      )}
                      {conf && <span>Match strength: {conf}</span>}
                    </div>
                    {svc != null && svc !== '' && (
                      <div className="text-xs text-[#0b2b43] mb-1">
                        Suggested service: <span className="font-medium">{humanizeService(String(svc))}</span>
                      </div>
                    )}
                    <div className="text-[#374151] whitespace-pre-wrap text-xs leading-snug">{excerpt}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {draftRuleCandidates.length > 0 && (
          <div>
            <div className="text-xs font-medium text-[#374151] mb-2">
              Draft rule candidates ({draftRuleCandidates.length})
              {groupedPolicyItems.length > 0 && (
                <span className="font-normal text-[#6b7280] ml-1">— technical traces; prefer grouped items above</span>
              )}
            </div>
            <div className="space-y-2 max-h-80 overflow-y-auto border border-[#e5e7eb] rounded-md divide-y divide-[#f3f4f6]">
              {draftRuleCandidates.slice(0, 50).map((r, i) => {
                const excerpt = String(r.source_excerpt || '').trim() || '—';
                const svc = r.candidate_service_key;
                const conf = confidencePercent(r.confidence);
                const pub = formatPublishabilityAssessment(r.publishability_assessment);
                return (
                  <div key={String(r.clause_id ?? i)} className="p-3 text-sm bg-white">
                    <div className="text-xs text-[#6b7280] mb-1">{pub}</div>
                    <div className="flex flex-wrap gap-2 text-xs text-[#6b7280] mb-1">
                      {conf && <span>Match strength: {conf}</span>}
                      {r.candidate_category != null && r.candidate_category !== '' && (
                        <span className="px-1.5 py-0.5 rounded bg-slate-100">{String(r.candidate_category)}</span>
                      )}
                    </div>
                    {svc != null && svc !== '' && (
                      <div className="text-xs text-[#0b2b43] mb-1">
                        Suggested service: <span className="font-medium">{humanizeService(String(svc))}</span>
                      </div>
                    )}
                    <div className="text-[#374151] whitespace-pre-wrap text-xs leading-snug">{excerpt}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

      </Card>
      )}
        </div>
      </details>
      )}

      {/* Slice 3b removed the "Rules on this version" Card — it was a
          read-only restatement of every benefit + exclusion row, while
          the editable benefit table further down (the actual work
          surface in HrPolicyReviewWorkspace) shows the same rows with
          full per-row editing. Two cards for the same data was the
          biggest source of repetition on this page. */}

      {/* 5 — Employee visibility preview.
          Slice 3b collapses this by default. The 24-row baseline-vs-
          override-vs-effective grid is HR's per-employee audit; useful
          but not part of the fast "check + fix + publish" path. The
          headline banner stays visible so HR sees the visibility state
          at a glance and only expands the grid if they need the detail. */}
      {/* AIQ-1107: hidden (reversible via aiq1107Flags) */}
      {!AIQ1107_HIDE_SECTIONS && (
      <details
        className="bg-[#f8fafc] border border-[#e2e8f0] rounded-xl"
        id="hr-policy-employee-visibility-preview"
      >
        <summary className="cursor-pointer list-none px-5 py-4 [&::-webkit-details-marker]:hidden">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="text-sm font-semibold text-[#0b2b43] mb-2">Employee visibility preview</h3>
              <div
                className={`rounded-md border px-3 py-2 text-sm ${bannerToneClasses(
                  !employeeSeesPublished
                    ? 'neutral'
                    : workspaceResolved.comparisonSummary === 'full' && comparisonReadyStrict === true
                      ? 'success'
                      : workspaceResolved.comparisonSummary === 'partial'
                        ? 'warning'
                        : 'neutral'
                )}`}
              >
                <div className="font-medium">{visibility.headline}</div>
                <p className="text-xs mt-1 opacity-90">{visibility.detail}</p>
              </div>
            </div>
            <span className="text-xs text-[#64748b] shrink-0 mt-1">
              ▸ Show per-benefit detail
            </span>
          </div>
        </summary>

        <div className="px-5 pb-5">
        {entitlementPreview.length > 0 ? (
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {entitlementPreview.slice(0, 24).map((row, i) => {
              const bk = String(row.benefit_key || humanizeService(String(row.benefit_rule_id || i)));
              const baseline = row.baseline as Record<string, unknown> | undefined;
              const hrOv = row.hr_override as Record<string, unknown> | null | undefined;
              const effective = row.effective as Record<string, unknown> | undefined;
              const hasHrOverride =
                hrOv != null &&
                typeof hrOv === 'object' &&
                Object.values(hrOv).some((v) => v != null && v !== '');
              return (
                <div key={String(row.benefit_rule_id ?? i)} className="border border-[#e5e7eb] rounded-md p-3 bg-white text-sm">
                  <div className="font-medium text-[#0b2b43] mb-2">{humanizeService(bk)}</div>
                  <div className="text-xs text-[#6b7280] space-y-1">
                    <div>
                      As saved on the version: <span className="text-[#111827]">{TraceAmount(baseline)}</span>
                    </div>
                    {hasHrOverride && (
                      <div>
                        Your adjustment:{' '}
                        <span className="text-[#111827]">
                          {hrOv.amount_value_override != null
                            ? TraceAmount({ amount_value: hrOv.amount_value_override as string | number | undefined, currency: hrOv.currency_override as string | undefined, amount_unit: hrOv.amount_unit_override as string | undefined })
                            : 'Applied (see benefit table for detail)'}
                        </span>
                      </div>
                    )}
                    <div>
                      What employees would use if published:{' '}
                      <span className="text-[#111827] font-medium">{TraceAmount(effective)}</span>
                      {effective && effective.included === false && (
                        <span className="text-amber-800 ml-1">· Treated as not included</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-[#6b7280]">
            No row-by-row preview yet. When you add HR adjustments, they will show here with before and after context.
          </p>
        )}
        </div>
      </details>
      )}
    </div>
  );
};

function humanizeService(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
