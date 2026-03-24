/**
 * Read-first HR draft review: document summary, readiness, signals, publishable rules, blockers, employee preview.
 * Data: GET /api/hr/policy-review (+ normalized version context for “live” state).
 */
import React, { useMemo } from 'react';
import { Card } from '../../components/antigravity';
import type { HrPolicyWorkspaceResolved } from './hrPolicyWorkspaceState';
import {
  buildOverrideRuleIdSet,
  confidencePercent,
  deriveReviewStatusBanner,
  employeeComparisonVisibilityLabel,
  type ReadinessSlice,
  formatDocumentTypeLabel,
  formatExclusionBusinessLine,
  formatBenefitRuleBusinessLine,
  formatIssueTierLabel,
  formatPolicyScopeLabel,
  formatProcessingStatusLabel,
  formatPublishabilityAssessment,
  formatReadinessIssueForDisplay,
  groupLayer2BenefitRules,
  groupLayer2Exclusions,
} from './hrPolicyReviewFormatters';

export type HrPolicyDraftReviewPanelProps = {
  policyReview: Record<string, unknown> | null;
  workspaceResolved: HrPolicyWorkspaceResolved;
  /** Latest version status from normalized payload (e.g. draft vs published). */
  versionStatus: string;
  reviewLoading?: boolean;
};

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

function TraceAmount(line: Record<string, unknown> | null | undefined): string {
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
  versionStatus,
  reviewLoading,
}) => {
  const readiness = pickReadiness(policyReview);
  const employeeVis = (policyReview?.employee_visibility || null) as Record<string, unknown> | null;
  const comparisonRule = (readiness?.comparison_rule_readiness || null) as Record<string, unknown> | null;
  const employeeSeesPublished = employeeVis?.employee_sees_published_policy_matrix === true;
  const comparisonReadyStrict = comparisonRule?.comparison_ready_strict as boolean | undefined;
  const comparisonReadinessStatus = (readiness?.comparison_readiness as ReadinessSlice | undefined)?.status;

  const banner = useMemo(
    () =>
      deriveReviewStatusBanner({
        phase: workspaceResolved.phase,
        comparisonSummary: workspaceResolved.comparisonSummary,
        comparisonReadyStrict,
        employeeSeesPublished,
      }),
    [
      workspaceResolved.phase,
      workspaceResolved.comparisonSummary,
      comparisonReadyStrict,
      employeeSeesPublished,
    ]
  );

  const visibility = useMemo(
    () =>
      employeeComparisonVisibilityLabel({
        employeeSeesPublished,
        comparisonReadinessStatus,
        comparisonReadyStrict,
      }),
    [employeeSeesPublished, comparisonReadinessStatus, comparisonReadyStrict]
  );

  const sourceDoc = (policyReview?.source_document || null) as Record<string, unknown> | null;
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

  const clauseCandidates = useMemo(() => {
    const raw = policyReview?.clause_candidates;
    return Array.isArray(raw) ? (raw as Array<Record<string, unknown>>) : [];
  }, [policyReview?.clause_candidates]);

  const draftRuleCandidates = useMemo(() => {
    const raw = policyReview?.draft_rule_candidates;
    return Array.isArray(raw) ? (raw as Array<Record<string, unknown>>) : [];
  }, [policyReview?.draft_rule_candidates]);

  const groupedPolicyItems = useMemo(() => {
    const raw = policyReview?.grouped_policy_items;
    return Array.isArray(raw) ? (raw as Array<Record<string, unknown>>) : [];
  }, [policyReview?.grouped_policy_items]);

  const comparisonSubrules = useMemo(() => {
    const raw = policyReview?.comparison_subrules;
    return Array.isArray(raw) ? (raw as Array<Record<string, unknown>>) : [];
  }, [policyReview?.comparison_subrules]);

  const layer2 = (policyReview?.layer2_publishable || null) as Record<string, unknown> | null;
  const benefitRules = useMemo(() => {
    const raw = layer2?.benefit_rules;
    return Array.isArray(raw) ? (raw as Array<Record<string, unknown>>) : [];
  }, [layer2?.benefit_rules]);
  const exclusions = useMemo(() => {
    const raw = layer2?.exclusions;
    return Array.isArray(raw) ? (raw as Array<Record<string, unknown>>) : [];
  }, [layer2?.exclusions]);

  const groupedBenefits = useMemo(() => groupLayer2BenefitRules(benefitRules), [benefitRules]);
  const groupedExcl = useMemo(() => groupLayer2Exclusions(exclusions), [exclusions]);

  const overrideIds = useMemo(() => buildOverrideRuleIdSet(policyReview?.hr_overrides), [policyReview?.hr_overrides]);

  const issues = useMemo(() => {
    const raw = policyReview?.issues;
    return Array.isArray(raw) ? (raw as Array<Record<string, unknown>>) : [];
  }, [policyReview?.issues]);

  const missingStructure = useMemo(() => {
    const raw = policyReview?.missing_structure;
    return Array.isArray(raw) ? (raw as Array<Record<string, unknown>>) : [];
  }, [policyReview?.missing_structure]);

  const entitlementPreview = useMemo(() => {
    const raw = policyReview?.entitlement_effective_preview;
    return Array.isArray(raw) ? (raw as Array<Record<string, unknown>>) : [];
  }, [policyReview?.entitlement_effective_preview]);

  const supportId =
    policyReview && typeof policyReview.support === 'object' && policyReview.support
      ? String((policyReview.support as { request_id?: string }).request_id || '').trim()
      : '';

  const versionLive = String(versionStatus || '').toLowerCase() === 'published';

  if (workspaceResolved.phase === 'no_policy') {
    return null;
  }

  return (
    <div className="space-y-6" id="hr-policy-draft-review">
      <div>
        <h2 className="text-lg font-semibold text-[#0b2b43]">Policy draft review</h2>
        <p className="text-sm text-[#6b7280] mt-1 max-w-3xl">
          Read this summary first, then use the benefit table below to edit. What you see here matches the latest save
          of this policy version.
        </p>
      </div>

      {reviewLoading && (
        <div className="rounded-lg border border-[#e5e7eb] p-4 animate-pulse space-y-3" role="status" aria-live="polite">
          <div className="h-4 bg-slate-200 rounded w-1/3" />
          <div className="h-20 bg-slate-100 rounded" />
          <div className="h-20 bg-slate-100 rounded" />
        </div>
      )}

      {/* 1 — Document summary */}
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

      {/* 2 — Review status banner */}
      <div className={`rounded-lg border px-4 py-3 ${bannerToneClasses(banner.tone)}`}>
        <div className="text-sm font-semibold">{banner.title}</div>
        <p className="text-sm mt-1 opacity-90 leading-relaxed">{banner.body}</p>
        {!versionLive && benefitRules.length > 0 && (
          <p className="text-xs mt-2 opacity-80">
            Working version status: <strong>Draft</strong> — not shown to employees until published.
          </p>
        )}
      </div>

      {/* 3 — Extracted policy signals */}
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

        {clauseCandidates.length === 0 && draftRuleCandidates.length === 0 && groupedPolicyItems.length === 0 && (
          <p className="text-sm text-[#6b7280]">
            No clause highlights or pre-rule items for this version—common for a baseline created without a source file.
          </p>
        )}
      </Card>

      {/* 4 — Publishable rules */}
      <Card padding="lg">
        <h3 className="text-sm font-semibold text-[#0b2b43] mb-2">Rules on this version</h3>
        <p className="text-xs text-[#6b7280] mb-4">
          Saved benefit and exclusion rows are what ReloPass uses when you publish. Tags show whether a row is still
          HR-only, included in the live policy, or adjusted by your overrides.
        </p>

        {groupedBenefits.length === 0 && groupedExcl.length === 0 ? (
          <p className="text-sm text-[#6b7280]">No benefit rules or exclusions on this version yet.</p>
        ) : (
          <div className="space-y-6">
            {groupedBenefits.map(({ key, label, rows }) => (
              <div key={key}>
                <div className="text-xs font-semibold text-[#0b2b43] mb-2">{label}</div>
                <ul className="space-y-2">
                  {rows.map((r) => {
                    const id = String(r.id ?? '');
                    const hasOverride = id && overrideIds.has(id);
                    const auto = r.auto_generated === true;
                    return (
                      <li
                        key={id || formatBenefitRuleBusinessLine(r)}
                        className="border border-[#e5e7eb] rounded-md p-3 text-sm bg-[#fafafa]"
                      >
                        <div className="flex flex-wrap gap-1.5 mb-1">
                          {!versionLive && (
                            <span className="text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded bg-amber-100 text-amber-900">
                              Draft only (not live)
                            </span>
                          )}
                          {versionLive && (
                            <span className="text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-900">
                              Publishable
                            </span>
                          )}
                          {auto && (
                            <span className="text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded bg-slate-200 text-slate-800">
                              From extraction
                            </span>
                          )}
                          {hasOverride && (
                            <span className="text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-900">
                              Effective after your adjustment
                            </span>
                          )}
                        </div>
                        <div className="text-[#111827]">{formatBenefitRuleBusinessLine(r)}</div>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}

            {groupedExcl.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-[#0b2b43] mb-2">Exclusions</div>
                <ul className="space-y-2">
                  {groupedExcl.flatMap((g) =>
                    g.rows.map((r) => (
                      <li
                        key={String(r.id ?? formatExclusionBusinessLine(r))}
                        className="border border-[#e5e7eb] rounded-md p-3 text-sm bg-[#fafafa]"
                      >
                        <div className="flex flex-wrap gap-1.5 mb-1">
                          {!versionLive && (
                            <span className="text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded bg-amber-100 text-amber-900">
                              Draft only (not live)
                            </span>
                          )}
                          {versionLive && (
                            <span className="text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-900">
                              Publishable
                            </span>
                          )}
                          {r.auto_generated === true && (
                            <span className="text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded bg-slate-200 text-slate-800">
                              From extraction
                            </span>
                          )}
                        </div>
                        <div className="text-[#111827]">{formatExclusionBusinessLine(r)}</div>
                      </li>
                    ))
                  )}
                </ul>
              </div>
            )}
          </div>
        )}
      </Card>

      {/* 5 — Missing structure / blockers */}
      <Card padding="lg">
        <h3 className="text-sm font-semibold text-[#0b2b43] mb-2">What to fix before going live</h3>
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
            <p className="text-sm text-[#6b7280]">No open checklist items for this version right now.</p>
          )
        )}
      </Card>

      {/* 6 — Employee visibility preview */}
      <Card padding="lg" className="bg-[#f8fafc] border-[#e2e8f0]" id="hr-policy-employee-visibility-preview">
        <h3 className="text-sm font-semibold text-[#0b2b43] mb-2">Employee visibility preview</h3>
        <div
          className={`rounded-md border px-3 py-2 mb-4 text-sm ${bannerToneClasses(
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
                            ? TraceAmount({ amount_value: hrOv.amount_value_override, currency: hrOv.currency_override, amount_unit: hrOv.amount_unit_override } as Record<string, unknown>)
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
      </Card>
    </div>
  );
};

function humanizeService(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
