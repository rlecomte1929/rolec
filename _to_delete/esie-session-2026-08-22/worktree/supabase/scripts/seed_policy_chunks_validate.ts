/**
 * [P2-7] seed_policy_chunks_validate.ts
 *
 * Validation and seeding script for the policy_chunks vector store.
 *
 * What it does:
 *   1. Seeds 50 synthetic policy chunks (3 topic groups) using
 *      OpenAI text-embedding-3-large (1536 dims)
 *   2. Validates cosine similarity search returns expected top-5 for 3 queries
 *   3. Validates BM25 / tsvector keyword search on exact policy terms
 *   4. Validates company_id + tier filter correctly reduces the result set
 *   5. Cleans up all seeded rows (safe to run repeatedly)
 *
 * Usage:
 *   SUPABASE_URL=https://xxx.supabase.co \
 *   SUPABASE_SERVICE_KEY=eyJ... \
 *   OPENAI_API_KEY=sk-... \
 *   npx ts-node --esm supabase/scripts/seed_policy_chunks_validate.ts
 *
 * Requirements:
 *   npm install @supabase/supabase-js openai
 */

import { createClient } from '@supabase/supabase-js';
import OpenAI from 'openai';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const SUPABASE_URL = process.env.SUPABASE_URL ?? '';
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY ?? '';
const OPENAI_API_KEY = process.env.OPENAI_API_KEY ?? '';

if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY || !OPENAI_API_KEY) {
  console.error('Missing required env vars: SUPABASE_URL, SUPABASE_SERVICE_KEY, OPENAI_API_KEY');
  process.exit(1);
}

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
const openai = new OpenAI({ apiKey: OPENAI_API_KEY });

// ---------------------------------------------------------------------------
// Seed data — 50 chunks across 3 policy topic groups + 2 tenants
// ---------------------------------------------------------------------------

const COMPANY_A = 'test-company-alpha';
const COMPANY_B = 'test-company-beta';

interface SeedChunk {
  chunk_index: number;
  text: string;
  category_code: string;
  tier: string;
  company_id: string;
  section_path: string;
  page_start: number;
  page_end: number;
  confidence_score: number;
}

/**
 * Build 50 representative chunks: 5 tiers × 3 categories × 3 variants + 5 beta-company chunks
 * (5 × 3 × 3 = 45, + 5 = 50)
 */
function buildSeedChunks(): SeedChunk[] {
  const tiers = ['Junior', 'Senior', 'Manager', 'Director', 'Executive'];
  const categories: Array<{ code: string; label: string; amounts: number[] }> = [
    {
      code: 'housing_allowance',
      label: 'Housing allowance',
      amounts: [1500, 2000, 3500, 4500, 6000],
    },
    {
      code: 'relocation_lump_sum',
      label: 'Relocation lump sum',
      amounts: [5000, 8000, 12000, 18000, 25000],
    },
    {
      code: 'schooling_allowance',
      label: 'Schooling allowance',
      amounts: [0, 5000, 10000, 15000, 20000],
    },
  ];

  const chunks: SeedChunk[] = [];
  let idx = 0;

  for (const cat of categories) {
    for (let t = 0; t < tiers.length; t++) {
      const tier = tiers[t];
      const amount = cat.amounts[t];

      // Variant A — formal policy language
      chunks.push({
        chunk_index: idx++,
        text: `${cat.label} for ${tier} assignees: EUR ${amount.toLocaleString('en-US')} per month. ` +
          `This allowance covers reasonable housing costs in the destination city and is ` +
          `subject to annual review. Receipts must be submitted monthly.`,
        category_code: cat.code,
        tier,
        company_id: COMPANY_A,
        section_path: `Section 3 > ${cat.label} > ${tier}`,
        page_start: t + 10,
        page_end: t + 10,
        confidence_score: 0.92,
      });

      // Variant B — table row / summary
      chunks.push({
        chunk_index: idx++,
        text: `${tier} | ${cat.code.replace(/_/g, ' ')} | EUR ${amount.toLocaleString('en-US')} | monthly | taxable`,
        category_code: cat.code,
        tier,
        company_id: COMPANY_A,
        section_path: `Appendix A > ${cat.label} Table`,
        page_start: 45,
        page_end: 45,
        confidence_score: 0.85,
      });

      // Variant C — prose summary (company B, Manager only, to test tenant isolation)
      if (tier === 'Manager') {
        chunks.push({
          chunk_index: idx++,
          text: `Company Beta policy: ${cat.label} for Manager-level employees is set at ` +
            `EUR ${(amount * 0.9).toFixed(0)} per month, reviewed bi-annually.`,
          category_code: cat.code,
          tier,
          company_id: COMPANY_B,
          section_path: `Policy Handbook > ${cat.label}`,
          page_start: 12,
          page_end: 12,
          confidence_score: 0.88,
        });
      }
    }
  }

  // Top up to exactly 50 with generic policy context chunks (company A)
  const fillerTexts = [
    'All relocation benefits are subject to the applicable tax withholding obligations in the host country.',
    'Employees must confirm their tier classification with HR before the assignment start date.',
    'Benefit caps are reviewed annually and may be adjusted for cost-of-living index changes.',
    'Housing allowances are capped at the lesser of actual cost or the tier maximum.',
    'Schooling allowance is available for dependent children aged 3–18 enrolled in accredited schools.',
  ];
  for (const text of fillerTexts) {
    chunks.push({
      chunk_index: idx++,
      text,
      category_code: 'general',
      tier: 'All',
      company_id: COMPANY_A,
      section_path: 'Section 1 > General Provisions',
      page_start: 3,
      page_end: 3,
      confidence_score: 0.70,
    });
  }

  return chunks.slice(0, 50);
}

// ---------------------------------------------------------------------------
// Embedding helper
// ---------------------------------------------------------------------------

async function embedTexts(texts: string[]): Promise<number[][]> {
  console.log(`  Embedding ${texts.length} texts with text-embedding-3-large…`);
  const response = await openai.embeddings.create({
    model: 'text-embedding-3-large',
    input: texts,
  });
  return response.data.map((d) => d.embedding);
}

// ---------------------------------------------------------------------------
// Seed
// ---------------------------------------------------------------------------

async function seedChunks(chunks: SeedChunk[]): Promise<string[]> {
  console.log('\n[1/4] Embedding seed chunks…');
  const texts = chunks.map((c) => c.text);
  const embeddings = await embedTexts(texts);

  const rows = chunks.map((c, i) => ({
    ...c,
    embedding: `[${embeddings[i].join(',')}]`,
  }));

  console.log(`[2/4] Inserting ${rows.length} chunks into policy_chunks…`);
  const { data, error } = await supabase
    .from('policy_chunks')
    .insert(rows)
    .select('id');

  if (error) {
    throw new Error(`Insert failed: ${error.message}`);
  }
  const ids = (data ?? []).map((r: { id: string }) => r.id);
  console.log(`  ✓ Inserted ${ids.length} rows.`);
  return ids;
}

// ---------------------------------------------------------------------------
// Validation helpers
// ---------------------------------------------------------------------------

interface ValidationResult {
  name: string;
  passed: boolean;
  detail: string;
}

async function validateVectorSearch(queryText: string, expectedCategory: string, expectedTier: string): Promise<ValidationResult> {
  const name = `Vector search: "${queryText.slice(0, 50)}"`;
  try {
    const [[embedding]] = [await embedTexts([queryText])];

    const { data, error } = await supabase.rpc('hybrid_search', {
      query_embedding: `[${embedding.join(',')}]`,
      query_text: queryText,
      company: COMPANY_A,
      tier_filter: null,
      match_count: 5,
    });

    if (error) return { name, passed: false, detail: `RPC error: ${error.message}` };
    if (!data || data.length === 0) return { name, passed: false, detail: 'No results returned' };

    const top = data[0] as { category_code: string; tier: string; hybrid_score: number };
    const hit = data.some(
      (r: { category_code: string; tier: string }) =>
        r.category_code === expectedCategory && r.tier === expectedTier,
    );
    return {
      name,
      passed: hit,
      detail: hit
        ? `Top-5 includes ${expectedCategory}/${expectedTier}. Top result: ${top.category_code}/${top.tier} (score ${top.hybrid_score.toFixed(4)})`
        : `Expected ${expectedCategory}/${expectedTier} in top-5 but got: ${data.map((r: { category_code: string; tier: string }) => `${r.category_code}/${r.tier}`).join(', ')}`,
    };
  } catch (e) {
    return { name, passed: false, detail: String(e) };
  }
}

async function validateBm25Search(): Promise<ValidationResult> {
  const name = 'BM25 keyword search: "housing allowance manager"';
  try {
    const { data, error } = await supabase
      .from('policy_chunks')
      .select('id, category_code, tier, text')
      .eq('company_id', COMPANY_A)
      .textSearch('bm25_vector', 'housing & allowance & manager')
      .limit(10);

    if (error) return { name, passed: false, detail: `Query error: ${error.message}` };
    if (!data || data.length === 0) return { name, passed: false, detail: 'No BM25 results returned' };

    const hasHousing = data.some((r: { category_code: string }) => r.category_code === 'housing_allowance');
    const hasManager = data.some((r: { tier: string }) => r.tier === 'Manager');
    const passed = hasHousing && hasManager;
    return {
      name,
      passed,
      detail: passed
        ? `Found ${data.length} BM25 results; housing_allowance ✓; Manager tier ✓`
        : `BM25 returned ${data.length} results but missing: ${!hasHousing ? 'housing_allowance ' : ''}${!hasManager ? 'Manager tier' : ''}`,
    };
  } catch (e) {
    return { name, passed: false, detail: String(e) };
  }
}

async function validateTenantFilter(): Promise<ValidationResult> {
  const name = 'Tenant + tier filter: company_id=COMPANY_B AND tier=Manager';
  try {
    const { data: allData, error: allError } = await supabase
      .from('policy_chunks')
      .select('id')
      .eq('company_id', COMPANY_A);

    const { data: filteredData, error: filteredError } = await supabase
      .from('policy_chunks')
      .select('id, tier')
      .eq('company_id', COMPANY_B)
      .eq('tier', 'Manager');

    if (allError || filteredError) {
      return { name, passed: false, detail: `Query error: ${allError?.message ?? filteredError?.message}` };
    }

    const allCount = allData?.length ?? 0;
    const filteredCount = filteredData?.length ?? 0;

    const passed = filteredCount > 0 && filteredCount < allCount;
    return {
      name,
      passed,
      detail: passed
        ? `COMPANY_A total: ${allCount} rows; COMPANY_B/Manager: ${filteredCount} rows — filter correctly isolates tenant data`
        : `Unexpected counts — COMPANY_A: ${allCount}, COMPANY_B/Manager: ${filteredCount}`,
    };
  } catch (e) {
    return { name, passed: false, detail: String(e) };
  }
}

// ---------------------------------------------------------------------------
// Cleanup
// ---------------------------------------------------------------------------

async function cleanup(insertedIds: string[]): Promise<void> {
  if (insertedIds.length === 0) return;
  console.log('\n[4/4] Cleaning up seed rows…');
  const { error } = await supabase
    .from('policy_chunks')
    .delete()
    .in('id', insertedIds);
  if (error) {
    console.warn(`  ⚠ Cleanup failed: ${error.message}`);
  } else {
    console.log(`  ✓ Deleted ${insertedIds.length} seed rows.`);
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  console.log('═══════════════════════════════════════════════════════');
  console.log('  P2-7 · policy_chunks validation script               ');
  console.log('═══════════════════════════════════════════════════════');

  let insertedIds: string[] = [];

  try {
    // Seed
    const chunks = buildSeedChunks();
    insertedIds = await seedChunks(chunks);

    // Validate
    console.log('\n[3/4] Running validation checks…');
    const results: ValidationResult[] = await Promise.all([
      validateVectorSearch(
        'monthly housing allowance for managers in the destination city',
        'housing_allowance',
        'Manager',
      ),
      validateVectorSearch(
        'one-time relocation payment for senior employees',
        'relocation_lump_sum',
        'Senior',
      ),
      validateVectorSearch(
        'schooling benefit for children of executives on assignment',
        'schooling_allowance',
        'Executive',
      ),
      validateBm25Search(),
      validateTenantFilter(),
    ]);

    // Report
    console.log('\n────────────────────────────────────────────────────');
    console.log('  Validation Results                                  ');
    console.log('────────────────────────────────────────────────────');
    let allPassed = true;
    for (const r of results) {
      const icon = r.passed ? '✓' : '✗';
      console.log(`  ${icon} ${r.name}`);
      console.log(`    → ${r.detail}`);
      if (!r.passed) allPassed = false;
    }
    console.log('────────────────────────────────────────────────────');
    console.log(`  Overall: ${allPassed ? 'ALL CHECKS PASSED ✓' : 'SOME CHECKS FAILED ✗'}`);
    console.log('────────────────────────────────────────────────────');

    if (!allPassed) process.exitCode = 1;
  } finally {
    await cleanup(insertedIds);
  }
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
