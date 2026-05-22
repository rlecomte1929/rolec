/**
 * [P4-5] assistant_router.test.ts
 *
 * Validation criteria (from Notion AIQ-245):
 *   VC-1  Query with no relevant context (top RRF < 0.65) → refusal string, zero LLM calls
 *   VC-2  Faithfulness fail → raw excerpt, not generated response
 *   VC-3  Expired policy → exact POLICY_EXPIRED_MSG string
 *   VC-4  All fallback paths produce log entries with reason code
 *   VC-5  TOPIC_REJECTED path: no retrieval, no LLM
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';

// ---------------------------------------------------------------------------
// Module mocks — must appear before any import of the mocked modules
// ---------------------------------------------------------------------------

vi.mock('../../../lib/supabase', () => {
  const fromMock = vi.fn();
  return {
    supabase: {
      from: fromMock,
      auth: { getSession: vi.fn(), getUser: vi.fn() },
    },
  };
});

vi.mock('../topic_classifier', () => ({
  classifyQuery: vi.fn(),
  fastPathReject: vi.fn().mockReturnValue(null),
  REJECTION_MSG:
    'I can only answer questions about your relocation policy and associated benefits. ' +
    'For other matters, please contact your HR Business Partner directly.',
}));

vi.mock('../retrieve_policy', () => ({
  retrievePolicy: vi.fn(),
  computeRRF: vi.fn(),
}));

vi.mock('../faithfulness_checker', () => ({
  checkFaithfulness: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Imports (after mocks)
// ---------------------------------------------------------------------------

import {
  processQuery,
  isPolicyExpired,
  generateResponse,
  buildRawExcerptResponse,
  LOW_CONFIDENCE_MSG,
  POLICY_EXPIRED_MSG,
  TOPIC_REJECTION_MSG,
  MIN_RRF_SCORE,
  POLICY_MAX_AGE_DAYS,
} from '../assistant_router';
import { classifyQuery } from '../topic_classifier';
import { retrievePolicy } from '../retrieve_policy';
import { checkFaithfulness } from '../faithfulness_checker';
import { supabase } from '../../../lib/supabase';
import type { PolicyChunk } from '../retrieve_policy';

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const MOCK_EMPLOYEE_ID = 'emp-123';
const MOCK_COMPANY_ID = 'acme-corp';
const MOCK_TIER = 'Manager';

const MOCK_CHUNKS: PolicyChunk[] = [
  {
    id: 'chunk-1',
    doc_id: 'doc-1',
    text: 'Housing allowance for Manager tier is EUR 3,500 per month.',
    section_path: 'Section 3 > Housing',
    category_code: 'housing_allowance',
    tier: 'Manager',
    page_start: 5,
    page_end: 5,
    confidence_score: 0.95,
    similarity_score: 0.88,
    bm25_rank: 0.72,
    rrf_score: 0.82,
  },
  {
    id: 'chunk-2',
    doc_id: 'doc-1',
    text: 'School fees up to 80% of actual costs per child are covered.',
    section_path: 'Section 4 > Education',
    category_code: 'schooling',
    tier: 'Manager',
    page_start: 8,
    page_end: 8,
    confidence_score: 0.91,
    similarity_score: 0.79,
    bm25_rank: 0.68,
    rrf_score: 0.77,
  },
];

// ---------------------------------------------------------------------------
// Supabase mock helpers
// ---------------------------------------------------------------------------

/** Returns a Supabase chain that serves a profile row */
function makeProfileChain(profile: { company_id: string; employee_tier: string } | null) {
  return {
    select: () => ({
      eq: () => ({
        single: async () => ({ data: profile, error: profile ? null : { message: 'not found' } }),
      }),
    }),
  };
}

/** Returns a Supabase chain that serves a policy_documents row */
function makePolicyDocChain(data: { effective_date: string | null; processing_status: string } | null) {
  return {
    select: () => ({
      eq: () => ({
        eq: () => ({
          order: () => ({
            limit: () => ({
              maybeSingle: async () => ({ data, error: data ? null : { message: 'no rows' } }),
            }),
          }),
        }),
      }),
    }),
  };
}

/** Set up supabase.from to route by table name */
function mockSupabase(opts: {
  profile?: { company_id: string; employee_tier: string } | null;
  policyDoc?: { effective_date: string | null; processing_status: string } | null;
}) {
  vi.mocked(supabase.from).mockImplementation((table: string) => {
    if (table === 'profiles') return makeProfileChain(opts.profile ?? null) as any;
    if (table === 'policy_documents') return makePolicyDocChain(opts.policyDoc ?? null) as any;
    return makeProfileChain(null) as any;
  });
}

const TODAY_DATE = new Date().toISOString().slice(0, 10);
const THREE_YEARS_AGO = new Date(Date.now() - 3 * 365 * 24 * 60 * 60 * 1000)
  .toISOString()
  .slice(0, 10);

function mockGenerateFetch(text: string) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ content: [{ type: 'text', text }] }),
      text: async () => '',
    }),
  );
}

/** Default happy-path classification */
function mockInScope() {
  vi.mocked(classifyQuery).mockResolvedValue({
    category: 'hr_policy',
    confidence: 0.95,
    query_hash: 'abc12345',
    latency_ms: 6,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

describe('exported constants', () => {
  it('LOW_CONFIDENCE_MSG references HR administrator', () => {
    expect(LOW_CONFIDENCE_MSG).toContain('HR administrator');
  });
  it('POLICY_EXPIRED_MSG references HR', () => {
    expect(POLICY_EXPIRED_MSG).toContain('contact HR');
  });
  it('TOPIC_REJECTION_MSG references relocation policy', () => {
    expect(TOPIC_REJECTION_MSG).toContain('relocation policy');
  });
  it('MIN_RRF_SCORE is 0.65', () => {
    expect(MIN_RRF_SCORE).toBe(0.65);
  });
  it('POLICY_MAX_AGE_DAYS is 730', () => {
    expect(POLICY_MAX_AGE_DAYS).toBe(730);
  });
});

// ---------------------------------------------------------------------------
// buildRawExcerptResponse
// ---------------------------------------------------------------------------

describe('buildRawExcerptResponse', () => {
  it('includes section_path as label', () => {
    expect(buildRawExcerptResponse(MOCK_CHUNKS)).toContain('Section 3 > Housing');
  });

  it('includes chunk text', () => {
    expect(buildRawExcerptResponse(MOCK_CHUNKS)).toContain('EUR 3,500');
  });

  it('limits to top 3 chunks', () => {
    const sixChunks: PolicyChunk[] = Array.from({ length: 6 }, (_, i) => ({
      ...MOCK_CHUNKS[0],
      id: `chunk-${i}`,
      section_path: `SectionLabel${i}`,
    }));
    const result = buildRawExcerptResponse(sixChunks);
    // Should include labels 0,1,2 but not 3,4,5
    expect(result).toContain('SectionLabel0');
    expect(result).toContain('SectionLabel2');
    expect(result).not.toContain('SectionLabel3');
  });

  it('includes disclaimer about direct retrieval', () => {
    expect(buildRawExcerptResponse(MOCK_CHUNKS)).toContain('retrieved directly');
  });
});

// ---------------------------------------------------------------------------
// generateResponse
// ---------------------------------------------------------------------------

describe('generateResponse', () => {
  it('calls Anthropic API at temperature=0 with correct model', async () => {
    mockGenerateFetch('The housing allowance is EUR 3,500 per month.');
    await generateResponse('What is my housing allowance?', MOCK_CHUNKS, 'test-key');
    expect(vi.mocked(fetch)).toHaveBeenCalledOnce();
    const body = JSON.parse((vi.mocked(fetch).mock.calls[0][1] as RequestInit).body as string);
    expect(body.temperature).toBe(0);
    expect(body.model).toBe('claude-haiku-4-5-20251001');
  });

  it('includes section_path labels in prompt context', async () => {
    mockGenerateFetch('Answer.');
    await generateResponse('query', MOCK_CHUNKS, 'test-key');
    const body = JSON.parse((vi.mocked(fetch).mock.calls[0][1] as RequestInit).body as string);
    const userContent = body.messages[0].content as string;
    expect(userContent).toContain('Section 3 > Housing');
  });

  it('includes grounded system prompt', async () => {
    mockGenerateFetch('Answer.');
    await generateResponse('query', MOCK_CHUNKS, 'test-key');
    const body = JSON.parse((vi.mocked(fetch).mock.calls[0][1] as RequestInit).body as string);
    expect(body.system).toContain('ONLY');
  });

  it('returns the text from the API response', async () => {
    const expected = 'EUR 3,500 per month is your housing allowance.';
    mockGenerateFetch(expected);
    const result = await generateResponse('What is my allowance?', MOCK_CHUNKS, 'test-key');
    expect(result).toBe(expected);
  });

  it('throws on non-2xx API response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 503, text: async () => 'Service Unavailable',
    }));
    await expect(generateResponse('q', MOCK_CHUNKS, 'key')).rejects.toThrow('503');
  });

  it('throws when response body has no text content', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ content: [] }),
      text: async () => '',
    }));
    await expect(generateResponse('q', MOCK_CHUNKS, 'key')).rejects.toThrow('empty response');
  });
});

// ---------------------------------------------------------------------------
// isPolicyExpired
// ---------------------------------------------------------------------------

describe('isPolicyExpired', () => {
  it('returns false when an approved, recent document exists', async () => {
    vi.mocked(supabase.from).mockReturnValue(makePolicyDocChain({
      effective_date: TODAY_DATE,
      processing_status: 'approved',
    }) as any);
    expect(await isPolicyExpired('test-company')).toBe(false);
  });

  it('returns true when no approved document exists', async () => {
    vi.mocked(supabase.from).mockReturnValue(makePolicyDocChain(null) as any);
    expect(await isPolicyExpired('test-company')).toBe(true);
  });

  it('returns true when effective_date is older than POLICY_MAX_AGE_DAYS', async () => {
    vi.mocked(supabase.from).mockReturnValue(makePolicyDocChain({
      effective_date: THREE_YEARS_AGO,
      processing_status: 'approved',
    }) as any);
    expect(await isPolicyExpired('test-company')).toBe(true);
  });

  it('returns false when effective_date is null (assume valid)', async () => {
    vi.mocked(supabase.from).mockReturnValue(makePolicyDocChain({
      effective_date: null,
      processing_status: 'approved',
    }) as any);
    expect(await isPolicyExpired('test-company')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// VC-5: TOPIC_REJECTED — no retrieval, no LLM
// ---------------------------------------------------------------------------

describe('VC-5: TOPIC_REJECTED path', () => {
  it('returns TOPIC_REJECTION_MSG with no retrieval or LLM calls', async () => {
    vi.mocked(classifyQuery).mockResolvedValue({
      category: 'off_topic',
      confidence: 0.97,
      rejection_reason: TOPIC_REJECTION_MSG,
      query_hash: 'abc12345',
      latency_ms: 5,
    });
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);

    const result = await processQuery("What's the weather in Oslo?", MOCK_EMPLOYEE_ID, {
      anthropicKey: 'test-key',
    });

    expect(result.answer_type).toBe('refusal');
    expect(result.fallback_reason).toBe('TOPIC_REJECTED');
    expect(result.answer_text).toBe(TOPIC_REJECTION_MSG);
    expect(vi.mocked(retrievePolicy)).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('VC-4: TOPIC_REJECTED logs the fallback reason', async () => {
    vi.mocked(classifyQuery).mockResolvedValue({
      category: 'off_topic',
      confidence: 0.95,
      rejection_reason: TOPIC_REJECTION_MSG,
      query_hash: 'xyz99',
      latency_ms: 3,
    });
    vi.stubGlobal('fetch', vi.fn());
    const spy = vi.spyOn(console, 'log');
    await processQuery('who won the football?', MOCK_EMPLOYEE_ID, { anthropicKey: 'test-key' });
    expect(spy).toHaveBeenCalledWith(expect.stringContaining('TOPIC_REJECTED'));
  });
});

// ---------------------------------------------------------------------------
// VC-1: LOW_CONFIDENCE — top RRF < 0.65, no LLM call
// ---------------------------------------------------------------------------

describe('VC-1: LOW_CONFIDENCE path', () => {
  beforeEach(() => {
    mockInScope();
    mockSupabase({ profile: { company_id: MOCK_COMPANY_ID, employee_tier: MOCK_TIER } });
  });

  it('returns LOW_CONFIDENCE_MSG when top chunk RRF < 0.65 (no LLM call)', async () => {
    vi.mocked(retrievePolicy).mockResolvedValue({
      chunks: [{ ...MOCK_CHUNKS[0], rrf_score: 0.45 }],
      latency_ms: 12,
    });
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);

    const result = await processQuery('What is my allowance?', MOCK_EMPLOYEE_ID, {
      anthropicKey: 'test-key',
    });

    expect(result.answer_type).toBe('refusal');
    expect(result.fallback_reason).toBe('LOW_CONFIDENCE');
    expect(result.answer_text).toBe(LOW_CONFIDENCE_MSG);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('returns LOW_CONFIDENCE_MSG when no chunks returned', async () => {
    vi.mocked(retrievePolicy).mockResolvedValue({ chunks: [], latency_ms: 5 });
    vi.stubGlobal('fetch', vi.fn());
    const result = await processQuery('query', MOCK_EMPLOYEE_ID, { anthropicKey: 'test-key' });
    expect(result.fallback_reason).toBe('LOW_CONFIDENCE');
  });

  it('VC-4: LOW_CONFIDENCE logs fallback reason with RRF score', async () => {
    vi.mocked(retrievePolicy).mockResolvedValue({
      chunks: [{ ...MOCK_CHUNKS[0], rrf_score: 0.30 }],
      latency_ms: 10,
    });
    vi.stubGlobal('fetch', vi.fn());
    const spy = vi.spyOn(console, 'log');
    await processQuery('query', MOCK_EMPLOYEE_ID, { anthropicKey: 'test-key' });
    expect(spy).toHaveBeenCalledWith(expect.stringContaining('LOW_CONFIDENCE'));
  });
});

// ---------------------------------------------------------------------------
// VC-3: POLICY_EXPIRED — exact message string, no LLM call
// ---------------------------------------------------------------------------

describe('VC-3: POLICY_EXPIRED path', () => {
  beforeEach(() => {
    mockInScope();
    vi.mocked(retrievePolicy).mockResolvedValue({ chunks: MOCK_CHUNKS, latency_ms: 15 });
    // Profile OK, but no approved policy document
    mockSupabase({
      profile: { company_id: MOCK_COMPANY_ID, employee_tier: MOCK_TIER },
      policyDoc: null,
    });
  });

  it('VC-3: returns exact POLICY_EXPIRED_MSG when no approved policy document', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);

    const result = await processQuery('What is my allowance?', MOCK_EMPLOYEE_ID, {
      anthropicKey: 'test-key',
    });

    expect(result.answer_text).toBe(POLICY_EXPIRED_MSG);
    expect(result.answer_type).toBe('refusal');
    expect(result.fallback_reason).toBe('POLICY_EXPIRED');
    expect(fetchSpy).not.toHaveBeenCalled(); // no LLM call
  });

  it('VC-4: POLICY_EXPIRED logs the fallback reason', async () => {
    vi.stubGlobal('fetch', vi.fn());
    const spy = vi.spyOn(console, 'log');
    await processQuery('query', MOCK_EMPLOYEE_ID, { anthropicKey: 'test-key' });
    expect(spy).toHaveBeenCalledWith(expect.stringContaining('POLICY_EXPIRED'));
  });
});

// ---------------------------------------------------------------------------
// VC-2: FAITHFULNESS_FAIL — raw excerpt served, not generated text
// ---------------------------------------------------------------------------

describe('VC-2: FAITHFULNESS_FAIL path', () => {
  beforeEach(() => {
    mockInScope();
    vi.mocked(retrievePolicy).mockResolvedValue({ chunks: MOCK_CHUNKS, latency_ms: 18 });
    mockSupabase({
      profile: { company_id: MOCK_COMPANY_ID, employee_tier: MOCK_TIER },
      policyDoc: { effective_date: TODAY_DATE, processing_status: 'approved' },
    });
  });

  it('VC-2: serves raw excerpt when faithfulness fails — hallucinated text NOT in response', async () => {
    mockGenerateFetch('Your housing allowance is EUR 8,000 per month and covers all expenses.');
    vi.mocked(checkFaithfulness).mockResolvedValue({
      pass: false,
      flaggedSentences: ['Your housing allowance is EUR 8,000 per month and covers all expenses.'],
      score: 0.0,
      latency_ms: 45,
    });

    const result = await processQuery('What is my housing allowance?', MOCK_EMPLOYEE_ID, {
      anthropicKey: 'test-key',
    });

    expect(result.answer_type).toBe('raw_excerpt');
    expect(result.fallback_reason).toBe('FAITHFULNESS_FAIL');
    expect(result.answer_text).not.toContain('EUR 8,000'); // hallucinated amount absent
    expect(result.answer_text).toContain('EUR 3,500');     // real chunk content present
    expect(result.faithfulness_score).toBe(0.0);
  });

  it('VC-4: FAITHFULNESS_FAIL logs reason with score and flagged count', async () => {
    mockGenerateFetch('Hallucinated text with EUR 9,000.');
    vi.mocked(checkFaithfulness).mockResolvedValue({
      pass: false,
      flaggedSentences: ['Hallucinated text with EUR 9,000.'],
      score: 0.2,
      latency_ms: 30,
    });
    const spy = vi.spyOn(console, 'log');
    await processQuery('query', MOCK_EMPLOYEE_ID, { anthropicKey: 'test-key' });
    expect(spy).toHaveBeenCalledWith(expect.stringContaining('FAITHFULNESS_FAIL'));
  });
});

// ---------------------------------------------------------------------------
// Happy path — generated response with citations
// ---------------------------------------------------------------------------

describe('Happy path — generated response', () => {
  const GENERATED_TEXT =
    'Your housing allowance is EUR 3,500 per month. [Source: Section 3 > Housing]';

  beforeEach(() => {
    mockInScope();
    vi.mocked(retrievePolicy).mockResolvedValue({ chunks: MOCK_CHUNKS, latency_ms: 20 });
    mockSupabase({
      profile: { company_id: MOCK_COMPANY_ID, employee_tier: MOCK_TIER },
      policyDoc: { effective_date: TODAY_DATE, processing_status: 'approved' },
    });
    mockGenerateFetch(GENERATED_TEXT);
    vi.mocked(checkFaithfulness).mockResolvedValue({
      pass: true, flaggedSentences: [], score: 1.0, latency_ms: 35,
    });
  });

  it('returns answer_type=generated when all checks pass', async () => {
    const result = await processQuery('What is my housing allowance?', MOCK_EMPLOYEE_ID, {
      anthropicKey: 'test-key',
    });
    expect(result.answer_type).toBe('generated');
    expect(result.answer_text).toBe(GENERATED_TEXT);
    expect(result.fallback_reason).toBeUndefined();
    expect(result.faithfulness_score).toBe(1.0);
  });

  it('includes chunks for citation rendering', async () => {
    const result = await processQuery('query', MOCK_EMPLOYEE_ID, { anthropicKey: 'test-key' });
    expect(result.chunks).toHaveLength(2);
    expect(result.chunks![0].id).toBe('chunk-1');
  });

  it('includes latency_ms', async () => {
    const result = await processQuery('query', MOCK_EMPLOYEE_ID, { anthropicKey: 'test-key' });
    expect(result.latency_ms).toBeGreaterThanOrEqual(0);
  });

  it('logs OK with faithfulness score and chunk count', async () => {
    const spy = vi.spyOn(console, 'log');
    await processQuery('query', MOCK_EMPLOYEE_ID, { anthropicKey: 'test-key' });
    expect(spy).toHaveBeenCalledWith(expect.stringContaining('OK'));
    expect(spy).toHaveBeenCalledWith(expect.stringContaining('faithfulness=1'));
  });
});
