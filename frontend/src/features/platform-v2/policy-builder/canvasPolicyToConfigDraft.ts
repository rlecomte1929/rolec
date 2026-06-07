// canvasPolicyToConfigDraft.ts
//
// Maps the Policy Builder canvas model (tiers × benefit matrix) onto the
// `policy_config` "PUT draft" body consumed by
//   PUT /api/hr/policy-config/draft   (policyConfigMatrixAPI.hrPutDraft)
//
// This is the bridge that makes the builder a REAL authoring tool: publishing
// the resulting draft (POST /api/hr/policy-config/publish) makes it both
// employee-visible and rebuilds the RAG index (policy_assistant_chunks) so the
// Policy Assistant can answer about it.
//
// The contract mirrors backend/schemas_compensation_allowance.py
// (PolicyConfigBenefitWrite) and the validate_put_body() rules in
// backend/app/services/policy_config_matrix_service.py.
//
// Kept as a pure function (no React/API imports) so it is unit-testable.

// ─── policy_config enum types (from schemas_compensation_allowance.py) ──────
export type ConfigCategoryKey =
  | 'pre_assignment_support'
  | 'relocation_assistance'
  | 'compensation_allowances'
  | 'family_support_education'
  | 'leave_repatriation'
  | 'tax_payroll';

type ConfigValueType = 'currency' | 'percentage' | 'text' | 'none';
type ConfigFreq =
  | 'one_time' | 'monthly' | 'yearly' | 'per_trip' | 'per_day' | 'per_dependent' | 'custom';
type ConfigAssignmentType = 'short_term' | 'long_term' | 'permanent' | 'international';
type ConfigFamilyStatus = 'single' | 'spouse_partner' | 'dependents';
type ConfigEmployeeLevel = 'entry' | 'manager' | 'director' | 'vp' | 'c_suite';

// ─── Minimal structural inputs (compatible with the canvas page types) ──────
// Declared structurally so the mapper does not depend on the page module.
export interface MapInBenefitValue {
  covered: boolean;
  value_type: 'currency' | 'percentage' | 'text' | 'none';
  amount: number;
  freq: 'one_time' | 'monthly' | 'yearly' | 'per_trip' | 'per_dependent';
  lump_inc: 'included' | 'optional' | 'excluded' | null;
  cap: boolean;
  conditions: boolean;
}
export interface MapInTier {
  id: string;
  name: string;
  mode: 'lump' | 'caps';
  lump: number;
  targeting: { level: string[]; type: string[]; family: string[] };
  benefits: Record<string, MapInBenefitValue>;
}
export interface MapInBenefitDef { k: string; lbl: string }
export interface MapInCategoryDef { key: string; benefits: MapInBenefitDef[] }

// ─── Output row shape (PolicyConfigBenefitWrite) ────────────────────────────
export interface ConfigBenefitRow {
  benefit_key: string;
  benefit_label: string;
  category: ConfigCategoryKey;
  covered: boolean;
  value_type: ConfigValueType;
  amount_value: number | null;
  currency_code: string | null;
  percentage_value: number | null;
  unit_frequency: ConfigFreq;
  cap_rule_json: Record<string, unknown>;
  notes: string | null;
  conditions_json: Record<string, unknown>;
  assignment_types: ConfigAssignmentType[];
  family_statuses: ConfigFamilyStatus[];
  employee_levels: ConfigEmployeeLevel[];
  is_active: boolean;
  display_order: number;
}

export interface PolicyConfigDraftBody {
  policy_version: string;
  effective_date: string;
  categories: Array<{ category_key: ConfigCategoryKey; benefits: ConfigBenefitRow[] }>;
}

export interface CanvasMapResult {
  body: PolicyConfigDraftBody;
  warnings: string[];
  rowCount: number;
}

// ─── Canvas → policy_config translation tables ──────────────────────────────
const CANVAS_TO_CONFIG_CATEGORY: Record<string, ConfigCategoryKey> = {
  pre_assignment: 'pre_assignment_support',
  relocation: 'relocation_assistance',
  compensation: 'compensation_allowances',
  family: 'family_support_education',
  leave: 'leave_repatriation',
  tax: 'tax_payroll',
};

const TYPE_MAP: Record<string, ConfigAssignmentType | undefined> = {
  long_term: 'long_term',
  short_term: 'short_term',
  permanent: 'permanent',
  // No policy_config equivalent — intentionally omitted (won't gate eligibility):
  commuter: undefined,
  extended_business_trip: undefined,
};
const FAMILY_MAP: Record<string, ConfigFamilyStatus | undefined> = {
  single: 'single',
  married: 'spouse_partner',
  accompanied_family: 'dependents',
};
const LEVEL_MAP: Record<string, ConfigEmployeeLevel | undefined> = {
  entry: 'entry',
  manager: 'manager',
  director: 'director',
  vp: 'vp',
  c_suite: 'c_suite',
};
const FREQ_MAP: Record<string, ConfigFreq> = {
  one_time: 'one_time',
  monthly: 'monthly',
  yearly: 'yearly',
  per_trip: 'per_trip',
  per_dependent: 'per_dependent',
};
const FREQ_LABEL: Record<string, string> = {
  one_time: '', monthly: '/mo', yearly: '/yr', per_trip: '/trip', per_dependent: '/dependent',
};

function mapAxis<T>(vals: string[], table: Record<string, T | undefined>): T[] {
  const out: T[] = [];
  for (const v of vals) {
    const mapped = table[v];
    if (mapped !== undefined) out.push(mapped);
  }
  return out;
}

function buildCatalog(
  categories: MapInCategoryDef[],
): Map<string, { label: string; category: ConfigCategoryKey }> {
  const map = new Map<string, { label: string; category: ConfigCategoryKey }>();
  for (const c of categories) {
    const cat = CANVAS_TO_CONFIG_CATEGORY[c.key];
    if (!cat) continue;
    for (const b of c.benefits) map.set(b.k, { label: b.lbl, category: cat });
  }
  return map;
}

/**
 * Translate the canvas tiers + catalog into a policy_config draft PUT body.
 *
 * Each (tier, covered-benefit) pair becomes one policy_config benefit row,
 * carrying that tier's targeting (assignment_types / family_statuses /
 * employee_levels). The same benefit_key can appear across multiple tiers with
 * different targeting — exactly how policy_config models tiers.
 *
 * Rules enforced to match the backend:
 *  - only emit covered benefits (caps mode) / included|optional (lump mode);
 *  - currency rows always carry currency_code (backend requires it);
 *  - drop duplicate (benefit_key, targeting) pairs (backend rejects them).
 */
export function canvasPolicyToConfigDraft(args: {
  tiers: MapInTier[];
  categories: MapInCategoryDef[];
  effectiveDate: string;
  currency: string;
  policyVersion: string;
}): CanvasMapResult {
  const { tiers, categories, effectiveDate, currency, policyVersion } = args;
  const catalog = buildCatalog(categories);
  const warnings: string[] = [];
  const byCategory = new Map<ConfigCategoryKey, ConfigBenefitRow[]>();
  const seen = new Set<string>();

  for (const tier of tiers) {
    const assignment_types = mapAxis(tier.targeting.type, TYPE_MAP);
    const family_statuses = mapAxis(tier.targeting.family, FAMILY_MAP);
    const employee_levels = mapAxis(tier.targeting.level, LEVEL_MAP);

    const droppedTypes = tier.targeting.type.filter((t) => TYPE_MAP[t] === undefined);
    if (droppedTypes.length) {
      warnings.push(
        `Tier "${tier.name}": assignment type(s) ${droppedTypes.join(', ')} have no policy-config equivalent and were omitted from targeting.`,
      );
    }

    const isLump = tier.mode === 'lump';

    for (const [bKey, bv] of Object.entries(tier.benefits)) {
      const meta = catalog.get(bKey);
      if (!meta) continue; // unknown / custom benefit — skip

      const noteParts: string[] = [];
      const conditions_json: Record<string, unknown> = {};

      if (isLump) {
        const inc = bv.lump_inc ?? (bv.covered ? 'included' : 'excluded');
        if (inc === 'excluded') continue; // not provided in this tier
        if (inc === 'optional') noteParts.push('Optional under lump-sum budget');
        // The tier's single lump-sum budget has no per-benefit field in
        // policy_config; preserve it in conditions_json rather than invent one.
        conditions_json.lump_sum_budget = tier.lump;
        conditions_json.lump_currency = currency;
      } else if (!bv.covered) {
        continue; // only emit covered benefits
      }

      const sig = [
        [...assignment_types].sort().join('|'),
        [...family_statuses].sort().join('|'),
        [...employee_levels].sort().join('|'),
      ].join('::');
      const dedupeKey = `${bKey}@@${sig}`;
      if (seen.has(dedupeKey)) {
        warnings.push(
          `Duplicate "${meta.label}" for identical targeting (tier "${tier.name}") was skipped.`,
        );
        continue;
      }
      seen.add(dedupeKey);

      let value_type: ConfigValueType = 'none';
      let amount_value: number | null = null;
      let currency_code: string | null = null;
      let percentage_value: number | null = null;

      if (!isLump) {
        value_type = bv.value_type;
        if (value_type === 'currency') {
          amount_value = bv.amount || 0;
          currency_code = currency; // backend requires currency_code with an amount
        } else if (value_type === 'percentage') {
          percentage_value = bv.amount || 0;
        } else if (value_type === 'text' && bv.amount) {
          // e.g. home-leave "2 /yr", extra holidays "5 /yr" — keep as a note
          noteParts.push(`${bv.amount} ${FREQ_LABEL[bv.freq] || ''}`.trim());
        }
      }
      // lump mode → value_type stays 'none' (inclusion captured via covered + notes)

      if (bv.cap) conditions_json.cap = true;
      if (bv.conditions) conditions_json.conditional = true;

      const row: ConfigBenefitRow = {
        benefit_key: bKey,
        benefit_label: meta.label,
        category: meta.category,
        covered: true,
        value_type,
        amount_value,
        currency_code,
        percentage_value,
        unit_frequency: FREQ_MAP[bv.freq] || 'one_time',
        cap_rule_json: bv.cap ? { capped: true } : {},
        notes: noteParts.length ? noteParts.join(' · ') : null,
        conditions_json,
        assignment_types,
        family_statuses,
        employee_levels,
        is_active: true,
        display_order: 0,
      };

      const arr = byCategory.get(meta.category) ?? [];
      arr.push(row);
      byCategory.set(meta.category, arr);
    }
  }

  const categoriesOut = [...byCategory.entries()].map(([category_key, benefits]) => ({
    category_key,
    benefits,
  }));
  const rowCount = categoriesOut.reduce((n, c) => n + c.benefits.length, 0);

  return {
    body: { policy_version: policyVersion, effective_date: effectiveDate, categories: categoriesOut },
    warnings,
    rowCount,
  };
}
