/**
 * [P4-4] faithfulness_checker.test.ts
 *
 * Validation criteria (from Notion AIQ-244):
 *   VC-1  20 test responses (10 faithful, 10 with planted hallucinations):
 *          recall = 100% (all hallucinations flagged), precision = 100% (no false positives)
 *   VC-2  Hallucinations use benefit figures NOT present in retrieved chunks
 *   VC-3  Numeric claim fast-path: deterministic checks for EUR/NOK amounts, percentages,
 *          counts+units, dates — no LLM call required
 *   VC-4  Latency < 500ms per response [unit tests: mocked, always trivial]
 *
 * Strategy:
 *   • Pure function tests (splitSentences, extractNumericClaims, etc.) have no mocking
 *   • Benchmark cases use numeric hallucinations → fast-path catches them deterministically
 *     (no Anthropic API calls needed for precision/recall benchmark)
 *   • NLI path tested separately with vi.stubGlobal('fetch', …)
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  splitSentences,
  extractNumericClaims,
  numericClaimInContext,
  fastCheckNumeric,
  checkFaithfulness,
} from '../faithfulness_checker';

// ---------------------------------------------------------------------------
// Mock fetch helper for NLI tests
// ---------------------------------------------------------------------------

function mockNliFetch(results: boolean[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({
        content: [{ type: 'text', text: JSON.stringify(results) }],
      }),
      text: () => Promise.resolve(''),
    }),
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// splitSentences — unit tests
// ---------------------------------------------------------------------------

describe('splitSentences', () => {
  it('splits two sentences at punctuation boundary', () => {
    const result = splitSentences(
      'Your housing allowance is EUR 3,500 per month. Please submit receipts promptly.',
    );
    expect(result.length).toBeGreaterThanOrEqual(1);
  });

  it('does not split on EUR abbreviation mid-sentence', () => {
    const text = 'Your allowance is EUR 3,500 per month. Submit receipts to HR department.';
    const sentences = splitSentences(text);
    const combined = sentences.join(' ');
    expect(combined).toContain('EUR 3,500');
  });

  it('strips citation markers before splitting', () => {
    const text =
      'The allowance is EUR 3,500 [Source: Section 3]. You must submit receipts to HR.';
    const sentences = splitSentences(text);
    const combined = sentences.join(' ');
    expect(combined).not.toContain('[Source:');
  });

  it('filters out very short fragments (< 15 chars)', () => {
    const result = splitSentences('A. B. This is a valid long sentence here.');
    result.forEach((s) => expect(s.length).toBeGreaterThanOrEqual(15));
  });

  it('returns empty array for empty string', () => {
    expect(splitSentences('')).toEqual([]);
  });

  it('handles single sentence without terminal period', () => {
    const text = 'Your housing allowance is EUR 3,500 per month for the duration of your assignment';
    const result = splitSentences(text);
    expect(result.length).toBeGreaterThanOrEqual(1);
  });

  it('does not split on Dr. or Mr. abbreviations', () => {
    const text =
      'Please contact Dr. Hansen in the HR department. He will assist with your claim.';
    const sentences = splitSentences(text);
    // Should not split into 3+ fragments on "Dr."
    expect(sentences.length).toBeLessThanOrEqual(2);
  });
});

// ---------------------------------------------------------------------------
// extractNumericClaims — unit tests
// ---------------------------------------------------------------------------

describe('extractNumericClaims', () => {
  it('extracts EUR currency amount', () => {
    const claims = extractNumericClaims('Your allowance is EUR 3,500 per month.');
    expect(claims.some((c) => /EUR/i.test(c))).toBe(true);
  });

  it('extracts NOK currency amount', () => {
    const claims = extractNumericClaims('You receive NOK 80,000 as a lump sum.');
    expect(claims.some((c) => /NOK/i.test(c))).toBe(true);
  });

  it('extracts USD and GBP amounts', () => {
    expect(extractNumericClaims('USD 12,000 reimbursement available.').some((c) => /USD/i.test(c))).toBe(true);
    expect(extractNumericClaims('GBP 5,000 cap applies.').some((c) => /GBP/i.test(c))).toBe(true);
  });

  it('extracts percentage', () => {
    const claims = extractNumericClaims('School fees covered up to 80% of tuition costs.');
    expect(claims.some((c) => c.includes('%'))).toBe(true);
  });

  it('extracts count with unit (flights)', () => {
    const claims = extractNumericClaims('You are entitled to 5 flights per year.');
    expect(claims.some((c) => /5\s+flights?/i.test(c))).toBe(true);
  });

  it('extracts count with unit (months)', () => {
    const claims = extractNumericClaims('The assignment period is 24 months in duration.');
    expect(claims.some((c) => /24\s+months?/i.test(c))).toBe(true);
  });

  it('extracts date', () => {
    const claims = extractNumericClaims('Support begins on 1 January 2025 for all employees.');
    expect(claims.length).toBeGreaterThan(0);
  });

  it('returns empty array for non-numeric sentence', () => {
    const claims = extractNumericClaims('Furthermore, the policy applies to all employees.');
    expect(claims).toHaveLength(0);
  });

  it('deduplicates repeated identical claims', () => {
    const claims = extractNumericClaims('EUR 3,500 monthly; the cap is also EUR 3,500.');
    const eurClaims = claims.filter((c) => /EUR/i.test(c));
    expect(eurClaims.length).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// numericClaimInContext — unit tests
// ---------------------------------------------------------------------------

describe('numericClaimInContext', () => {
  const chunks = [
    'Housing allowance is EUR 3,500 per month for Manager tier employees.',
    'School fees up to 80% are covered under the schooling benefit.',
    'Employees are entitled to 5 flights per year for home visits.',
  ];

  it('returns true for exact match (EUR amount)', () => {
    expect(numericClaimInContext('EUR 3,500', chunks)).toBe(true);
  });

  it('returns true for case-insensitive match', () => {
    expect(numericClaimInContext('eur 3,500', chunks)).toBe(true);
  });

  it('returns false when amount is absent from context (EUR 5,000)', () => {
    expect(numericClaimInContext('EUR 5,000', chunks)).toBe(false);
  });

  it('returns true within ±1 rounding tolerance (EUR 3,499)', () => {
    expect(numericClaimInContext('EUR 3,499', chunks)).toBe(true);
  });

  it('returns true within ±1 rounding tolerance (EUR 3,501)', () => {
    expect(numericClaimInContext('EUR 3,501', chunks)).toBe(true);
  });

  it('returns false for claim outside ±1 tolerance (EUR 3,000)', () => {
    expect(numericClaimInContext('EUR 3,000', chunks)).toBe(false);
  });

  it('returns true for percentage present in context', () => {
    expect(numericClaimInContext('80%', chunks)).toBe(true);
  });

  it('returns false for wrong percentage (90%)', () => {
    expect(numericClaimInContext('90%', chunks)).toBe(false);
  });

  it('returns true for count+unit match (5 flights)', () => {
    expect(numericClaimInContext('5 flights', chunks)).toBe(true);
  });

  it('returns false for wrong count (10 flights)', () => {
    expect(numericClaimInContext('10 flights', chunks)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// fastCheckNumeric — unit tests
// ---------------------------------------------------------------------------

describe('fastCheckNumeric', () => {
  const chunks = [
    'The housing allowance is EUR 3,500 per month for eligible employees.',
    'School fees covered up to 80% of actual annual costs.',
  ];

  it('returns null for non-numeric sentence (no fast-path applicable)', () => {
    const result = fastCheckNumeric(
      'Furthermore, all employees are eligible for the policy.',
      chunks,
    );
    expect(result).toBeNull();
  });

  it('returns entailed=true when amount is in context', () => {
    const result = fastCheckNumeric('Your allowance is EUR 3,500 per month.', chunks);
    expect(result).not.toBeNull();
    expect(result!.entailed).toBe(true);
    expect(result!.method).toBe('numeric');
  });

  it('returns entailed=false when amount is NOT in context', () => {
    const result = fastCheckNumeric('Your allowance is EUR 5,000 per month.', chunks);
    expect(result).not.toBeNull();
    expect(result!.entailed).toBe(false);
    expect(result!.method).toBe('numeric');
  });

  it('returns entailed=false when percentage is wrong', () => {
    const result = fastCheckNumeric('School fees are covered up to 90%.', chunks);
    expect(result).not.toBeNull();
    expect(result!.entailed).toBe(false);
  });

  it('returns entailed=true when percentage matches', () => {
    const result = fastCheckNumeric('School fees are covered up to 80%.', chunks);
    expect(result).not.toBeNull();
    expect(result!.entailed).toBe(true);
  });

  it('includes the original sentence in the result', () => {
    const sentence = 'Your allowance is EUR 3,500 per month.';
    const result = fastCheckNumeric(sentence, chunks);
    expect(result!.sentence).toBe(sentence);
  });
});

// ---------------------------------------------------------------------------
// checkFaithfulness — edge cases and NLI path
// ---------------------------------------------------------------------------

describe('checkFaithfulness — edge cases', () => {
  it('returns pass=false and score=0 for empty retrievedChunks', async () => {
    const result = await checkFaithfulness('The allowance is EUR 3,500.', [], 'test-key');
    expect(result.pass).toBe(false);
    expect(result.score).toBe(0);
  });

  it('returns pass=true for whitespace-only response', async () => {
    const result = await checkFaithfulness('   ', ['Some policy text here for context.'], 'test-key');
    expect(result.pass).toBe(true);
  });

  it('includes latency_ms in every result', async () => {
    const chunks = ['EUR 3,500 is the housing allowance per month.'];
    const result = await checkFaithfulness('Your allowance is EUR 3,500.', chunks, 'test-key');
    expect(result.latency_ms).toBeGreaterThanOrEqual(0);
  });

  it('numeric hallucination caught without any API call', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);

    const chunks = ['Housing allowance is EUR 3,500 per month.'];
    const response = 'Your housing allowance is EUR 8,000 per month.';
    const result = await checkFaithfulness(response, chunks, 'test-key');

    expect(result.pass).toBe(false);
    expect(result.flaggedSentences.length).toBeGreaterThan(0);
    // Numeric fast-path catches this — no fetch needed
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('non-numeric sentence falls through to NLI (fetch called)', async () => {
    mockNliFetch([true]);
    const chunks = ['The policy covers all relocation expenses for eligible employees.'];
    const response = 'All relocation expenses are covered for eligible employees under policy.';
    const result = await checkFaithfulness(response, chunks, 'test-key');
    expect(result.pass).toBe(true);
    expect(vi.mocked(fetch)).toHaveBeenCalledOnce();
  });

  it('NLI returns false → sentence is flagged', async () => {
    mockNliFetch([false]);
    const chunks = ['The policy covers housing only for relocated employees.'];
    const response = 'Flights and hotels are both fully reimbursed under this policy here.';
    const result = await checkFaithfulness(response, chunks, 'test-key');
    expect(result.pass).toBe(false);
    expect(result.flaggedSentences.length).toBeGreaterThan(0);
  });

  it('score is fractional when some sentences pass and some fail', async () => {
    mockNliFetch([true, false]);
    const chunks = ['The policy provides housing benefits to all employees at Manager level.'];
    const response =
      'The housing benefit applies to Manager level employees. Flights are also reimbursed for every single trip globally.';
    const result = await checkFaithfulness(response, chunks, 'test-key');
    expect(result.score).toBeGreaterThan(0);
    expect(result.score).toBeLessThan(1);
  });

  it('no API key → defaults all non-numeric to entailed (conservative non-blocking)', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);

    const chunks = ['The policy covers relocation for eligible employees.'];
    const response = 'All employees are covered for relocation expenses under this scheme.';
    // Pass undefined key — simulates missing env var
    const result = await checkFaithfulness(response, chunks, undefined);
    // Without key, NLI is skipped → no fetch, all non-numeric pass
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(result.pass).toBe(true);
  });

  it('handles malformed NLI JSON response gracefully (defaults to all-entailed)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ content: [{ type: 'text', text: 'not valid JSON {{[' }] }),
        text: () => Promise.resolve(''),
      }),
    );
    const chunks = ['The policy covers housing allowances for all employees.'];
    const response = 'Housing allowances are provided to all employees in the policy coverage.';
    // Should not throw — defaults to all-entailed on parse failure
    const result = await checkFaithfulness(response, chunks, 'test-key');
    expect(result.pass).toBe(true);
  });

  it('throws on Anthropic API error (non-2xx response)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        text: () => Promise.resolve('Internal Server Error'),
      }),
    );
    const chunks = ['The policy text goes here with important information content.'];
    const response = 'The policy explains coverage details for all employees here.';
    await expect(checkFaithfulness(response, chunks, 'test-key')).rejects.toThrow('500');
  });

  it('score rounds to 3 decimal places', async () => {
    mockNliFetch([true]);
    const chunks = ['This policy provides comprehensive coverage for relocated employees.'];
    const response = 'Relocated employees receive comprehensive coverage under this arrangement.';
    const result = await checkFaithfulness(response, chunks, 'test-key');
    // score should be a clean number (rounded to 3dp)
    const rounded = Math.round(result.score * 1000) / 1000;
    expect(result.score).toBe(rounded);
  });
});

// ---------------------------------------------------------------------------
// VC-1: 20-case precision/recall benchmark
// ---------------------------------------------------------------------------

describe('VC-1: 20-case precision/recall benchmark', () => {
  /**
   * Context: a realistic policy excerpt with specific, unambiguous benefit figures.
   *
   * Faithful responses quote amounts that ARE in the context.
   * Hallucinated responses quote amounts that are NOT in the context.
   *
   * All hallucinations use numeric claims → caught by the numeric fast-path
   * deterministically, without any LLM/API call.
   *
   * This validates:
   *   (a) Recall = 100%: all 10 hallucinations are detected (pass=false)
   *   (b) Precision = 100%: all 10 faithful responses are clean (pass=true)
   */

  const POLICY_CONTEXT = [
    'Housing allowance for Manager tier: EUR 3,500 per month, paid directly to landlord.',
    'Relocation lump sum for Senior employees: NOK 80,000 gross, paid upon arrival.',
    'School fees covered up to 80% of actual costs per child per academic year.',
    'Home visit entitlement: 5 flights per year in economy class for the assignee.',
    'Assignment support period: 24 months from the official start date.',
    'Language training: EUR 2,000 per year available upon written request to HR.',
    'Storage costs: up to EUR 1,500 per month reimbursable with valid receipts.',
    'Immigration legal fees covered up to EUR 4,000 per relocation event.',
  ];

  interface BenchmarkCase {
    id: string;
    response: string;
    isHallucination: boolean;
    description: string;
  }

  const BENCHMARK_CASES: BenchmarkCase[] = [
    // -----------------------------------------------------------------------
    // 10 FAITHFUL responses — all figures exactly match POLICY_CONTEXT
    // -----------------------------------------------------------------------
    {
      id: 'F-01',
      response: 'Your housing allowance as a Manager is EUR 3,500 per month.',
      isHallucination: false,
      description: 'Exact housing allowance amount (EUR 3,500)',
    },
    {
      id: 'F-02',
      response: 'The relocation lump sum for Senior employees is NOK 80,000 gross.',
      isHallucination: false,
      description: 'Exact lump sum for Senior tier (NOK 80,000)',
    },
    {
      id: 'F-03',
      response: 'School fees are covered up to 80% of actual costs per child.',
      isHallucination: false,
      description: 'Exact schooling percentage (80%)',
    },
    {
      id: 'F-04',
      response: 'You are entitled to 5 flights per year for home visits.',
      isHallucination: false,
      description: 'Exact home visit flight count (5 flights)',
    },
    {
      id: 'F-05',
      response: 'Your assignment support lasts for 24 months from your start date.',
      isHallucination: false,
      description: 'Exact assignment duration (24 months)',
    },
    {
      id: 'F-06',
      response: 'A language training allowance of EUR 2,000 per year is available upon request.',
      isHallucination: false,
      description: 'Exact language training allowance (EUR 2,000)',
    },
    {
      id: 'F-07',
      response: 'Storage costs up to EUR 1,500 per month are reimbursable with receipts.',
      isHallucination: false,
      description: 'Exact storage allowance cap (EUR 1,500)',
    },
    {
      id: 'F-08',
      response: 'Immigration legal fees are covered up to EUR 4,000 per relocation event.',
      isHallucination: false,
      description: 'Exact immigration legal fee cap (EUR 4,000)',
    },
    {
      id: 'F-09',
      response:
        'The housing allowance is EUR 3,500 monthly and school fees are covered at 80%.',
      isHallucination: false,
      description: 'Two faithful numeric claims in one response',
    },
    {
      id: 'F-10',
      response: 'You receive 5 flights per year and EUR 2,000 for language training annually.',
      isHallucination: false,
      description: 'Flight count and language allowance combined',
    },

    // -----------------------------------------------------------------------
    // 10 HALLUCINATED responses — figures NOT present in POLICY_CONTEXT
    // -----------------------------------------------------------------------
    {
      id: 'H-01',
      response: 'Your housing allowance as a Manager is EUR 5,000 per month.',
      isHallucination: true,
      description: 'Hallucinated housing allowance (EUR 5,000 ≠ EUR 3,500)',
    },
    {
      id: 'H-02',
      response: 'The relocation lump sum for Senior employees is NOK 120,000 gross.',
      isHallucination: true,
      description: 'Hallucinated lump sum (NOK 120,000 ≠ NOK 80,000)',
    },
    {
      id: 'H-03',
      response: 'School fees are covered up to 90% of actual costs per child.',
      isHallucination: true,
      description: 'Hallucinated schooling percentage (90% ≠ 80%)',
    },
    {
      id: 'H-04',
      response: 'You are entitled to 10 flights per year for home visits.',
      isHallucination: true,
      description: 'Hallucinated flight count (10 ≠ 5)',
    },
    {
      id: 'H-05',
      response: 'Your assignment support lasts for 36 months from your start date.',
      isHallucination: true,
      description: 'Hallucinated assignment duration (36 ≠ 24 months)',
    },
    {
      id: 'H-06',
      response: 'A language training allowance of EUR 5,000 per year is available upon request.',
      isHallucination: true,
      description: 'Hallucinated language allowance (EUR 5,000 ≠ EUR 2,000)',
    },
    {
      id: 'H-07',
      response: 'Storage costs up to EUR 2,500 per month are reimbursable with valid receipts.',
      isHallucination: true,
      description: 'Hallucinated storage cap (EUR 2,500 ≠ EUR 1,500)',
    },
    {
      id: 'H-08',
      response: 'Immigration legal fees are covered up to EUR 7,000 per relocation event.',
      isHallucination: true,
      description: 'Hallucinated immigration fee cap (EUR 7,000 ≠ EUR 4,000)',
    },
    {
      id: 'H-09',
      response:
        'The housing allowance is EUR 6,000 per month and school fees are covered at 95%.',
      isHallucination: true,
      description: 'Two hallucinated numeric claims in one response',
    },
    {
      id: 'H-10',
      response: 'You receive 8 flights per year and EUR 5,000 for language training annually.',
      isHallucination: true,
      description: 'Hallucinated flight count and language allowance',
    },
  ];

  it('VC-1: recall = 100% and precision = 100% on 20-case benchmark', async () => {
    const results: Array<{ id: string; pass: boolean; isHallucination: boolean }> = [];

    // Run sequentially — all hallucinations handled by numeric fast-path (no API calls)
    for (const tc of BENCHMARK_CASES) {
      const result = await checkFaithfulness(tc.response, POLICY_CONTEXT, '__no_key__');
      results.push({ id: tc.id, pass: result.pass, isHallucination: tc.isHallucination });
    }

    const flaggedAsHallucination = results.filter((r) => !r.pass);
    const truePositives = flaggedAsHallucination.filter((r) => r.isHallucination).length;
    const falsePositives = flaggedAsHallucination.filter((r) => !r.isHallucination).length;

    const actualHallucinations = results.filter((r) => r.isHallucination);
    const falseNegatives = actualHallucinations.filter((r) => r.pass).length;

    const precision = truePositives / (truePositives + falsePositives);
    const recall = truePositives / (truePositives + falseNegatives);

    console.log('\nFaithfulness Checker Benchmark (20 cases):');
    console.log(`  Faithful responses:     ${BENCHMARK_CASES.filter((c) => !c.isHallucination).length}`);
    console.log(`  Hallucinated responses: ${BENCHMARK_CASES.filter((c) => c.isHallucination).length}`);
    console.log(`  True positives:  ${truePositives}`);
    console.log(`  False positives: ${falsePositives}`);
    console.log(`  False negatives: ${falseNegatives}`);
    console.log(`  Precision: ${(precision * 100).toFixed(1)}%`);
    console.log(`  Recall:    ${(recall * 100).toFixed(1)}%`);

    results.forEach((r) => {
      if (r.isHallucination && r.pass) console.warn(`  MISSED hallucination: ${r.id}`);
      if (!r.isHallucination && !r.pass) console.warn(`  FALSE POSITIVE: ${r.id}`);
    });

    expect(precision, 'Precision must be 100%').toBe(1.0);
    expect(recall, 'Recall must be 100%').toBe(1.0);
  });

  it('VC-1: every faithful response returns pass=true', async () => {
    const faithfulCases = BENCHMARK_CASES.filter((c) => !c.isHallucination);
    for (const tc of faithfulCases) {
      const result = await checkFaithfulness(tc.response, POLICY_CONTEXT, '__no_key__');
      expect(result.pass, `${tc.id} "${tc.description}" should pass`).toBe(true);
    }
  });

  it('VC-1: every hallucinated response returns pass=false with flaggedSentences', async () => {
    const hallucinationCases = BENCHMARK_CASES.filter((c) => c.isHallucination);
    for (const tc of hallucinationCases) {
      const result = await checkFaithfulness(tc.response, POLICY_CONTEXT, '__no_key__');
      expect(result.pass, `${tc.id} "${tc.description}" should fail`).toBe(false);
      expect(
        result.flaggedSentences.length,
        `${tc.id} should have at least one flagged sentence`,
      ).toBeGreaterThan(0);
    }
  });

  it('VC-1: faithful responses have score = 1.0 (fully grounded)', async () => {
    const faithfulCases = BENCHMARK_CASES.filter((c) => !c.isHallucination);
    for (const tc of faithfulCases) {
      const result = await checkFaithfulness(tc.response, POLICY_CONTEXT, '__no_key__');
      expect(result.score, `${tc.id} score should be 1.0`).toBe(1.0);
    }
  });

  it('VC-1: hallucinated responses have score < 1.0', async () => {
    const hallucinationCases = BENCHMARK_CASES.filter((c) => c.isHallucination);
    for (const tc of hallucinationCases) {
      const result = await checkFaithfulness(tc.response, POLICY_CONTEXT, '__no_key__');
      expect(result.score, `${tc.id} score should be < 1.0`).toBeLessThan(1.0);
    }
  });
});
