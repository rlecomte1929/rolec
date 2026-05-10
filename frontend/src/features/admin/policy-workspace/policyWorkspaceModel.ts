/**
 * Derive Policy Workspace KPIs and per-theme stats from the structured policy matrix payload.
 */
import type {
  PolicyConfigBenefitRow,
  PolicyConfigCategoryBlock,
  PolicyConfigWorkingPayload,
} from '../../policy-config/types';
import { normalizeCategoryBlocks } from '../../policy-config/policyConfigUtils';
import { POLICY_WORKSPACE_CANONICAL_ROWS } from './policyWorkspaceCanonical';

export type WorkspaceDisplayRow = PolicyConfigBenefitRow & { _workspace_virtual?: boolean };

export function normalizeBenefitKey(key: string | null | undefined): string {
  return (key ?? '').trim().toLowerCase();
}

/** Row is limited by targeting or explicit notes/conditions (not caps alone). */
export function hasTargeting(row: PolicyConfigBenefitRow): boolean {
  return Boolean((row.assignment_types?.length ?? 0) > 0 || (row.family_statuses?.length ?? 0) > 0);
}

function hasLimitingNotesOrConditions(row: PolicyConfigBenefitRow): boolean {
  const cj = row.conditions_json && Object.keys(row.conditions_json).length > 0;
  return Boolean(cj || (row.notes && row.notes.trim()));
}

/**
 * Excluded = not covered.
 * Conditional = covered but limited by assignment types, family statuses, or notes/conditions.
 * Included = covered with broad applicability (no targeting, no limiting notes/conditions).
 */
export function deriveRowBucket(row: PolicyConfigBenefitRow): 'included' | 'excluded' | 'conditional' {
  if (!row.covered) return 'excluded';
  if (hasTargeting(row) || hasLimitingNotesOrConditions(row)) return 'conditional';
  return 'included';
}

export type ThemeStats = {
  included: number;
  excluded: number;
  conditional: number;
  total: number;
  configured: number;
};

export function deriveThemeStats(block: PolicyConfigCategoryBlock): ThemeStats {
  const benefits = block.benefits ?? [];
  let included = 0;
  let excluded = 0;
  let conditional = 0;
  for (const r of benefits) {
    const b = deriveRowBucket(r);
    if (b === 'included') included += 1;
    else if (b === 'excluded') excluded += 1;
    else conditional += 1;
  }
  return {
    included,
    excluded,
    conditional,
    total: benefits.length,
    configured: benefits.filter((x) => !(x as WorkspaceDisplayRow)._workspace_virtual && (x.benefit_key || '').trim()).length,
  };
}

export type WorkspaceAggregate = {
  included: number;
  excluded: number;
  conditional: number;
  categoriesConfigured: number;
  totalRows: number;
};

export function deriveWorkspaceAggregate(payload: PolicyConfigWorkingPayload | null): WorkspaceAggregate | null {
  if (!payload?.categories) return null;
  const cats = mergeCanonicalBaselineBlocks(normalizeCategoryBlocks(payload.categories));
  return deriveWorkspaceAggregateFromBlocks(cats);
}

export function deriveWorkspaceAggregateFromBlocks(blocks: PolicyConfigCategoryBlock[]): WorkspaceAggregate | null {
  let included = 0;
  let excluded = 0;
  let conditional = 0;
  let categoriesConfigured = 0;
  let totalRows = 0;
  for (const c of blocks) {
    const t = deriveThemeStats(c);
    included += t.included;
    excluded += t.excluded;
    conditional += t.conditional;
    totalRows += t.total;
    if (t.total > 0) categoriesConfigured += 1;
  }
  return { included, excluded, conditional, categoriesConfigured, totalRows };
}

/** Merge API rows with canonical baseline keys (placeholders for missing keys; append non-canonical API rows). */
export function mergeCanonicalBaselineBlocks(blocks: PolicyConfigCategoryBlock[]): PolicyConfigCategoryBlock[] {
  return blocks.map((block) => {
    const categoryKey = block.category_key ?? '';
    const apiBenefits = [...(block.benefits ?? [])];
    const canonical = POLICY_WORKSPACE_CANONICAL_ROWS[categoryKey] ?? [];
    const byKey = new Map<string, PolicyConfigBenefitRow>();
    for (const r of apiBenefits) {
      const nk = normalizeBenefitKey(r.benefit_key);
      if (nk) byKey.set(nk, r);
    }
    const used = new Set<string>();
    const merged: WorkspaceDisplayRow[] = [];
    for (const { key, label } of canonical) {
      const nk = normalizeBenefitKey(key);
      const existing = byKey.get(nk);
      if (existing) {
        merged.push(existing);
        used.add(nk);
      } else {
        merged.push({
          benefit_key: key,
          benefit_label: label,
          covered: false,
          category: categoryKey,
          value_type: 'none',
          _workspace_virtual: true,
        });
      }
    }
    const extras = apiBenefits.filter((r) => {
      const nk = normalizeBenefitKey(r.benefit_key);
      return nk && !used.has(nk);
    });
    extras.sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0) || (a.benefit_key || '').localeCompare(b.benefit_key || ''));
    merged.push(...extras);
    return { ...block, benefits: merged };
  });
}

export function formatCapValueSummary(row: PolicyConfigBenefitRow): string {
  const vt = (row.value_type ?? '').toLowerCase();
  if (vt === 'percentage' && row.percentage_value != null && !Number.isNaN(row.percentage_value)) {
    return `${row.percentage_value}%`;
  }
  if (row.amount_value != null && !Number.isNaN(Number(row.amount_value))) {
    const cur = (row.currency_code ?? '').trim();
    return cur ? `${cur} ${row.amount_value}` : String(row.amount_value);
  }
  if (row.maximum_budget_explanation?.trim()) {
    return truncateOneLine(row.maximum_budget_explanation, 48);
  }
  if (row.cap_rule_json && Object.keys(row.cap_rule_json).length > 0) return 'Cap rule defined';
  if (row.allowance_cap && Object.keys(row.allowance_cap).length > 0) return 'Allowance cap defined';
  if (row.covered) return 'Configured without cap';
  return '—';
}

export function formatApplicabilitySummary(row: PolicyConfigBenefitRow): string {
  const at = row.assignment_types?.filter(Boolean) ?? [];
  const fs = row.family_statuses?.filter(Boolean) ?? [];
  if (at.length === 0 && fs.length === 0) return 'All assignments & profiles';
  const parts: string[] = [];
  if (at.length) parts.push(`Assignment: ${at.join(', ')}`);
  if (fs.length) parts.push(`Family: ${fs.join(', ')}`);
  return parts.join(' · ');
}

export function notesPreview(row: PolicyConfigBenefitRow, maxLen = 72): string {
  const n = (row.notes ?? '').trim();
  if (!n) return '—';
  return truncateOneLine(n, maxLen);
}

function truncateOneLine(s: string, maxLen: number): string {
  const t = s.replace(/\s+/g, ' ').trim();
  if (t.length <= maxLen) return t;
  return `${t.slice(0, maxLen - 1)}…`;
}

/** Effective for workspace filter: empty targeting lists mean "applies to all". */
export function rowMatchesAssignmentFilter(row: PolicyConfigBenefitRow, filterValue: string | null): boolean {
  if (!filterValue?.trim()) return true;
  const at = row.assignment_types?.filter(Boolean) ?? [];
  if (at.length === 0) return true;
  return at.map((x) => normalizeBenefitKey(x)).includes(normalizeBenefitKey(filterValue));
}

export function rowMatchesFamilyFilter(row: PolicyConfigBenefitRow, filterValue: string | null): boolean {
  if (!filterValue?.trim()) return true;
  const fs = row.family_statuses?.filter(Boolean) ?? [];
  if (fs.length === 0) return true;
  return fs.map((x) => normalizeBenefitKey(x)).includes(normalizeBenefitKey(filterValue));
}

/** Product-facing source mode (manual / extracted / hybrid). */
export function deriveSourceModeLabel(
  sourceDocumentCount: number,
  payload: PolicyConfigWorkingPayload | null
): string {
  const pv = (payload?.policy_version ?? '').toString().trim();
  const scaffold =
    (payload?.status ?? '').toLowerCase() === 'empty_scaffold' ||
    (payload?.source ?? '').toLowerCase() === 'empty_scaffold' ||
    !pv;
  if (scaffold) {
    return sourceDocumentCount > 0 ? 'Extracted' : 'Manual';
  }
  return sourceDocumentCount > 0 ? 'Hybrid' : 'Manual';
}

export function workspaceStatusBadge(payload: PolicyConfigWorkingPayload | null): {
  label: string;
  tone: 'neutral' | 'warning' | 'success';
} {
  if (!payload) {
    return { label: 'No structured policy', tone: 'neutral' };
  }
  const st = (payload.status ?? '').toLowerCase();
  const src = (payload.source ?? '').toLowerCase();
  if (st === 'empty_scaffold' || src === 'empty_scaffold') {
    return { label: 'No structured policy', tone: 'neutral' };
  }
  if (src === 'draft' || src === 'draft_created' || st === 'draft') {
    return { label: 'Draft', tone: 'warning' };
  }
  if (src === 'published_clone' || st === 'published') {
    return { label: 'Published', tone: 'success' };
  }
  return { label: 'Structured baseline', tone: 'neutral' };
}

export function unpublishedChangesLabel(payload: PolicyConfigWorkingPayload | null): string {
  if (!payload) return '—';
  const src = (payload.source ?? '').toLowerCase();
  if (src === 'draft' || src === 'draft_created') return 'Yes';
  if (src === 'published_clone') return 'None';
  return '—';
}
