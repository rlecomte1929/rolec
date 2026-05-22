/**
 * [P2-9] eval_pipeline.test.ts
 *
 * Unit and integration tests for the ingestion pipeline evaluation harness.
 *
 * Coverage:
 *   1. mockClassify — keyword classifier produces valid ClassificationOutput
 *   2. numericValuesMatch — ±5% tolerance, null handling, string comparison
 *   3. countValueMatches — found/total counting for extracted values
 *   4. buildPolicyFacts — filters to correctly-classified chunks only
 *   5. conflictWasDetected — lookup against detected ConflictReport list
 *   6. reportFilename — YYYYMMDD format
 *   7. formatReport — valid JSON, required fields present
 *   8. runEvaluation (mock mode) — end-to-end with full ground truth
 *      ✓ classification accuracy ≥ 92%
 *      ✓ value extraction precision ≥ 95%
 *      ✓ conflict detection recall ≥ 98%
 *      ✓ report.overall_pass === true
 *      ✓ all 20 documents evaluated
 *      ✓ per-category breakdown present
 */

import { describe, it, expect, beforeAll } from 'vitest';
import {
  mockClassify,
  numericValuesMatch,
  countValueMatches,
  buildPolicyFacts,
  conflictWasDetected,
  runEvaluation,
  formatReport,
  reportFilename,
  type GroundTruth,
  type GroundTruthDocument,
  type GroundTruthChunk,
} from '../eval_pipeline';
import { CATEGORIES } from '../classification_prompt';

// Load ground truth
import groundTruthData from './eval_ground_truth.json';
const groundTruth = groundTruthData as GroundTruth;

// ---------------------------------------------------------------------------
// 1. mockClassify
// ---------------------------------------------------------------------------

describe('mockClassify', () => {
  it('returns a valid ClassificationOutput shape', () => {
    const result = mockClassify(
      'The housing allowance cap for Manager grade is EUR 3,500 per month.',
      [],
    );
    expect(result).toHaveProperty('category_code');
    expect(result).toHaveProperty('category_name');
    expect(Array.isArray(result.applicable_tiers)).toBe(true);
    expect(Array.isArray(result.extracted_values)).toBe(true);
    expect(typeof result.confidence_score).toBe('number');
    expect(typeof result.confidence_rationale).toBe('string');
  });

  it('classifies housing allowance as CAT-01', () => {
    const result = mockClassify(
      'The monthly housing allowance cap for Director-grade employees is EUR 4,500.',
      [],
    );
    expect(result.category_code).toBe('CAT-01');
  });

  it('classifies lump sum as CAT-02', () => {
    const result = mockClassify(
      'A one-time relocation lump sum of USD 10,000 is paid upon commencement.',
      [],
    );
    expect(result.category_code).toBe('CAT-02');
  });

  it('classifies shipping as CAT-03', () => {
    const result = mockClassify(
      'Household goods shipping is reimbursed up to EUR 8,000 for container shipments.',
      [],
    );
    expect(result.category_code).toBe('CAT-03');
  });

  it('classifies repatriation as CAT-14', () => {
    const result = mockClassify(
      'Repatriation services at end of assignment include return relocation flights.',
      [],
    );
    expect(result.category_code).toBe('CAT-14');
  });

  it('returns UNCLASSIFIED for text with no matching keywords', () => {
    const result = mockClassify('The company was founded in 1987.', []);
    expect(result.category_code).toBe('UNCLASSIFIED');
    expect(result.confidence_score).toBeLessThan(0.5);
  });

  it('injects mock_extracted_values into the output', () => {
    const mockValues = [{ value: 3500, unit: 'EUR/month', currency: 'EUR', condition: null }];
    const result = mockClassify(
      'The housing allowance for Manager grade is EUR 3,500 per month.',
      mockValues,
    );
    expect(result.extracted_values).toEqual(mockValues);
  });

  it('produces higher confidence_score for multi-keyword matches', () => {
    const single = mockClassify('The housing allowance is EUR 3,500.', []);
    const double = mockClassify('The housing cap is EUR 3,500 per month including utilities.', []);
    expect(double.confidence_score).toBeGreaterThanOrEqual(single.confidence_score);
  });
});

// ---------------------------------------------------------------------------
// 2. numericValuesMatch
// ---------------------------------------------------------------------------

describe('numericValuesMatch', () => {
  it('returns true for identical numbers', () => {
    expect(numericValuesMatch(3500, 3500)).toBe(true);
  });

  it('returns true within ±5% tolerance', () => {
    expect(numericValuesMatch(3500, 3400)).toBe(true); // 2.9% diff
    expect(numericValuesMatch(3500, 3675)).toBe(true); // 5% diff exactly
  });

  it('returns false outside ±5% tolerance', () => {
    expect(numericValuesMatch(3500, 3000)).toBe(false); // 14% diff
    expect(numericValuesMatch(3500, 4000)).toBe(false); // 14% diff
  });

  it('returns true for both null', () => {
    expect(numericValuesMatch(null, null)).toBe(true);
  });

  it('returns false when one is null and the other is not', () => {
    expect(numericValuesMatch(null, 3500)).toBe(false);
    expect(numericValuesMatch(3500, null)).toBe(false);
  });

  it('returns true for matching string values (case-insensitive)', () => {
    expect(numericValuesMatch('full reimbursement', 'Full Reimbursement')).toBe(true);
  });

  it('returns false for non-matching strings', () => {
    expect(numericValuesMatch('economy class', 'business class')).toBe(false);
  });

  it('handles numeric strings vs numbers', () => {
    expect(numericValuesMatch('3500', 3500)).toBe(true);
  });

  it('handles zero correctly', () => {
    expect(numericValuesMatch(0, 0)).toBe(true);
    expect(numericValuesMatch(0, 1)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 3. countValueMatches
// ---------------------------------------------------------------------------

describe('countValueMatches', () => {
  it('returns { found: 0, total: 0 } when no expected values', () => {
    const result = countValueMatches([], []);
    expect(result).toEqual({ found: 0, total: 0 });
  });

  it('returns correct counts when all values match', () => {
    const extracted = [
      { value: 3500, unit: 'EUR/month', currency: 'EUR', condition: null },
    ];
    const expected = [{ value: 3500, unit: 'EUR/month', currency: 'EUR', condition: null }];
    expect(countValueMatches(extracted, expected)).toEqual({ found: 1, total: 1 });
  });

  it('returns found=0 when no values match', () => {
    const extracted = [{ value: 4000, unit: 'EUR/month', currency: 'EUR', condition: null }];
    const expected = [{ value: 3500, unit: 'EUR/month', currency: 'EUR', condition: null }];
    expect(countValueMatches(extracted, expected)).toEqual({ found: 0, total: 1 });
  });

  it('handles multiple expected values', () => {
    const extracted = [
      { value: 60, unit: 'hours', currency: null, condition: null },
      { value: 2500, unit: 'EUR', currency: 'EUR', condition: 'cap' },
    ];
    const expected = [
      { value: 60, unit: 'hours', currency: null, condition: null },
      { value: 2500, unit: 'EUR', currency: 'EUR', condition: 'cap' },
    ];
    expect(countValueMatches(extracted, expected)).toEqual({ found: 2, total: 2 });
  });

  it('handles partial matches', () => {
    const extracted = [{ value: 60, unit: 'hours', currency: null, condition: null }];
    const expected = [
      { value: 60, unit: 'hours', currency: null, condition: null },
      { value: 2500, unit: 'EUR', currency: 'EUR', condition: 'cap' },
    ];
    expect(countValueMatches(extracted, expected)).toEqual({ found: 1, total: 2 });
  });

  it('handles null values in expected', () => {
    const extracted = [{ value: null, unit: null, currency: null, condition: 'includes family' }];
    const expected = [{ value: null, unit: null, currency: null, condition: 'includes family' }];
    expect(countValueMatches(extracted, expected)).toEqual({ found: 1, total: 1 });
  });
});

// ---------------------------------------------------------------------------
// 4. buildPolicyFacts
// ---------------------------------------------------------------------------

describe('buildPolicyFacts', () => {
  const mockOutput = {
    category_code: 'CAT-01',
    category_name: 'Housing Allowance',
    applicable_tiers: ['Manager'],
    extracted_values: [{ value: 3500, unit: 'EUR/month', currency: 'EUR', condition: null }],
    confidence_score: 0.95,
    confidence_rationale: 'Test',
  };

  it('includes only correctly-classified chunks', () => {
    const chunks = [
      {
        chunk_id: 'c1',
        doc_id: 'doc-001',
        doc_name: 'Policy A',
        classification: mockOutput,
        correctly_classified: true,
        expected_tier: 'Manager',
        expected_values: [],
      },
      {
        chunk_id: 'c2',
        doc_id: 'doc-001',
        doc_name: 'Policy A',
        classification: { ...mockOutput, category_code: 'CAT-02' },
        correctly_classified: false,
        expected_tier: null,
        expected_values: [],
      },
    ];

    const facts = buildPolicyFacts(chunks);
    expect(facts).toHaveLength(1);
    expect(facts[0].id).toBe('c1');
  });

  it('maps first extracted_value to normalized_value', () => {
    const chunks = [
      {
        chunk_id: 'c1',
        doc_id: 'doc-001',
        doc_name: 'Policy A',
        classification: mockOutput,
        correctly_classified: true,
        expected_tier: 'Manager',
        expected_values: [],
      },
    ];

    const facts = buildPolicyFacts(chunks);
    expect(facts[0].normalized_value.value).toBe(3500);
    expect(facts[0].normalized_value.currency).toBe('EUR');
  });

  it('uses ground truth tier (not LLM applicable_tiers)', () => {
    const chunks = [
      {
        chunk_id: 'c1',
        doc_id: 'doc-001',
        doc_name: 'Policy A',
        classification: { ...mockOutput, applicable_tiers: ['Director'] },
        correctly_classified: true,
        expected_tier: 'Manager', // ground truth wins
        expected_values: [],
      },
    ];

    const facts = buildPolicyFacts(chunks);
    expect(facts[0].tier).toBe('Manager'); // ground truth tier
  });

  it('uses null normalized_value when no extracted values', () => {
    const chunks = [
      {
        chunk_id: 'c1',
        doc_id: 'doc-001',
        doc_name: 'Policy A',
        classification: { ...mockOutput, extracted_values: [] },
        correctly_classified: true,
        expected_tier: null,
        expected_values: [],
      },
    ];

    const facts = buildPolicyFacts(chunks);
    expect(facts[0].normalized_value.value).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 5. conflictWasDetected
// ---------------------------------------------------------------------------

describe('conflictWasDetected', () => {
  const mockConflicts = [
    {
      value_a: { source_doc: 'Policy A', value: 3200, currency: 'EUR', unit: 'EUR/month' },
      value_b: { source_doc: 'Policy B', value: 4000, currency: 'EUR', unit: 'EUR/month' },
      category_code: 'CAT-01',
    },
  ];

  const chunkToDoc = new Map([
    ['c-a', 'Policy A'],
    ['c-b', 'Policy B'],
    ['c-c', 'Policy C'],
  ]);

  it('returns true when conflict is detected in A→B order', () => {
    expect(conflictWasDetected('c-a', 'c-b', 'CAT-01', mockConflicts, chunkToDoc)).toBe(true);
  });

  it('returns true when conflict is detected in B→A order', () => {
    expect(conflictWasDetected('c-b', 'c-a', 'CAT-01', mockConflicts, chunkToDoc)).toBe(true);
  });

  it('returns false when category does not match', () => {
    expect(conflictWasDetected('c-a', 'c-b', 'CAT-02', mockConflicts, chunkToDoc)).toBe(false);
  });

  it('returns false when chunk IDs are not in the conflict', () => {
    expect(conflictWasDetected('c-a', 'c-c', 'CAT-01', mockConflicts, chunkToDoc)).toBe(false);
  });

  it('returns false when chunk IDs are not in the map', () => {
    expect(conflictWasDetected('unknown', 'c-b', 'CAT-01', mockConflicts, chunkToDoc)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 6. reportFilename
// ---------------------------------------------------------------------------

describe('reportFilename', () => {
  it('produces YYYYMMDD format filename', () => {
    const report = {
      run_date: '2026-05-22',
      run_timestamp: '',
      mode: 'mock' as const,
      document_count: 20,
      chunk_count: 60,
      overall_pass: true,
      metrics: {
        classification_accuracy: { score: 0.95, target: 0.92, pass: true, details: '' },
        value_extraction_precision: { score: 0.97, target: 0.95, pass: true, details: '' },
        conflict_detection_recall: { score: 1.0, target: 0.98, pass: true, details: '' },
      },
      category_breakdown: [],
      summary: '',
    };
    expect(reportFilename(report)).toBe('eval_report_20260522.json');
  });
});

// ---------------------------------------------------------------------------
// 7. formatReport
// ---------------------------------------------------------------------------

describe('formatReport', () => {
  const sampleReport = {
    run_date: '2026-05-22',
    run_timestamp: '2026-05-22T07:00:00.000Z',
    mode: 'mock' as const,
    document_count: 20,
    chunk_count: 60,
    overall_pass: true,
    metrics: {
      classification_accuracy: { score: 0.95, target: 0.92, pass: true, details: '57/60' },
      value_extraction_precision: { score: 0.97, target: 0.95, pass: true, details: '70/72' },
      conflict_detection_recall: { score: 1.0, target: 0.98, pass: true, details: '6/6' },
    },
    category_breakdown: [],
    summary: '✅ PASS',
  };

  it('returns valid JSON string', () => {
    const str = formatReport(sampleReport);
    expect(() => JSON.parse(str)).not.toThrow();
  });

  it('contains all required top-level fields', () => {
    const parsed = JSON.parse(formatReport(sampleReport));
    expect(parsed).toHaveProperty('run_date');
    expect(parsed).toHaveProperty('run_timestamp');
    expect(parsed).toHaveProperty('mode');
    expect(parsed).toHaveProperty('overall_pass');
    expect(parsed).toHaveProperty('metrics');
    expect(parsed).toHaveProperty('category_breakdown');
    expect(parsed).toHaveProperty('summary');
  });

  it('contains all three metric keys', () => {
    const parsed = JSON.parse(formatReport(sampleReport));
    expect(parsed.metrics).toHaveProperty('classification_accuracy');
    expect(parsed.metrics).toHaveProperty('value_extraction_precision');
    expect(parsed.metrics).toHaveProperty('conflict_detection_recall');
  });

  it('each metric has score, target, pass, details', () => {
    const parsed = JSON.parse(formatReport(sampleReport));
    for (const metric of Object.values(parsed.metrics)) {
      const m = metric as Record<string, unknown>;
      expect(m).toHaveProperty('score');
      expect(m).toHaveProperty('target');
      expect(m).toHaveProperty('pass');
      expect(m).toHaveProperty('details');
    }
  });
});

// ---------------------------------------------------------------------------
// 8. runEvaluation — mock mode end-to-end
// ---------------------------------------------------------------------------

describe('runEvaluation (mock mode)', () => {
  let report: Awaited<ReturnType<typeof runEvaluation>>;

  beforeAll(async () => {
    report = await runEvaluation({
      groundTruth,
      mode: 'mock',
    });
  }, 30_000);

  it('evaluates all 20 documents', () => {
    expect(report.document_count).toBe(20);
  });

  it('evaluates all 60 chunks', () => {
    expect(report.chunk_count).toBe(60);
  });

  it('mode is "mock"', () => {
    expect(report.mode).toBe('mock');
  });

  it('run_date is a valid YYYY-MM-DD string', () => {
    expect(report.run_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('classification accuracy meets ≥ 92% target', () => {
    expect(report.metrics.classification_accuracy.score).toBeGreaterThanOrEqual(0.92);
    expect(report.metrics.classification_accuracy.pass).toBe(true);
  });

  it('value extraction precision meets ≥ 95% target', () => {
    expect(report.metrics.value_extraction_precision.score).toBeGreaterThanOrEqual(0.95);
    expect(report.metrics.value_extraction_precision.pass).toBe(true);
  });

  it('conflict detection recall meets ≥ 98% target', () => {
    expect(report.metrics.conflict_detection_recall.score).toBeGreaterThanOrEqual(0.98);
    expect(report.metrics.conflict_detection_recall.pass).toBe(true);
  });

  it('overall_pass is true', () => {
    expect(report.overall_pass).toBe(true);
  });

  it('summary contains ✅ PASS', () => {
    expect(report.summary).toContain('PASS');
  });

  it('category_breakdown covers all 14 categories', () => {
    const codes = new Set(report.category_breakdown.map((c) => c.category_code));
    CATEGORIES.forEach((cat) => {
      expect(codes.has(cat.code)).toBe(true);
    });
  });

  it('each category breakdown entry has accuracy between 0 and 1', () => {
    for (const entry of report.category_breakdown) {
      expect(entry.accuracy).toBeGreaterThanOrEqual(0);
      expect(entry.accuracy).toBeLessThanOrEqual(1);
      expect(entry.total).toBeGreaterThan(0);
      expect(entry.correct).toBeLessThanOrEqual(entry.total);
    }
  });

  it('classification failures list is present when any miss occurs', () => {
    const metric = report.metrics.classification_accuracy;
    if (metric.score < 1.0) {
      expect(metric.failures).toBeDefined();
      expect(metric.failures!.length).toBeGreaterThan(0);
    }
  });

  it('conflict detection details string contains X/Y format', () => {
    expect(report.metrics.conflict_detection_recall.details).toMatch(/\d+\/\d+/);
  });

  it('formatReport on runEvaluation output produces valid JSON', () => {
    const str = formatReport(report);
    const parsed = JSON.parse(str);
    expect(parsed.overall_pass).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 9. Ground truth dataset integrity checks
// ---------------------------------------------------------------------------

describe('Ground truth dataset integrity', () => {
  it('has exactly 20 documents', () => {
    expect(groundTruth.documents).toHaveLength(20);
  });

  it('has exactly 60 chunks (3 per document)', () => {
    const total = groundTruth.documents.reduce((s, d) => s + d.chunks.length, 0);
    expect(total).toBe(60);
  });

  it('all chunk IDs are unique', () => {
    const ids = groundTruth.documents.flatMap((d) => d.chunks.map((c) => c.chunk_id));
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('all expected_category values are valid CAT-XX codes', () => {
    const validCodes = new Set(CATEGORIES.map((c) => c.code));
    for (const doc of groundTruth.documents) {
      for (const chunk of doc.chunks) {
        expect(validCodes.has(chunk.expected_category)).toBe(true);
      }
    }
  });

  it('covers all 14 categories across the 60 chunks', () => {
    const covered = new Set(
      groundTruth.documents.flatMap((d) => d.chunks.map((c) => c.expected_category)),
    );
    CATEGORIES.forEach((cat) => {
      expect(covered.has(cat.code)).toBe(true);
    });
  });

  it('real_conflicts all reference valid known_conflict IDs', () => {
    const knownIds = new Set(groundTruth.known_conflicts.map((c) => c.conflict_id));
    for (const id of groundTruth.real_conflicts) {
      expect(knownIds.has(id)).toBe(true);
    }
  });

  it('all conflict chunk_a_id and chunk_b_id reference existing chunks', () => {
    const chunkIds = new Set(
      groundTruth.documents.flatMap((d) => d.chunks.map((c) => c.chunk_id)),
    );
    for (const conflict of groundTruth.known_conflicts) {
      expect(chunkIds.has(conflict.chunk_a_id)).toBe(true);
      expect(chunkIds.has(conflict.chunk_b_id)).toBe(true);
    }
  });
});
