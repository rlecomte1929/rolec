/**
 * Business-language helpers for GET /api/hr/policy-review payloads.
 * Prefer backend `message` strings; codes/tiers are mapped, not shown raw to HR.
 */

import type { HrPolicyComparisonSummary, HrPolicyWorkspacePhase } from './hrPolicyWorkspaceState';
import { POLICY_TOPIC_LABELS, POLICY_TOPIC_ORDER } from './policyTopicLabels';

export type ReadinessSlice = { status?: string; issues?: Array<{ code?: string; message?: string; field?: string }> };

export type HrPolicyReviewIssue = {
  tier?: string;
  code?: string;
  message?: string;
  field?: string;
};

const DOC_TYPE_LABELS: Record<string, string> = {
  assignment_policy: 'Assignment policy',
  policy_summary: 'Policy summary',
  tax_policy: 'Tax policy',
  country_addendum: 'Country addendum',
  starter_template: 'Platform starter baseline',
  unknown: 'Unknown document type',
};

const SCOPE_LABELS: Record<string, string> = {
  long_term_assignment: 'Long-term assignment',
  short_term_assignment: 'Short-term assignment',
  global: 'Global / all scopes',
  mixed: 'Mixed scopes',
  tax_equalization: 'Tax equalization',
  unknown: 'Scope not determined',
};

const PROCESSING_LABELS: Record<string, string> = {
  pending: 'Queued',
  processing: 'Processing',
  complete: 'Complete',
  failed: 'Failed',
  unknown: 'Unknown',
};

const PUBLISHABILITY_LABELS: Record<string, string> = {
  draft_only: 'Still in draft—not saved as a live rule row yet',
  publish_benefit_rule: 'Ready to save as a benefit rule on this version',
  publish_benefit_rule_with_conditions: 'Benefit rule with conditions—review before publish',
  publish_exclusion: 'Ready to save as an exclusion',
  publish_evidence_requirement: 'Evidence requirement—confirm before publish',
};

/** Issue codes → short HR-facing hints when `message` is missing. */
const ISSUE_CODE_HINTS: Record<string, string> = {
  ONLY_SUMMARY_LEVEL_SIGNALS:
    'This file reads like a summary. Add dollar limits in the table or upload a fuller policy so ReloPass can capture caps.',
  NO_PUBLISHABLE_BENEFITS_OR_EXCLUSIONS:
    'No benefit or exclusion rows are saved on this version yet—finish building them from the document or add them manually, then try publishing again.',
  NO_STRUCTURED_LIMITS: 'Some services still need a clear cap, unit, or currency before cost comparison can run.',
  COVERAGE_ONLY_NO_CAPS: 'Coverage is described, but numeric limits are missing for important services.',
  NO_CANONICAL_SERVICE_MATCH: 'Some text did not map cleanly to a standard service name—pick or edit the service in the table.',
  READY_FOR_DRAFT_ONLY: 'Draft is saved; finish the checklist so employees can rely on the published version.',
  READY_FOR_PUBLISH: 'Publishing checks passed for this version.',
  READY_FOR_COMPARISON: 'Cost comparison has the structure it needs for this version.',
  SOURCE_DOCUMENT_FAILED: 'The source file did not finish processing—re-upload or re-run processing, then build the policy again.',
  APPLICABILITY_INSUFFICIENT: 'Say who the rules apply to (assignment type or eligibility) so employee views stay accurate.',
  MISSING_DOCUMENT_TYPE: 'Document type was not detected—confirm the type in Documents & processing or re-run processing.',
  MISSING_SCOPE: 'Who the policy applies to (scope) is unclear—confirm in the document summary or adjust manually.',
  COMPARISON_RULES_NOT_STRICT_READY: 'A few rules still need clearer limits before full side-by-side cost comparison turns on.',
};

const TIER_LABELS: Record<string, string> = {
  normalization_readiness: 'Policy structure',
  publish_readiness: 'Publishing',
  comparison_readiness: 'Employee cost comparison',
  comparison_rule_readiness: 'Comparison rules',
  normalization_gate: 'Policy build',
  draft_normalization_readiness: 'Draft — policy structure',
  draft_publish_readiness: 'Draft — publishing',
  draft_comparison_readiness: 'Draft — cost comparison',
};

function normKey(s: unknown): string {
  return String(s ?? '')
    .trim()
    .toLowerCase();
}

export function formatDocumentTypeLabel(raw: unknown): string {
  const k = normKey(raw).replace(/-/g, '_');
  if (!k) return '—';
  return DOC_TYPE_LABELS[k] || humanizeToken(k);
}

export function formatPolicyScopeLabel(raw: unknown): string {
  const k = normKey(raw).replace(/-/g, '_');
  if (!k || k === 'unknown') return SCOPE_LABELS.unknown;
  return SCOPE_LABELS[k] || humanizeToken(k);
}

export function formatProcessingStatusLabel(raw: unknown): string {
  const k = normKey(raw);
  if (!k) return '—';
  return PROCESSING_LABELS[k] || humanizeToken(k);
}

function humanizeToken(s: string): string {
  return s
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export function formatPublishabilityAssessment(raw: unknown): string {
  const k = normKey(raw).replace(/-/g, '_');
  if (!k) return 'Under review';
  return PUBLISHABILITY_LABELS[k] || humanizeToken(k);
}

export function formatReadinessIssueForDisplay(issue: HrPolicyReviewIssue): string {
  const msg = String(issue.message || '').trim();
  if (msg) return msg;
  const code = String(issue.code || '').trim();
  if (code && ISSUE_CODE_HINTS[code]) return ISSUE_CODE_HINTS[code];
  if (code) return humanizeToken(code);
  return 'Review this item in the draft or benefit table.';
}

export function formatIssueTierLabel(tier: unknown): string {
  const k = String(tier || '').trim();
  if (!k) return 'Review';
  if (TIER_LABELS[k]) return TIER_LABELS[k];
  if (k.startsWith('draft_')) {
    const rest = k.slice('draft_'.length);
    return TIER_LABELS[rest] ? `Draft — ${TIER_LABELS[rest]}` : humanizeToken(k);
  }
  return humanizeToken(k);
}

export type ReviewStatusBannerKind =
  | 'draft_needs_review'
  | 'ready_to_publish'
  | 'published_partial_comparison'
  | 'published_comparison_ready'
  | 'published_informational';

export type ReviewStatusBannerModel = {
  kind: ReviewStatusBannerKind;
  title: string;
  body: string;
  tone: 'neutral' | 'warning' | 'success' | 'danger';
};

/**
 * Maps workspace phase + comparison summary + strict rule readiness into the four UX states requested.
 */
export function deriveReviewStatusBanner(args: {
  phase: HrPolicyWorkspacePhase;
  comparisonSummary: HrPolicyComparisonSummary;
  comparisonReadyStrict: boolean | null | undefined;
  employeeSeesPublished: boolean;
}): ReviewStatusBannerModel {
  const { phase, comparisonSummary, comparisonReadyStrict, employeeSeesPublished } = args;

  if (!employeeSeesPublished) {
    if (phase === 'ready_to_publish') {
      return {
        kind: 'ready_to_publish',
        title: 'Ready to go live',
        body: 'ReloPass checks passed. Publishing is the step that puts these benefits on employee assignments (within eligibility).',
        tone: 'success',
      };
    }
    return {
      kind: 'draft_needs_review',
      title: 'Draft—not live for employees yet',
      body: 'Review the summary and checklist below, fix gaps in the benefit table, then publish when this page shows ready.',
      tone: 'warning',
    };
  }

  const strictOk = comparisonReadyStrict === true;
  if (comparisonSummary === 'full' && strictOk) {
    return {
      kind: 'published_comparison_ready',
      title: 'Live—cost comparison on',
      body: 'Employees see this published policy, and limits are defined well enough for automated comparison on supported services.',
      tone: 'success',
    };
  }
  if (comparisonSummary === 'partial' || !strictOk) {
    return {
      kind: 'published_partial_comparison',
      title: 'Live—comparison partly on',
      body: 'Employees see this policy; some rows support full cost comparison, others stay descriptive until you finish a few limits.',
      tone: 'warning',
    };
  }
  return {
    kind: 'published_informational',
    title: 'Live—overview style view',
    body: 'Employees see benefits from the published policy; side-by-side cost comparison stays limited until required caps and categories are complete.',
    tone: 'neutral',
  };
}

export function confidencePercent(raw: unknown): string | null {
  if (raw == null || raw === '') return null;
  const n = typeof raw === 'number' ? raw : parseFloat(String(raw));
  if (Number.isNaN(n)) return null;
  const pct = n <= 1 && n >= 0 ? Math.round(n * 100) : Math.round(Math.min(100, Math.max(0, n)));
  return `${pct}%`;
}

export function groupLayer2BenefitRules(rules: Array<Record<string, unknown>>): Array<{ key: string; label: string; rows: typeof rules }> {
  const by: Record<string, typeof rules> = {};
  for (const r of rules) {
    const cat = String(r.benefit_category || r.domain || 'misc').trim() || 'misc';
    if (!by[cat]) by[cat] = [];
    by[cat].push(r);
  }
  const ordered: string[] = [];
  for (const k of POLICY_TOPIC_ORDER) {
    if (by[k]?.length) ordered.push(k);
  }
  for (const k of Object.keys(by)) {
    if (!ordered.includes(k)) ordered.push(k);
  }
  return ordered.map((key) => ({
    key,
    label: POLICY_TOPIC_LABELS[key] || humanizeToken(key),
    rows: by[key] || [],
  }));
}

export function groupLayer2Exclusions(exclusions: Array<Record<string, unknown>>): Array<{ key: string; label: string; rows: typeof exclusions }> {
  const by: Record<string, typeof exclusions> = {};
  for (const r of exclusions) {
    const dom = String(r.domain || 'misc').trim() || 'misc';
    if (!by[dom]) by[dom] = [];
    by[dom].push(r);
  }
  const keys = Object.keys(by).sort((a, b) => {
    const ia = POLICY_TOPIC_ORDER.indexOf(a);
    const ib = POLICY_TOPIC_ORDER.indexOf(b);
    if (ia === -1 && ib === -1) return a.localeCompare(b);
    if (ia === -1) return 1;
    if (ib === -1) return -1;
    return ia - ib;
  });
  return keys.map((key) => ({
    key,
    label: POLICY_TOPIC_LABELS[key] || humanizeToken(key),
    rows: by[key] || [],
  }));
}

export function buildOverrideRuleIdSet(hrOverrides: unknown): Set<string> {
  const set = new Set<string>();
  if (!Array.isArray(hrOverrides)) return set;
  for (const o of hrOverrides) {
    if (o && typeof o === 'object' && 'benefit_rule_id' in o && (o as { benefit_rule_id?: string }).benefit_rule_id) {
      set.add(String((o as { benefit_rule_id: string }).benefit_rule_id));
    }
  }
  return set;
}

export function employeeComparisonVisibilityLabel(args: {
  employeeSeesPublished: boolean;
  comparisonReadinessStatus: unknown;
  comparisonReadyStrict: boolean | null | undefined;
}): { headline: string; detail: string } {
  const { employeeSeesPublished, comparisonReadinessStatus, comparisonReadyStrict } = args;
  const st = normKey(comparisonReadinessStatus);
  if (!employeeSeesPublished) {
    return {
      headline: 'Not live for employees yet',
      detail: 'Nothing from this working copy appears on assignments until you publish a version.',
    };
  }
  if (st === 'ready' && comparisonReadyStrict === true) {
    return {
      headline: 'Cost comparison is on',
      detail: 'Published limits are clear enough for ReloPass to compare employee costs to the policy on supported services.',
    };
  }
  if (st === 'partial') {
    return {
      headline: 'Cost comparison is partly on',
      detail: 'Some services support full comparison; others show text or partial numbers until limits are finished.',
    };
  }
  return {
    headline: 'Overview-style view for employees',
    detail: 'Employees see policy benefits; automated cost comparison waits on a few clearer caps and categories.',
  };
}

export function formatBenefitRuleBusinessLine(rule: Record<string, unknown>): string {
  const desc = String(rule.description || '').trim();
  const bk = String(rule.benefit_key || '').trim();
  const parts: string[] = [];
  if (desc) parts.push(desc);
  else if (bk) parts.push(humanizeToken(bk.replace(/_/g, ' ')));
  const amt = rule.amount_value;
  const cur = rule.currency;
  const unit = rule.amount_unit;
  const freq = rule.frequency;
  if (amt != null && amt !== '') {
    parts.push(`${cur ? `${cur} ` : ''}${amt}${unit ? ` ${unit}` : ''}${freq ? ` · ${freq}` : ''}`.trim());
  } else if (parts.length === 0) {
    parts.push('Benefit rule');
  }
  return parts.join(' — ');
}

export function formatExclusionBusinessLine(rule: Record<string, unknown>): string {
  const d = String(rule.description || '').trim();
  return d || 'Exclusion';
}
