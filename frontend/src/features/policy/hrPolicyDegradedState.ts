/**
 * HR Policy workspace pipeline states (degraded / progress).
 * Align with docs/policy/policy-degraded-states.md
 */

export type HrPolicyPipelineState =
  | 'workspace_empty'
  | 'uploaded_not_normalized'
  | 'normalized_failed'
  | 'normalized_partial'
  | 'published_not_comparison_ready'
  | 'published_comparison_ready';

export type HrPolicyPipelineDerived = {
  state: HrPolicyPipelineState;
  /** Subtext (e.g. first comparison blockers, extraction error snippet). */
  detail?: string;
};

function sortDocsNewestFirst(documents: any[]): any[] {
  return [...(documents || [])].sort(
    (a, b) =>
      new Date(b?.uploaded_at || 0).getTime() - new Date(a?.uploaded_at || 0).getTime()
  );
}

/**
 * Derive HR-facing pipeline state from workspace payloads.
 * `normalized` is the API shape from GET /api/company-policies/{id}/normalized (includes published_* fields).
 */
export function deriveHrPolicyPipelineState(
  documents: any[],
  normalized: any | null
): HrPolicyPipelineDerived {
  const primaryDoc = sortDocsNewestFirst(documents)[0] ?? null;
  const pub = normalized?.published_version;
  const readiness = normalized?.published_comparison_readiness;
  const latest = normalized?.version;
  const rules = normalized?.benefit_rules?.length ?? 0;
  const excl = normalized?.exclusions?.length ?? 0;
  const hasStructure = rules > 0 || excl > 0;

  const pubPublished =
    pub && String(pub.status || '').toLowerCase() === 'published';

  if (primaryDoc?.processing_status === 'failed') {
    const err = primaryDoc.extraction_error;
    return {
      state: 'normalized_failed',
      detail: typeof err === 'string' && err.trim() ? err.slice(0, 200) : undefined,
    };
  }

  if (pubPublished) {
    if (readiness?.comparison_ready === true) {
      return { state: 'published_comparison_ready' };
    }
    const blockers = readiness?.comparison_blockers;
    const detail = Array.isArray(blockers) && blockers.length ? blockers.slice(0, 4).join(' · ') : undefined;
    return { state: 'published_not_comparison_ready', detail };
  }

  const docSt = primaryDoc?.processing_status as string | undefined;
  const docNormalizedStage = docSt === 'normalized' || docSt === 'approved';

  if (primaryDoc && docSt && !docNormalizedStage) {
    return { state: 'uploaded_not_normalized' };
  }

  if (latest && hasStructure) {
    return { state: 'normalized_partial' };
  }

  if (docNormalizedStage && (!latest || !hasStructure)) {
    return { state: 'normalized_partial' };
  }

  if (!primaryDoc && !latest && !pub) {
    return { state: 'workspace_empty' };
  }

  return { state: 'uploaded_not_normalized' };
}

export const HR_POLICY_PIPELINE_COPY: Record<
  HrPolicyPipelineState,
  { title: string; body: string; variant: 'info' | 'success' | 'warning' | 'error' | 'neutral' }
> = {
  workspace_empty: {
    variant: 'neutral',
    title: 'No policy workspace data yet',
    body: 'Upload a company policy document, or ensure a company policy exists. Employees only see content after you normalize and publish a version.',
  },
  uploaded_not_normalized: {
    variant: 'info',
    title: 'Document uploaded — normalization not complete',
    body: 'Text extraction or classification is still in progress, or you have not run Normalize & publish yet. Layer‑1 metadata on the document is not employee-facing until you produce a published policy version.',
  },
  normalized_failed: {
    variant: 'error',
    title: 'Document processing failed',
    body: 'Fix the issue (try Reprocess), then normalize again. Failed documents cannot be published for employees.',
  },
  normalized_partial: {
    variant: 'warning',
    title: 'Structured policy exists — not published to employees',
    body: 'Review the benefit matrix, then use Publish version. Until a version is published, employees will not see this policy on Package & limits or Services.',
  },
  published_not_comparison_ready: {
    variant: 'warning',
    title: 'Published — employee cost comparison not active',
    body: 'Employees see resolved benefits where applicable, but comparison bars and gated comparisons stay off until required benefit rules are complete. Use blockers below to fix gaps.',
  },
  published_comparison_ready: {
    variant: 'success',
    title: 'Published — comparison-ready for employees',
    body: 'Employees with a matching assignment can use policy-backed comparison on supported services and package summary, subject to resolution context.',
  },
};
