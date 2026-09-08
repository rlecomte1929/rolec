import { describe, expect, it } from 'vitest';
import type { AdminCompany } from '../../../types';
import { listToV2Shape, toV2Shape, type CompanyV2 } from './adapter';
import fixture from './adapter.fixture.json';

const SAMPLE: AdminCompany[] = (fixture as { companies: AdminCompany[] }).companies;

describe('s9g Companies · adapter', () => {
  it('passes through every field the backend already provides', () => {
    const real = SAMPLE[0]!;
    const v2 = toV2Shape(real);

    expect(v2.id).toBe(real.id);
    expect(v2.name).toBe(real.name);
    expect(v2.country).toBe(real.country);
    expect(v2.size_band).toBe(real.size_band);
    expect(v2.address).toBe(real.address);
    expect(v2.phone).toBe(real.phone);
    expect(v2.created_at).toBe(real.created_at);
    expect(v2.updated_at).toBe(real.updated_at);
    expect(v2.primary_contact_name).toBe(real.primary_contact_name);
    expect(v2.hr_contact).toBe(real.hr_contact);
    expect(v2.support_email).toBe(real.support_email);
    expect(v2.hr_users_count).toBe(real.hr_users_count);
    expect(v2.hr_seat_limit).toBe(real.hr_seat_limit);
    expect(v2.employee_count).toBe(real.employee_count);
    expect(v2.employee_seat_limit).toBe(real.employee_seat_limit);
    expect(v2.assignments_count).toBe(real.assignments_count);
  });

  it('falls back legal_name to name when backend has no legal_name column', () => {
    const v2 = toV2Shape(SAMPLE[0]!);
    expect(v2.legal_name).toBe(SAMPLE[0]!.name);
  });

  it('returns null for industry/website/hq_city (not in backend yet)', () => {
    const v2 = toV2Shape(SAMPLE[0]!);
    expect(v2.industry).toBeNull();
    expect(v2.website).toBeNull();
    expect(v2.hq_city).toBeNull();
  });

  it('coalesces missing counters to 0', () => {
    const real = { id: 'x', name: 'Sparse Co', created_at: '2026-01-01T00:00:00Z' } as AdminCompany;
    const v2 = toV2Shape(real);
    expect(v2.hr_users_count).toBe(0);
    expect(v2.employee_count).toBe(0);
    expect(v2.assignments_count).toBe(0);
    expect(v2.orphan_row_count).toBe(0);
  });

  it('narrows unknown status / plan_tier to safe defaults', () => {
    const edge = SAMPLE.find((c) => c.id === 'co_real_unknown_enum')!;
    const v2 = toV2Shape(edge);
    expect(v2.status).toBe('active'); // 'SuspendedByBilling' → fallback
    expect(v2.plan_tier).toBe('low'); // 'enterprise_v2' → fallback
  });

  it('lowercases case-shifted enums (e.g. "Active" → "active")', () => {
    const shifted = { ...SAMPLE[0]!, status: 'Active', plan_tier: 'Premium' };
    const v2 = toV2Shape(shifted);
    expect(v2.status).toBe('active');
    expect(v2.plan_tier).toBe('premium');
  });

  it('derives tone deterministically: same id → same tone, every time', () => {
    const a = toV2Shape(SAMPLE[0]!);
    const b = toV2Shape(SAMPLE[0]!);
    expect(a.tone).toBe(b.tone);
    expect(['a', 'b', 'c', 'd', 'e', 'f']).toContain(a.tone);
  });

  it('distributes tones across the bucket (not all the same)', () => {
    const tones = new Set(SAMPLE.map((c) => toV2Shape(c).tone));
    // With 4 sample rows we expect at least 2 distinct buckets; if this ever
    // collapses to 1, the hash function regressed.
    expect(tones.size).toBeGreaterThanOrEqual(2);
  });

  it('surfaces missing_from_registry as has_registry_issue', () => {
    const sparse = SAMPLE.find((c) => c.id === 'co_real_sparse')!;
    const v2 = toV2Shape(sparse);
    expect(v2.has_registry_issue).toBe(true);
  });

  it('surfaces missing_from_companies_table as orphan_row_count', () => {
    const archived = SAMPLE.find((c) => c.id === 'co_real_archived')!;
    const v2 = toV2Shape(archived);
    expect(v2.orphan_row_count).toBe(2);
  });

  it('listToV2Shape maps in order, returning a CompanyV2 array', () => {
    const v2List = listToV2Shape(SAMPLE);
    expect(v2List).toHaveLength(SAMPLE.length);
    v2List.forEach((row, i) => {
      expect(row.id).toBe(SAMPLE[i]!.id);
    });
  });

  it('toV2Shape is pure — does not mutate the input', () => {
    const real = SAMPLE[0]!;
    const before = JSON.stringify(real);
    toV2Shape(real);
    expect(JSON.stringify(real)).toBe(before);
  });

  it('produces type-correct CompanyV2 (compile-time + structural check)', () => {
    const v2: CompanyV2 = toV2Shape(SAMPLE[0]!);
    // Spot-check structural keys so a renamed field would fail here too.
    expect(Object.keys(v2)).toEqual(
      expect.arrayContaining([
        'id',
        'name',
        'legal_name',
        'industry',
        'website',
        'hq_city',
        'country',
        'size_band',
        'status',
        'plan_tier',
        'tone',
        'has_registry_issue',
        'orphan_row_count',
      ]),
    );
  });
});
