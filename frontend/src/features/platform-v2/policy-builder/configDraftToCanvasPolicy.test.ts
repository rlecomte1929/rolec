import { describe, it, expect } from 'vitest';
import { canvasPolicyToConfigDraft, type MapInTier, type MapInCategoryDef } from './canvasPolicyToConfigDraft';
import { configDraftToCanvasPolicy, type DraftPayload } from './configDraftToCanvasPolicy';

const CATALOG: MapInCategoryDef[] = [
  { key: 'compensation', benefits: [
    { k: 'mobility_premium', lbl: 'Mobility premium' },
    { k: 'host_housing_cap', lbl: 'Housing cap' },
  ] },
  { key: 'relocation', benefits: [
    { k: 'relocation_allowance_assignee_partner', lbl: 'Relocation allowance' },
  ] },
];

const bv = (o: Partial<MapInTier['benefits'][string]>): MapInTier['benefits'][string] => ({
  covered: true, value_type: 'none', amount: 0, freq: 'one_time', lump_inc: null, cap: false, conditions: false, ...o,
});

// A caps tier (manager) + a lump tier (director) with distinct targeting.
const TIERS: MapInTier[] = [
  {
    id: 'a', name: 'Manager', mode: 'caps', lump: 0,
    targeting: { level: ['manager'], type: ['long_term'], family: ['single', 'married'] },
    benefits: {
      mobility_premium: bv({ value_type: 'percentage', amount: 15 }),
      host_housing_cap: bv({ value_type: 'currency', amount: 2400, freq: 'monthly', cap: true }),
    },
  },
  {
    id: 'b', name: 'Director', mode: 'lump', lump: 50000,
    targeting: { level: ['director'], type: ['long_term'], family: ['single'] },
    benefits: {
      relocation_allowance_assignee_partner: bv({ lump_inc: 'included' }),
    },
  },
];

function roundTrip() {
  const fwd = canvasPolicyToConfigDraft({
    tiers: TIERS, categories: CATALOG, effectiveDate: '2026-06-12', currency: 'EUR', policyVersion: 'v1',
  });
  // The forward body's categories are structurally the GET payload's categories.
  const payload: DraftPayload = { policy_version: 'v1', status: 'draft', categories: fwd.body.categories };
  return configDraftToCanvasPolicy(payload);
}

describe('configDraftToCanvasPolicy (round-trip)', () => {
  it('reconstructs one tier per distinct targeting signature', () => {
    const { tiers } = roundTrip();
    expect(tiers).toHaveLength(2);
  });

  it('recovers caps-tier benefit values and targeting (with reverse enum mapping)', () => {
    const { tiers } = roundTrip();
    const mgr = tiers.find((t) => t.targeting.level.includes('manager'))!;
    expect(mgr).toBeDefined();
    expect(mgr.mode).toBe('caps');
    expect(mgr.targeting.type).toEqual(['long_term']);
    // spouse_partner → married on the way back
    expect(mgr.targeting.family.sort()).toEqual(['married', 'single']);
    expect(mgr.benefits.mobility_premium).toMatchObject({ value_type: 'percentage', amount: 15 });
    expect(mgr.benefits.host_housing_cap).toMatchObject({ value_type: 'currency', amount: 2400, freq: 'monthly', cap: true });
  });

  it('infers lump mode + budget from conditions_json', () => {
    const { tiers } = roundTrip();
    const dir = tiers.find((t) => t.targeting.level.includes('director'))!;
    expect(dir).toBeDefined();
    expect(dir.mode).toBe('lump');
    expect(dir.lump).toBe(50000);
    expect(dir.benefits.relocation_allowance_assignee_partner.lump_inc).toBe('included');
  });

  it('carries source + field_confidence onto AI-extracted benefit values (AIQ-991)', () => {
    const payload: DraftPayload = {
      status: 'draft',
      categories: [{
        category_key: 'compensation_allowances',
        benefits: [{
          benefit_key: 'host_housing_cap',
          covered: true,
          value_type: 'currency',
          amount_value: 2400,
          unit_frequency: 'monthly',
          source: 'extracted_llm',
          field_confidence: 0.92,
          employee_levels: ['manager'],
        }],
      }],
    };
    const { tiers } = configDraftToCanvasPolicy(payload);
    const bv = tiers[0].benefits.host_housing_cap;
    expect(bv.source).toBe('extracted_llm');
    expect(bv.field_confidence).toBe(0.92);
  });

  it('returns empty tiers for a payload with no rows (fresh company)', () => {
    expect(configDraftToCanvasPolicy({ categories: [] }).tiers).toHaveLength(0);
    expect(configDraftToCanvasPolicy(null).tiers).toHaveLength(0);
  });
});
