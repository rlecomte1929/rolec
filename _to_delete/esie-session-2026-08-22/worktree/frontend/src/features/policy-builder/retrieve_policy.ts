/**
 * [P4-1] retrieve_policy.ts — Hybrid retrieval client for the AI policy assistant
 *
 * Calls the `retrieve-policy` Supabase Edge Function, which:
 *   1. Embeds the query using OpenAI text-embedding-3-large (server-side)
 *   2. Calls the hybrid_search() SQL function (BM25 + cosine, RRF-fused)
 *   3. Enforces tier + company_id isolation at the SQL layer (non-negotiable)
 *   4. Returns top-k PolicyChunk[] ranked by RRF score
 *
 * Tier isolation is a SECURITY BOUNDARY — no cross-tier results can leak through
 * under any circumstances, as the WHERE clause is applied before ranking.
 *
 * Usage:
 *   const chunks = await retrievePolicy({
 *     query: 'housing allowance reimbursement',
 *     employee_tier: 'Manager',
 *     company_id: 'acme-corp',
 *     k: 5,
 *   });
 */

// Supabase client is imported lazily inside functions that need it so that
// this module can be imported in test environments without Supabase env vars.
import type { SupabaseClient } from '@supabase/supabase-js';

async function getSupabase(): Promise<SupabaseClient> {
  const { supabase } = await import('../../lib/supabase');
  return supabase;
}

// ---------------------------------------------------------------------------
// Public types (re-exported for consumers)
// ---------------------------------------------------------------------------

export interface PolicyChunk {
  /** policy_chunks.id */
  id: string;
  /** Source document id */
  doc_id: string | null;
  /** Raw text of the chunk */
  text: string;
  /** Document hierarchy path, e.g. "Section 3 > Housing > Manager" */
  section_path: string | null;
  /** Policy category code, e.g. "housing_allowance" */
  category_code: string | null;
  /** Tier this chunk applies to */
  tier: string | null;
  /** Page number in the source PDF */
  page_start: number | null;
  page_end: number | null;
  /** Extraction confidence from the policy pipeline (0–1) */
  confidence_score: number | null;
  /** 1 − cosine_distance (0–1, higher = more semantically similar) */
  similarity_score: number;
  /** ts_rank_cd score from BM25 full-text match */
  bm25_rank: number;
  /** Reciprocal Rank Fusion composite score */
  rrf_score: number;
}

export interface RetrievePolicyOptions {
  /** Natural-language query string */
  query: string;
  /**
   * Employee tier — enforced as a SQL WHERE clause before any ranking.
   * Results from other tiers will NEVER appear regardless of similarity.
   */
  employee_tier: string;
  /** Company / tenant ID — enforced as a SQL WHERE clause */
  company_id: string;
  /** Maximum results to return (1–20, default 5) */
  k?: number;
}

export interface RetrievePolicyResult {
  chunks: PolicyChunk[];
  /** Total round-trip latency in milliseconds (measured server-side) */
  latency_ms: number;
}

// ---------------------------------------------------------------------------
// Reciprocal Rank Fusion helper (exported for testing)
// ---------------------------------------------------------------------------

/**
 * Computes RRF scores for a set of results from two ranked lists.
 *
 * RRF formula (Cormack et al. 2009):
 *   RRF(d) = Σ_i  1 / (k + rank_i(d))
 *
 * @param cosineResults  Results ordered by cosine_distance ascending (best first)
 * @param bm25Results    Results ordered by bm25_rank descending (best first)
 * @param k              Smoothing constant (default 60 per spec)
 * @returns              Map from chunk id → RRF score
 */
export function computeRRF(
  cosineResults: Array<{ id: string }>,
  bm25Results: Array<{ id: string }>,
  k = 60,
): Map<string, number> {
  const scores = new Map<string, number>();

  cosineResults.forEach((chunk, rank) => {
    scores.set(chunk.id, (scores.get(chunk.id) ?? 0) + 1 / (k + rank + 1));
  });

  bm25Results.forEach((chunk, rank) => {
    scores.set(chunk.id, (scores.get(chunk.id) ?? 0) + 1 / (k + rank + 1));
  });

  return scores;
}

// ---------------------------------------------------------------------------
// Main retrieval function
// ---------------------------------------------------------------------------

/**
 * Retrieve the top-k most relevant policy chunks for a given query and tier.
 *
 * Tier isolation is enforced at the database level — it is not possible to
 * receive chunks belonging to a different tier even if they score higher.
 *
 * @throws {Error} If the Edge Function returns a non-2xx response
 */
export async function retrievePolicy(
  opts: RetrievePolicyOptions,
): Promise<RetrievePolicyResult> {
  const { query, employee_tier, company_id, k = 5 } = opts;

  if (!query.trim()) throw new Error('retrievePolicy: query must not be empty');
  if (!employee_tier.trim()) throw new Error('retrievePolicy: employee_tier is required');
  if (!company_id.trim()) throw new Error('retrievePolicy: company_id is required');

  // Resolve the Edge Function URL from the Supabase client config
  const supabase = await getSupabase();
  const supabaseUrl: string =
    (supabase as unknown as { supabaseUrl?: string }).supabaseUrl ??
    (import.meta.env.VITE_SUPABASE_URL);

  const functionUrl = `${supabaseUrl}/functions/v1/retrieve-policy`;

  // Get the current session token so the Edge Function can verify the caller
  const { data: { session } } = await supabase.auth.getSession();
  const authHeader = session?.access_token
    ? `Bearer ${session.access_token}`
    : `Bearer ${import.meta.env.VITE_SUPABASE_ANON_KEY}`;

  const response = await fetch(functionUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: authHeader,
      apikey: import.meta.env.VITE_SUPABASE_ANON_KEY,
    },
    body: JSON.stringify({ query, employee_tier, company_id, k }),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(
      `retrievePolicy: Edge Function returned ${response.status}${body ? ': ' + body : ''}`,
    );
  }

  const result = (await response.json()) as RetrievePolicyResult;
  return result;
}

// ---------------------------------------------------------------------------
// Convenience: retrieve for the currently authenticated user
// ---------------------------------------------------------------------------

/**
 * Retrieve policy chunks for the currently logged-in HR or Employee user.
 * Automatically resolves company_id and employee_tier from their Supabase profile.
 *
 * Requires the user to be authenticated; throws otherwise.
 */
export async function retrievePolicyForCurrentUser(
  query: string,
  overrideTier?: string,
  k = 5,
): Promise<RetrievePolicyResult> {
  const supabase = await getSupabase();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('retrievePolicyForCurrentUser: not authenticated');

  const { data: profile, error } = await supabase
    .from('profiles')
    .select('company_id, employee_tier')
    .eq('id', user.id)
    .single();

  if (error || !profile) {
    throw new Error('retrievePolicyForCurrentUser: could not load profile');
  }

  const tier = overrideTier ?? (profile.employee_tier as string | null) ?? 'All';
  const companyId = profile.company_id as string;

  return retrievePolicy({ query, employee_tier: tier, company_id: companyId, k });
}
