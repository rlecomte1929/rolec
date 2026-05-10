/**
 * HR Policy workspace — derive a single primary UX phase from API data.
 * Uses GET /api/company-policies/{id}/normalized and optionally GET /api/hr/policy-review.
 * Avoid user-facing jargon (no "Layer-2", etc.).
 *
 * ## Phase precedence (deterministic)
 * Evaluated in order; first match wins.
 *
 * 1. **no_policy** — No row in `company_policies` for this company (`policies.length === 0`).
 *    Stale uploads may still exist; UI hints via `documentsCount`, not phase.
 *
 * 2. **published** — `published_version` exists and its `status` is `published`.
 *    Remains `published` even when a newer working version exists; that case sets
 *    `hasUnpublishedDraftAhead === true` (live row ≠ latest row, latest not published).
 *
 * 3. **ready_to_publish** — Not (2), but `publish_readiness.status` is `ready` and the
 *    latest `version` is not published. Comparison readiness may still be partial;
 *    publish and comparison are independent gates (comparison affects employee UX, not phase).
 *
 * 4. **draft_not_publishable** — Company policy exists, no published version row as in (2),
 *    and not (3). Includes “summary-only” drafts and blocked publish.
 *
 * `hasUnpublishedDraftAhead` is only true when (2) holds and there is a separate non-published
 * latest version — i.e. published live + replacement draft in progress.
 */

export type HrPolicyWorkspacePhase =
  | 'no_policy'
  | 'draft_not_publishable'
  | 'ready_to_publish'
  | 'published';

export type HrPolicyComparisonSummary = 'full' | 'partial' | 'informational';

export type ReadinessSlice = {
  status?: string;
  issues?: Array<{ code?: string; message?: string; field?: string }>;
};

/** Single primary button for the workspace at-a-glance card (one CTA per state). */
export type HrPolicyPrimaryAction =
  | 'start_baseline_or_upload'
  | 'review_draft'
  | 'publish'
  | 'review_replacement_draft'
  | 'adjust_values';

export type HrPolicyWorkspaceResolved = {
  phase: HrPolicyWorkspacePhase;
  /** True when published version exists but latest version is different or not yet published */
  hasUnpublishedDraftAhead: boolean;
  comparisonSummary: HrPolicyComparisonSummary;
  comparisonBlockers: string[];
  publishReadiness: ReadinessSlice | null;
  comparisonReadiness: ReadinessSlice | null;
  normalizationReadiness: ReadinessSlice | null;
  /** Merged human-facing issues for banners (from readiness slices + review issues) */
  highlightIssues: Array<{ message: string; tier?: string }>;
  publishedTitle: string | null;
  publishedVersionNumber: number | null;
  draftVersionNumber: number | null;
  benefitRuleCount: number;
  exclusionCount: number;
  draftRuleCandidatesCount: number;
};

/**
 * One primary CTA per workspace state (see product rules in module comment).
 */
export function deriveHrPolicyPrimaryAction(resolved: HrPolicyWorkspaceResolved): HrPolicyPrimaryAction {
  if (resolved.phase === 'no_policy') return 'start_baseline_or_upload';
  if (resolved.phase === 'published' && resolved.hasUnpublishedDraftAhead) return 'review_replacement_draft';
  if (resolved.phase === 'draft_not_publishable') return 'review_draft';
  if (resolved.phase === 'ready_to_publish') return 'publish';
  return 'adjust_values';
}

function normStatus(v: unknown): string {
  return String(v || '')
    .trim()
    .toLowerCase();
}

function isPublishedRow(row: unknown): boolean {
  if (!row || typeof row !== 'object') return false;
  return normStatus((row as { status?: string }).status) === 'published';
}

/**
 * Map backend comparison signals to HR-facing summary (employee cost comparison).
 * Prefers **published** readiness when present, else falls back to working-version readiness.
 */
export function deriveComparisonSummary(normalized: Record<string, unknown> | null | undefined): HrPolicyComparisonSummary {
  if (!normalized) return 'informational';
  const pubCr = normalized.published_comparison_readiness as { comparison_ready?: boolean; partial_numeric_coverage?: boolean } | undefined;
  if (pubCr?.comparison_ready === true) return 'full';
  if (pubCr?.partial_numeric_coverage === true) return 'partial';
  return deriveWorkingVersionComparisonSummary(normalized);
}

/** Comparison tier for what employees see **today** (published version only). */
export function derivePublishedComparisonSummary(normalized: Record<string, unknown> | null | undefined): HrPolicyComparisonSummary {
  if (!normalized) return 'informational';
  const pubCr = normalized.published_comparison_readiness as { comparison_ready?: boolean; partial_numeric_coverage?: boolean } | undefined;
  if (pubCr?.comparison_ready === true) return 'full';
  if (pubCr?.partial_numeric_coverage === true) return 'partial';
  return 'informational';
}

/**
 * Comparison tier for the **working** policy version if it were published
 * (from `policy_readiness.comparison_readiness` on normalized).
 */
export function deriveWorkingVersionComparisonSummary(normalized: Record<string, unknown> | null | undefined): HrPolicyComparisonSummary {
  if (!normalized) return 'informational';
  const pr = normalized.policy_readiness as { comparison_readiness?: { status?: string } } | undefined;
  const st = normStatus(pr?.comparison_readiness?.status);
  if (st === 'partial') return 'partial';
  if (st === 'ready') return 'full';
  return 'informational';
}

export function resolveHrPolicyWorkspaceState(input: {
  policies: unknown[];
  normalized: Record<string, unknown> | null | undefined;
  policyReview: Record<string, unknown> | null | undefined;
}): HrPolicyWorkspaceResolved {
  const { policies, normalized, policyReview } = input;
  const hasCompanyPolicy = Array.isArray(policies) && policies.length > 0;

  const published = (normalized?.published_version || null) as Record<string, unknown> | null;
  const latest = (normalized?.version || null) as Record<string, unknown> | null;
  const hasPublished = isPublishedRow(published);
  const pr = (normalized?.policy_readiness || null) as {
    publish_readiness?: ReadinessSlice;
    comparison_readiness?: ReadinessSlice;
    normalization_readiness?: ReadinessSlice;
  } | null;

  const publishReadiness = pr?.publish_readiness ?? null;
  const comparisonReadiness = pr?.comparison_readiness ?? null;
  const normalizationReadiness = pr?.normalization_readiness ?? null;
  const publishStatus = normStatus(publishReadiness?.status);

  const benefitRules = (normalized?.benefit_rules as unknown[]) || [];
  const exclusions = (normalized?.exclusions as unknown[]) || [];
  const benefitRuleCount = benefitRules.length;
  const exclusionCount = exclusions.length;

  const draftFromReview = policyReview?.draft_rule_candidates as unknown[] | undefined;
  const draftFromNorm = (normalized?.normalization_draft as Record<string, unknown> | undefined)?.draft_rule_candidates as unknown[] | undefined;
  const draftRuleCandidatesCount = Array.isArray(draftFromReview)
    ? draftFromReview.length
    : Array.isArray(draftFromNorm)
      ? draftFromNorm.length
      : 0;

  const publishedTitle =
    (normalized?.policy as { title?: string } | undefined)?.title ||
    (hasCompanyPolicy ? String((policies[0] as { title?: string }).title || '') : null);
  const publishedVersionNumber = hasPublished
    ? Number((published as { version_number?: number }).version_number) || null
    : null;
  const draftVersionNumber = latest ? Number((latest as { version_number?: number }).version_number) || null : null;

  const comparisonSummary = deriveComparisonSummary(normalized);
  const blockersRaw = (normalized?.published_comparison_readiness as { comparison_blockers?: string[] } | undefined)?.comparison_blockers;
  const comparisonBlockers = Array.isArray(blockersRaw) ? blockersRaw.filter(Boolean).map(String) : [];

  const reviewIssues = (policyReview?.issues as Array<{ message?: string; tier?: string }> | undefined) || [];
  const highlightIssues: Array<{ message: string; tier?: string }> = [];

  const pushIssues = (slice: ReadinessSlice | null | undefined, tier: string) => {
    if (!slice?.issues?.length) return;
    for (const it of slice.issues) {
      const m = it?.message;
      if (m && String(m).trim()) highlightIssues.push({ message: String(m), tier });
    }
  };
  pushIssues(normalizationReadiness, 'normalization');
  pushIssues(publishReadiness, 'publish');
  pushIssues(comparisonReadiness, 'comparison');
  for (const ri of reviewIssues) {
    if (ri?.message) highlightIssues.push({ message: String(ri.message), tier: ri.tier });
  }

  let phase: HrPolicyWorkspacePhase = 'no_policy';
  if (!hasCompanyPolicy) {
    phase = 'no_policy';
  } else if (hasPublished) {
    phase = 'published';
  } else if (publishStatus === 'ready' && latest && normStatus(latest.status) !== 'published') {
    phase = 'ready_to_publish';
  } else {
    phase = 'draft_not_publishable';
  }

  const latestId = latest?.id ? String(latest.id) : null;
  const publishedId = published?.id ? String(published.id) : null;
  const hasUnpublishedDraftAhead =
    hasPublished &&
    !!latest &&
    !!latestId &&
    !!publishedId &&
    latestId !== publishedId &&
    normStatus((latest as { status?: string }).status) !== 'published';

  return {
    phase,
    hasUnpublishedDraftAhead,
    comparisonSummary,
    comparisonBlockers,
    publishReadiness,
    comparisonReadiness,
    normalizationReadiness,
    highlightIssues,
    publishedTitle: publishedTitle && publishedTitle.trim() ? publishedTitle : null,
    publishedVersionNumber,
    draftVersionNumber,
    benefitRuleCount,
    exclusionCount,
    draftRuleCandidatesCount,
  };
}

/** User-facing strings per primary phase (headlines / bodies for layout). */
export const HR_POLICY_WORKSPACE_COPY: Record<
  HrPolicyWorkspacePhase,
  { headline: string; subline: string }
> = {
  no_policy: {
    headline: 'Get your relocation policy in place',
    subline:
      'Nothing is live for employees yet. Pick a standard baseline to start fast, or upload your company’s PDF or Word policy—then review and publish when ReloPass says you’re clear.',
  },
  draft_not_publishable: {
    headline: 'Draft saved—finish review before it goes live',
    subline:
      'ReloPass turned your file (or baseline) into an editable draft. Work through the checklist below and the benefit table; when checks pass, you can publish.',
  },
  ready_to_publish: {
    headline: 'Ready to go live',
    subline:
      'This version passed ReloPass checks. Publishing is the step that puts these benefits and limits on employee assignments (by eligibility).',
  },
  published: {
    headline: 'Live for employees',
    subline:
      'This published version is what relocating employees see today, subject to eligibility. Upload a newer policy file or edit values anytime; changes stay in draft until you publish again.',
  },
};

export const COMPARISON_SUMMARY_COPY: Record<HrPolicyComparisonSummary, string> = {
  full: 'Employees get side-by-side cost comparison on services where your policy states clear dollar or unit limits.',
  partial:
    'Some services support full comparison; others show what is covered (or text-only guidance) until you add complete limits.',
  informational:
    'Employees can read benefits from the published policy; automated cost comparison stays off until the required caps and categories are filled in.',
};
