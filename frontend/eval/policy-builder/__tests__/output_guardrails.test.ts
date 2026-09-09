/**
 * Tests for [P5-2] output_guardrails.ts
 *
 * Groups:
 *   1. extractMonetaryValues — regex extraction
 *   2. normaliseMonetaryValue — normalisation helper
 *   3. checkCrossTierLeak — synchronous cross-tier fence
 *   4. runOutputGuardrails — full pipeline (faithfulness mocked)
 *   5. Stress test — 50 responses with random tier mismatches → zero leaks returned
 *   6. Integration smoke — PASS case end-to-end
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  extractMonetaryValues,
  normaliseMonetaryValue,
  checkCrossTierLeak,
  runOutputGuardrails,
  UNIVERSAL_TIERS,
} from '../output_guardrails';
import type { PolicyChunk } from '../../../src/features/policy-builder/retrieve_policy';

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

function makeChunk(overrides: Partial<PolicyChunk> = {}): PolicyChunk {
  return {
    id: 'chunk-1',
    doc_id: 'doc-1',
    text: 'The housing allowance for Manager grade is EUR 3,500 per month.',
    section_path: 'Housing > Manager',
    category_code: 'CAT-01',
    tier: 'Manager',
    page_start: 12,
    page_end: 12,
    confidence_score: 0.95,
    similarity_score: 0.92,
    bm25_rank: 0.88,
    rrf_score: 0.91,
    ...overrides,
  };
}

const MANAGER_CHUNK = makeChunk({
  id: 'chunk-mgr',
  tier: 'Manager',
  text: 'Manager grade: housing allowance EUR 3,500 per month.',
});

const EXECUTIVE_CHUNK = makeChunk({
  id: 'chunk-exec',
  tier: 'Executive',
  text: 'Executive grade: housing allowance EUR 10,000 per month.',
});

const ALL_TIER_CHUNK = makeChunk({
  id: 'chunk-all',
  tier: 'All',
  text: 'All employees receive EUR 500 for initial setup costs.',
});

// ---------------------------------------------------------------------------
// Mock: faithfulness_checker
// ---------------------------------------------------------------------------

vi.mock('../faithfulness_checker', () => ({
  checkFaithfulness: vi.fn(),
}));

import { checkFaithfulness } from '../faithfulness_checker';
const mockCheckFaithfulness = vi.mocked(checkFaithfulness);

beforeEach(() => {
  vi.clearAllMocks();
  // Default: faithfulness passes
  mockCheckFaithfulness.mockResolvedValue({
    pass: true,
    flaggedSentences: [],
    score: 1.0,
    latency_ms: 10,
  });
});

// ---------------------------------------------------------------------------
// Group 1: extractMonetaryValues
// ---------------------------------------------------------------------------

describe('extractMonetaryValues', () => {
  it('1.1 extracts a single EUR amount', () => {
    const result = extractMonetaryValues('Your housing allowance is EUR 3,500 per month.');
    expect(result).toContain('EUR 3,500');
  });

  it('1.2 extracts multiple currencies in one sentence', () => {
    const result = extractMonetaryValues('Manager: EUR 3,500; Executive: USD 10,000.');
    expect(result).toContain('EUR 3,500');
    expect(result).toContain('USD 10,000');
  });

  it('1.3 extracts GBP amount', () => {
    const result = extractMonetaryValues('Relocation cap: GBP 5,000.');
    expect(result).toContain('GBP 5,000');
  });

  it('1.4 deduplicates identical values', () => {
    const result = extractMonetaryValues('EUR 3,500 allowance plus EUR 3,500 bonus.');
    expect(result.filter((v) => v.includes('3,500'))).toHaveLength(1);
  });

  it('1.5 returns empty array when no monetary values present', () => {
    const result = extractMonetaryValues('No financial information provided.');
    expect(result).toHaveLength(0);
  });

  it('1.6 handles NOK and CHF', () => {
    const result = extractMonetaryValues('NOK 80,000 and CHF 12,500 annually.');
    expect(result.some((v) => v.includes('NOK'))).toBe(true);
    expect(result.some((v) => v.includes('CHF'))).toBe(true);
  });

  it('1.7 extracts decimal amounts', () => {
    const result = extractMonetaryValues('Rate: EUR 1,234.56 per month.');
    expect(result.some((v) => v.includes('1,234.56'))).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Group 2: normaliseMonetaryValue
// ---------------------------------------------------------------------------

describe('normaliseMonetaryValue', () => {
  it('2.1 uppercases currency code and removes thousands separator', () => {
    expect(normaliseMonetaryValue('eur 3,500')).toBe('EUR 3500');
  });

  it('2.2 removes thousands separators', () => {
    expect(normaliseMonetaryValue('EUR 3,500')).toBe('EUR 3500');
  });

  it('2.3 trims whitespace', () => {
    expect(normaliseMonetaryValue('  EUR 3,500  ')).toBe('EUR 3500');
  });

  it('2.4 handles amounts without separators unchanged', () => {
    expect(normaliseMonetaryValue('EUR 3500')).toBe('EUR 3500');
  });
});

// ---------------------------------------------------------------------------
// Group 3: checkCrossTierLeak
// ---------------------------------------------------------------------------

describe('checkCrossTierLeak', () => {
  it('3.1 PASS — response value matches employee tier chunk', () => {
    const response = 'Your housing allowance is EUR 3,500 per month.';
    const result = checkCrossTierLeak(response, [MANAGER_CHUNK], 'Manager');
    expect(result.pass).toBe(true);
    expect(result.leaks).toHaveLength(0);
  });

  it('3.2 FAIL — response contains Executive-tier amount when employee is Manager', () => {
    const response = 'Your housing allowance is EUR 10,000 per month.';
    const result = checkCrossTierLeak(response, [MANAGER_CHUNK, EXECUTIVE_CHUNK], 'Manager');
    expect(result.pass).toBe(false);
    expect(result.leaks.length).toBeGreaterThan(0);
    expect(result.leaks[0].chunk_tier).toBe('Executive');
    expect(result.leaks[0].employee_tier).toBe('Manager');
  });

  it('3.3 PASS — All-tier chunk value does not trigger cross-tier fail', () => {
    const response = 'All employees receive EUR 500 for initial setup costs.';
    const result = checkCrossTierLeak(response, [ALL_TIER_CHUNK], 'Manager');
    expect(result.pass).toBe(true);
  });

  it('3.4 PASS — no monetary values in response', () => {
    const response = 'Please contact HR for more information.';
    const result = checkCrossTierLeak(response, [MANAGER_CHUNK, EXECUTIVE_CHUNK], 'Manager');
    expect(result.pass).toBe(true);
  });

  it('3.5 FAIL — reports flagged_value in leak entry', () => {
    const response = 'Executive housing allowance is EUR 10,000 per month.';
    const result = checkCrossTierLeak(response, [EXECUTIVE_CHUNK], 'Manager');
    expect(result.leaks[0].value).toMatch(/EUR\s*10.000/i);
  });

  it('3.6 PASS — null tier chunk is treated as universal (no leak)', () => {
    const nullTierChunk = makeChunk({ tier: null, text: 'EUR 5,000 setup cost.' });
    const response = 'You receive EUR 5,000 for setup.';
    const result = checkCrossTierLeak(response, [nullTierChunk], 'Manager');
    expect(result.pass).toBe(true);
  });

  it('3.7 PASS — Universal tier chunk does not trigger leak', () => {
    const universalChunk = makeChunk({ tier: 'Universal', text: 'EUR 200 relocation kit.' });
    const response = 'You receive EUR 200 relocation kit.';
    const result = checkCrossTierLeak(response, [universalChunk], 'Manager');
    expect(result.pass).toBe(true);
  });

  it('3.8 records chunk_id in leak entry', () => {
    const response = 'Executive housing allowance is EUR 10,000 per month.';
    const result = checkCrossTierLeak(response, [EXECUTIVE_CHUNK], 'Manager');
    expect(result.leaks[0].chunk_id).toBe('chunk-exec');
  });
});

// ---------------------------------------------------------------------------
// Group 4: runOutputGuardrails — full pipeline
// ---------------------------------------------------------------------------

describe('runOutputGuardrails', () => {
  const CHUNKS = [MANAGER_CHUNK];

  it('4.1 PASS — clean response, faithfulness passes', async () => {
    const result = await runOutputGuardrails(
      'Your housing allowance is EUR 3,500 per month.',
      CHUNKS,
      'Manager',
    );
    expect(result.action).toBe('PASS');
    expect(result.faithfulness_score).toBe(1.0);
    expect(mockCheckFaithfulness).toHaveBeenCalledOnce();
  });

  it('4.2 SERVE_RAW — faithfulness check fails', async () => {
    mockCheckFaithfulness.mockResolvedValueOnce({
      pass: false,
      flaggedSentences: ['The allowance is EUR 99,999.'],
      score: 0.4,
      latency_ms: 20,
    });

    const result = await runOutputGuardrails(
      'The allowance is EUR 99,999.',
      CHUNKS,
      'Manager',
    );
    expect(result.action).toBe('SERVE_RAW');
    expect(result.block_reason).toBe('FAITHFULNESS_BLOCK');
    expect(result.faithfulness_score).toBe(0.4);
  });

  it('4.3 REGENERATE — cross-tier leak detected', async () => {
    const chunksWithExec = [MANAGER_CHUNK, EXECUTIVE_CHUNK];
    const result = await runOutputGuardrails(
      'Your housing allowance is EUR 10,000 per month.',
      chunksWithExec,
      'Manager',
    );
    expect(result.action).toBe('REGENERATE');
    expect(result.block_reason).toBe('CROSS_TIER');
    expect(result.leaks).toBeDefined();
    expect(result.leaks!.length).toBeGreaterThan(0);
    // Cross-tier is detected before faithfulness — faithfulness should NOT have been called
    expect(mockCheckFaithfulness).not.toHaveBeenCalled();
  });

  it('4.4 log_entry is present on REGENERATE', async () => {
    const chunksWithExec = [MANAGER_CHUNK, EXECUTIVE_CHUNK];
    const result = await runOutputGuardrails(
      'Executive allowance EUR 10,000.',
      chunksWithExec,
      'Manager',
      undefined,
      undefined,
      'test-session-001',
    );
    expect(result.log_entry).toBeDefined();
    expect(result.log_entry!.block_type).toBe('CROSS_TIER');
    expect(result.log_entry!.session_id).toBe('test-session-001');
    expect(result.log_entry!.employee_tier).toBe('Manager');
    expect(result.log_entry!.flagged_value).toBeDefined();
    expect(result.log_entry!.timestamp).toBeTruthy();
  });

  it('4.5 log_entry is present on SERVE_RAW', async () => {
    mockCheckFaithfulness.mockResolvedValueOnce({
      pass: false,
      flaggedSentences: ['hallucinated sentence'],
      score: 0.0,
      latency_ms: 5,
    });

    const result = await runOutputGuardrails(
      'hallucinated sentence',
      CHUNKS,
      'Manager',
      undefined,
      undefined,
      'test-session-002',
    );
    expect(result.log_entry).toBeDefined();
    expect(result.log_entry!.block_type).toBe('FAITHFULNESS_BLOCK');
    expect(result.log_entry!.faithfulness_score).toBe(0.0);
  });

  it('4.6 no log_entry on PASS', async () => {
    const result = await runOutputGuardrails(
      'Your housing allowance is EUR 3,500.',
      CHUNKS,
      'Manager',
    );
    expect(result.action).toBe('PASS');
    expect(result.log_entry).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// Group 5: Stress test — 50 responses, zero cross-tier data leaks
// ---------------------------------------------------------------------------

describe('Stress test — 50 responses with cross-tier chunk injection', () => {
  it('5.1 zero cross-tier leaks return PASS when employee tier matches all response values', () => {
    // All responses reference Manager-tier values from Manager-tier chunks
    const managerAmounts = [
      'EUR 3,500', 'EUR 4,000', 'EUR 2,800', 'USD 5,000', 'GBP 3,000',
      'NOK 35,000', 'EUR 1,200', 'EUR 6,500', 'USD 8,000', 'EUR 2,500',
    ];
    const executiveAmounts = [
      'EUR 10,000', 'EUR 15,000', 'USD 20,000', 'GBP 12,000', 'EUR 8,500',
    ];

    const chunks = [
      ...managerAmounts.map((amt, i) =>
        makeChunk({ id: `mgr-${i}`, tier: 'Manager', text: `Manager allowance ${amt}.` }),
      ),
      ...executiveAmounts.map((amt, i) =>
        makeChunk({ id: `exec-${i}`, tier: 'Executive', text: `Executive allowance ${amt}.` }),
      ),
    ];

    let passCt = 0;
    let failCt = 0;

    for (let i = 0; i < 50; i++) {
      // Pick a random Manager-tier amount — response should always PASS
      const amount = managerAmounts[i % managerAmounts.length];
      const response = `Your entitlement is ${amount} per month.`;
      const result = checkCrossTierLeak(response, chunks, 'Manager');
      result.pass ? passCt++ : failCt++;
    }

    expect(failCt).toBe(0);
    expect(passCt).toBe(50);
  });

  it('5.2 all cross-tier responses are correctly detected as leaks', () => {
    const executiveAmounts = ['EUR 10,000', 'EUR 15,000', 'USD 20,000', 'GBP 12,000'];
    const chunks = executiveAmounts.map((amt, i) =>
      makeChunk({ id: `exec-${i}`, tier: 'Executive', text: `Executive allowance ${amt}.` }),
    );

    let leakDetected = 0;

    for (let i = 0; i < 50; i++) {
      const amount = executiveAmounts[i % executiveAmounts.length];
      const response = `Your housing allowance is ${amount} per month.`;
      const result = checkCrossTierLeak(response, chunks, 'Manager');
      if (!result.pass) leakDetected++;
    }

    // All 50 responses contain Executive-tier amounts — all should be detected
    expect(leakDetected).toBe(50);
  });
});

// ---------------------------------------------------------------------------
// Group 6: Integration smoke — UNIVERSAL_TIERS set is complete
// ---------------------------------------------------------------------------

describe('UNIVERSAL_TIERS constant', () => {
  it('6.1 contains expected values', () => {
    expect(UNIVERSAL_TIERS.has('All')).toBe(true);
    expect(UNIVERSAL_TIERS.has('Universal')).toBe(true);
    expect(UNIVERSAL_TIERS.has('all')).toBe(true);
    expect(UNIVERSAL_TIERS.has('')).toBe(true);
  });

  it('6.2 does not contain employee-specific tiers', () => {
    expect(UNIVERSAL_TIERS.has('Manager')).toBe(false);
    expect(UNIVERSAL_TIERS.has('Executive')).toBe(false);
    expect(UNIVERSAL_TIERS.has('Staff')).toBe(false);
  });
});
