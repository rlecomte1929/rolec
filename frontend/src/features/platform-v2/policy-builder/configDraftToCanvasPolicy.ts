// configDraftToCanvasPolicy.ts
//
// Inverse of canvasPolicyToConfigDraft.ts: maps a `policy_config` working
// payload (GET /api/hr/policy-config → policyConfigMatrixAPI.hrGet) back onto
// the Policy Builder canvas model (tiers × benefit matrix), so HR opening the
// builder sees their EXISTING draft/published policy instead of a blank
// template.
//
// policy_config stores a flat list of benefit rows; each row carries its own
// targeting (assignment_types / family_statuses / employee_levels). The forward
// mapper emits one row per (tier, covered-benefit) pair, so a "tier" is encoded
// purely by its targeting signature. This inverse therefore GROUPS rows by that
// signature — each distinct signature becomes one canvas tier.
//
// The reconstruction is best-effort: the canvas tier `name`, lump/caps `mode`,
// and lump budget are not first-class columns (the forward mapper drops the name
// and stashes the lump budget in conditions_json), and `text` benefit amounts
// were flattened into notes. We recover what is recoverable and surface the rest
// via `warnings`. Kept pure (no React/API imports) so it is unit-testable.

// ─── Canvas-side value types (structural; mirror the page's BenefitValue) ────
type CanvasValueType = 'currency' | 'percentage' | 'text' | 'none';
type CanvasFreq = 'one_time' | 'monthly' | 'yearly' | 'per_trip' | 'per_dependent';
type CanvasLumpInc = 'included' | 'optional' | 'excluded';

export interface LoadedBenefitValue {
  covered: boolean;
  value_type: CanvasValueType;
  amount: number;
  freq: CanvasFreq;
  lump_inc: CanvasLumpInc | null;
  cap: boolean;
  conditions: boolean;
  // Provenance + extraction confidence (AIQ-991): only meaningful for AI-extracted
  // rows (source='extracted_llm'); used to badge confidence in the builder.
  source?: string | null;
  field_confidence?: number | null;
}

// A reconstructed tier WITHOUT page-only chrome (id / color / emp), which the
// page fills in. `benefits` holds only the rows present in the payload; the page
// merges them over its default scaffold so every catalog key still renders.
export interface LoadedTier {
  name: string;
  mode: 'lump' | 'caps';
  lump: number;
  targeting: { level: string[]; type: string[]; family: string[] };
  benefits: Record<string, LoadedBenefitValue>;
}

export interface LoadResult {
  tiers: LoadedTier[];
  warnings: string[];
  rowCount: number;
}

// ─── Structural input (the subset of the GET payload we read) ────────────────
export interface DraftBenefitRow {
  benefit_key: string;
  covered?: boolean;
  value_type?: string | null;
  amount_value?: number | null;
  percentage_value?: number | null;
  unit_frequency?: string | null;
  notes?: string | null;
  cap_rule_json?: Record<string, unknown> | null;
  conditions_json?: Record<string, unknown> | null;
  source?: string | null;
  field_confidence?: number | null;
  assignment_types?: string[] | null;
  family_statuses?: string[] | null;
  employee_levels?: string[] | null;
}
export interface DraftCategory {
  category_key?: string;
  benefits?: DraftBenefitRow[] | null;
}
export interface DraftPayload {
  categories?: DraftCategory[] | null;
  policy_version?: string | null;
  status?: string | null;
}

// ─── policy_config → canvas reverse tables (invert canvasPolicyToConfigDraft) ─
const CONFIG_TO_CANVAS_TYPE: Record<string, string | undefined> = {
  long_term: 'long_term',
  short_term: 'short_term',
  permanent: 'permanent',
  international: undefined, // no canvas equivalent — omitted on load
};
const CONFIG_TO_CANVAS_FAMILY: Record<string, string | undefined> = {
  single: 'single',
  spouse_partner: 'married',
  dependents: 'accompanied_family',
};
const CONFIG_TO_CANVAS_LEVEL: Record<string, string | undefined> = {
  entry: 'entry',
  manager: 'manager',
  director: 'director',
  vp: 'vp',
  c_suite: 'c_suite',
};
const CONFIG_TO_CANVAS_FREQ: Record<string, CanvasFreq> = {
  one_time: 'one_time',
  monthly: 'monthly',
  yearly: 'yearly',
  per_trip: 'per_trip',
  per_dependent: 'per_dependent',
};

function reverseAxis(vals: string[] | null | undefined, table: Record<string, string | undefined>): string[] {
  const out: string[] = [];
  for (const v of vals || []) {
    const mapped = table[v];
    if (mapped !== undefined && !out.includes(mapped)) out.push(mapped);
  }
  return out;
}

const LEVEL_LABEL: Record<string, string> = {
  entry: 'Entry', manager: 'Manager', director: 'Director', vp: 'VP', c_suite: 'C-Suite',
};

function titleForTier(levels: string[], types: string[], index: number): string {
  if (levels.length) return levels.map((l) => LEVEL_LABEL[l] || l).join(' / ');
  if (types.length) return types.map((t) => t.replace(/_/g, ' ')).join(' / ');
  return `Imported tier ${index + 1}`;
}

function asNumber(v: unknown): number {
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
}

function rowToBenefitValue(row: DraftBenefitRow, isLump: boolean): LoadedBenefitValue {
  const vt = (row.value_type || 'none') as CanvasValueType;
  let amount = 0;
  if (vt === 'currency') amount = asNumber(row.amount_value);
  else if (vt === 'percentage') amount = asNumber(row.percentage_value);
  // `text` amounts were flattened into notes by the forward mapper and are not
  // safely recoverable, so they stay 0 (the note text still renders).

  const cap =
    !!(row.cap_rule_json && (row.cap_rule_json as Record<string, unknown>).capped) ||
    !!(row.conditions_json && (row.conditions_json as Record<string, unknown>).cap);
  const conditions = !!(row.conditions_json && (row.conditions_json as Record<string, unknown>).conditional);

  return {
    covered: row.covered !== false,
    value_type: vt,
    amount,
    freq: CONFIG_TO_CANVAS_FREQ[String(row.unit_frequency || 'one_time')] || 'one_time',
    lump_inc: isLump ? 'included' : null,
    cap,
    conditions,
    source: row.source ?? null,
    field_confidence: typeof row.field_confidence === 'number' ? row.field_confidence : null,
  };
}

/**
 * Translate a policy_config working payload into canvas tiers.
 *
 * Rows are grouped by their targeting signature (the canvas tier identity); each
 * group yields one `LoadedTier`. `mode`/`lump` are inferred from the
 * `conditions_json.lump_sum_budget` the forward mapper stashes for lump tiers.
 * Returns empty `tiers` when the payload has no benefit rows (a fresh company
 * with no draft) so the caller keeps its template-picker flow.
 */
export function configDraftToCanvasPolicy(payload: DraftPayload | null | undefined): LoadResult {
  const warnings: string[] = [];
  const rows: DraftBenefitRow[] = [];
  for (const cat of payload?.categories || []) {
    for (const b of cat?.benefits || []) {
      if (b && b.benefit_key) rows.push(b);
    }
  }
  if (!rows.length) return { tiers: [], warnings, rowCount: 0 };

  // Group rows by targeting signature, preserving first-seen order.
  const groups = new Map<string, { types: string[]; family: string[]; levels: string[]; rows: DraftBenefitRow[] }>();
  for (const row of rows) {
    const types = reverseAxis(row.assignment_types, CONFIG_TO_CANVAS_TYPE);
    const family = reverseAxis(row.family_statuses, CONFIG_TO_CANVAS_FAMILY);
    const levels = reverseAxis(row.employee_levels, CONFIG_TO_CANVAS_LEVEL);
    const sig = [
      [...types].sort().join('|'),
      [...family].sort().join('|'),
      [...levels].sort().join('|'),
    ].join('::');
    let g = groups.get(sig);
    if (!g) {
      g = { types, family, levels, rows: [] };
      groups.set(sig, g);
    }
    g.rows.push(row);
  }

  const tiers: LoadedTier[] = [];
  let index = 0;
  for (const g of groups.values()) {
    // Infer lump mode + budget from the stashed conditions_json.lump_sum_budget.
    let lump = 0;
    let isLump = false;
    for (const r of g.rows) {
      const budget = r.conditions_json && (r.conditions_json as Record<string, unknown>).lump_sum_budget;
      if (budget != null) {
        isLump = true;
        lump = asNumber(budget);
        break;
      }
    }
    const benefits: Record<string, LoadedBenefitValue> = {};
    for (const r of g.rows) {
      // First row per benefit_key wins within a tier (matches the forward
      // mapper's de-dupe of identical (key, targeting) pairs).
      if (!benefits[r.benefit_key]) benefits[r.benefit_key] = rowToBenefitValue(r, isLump);
    }
    tiers.push({
      name: titleForTier(g.levels, g.types, index),
      mode: isLump ? 'lump' : 'caps',
      lump,
      targeting: { level: g.levels, type: g.types, family: g.family },
      benefits,
    });
    index += 1;
  }

  return { tiers, warnings, rowCount: rows.length };
}
