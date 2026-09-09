/**
 * [P4-7] eval_assistant.test.ts — Unit tests for the AI assistant evaluation harness
 *
 * Tests cover all pure metric computation functions:
 *   - computeContextPrecision
 *   - computeContextRecall
 *   - checkCitationAccuracy
 *   - isRefusal
 *   - aggregateResults
 *   - formatReport
 *   - TEST_SET composition validation
 *
 * The integration path (runEvaluation calling real Supabase + Anthropic) is NOT
 * tested here — it requires live credentials and is executed via CLI in CI.
 * The metric functions are fully deterministic and need no mocks.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import type { PolicyChunk } from '../../../src/features/policy-builder/retrieve_policy';
import {
  computeContextPrecision,
  computeContextRecall,
  checkCitationAccuracy,
  isRefusal,
  aggregateResults,
  formatReport,
  TEST_SET,
  METRIC_THRESHOLDS,
  isAnswerable,
} from '../eval_assistant';
import type {
  EvalConfig,
  QuestionResult,
  AnswerableTestCase,
  UnanswerableTestCase,
} from '../eval_assistant';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_CONFIG: EvalConfig = {
  supabaseUrl: 'https://test.supabase.co',
  supabaseKey: 'test-anon-key',
  anthropicKey: 'test-api-key',
  companyId: 'company-test-001',
  employeeTier: 'Manager',
  k: 5,
};

function makeChunk(overrides: Partial<PolicyChunk> = {}): PolicyChunk {
  return {
    id: 'chunk-1',
    section_path: '4.2 Housing Cap by Grade',
    text: 'The housing allowance for Manager grade is EUR 3,500 per month.',
    confidence_score: 0.94,
    page_start: 12,
    doc_id: 'doc-1',
    rrf_score: 0.75,
    ...overrides,
  };
}

function makeAnswerableResult(overrides: Partial<QuestionResult> = {}): QuestionResult {
  return {
    id: 'Q01',
    query: 'What is the monthly housing allowance?',
    type: 'answerable',
    precision: 0.8,
    recall: 0.75,
    faithfulness: 0.95,
    citationAccurate: true,
    ...overrides,
  };
}

function makeUnanswerableResult(overrides: Partial<QuestionResult> = {}): QuestionResult {
  return {
    id: 'Q21',
    query: 'What is my bonus structure?',
    type: 'unanswerable',
    correctlyRefused: true,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// computeContextPrecision
// ---------------------------------------------------------------------------

describe('computeContextPrecision', () => {
  it('returns 0 for empty retrieved list', () => {
    expect(computeContextPrecision([], ['housing'])).toBe(0);
  });

  it('returns 1.0 when all chunks match relevant sections', () => {
    const paths = ['4.2 Housing Cap', '4.3 Temporary Housing', '4.1 Housing Overview'];
    expect(computeContextPrecision(paths, ['housing'])).toBe(1.0);
  });

  it('returns 0.0 when no chunks match relevant sections', () => {
    const paths = ['5.1 Travel Benefits', '5.2 Air Travel', '5.3 Baggage'];
    expect(computeContextPrecision(paths, ['housing', 'accommodation'])).toBe(0);
  });

  it('returns fractional precision for partial match', () => {
    const paths = [
      '4.2 Housing Cap',      // relevant
      '5.1 Travel Benefits',  // not relevant
      '4.3 Temporary Housing', // relevant
      '6.1 Healthcare',       // not relevant
    ];
    const precision = computeContextPrecision(paths, ['housing']);
    expect(precision).toBeCloseTo(0.5, 5);
  });

  it('is case-insensitive', () => {
    const paths = ['HOUSING ALLOWANCE CAP'];
    expect(computeContextPrecision(paths, ['housing'])).toBe(1.0);
  });

  it('matches if any relevant section matches the path', () => {
    const paths = ['4.2 Housing Cap by Grade'];
    expect(computeContextPrecision(paths, ['travel', 'housing', 'visa'])).toBe(1.0);
  });

  it('handles null/empty section_paths gracefully', () => {
    // Empty paths treated as empty strings
    const paths = ['', '4.2 Housing Cap'];
    const precision = computeContextPrecision(paths, ['housing']);
    expect(precision).toBeCloseTo(0.5, 5);
  });
});

// ---------------------------------------------------------------------------
// computeContextRecall
// ---------------------------------------------------------------------------

describe('computeContextRecall', () => {
  it('returns 1 for empty relevant_sections', () => {
    expect(computeContextRecall(['housing', 'travel'], [])).toBe(1);
  });

  it('returns 1.0 when all relevant sections are covered', () => {
    const paths = ['4.2 Housing Cap', '5.1 Travel Benefits'];
    expect(computeContextRecall(paths, ['housing', 'travel'])).toBe(1.0);
  });

  it('returns 0.0 when no relevant sections are covered', () => {
    const paths = ['5.1 Travel Benefits', '5.2 Air Travel'];
    expect(computeContextRecall(paths, ['housing', 'accommodation'])).toBe(0);
  });

  it('returns fractional recall for partial coverage', () => {
    const paths = ['4.2 Housing Cap'];
    // 2 relevant sections, only 1 covered
    const recall = computeContextRecall(paths, ['housing', 'travel']);
    expect(recall).toBeCloseTo(0.5, 5);
  });

  it('is case-insensitive', () => {
    const paths = ['HOUSING ALLOWANCE'];
    expect(computeContextRecall(paths, ['Housing'])).toBe(1.0);
  });

  it('returns 0 when retrieved list is empty', () => {
    expect(computeContextRecall([], ['housing', 'travel'])).toBe(0);
  });

  it('handles empty retrieved paths', () => {
    expect(computeContextRecall([], ['housing'])).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// checkCitationAccuracy
// ---------------------------------------------------------------------------

describe('checkCitationAccuracy', () => {
  const groundTruth = {
    doc_name_contains: 'Policy',
    section_contains: 'Housing',
    page: 12,
  };

  it('returns true for fully matching citation', () => {
    const chunk = makeChunk({
      section_path: '4.2 Housing Cap',
      page_start: 12,
      doc_id: 'doc-global-policy',
    });
    expect(checkCitationAccuracy(chunk, groundTruth, 'Global Policy 2025')).toBe(true);
  });

  it('returns false when undefined chunk provided', () => {
    expect(checkCitationAccuracy(undefined, groundTruth, 'Global Policy')).toBe(false);
  });

  it('returns false when section does not match', () => {
    const chunk = makeChunk({ section_path: '5.1 Travel Benefits', page_start: 12 });
    expect(checkCitationAccuracy(chunk, groundTruth, 'Global Policy')).toBe(false);
  });

  it('returns false when doc_name does not match', () => {
    const chunk = makeChunk({ section_path: '4.2 Housing Cap', page_start: 12 });
    expect(checkCitationAccuracy(chunk, groundTruth, 'Unrelated Document')).toBe(false);
  });

  it('returns false when page is more than ±1 off', () => {
    const chunk = makeChunk({ section_path: '4.2 Housing Cap', page_start: 15 });
    expect(checkCitationAccuracy(chunk, groundTruth, 'Global Policy')).toBe(false);
  });

  it('returns true when page is within ±1 tolerance', () => {
    const chunk11 = makeChunk({ section_path: '4.2 Housing Cap', page_start: 11 });
    const chunk13 = makeChunk({ section_path: '4.2 Housing Cap', page_start: 13 });
    expect(checkCitationAccuracy(chunk11, groundTruth, 'Global Policy')).toBe(true);
    expect(checkCitationAccuracy(chunk13, groundTruth, 'Global Policy')).toBe(true);
  });

  it('returns false when page_start is null', () => {
    const chunk = makeChunk({ section_path: '4.2 Housing Cap', page_start: null });
    expect(checkCitationAccuracy(chunk, groundTruth, 'Global Policy')).toBe(false);
  });

  it('is case-insensitive for section and doc_name checks', () => {
    const chunk = makeChunk({ section_path: 'HOUSING ALLOWANCE CAP', page_start: 12 });
    expect(checkCitationAccuracy(chunk, groundTruth, 'global policy 2025')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// isRefusal
// ---------------------------------------------------------------------------

describe('isRefusal', () => {
  it('returns true for "refusal" answer_type', () => {
    expect(isRefusal('refusal')).toBe(true);
  });

  it('returns false for "generated" answer_type', () => {
    expect(isRefusal('generated')).toBe(false);
  });

  it('returns false for "raw_excerpt" answer_type', () => {
    expect(isRefusal('raw_excerpt')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// aggregateResults
// ---------------------------------------------------------------------------

describe('aggregateResults', () => {
  it('produces overall_pass=true when all metrics exceed thresholds', () => {
    const results: QuestionResult[] = [
      makeAnswerableResult({ precision: 0.9, recall: 0.8, faithfulness: 0.97, citationAccurate: true }),
      makeAnswerableResult({ id: 'Q02', precision: 0.85, recall: 0.78, faithfulness: 0.96, citationAccurate: true }),
      makeUnanswerableResult({ correctlyRefused: true }),
      makeUnanswerableResult({ id: 'Q22', correctlyRefused: true }),
    ];
    const report = aggregateResults(results, MOCK_CONFIG, 5);
    expect(report.overall_pass).toBe(true);
    expect(report.metrics.context_precision.pass).toBe(true);
    expect(report.metrics.context_recall.pass).toBe(true);
    expect(report.metrics.faithfulness.pass).toBe(true);
    expect(report.metrics.citation_accuracy.pass).toBe(true);
    expect(report.metrics.refusal_recall.pass).toBe(true);
  });

  it('produces overall_pass=false when faithfulness is below threshold', () => {
    const results: QuestionResult[] = [
      makeAnswerableResult({ faithfulness: 0.8 }), // below 0.95
      makeUnanswerableResult({ correctlyRefused: true }),
    ];
    const report = aggregateResults(results, MOCK_CONFIG, 5);
    expect(report.overall_pass).toBe(false);
    expect(report.metrics.faithfulness.pass).toBe(false);
  });

  it('produces overall_pass=false when refusal_recall is below threshold', () => {
    const results: QuestionResult[] = [
      makeAnswerableResult(),
      makeUnanswerableResult({ correctlyRefused: false }),  // missed refusal
      makeUnanswerableResult({ id: 'Q22', correctlyRefused: false }),
      makeUnanswerableResult({ id: 'Q23', correctlyRefused: false }),
    ];
    const report = aggregateResults(results, MOCK_CONFIG, 5);
    expect(report.metrics.refusal_recall.pass).toBe(false);
    expect(report.metrics.refusal_recall.failures).toContain('Q21');
  });

  it('includes correct question IDs in failure lists', () => {
    const results: QuestionResult[] = [
      makeAnswerableResult({ id: 'Q01', citationAccurate: false }),
      makeAnswerableResult({ id: 'Q02', citationAccurate: true }),
      makeUnanswerableResult({ id: 'Q21', correctlyRefused: false }),
      makeUnanswerableResult({ id: 'Q22', correctlyRefused: true }),
    ];
    const report = aggregateResults(results, MOCK_CONFIG, 5);
    expect(report.metrics.citation_accuracy.failures).toContain('Q01');
    expect(report.metrics.citation_accuracy.failures).not.toContain('Q02');
    expect(report.metrics.refusal_recall.failures).toContain('Q21');
    expect(report.metrics.refusal_recall.failures).not.toContain('Q22');
  });

  it('handles no answerable questions gracefully', () => {
    const results: QuestionResult[] = [
      makeUnanswerableResult({ correctlyRefused: true }),
    ];
    const report = aggregateResults(results, MOCK_CONFIG, 5);
    // No answerable questions → precision/recall/faithfulness/citation default to passing
    expect(report.metrics.context_precision.score).toBe(0);
    expect(report.metrics.refusal_recall.pass).toBe(true);
  });

  it('handles no unanswerable questions gracefully', () => {
    const results: QuestionResult[] = [
      makeAnswerableResult({ precision: 0.9, recall: 0.8, faithfulness: 0.97, citationAccurate: true }),
    ];
    const report = aggregateResults(results, MOCK_CONFIG, 5);
    // No unanswerable → refusal_recall defaults to 1 (pass)
    expect(report.metrics.refusal_recall.score).toBe(1);
    expect(report.metrics.refusal_recall.pass).toBe(true);
  });

  it('computes averaged metrics correctly across multiple questions', () => {
    const results: QuestionResult[] = [
      makeAnswerableResult({ id: 'Q01', precision: 0.6, recall: 0.6, faithfulness: 0.95, citationAccurate: true }),
      makeAnswerableResult({ id: 'Q02', precision: 1.0, recall: 1.0, faithfulness: 1.0, citationAccurate: true }),
    ];
    const report = aggregateResults(results, MOCK_CONFIG, 5);
    expect(report.metrics.context_precision.score).toBeCloseTo(0.8, 2);
    expect(report.metrics.context_recall.score).toBeCloseTo(0.8, 2);
    expect(report.metrics.faithfulness.score).toBeCloseTo(0.975, 2);
  });

  it('includes run_date and config in report', () => {
    const report = aggregateResults([makeAnswerableResult()], MOCK_CONFIG, 5);
    expect(report.run_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(report.config.company_id).toBe('company-test-001');
    expect(report.config.employee_tier).toBe('Manager');
    expect(report.config.k).toBe(5);
    expect(report.config.total_questions).toBe(1);
  });

  it('rounds metric scores to 3 decimal places', () => {
    const results: QuestionResult[] = [
      makeAnswerableResult({ precision: 1 / 3, recall: 2 / 3, faithfulness: 0.9 }),
    ];
    const report = aggregateResults(results, MOCK_CONFIG, 5);
    // Should be rounded to 3 decimal places
    expect(String(report.metrics.context_precision.score)).toMatch(/^\d+\.\d{1,3}$/);
  });
});

// ---------------------------------------------------------------------------
// formatReport
// ---------------------------------------------------------------------------

describe('formatReport', () => {
  it('includes PASS for all metrics when all pass', () => {
    const results: QuestionResult[] = [
      makeAnswerableResult({ precision: 0.9, recall: 0.8, faithfulness: 0.97, citationAccurate: true }),
      makeUnanswerableResult({ correctlyRefused: true }),
    ];
    const report = aggregateResults(results, MOCK_CONFIG, 5);
    const formatted = formatReport(report);
    expect(formatted).toContain('✅ PASS');
    expect(formatted).not.toContain('❌ FAIL');
    expect(formatted).toContain('✅ ALL METRICS PASS');
  });

  it('includes FAIL for failing metrics', () => {
    const results: QuestionResult[] = [
      makeAnswerableResult({ faithfulness: 0.7 }), // below threshold
      makeUnanswerableResult({ correctlyRefused: false }),
    ];
    const report = aggregateResults(results, MOCK_CONFIG, 5);
    const formatted = formatReport(report);
    expect(formatted).toContain('❌ FAIL');
    expect(formatted).toContain('❌ ONE OR MORE METRICS FAIL');
  });

  it('includes run_date and company info', () => {
    const report = aggregateResults([makeAnswerableResult()], MOCK_CONFIG, 5);
    const formatted = formatReport(report);
    expect(formatted).toContain('company-test-001');
    expect(formatted).toContain('Manager');
  });

  it('lists failing question IDs in the formatted output', () => {
    const results: QuestionResult[] = [
      makeAnswerableResult({ id: 'Q03', citationAccurate: false }),
      makeUnanswerableResult({ id: 'Q27', correctlyRefused: false }),
    ];
    const report = aggregateResults(results, MOCK_CONFIG, 5);
    const formatted = formatReport(report);
    expect(formatted).toContain('Q03');
    expect(formatted).toContain('Q27');
  });
});

// ---------------------------------------------------------------------------
// TEST_SET composition validation
// ---------------------------------------------------------------------------

describe('TEST_SET composition', () => {
  it('has exactly 30 test cases', () => {
    expect(TEST_SET).toHaveLength(30);
  });

  it('has 20 answerable questions (Q01–Q20)', () => {
    const answerable = TEST_SET.filter(isAnswerable);
    expect(answerable).toHaveLength(20);
  });

  it('has 10 unanswerable questions (Q21–Q30)', () => {
    const unanswerable = TEST_SET.filter((tc) => !isAnswerable(tc));
    expect(unanswerable).toHaveLength(10);
  });

  it('all question IDs are unique', () => {
    const ids = TEST_SET.map((tc) => tc.id);
    const uniqueIds = new Set(ids);
    expect(uniqueIds.size).toBe(30);
  });

  it('answerable questions have required fields', () => {
    const answerable = TEST_SET.filter(isAnswerable) as AnswerableTestCase[];
    for (const tc of answerable) {
      expect(tc.id).toBeTruthy();
      expect(tc.query).toBeTruthy();
      expect(tc.relevant_sections.length).toBeGreaterThan(0);
      expect(tc.ground_truth_citation.doc_name_contains).toBeTruthy();
      expect(tc.ground_truth_citation.section_contains).toBeTruthy();
      expect(tc.ground_truth_citation.page).toBeGreaterThan(0);
    }
  });

  it('unanswerable questions have expected="refusal"', () => {
    const unanswerable = TEST_SET.filter((tc) => !isAnswerable(tc)) as UnanswerableTestCase[];
    for (const tc of unanswerable) {
      expect(tc.expected).toBe('refusal');
    }
  });

  it('answerable questions span diverse policy topics', () => {
    const answerable = TEST_SET.filter(isAnswerable) as AnswerableTestCase[];
    const allSections = answerable.flatMap((tc) => tc.relevant_sections).join(' ').toLowerCase();
    // Should cover all major policy domains
    expect(allSections).toContain('housing');
    expect(allSections).toContain('travel');
    expect(allSections).toContain('school');
    expect(allSections).toContain('medical');
    expect(allSections).toContain('lump sum');
    expect(allSections).toContain('language');
    expect(allSections).toContain('immigration');
  });

  it('unanswerable questions are genuinely off-topic (HR, not relocation)', () => {
    const unanswerable = TEST_SET.filter((tc) => !isAnswerable(tc)) as UnanswerableTestCase[];
    const topics = unanswerable.map((tc) => tc.query.toLowerCase());
    // All should be non-relocation topics
    const offTopicKeywords = ['bonus', 'vacation', 'stock', 'grievance', 'parental', 'remote work', 'dinner', 'equipment', 'pension', 'car'];
    for (const keyword of offTopicKeywords) {
      expect(topics.some((q) => q.includes(keyword))).toBe(true);
    }
  });
});

// ---------------------------------------------------------------------------
// METRIC_THRESHOLDS
// ---------------------------------------------------------------------------

describe('METRIC_THRESHOLDS', () => {
  it('has correct threshold values per spec', () => {
    expect(METRIC_THRESHOLDS.context_precision).toBe(0.80);
    expect(METRIC_THRESHOLDS.context_recall).toBe(0.75);
    expect(METRIC_THRESHOLDS.faithfulness).toBe(0.95);
    expect(METRIC_THRESHOLDS.citation_accuracy).toBe(0.99);
    expect(METRIC_THRESHOLDS.refusal_recall).toBe(0.95);
  });
});
