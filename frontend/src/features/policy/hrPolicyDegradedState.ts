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
    title: 'No policy to work with yet',
    body: 'Upload a company policy file or create a baseline from the options above, then build and publish a version. Employees only see benefits after a version is published.',
  },
  uploaded_not_normalized: {
    variant: 'info',
    title: 'File received—policy build not finished',
    body: 'We may still be reading the file, or you have not finished “build policy from document” in Documents & processing. Until you publish, employees keep seeing the previous live policy—or none if this is your first one.',
  },
  normalized_failed: {
    variant: 'error',
    title: 'We could not finish processing this file',
    body: 'Fix the source file if needed, choose Reprocess, then build the policy again. Employees cannot use a policy that did not finish processing.',
  },
  normalized_partial: {
    variant: 'warning',
    title: 'Draft policy on file—not live yet',
    body: 'ReloPass saved benefit rules you can edit. Review the table and publish when the workspace shows you can. Until then, employees do not see this draft on Package & limits or Services.',
  },
  published_not_comparison_ready: {
    variant: 'warning',
    title: 'Live policy—cost comparison not fully on',
    body: 'Employees see benefits from what you published, but some comparison bars stay off until a few services have clearer limits. Use the checklist in the draft review panel to close the gaps.',
  },
  published_comparison_ready: {
    variant: 'success',
    title: 'Live policy—cost comparison available',
    body: 'Employees on a matching assignment can compare costs to policy limits on supported services where your caps are defined.',
  },
};
