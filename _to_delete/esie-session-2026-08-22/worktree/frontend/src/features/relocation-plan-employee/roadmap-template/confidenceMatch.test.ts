import { describe, it, expect } from 'vitest';
import type { RoadmapV2Response, RoadmapV2Step } from '../../../api/roadmapV2';
import { normalizeStepTitle, buildConfidenceByTitle } from './roadmapTemplateHelpers';

function step(p: Partial<RoadmapV2Step>): RoadmapV2Step {
  return {
    id: 's',
    title: 'Step',
    description: null,
    status: 'pending',
    owner: 'employee',
    due_date: null,
    sort_order: 0,
    ai_suggestion: null,
    dependency_ids: [],
    vendor_id: null,
    doc_count: 0,
    worst_doc_status: null,
    ...p,
  };
}

function tracks(steps: RoadmapV2Step[]): RoadmapV2Response {
  return { tracks: [{ id: 't', name: 'T', icon: '', sort_order: 0, progress_pct: 0, steps }] };
}

describe('normalizeStepTitle', () => {
  it('lowercases, strips punctuation, collapses whitespace', () => {
    expect(normalizeStepTitle('  Upload  Passport-Copy! ')).toBe('upload passport copy');
    expect(normalizeStepTitle('Apply for VLS-TS (visa)')).toBe('apply for vls ts visa');
  });
});

describe('buildConfidenceByTitle', () => {
  it('indexes confident, sourced steps by normalized title', () => {
    const map = buildConfidenceByTitle(
      tracks([
        step({ title: 'Apply for Long-Stay Visa', confidence_level: 'HIGH', source_url: 'https://gov.example/lsv' }),
      ]),
    );
    expect(map['apply for long stay visa']).toEqual({
      level: 'HIGH',
      sourceUrl: 'https://gov.example/lsv',
      sourceFetchedAt: undefined,
      sourceExcerpt: undefined,
    });
  });

  it('drops steps that resolve to UNKNOWN (no source = no badge noise)', () => {
    const map = buildConfidenceByTitle(
      tracks([
        step({ title: 'Sourceless step', confidence_level: 'HIGH', source_url: null }),
        step({ title: 'Unknown step', confidence_level: 'UNKNOWN', source_url: 'https://x' }),
        step({ title: 'No confidence' }),
      ]),
    );
    expect(map).toEqual({});
  });

  it('first confident step per title wins', () => {
    const map = buildConfidenceByTitle(
      tracks([
        step({ title: 'Register', confidence_level: 'HIGH', source_url: 'https://a' }),
        step({ title: 'register', confidence_level: 'LOW', source_url: 'https://b' }),
      ]),
    );
    expect(map['register'].level).toBe('HIGH');
  });

  it('tolerates null/empty input', () => {
    expect(buildConfidenceByTitle(null)).toEqual({});
    expect(buildConfidenceByTitle(undefined)).toEqual({});
    expect(buildConfidenceByTitle({ tracks: [] })).toEqual({});
  });
});
