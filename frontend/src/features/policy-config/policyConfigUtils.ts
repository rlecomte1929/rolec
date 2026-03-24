import type {
  PolicyConfigBenefitRow,
  PolicyConfigCategoryBlock,
  PolicyConfigWorkingPayload,
} from './types';
import { POLICY_CONFIG_CATEGORIES } from './constants';

/** Deterministic JSON shape for saves and dirty comparison (sorted object keys recursively). */
export function stableJsonNormalize(v: unknown): unknown {
  if (v === null || typeof v !== 'object') return v;
  if (Array.isArray(v)) return v.map(stableJsonNormalize);
  const o = v as Record<string, unknown>;
  return Object.keys(o)
    .sort()
    .reduce<Record<string, unknown>>((acc, k) => {
      acc[k] = stableJsonNormalize(o[k]);
      return acc;
    }, {});
}

/** Merge API categories with canonical order; ensure all six sections exist. */
export function normalizeCategoryBlocks(categories: PolicyConfigCategoryBlock[] | undefined): PolicyConfigCategoryBlock[] {
  const map = new Map<string, PolicyConfigCategoryBlock>();
  for (const c of categories ?? []) {
    const k = c.category_key;
    if (k) map.set(k, { ...c, benefits: [...(c.benefits ?? [])] });
  }
  return POLICY_CONFIG_CATEGORIES.map(({ key, label }) => {
    const existing = map.get(key);
    return {
      category_key: key,
      category_label: existing?.category_label || label,
      benefits: existing?.benefits ?? [],
    };
  });
}

export function buildPutBody(state: PolicyConfigWorkingPayload): Record<string, unknown> {
  const categories = normalizeCategoryBlocks(state.categories).map((block) => ({
    category_key: block.category_key,
    category_label: block.category_label,
    benefits: (block.benefits ?? []).map((b) => ({
      benefit_key: b.benefit_key,
      benefit_label: b.benefit_label,
      category: block.category_key,
      covered: Boolean(b.covered),
      value_type: b.value_type ?? 'none',
      amount_value: b.amount_value ?? null,
      currency_code: b.currency_code ?? null,
      percentage_value: b.percentage_value ?? null,
      unit_frequency: b.unit_frequency ?? 'one_time',
      cap_rule_json: stableJsonNormalize(
        b.cap_rule_json && typeof b.cap_rule_json === 'object' ? b.cap_rule_json : {}
      ) as Record<string, unknown>,
      notes: b.notes ?? null,
      conditions_json: stableJsonNormalize(
        b.conditions_json && typeof b.conditions_json === 'object' ? b.conditions_json : {}
      ) as Record<string, unknown>,
      assignment_types: b.assignment_types ?? [],
      family_statuses: b.family_statuses ?? [],
      is_active: b.is_active !== false,
      display_order: typeof b.display_order === 'number' ? b.display_order : 0,
    })),
  }));
  return {
    policy_version: state.policy_version,
    effective_date: state.effective_date,
    categories,
  };
}

/**
 * Immutable single-row update without cloning the full matrix (large forms stay responsive).
 */
export function patchBenefitInPayload(
  payload: PolicyConfigWorkingPayload,
  categoryKey: string,
  prev: PolicyConfigBenefitRow,
  next: PolicyConfigBenefitRow
): PolicyConfigWorkingPayload {
  const cats = normalizeCategoryBlocks(payload.categories);
  const bi = cats.findIndex((c) => c.category_key === categoryKey);
  if (bi < 0) return payload;
  const benefits = [...(cats[bi].benefits ?? [])];
  const ri = benefits.findIndex(
    (b) =>
      b.benefit_key === prev.benefit_key &&
      (b.targeting_signature || 'global') === (prev.targeting_signature || 'global')
  );
  if (ri < 0) return payload;
  const nextBenefits = [...benefits];
  nextBenefits[ri] = { ...next, category: categoryKey };
  const nextCategories = cats.map((c, i) => (i === bi ? { ...c, benefits: nextBenefits } : c));
  return { ...payload, categories: nextCategories };
}

export function statusBadgeVariant(
  status: string | undefined,
  source: string | undefined
): { label: string; tone: 'default' | 'success' | 'warning' | 'neutral' } {
  const st = (status || '').toLowerCase();
  if (st === 'published') return { label: 'Published', tone: 'success' };
  if (st === 'draft') return { label: 'Draft', tone: 'warning' };
  if (source === 'published_clone') return { label: 'Published (read-only)', tone: 'neutral' };
  if (source === 'empty_scaffold') return { label: 'New setup', tone: 'neutral' };
  return { label: status || 'Unknown', tone: 'default' };
}
