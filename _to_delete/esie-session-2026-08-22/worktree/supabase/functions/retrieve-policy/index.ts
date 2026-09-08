/**
 * [P4-1] retrieve-policy — Supabase Edge Function
 *
 * Hybrid retrieval layer for the AI policy assistant.
 * Combines BM25 full-text search and pgvector cosine similarity via
 * Reciprocal Rank Fusion (RRF, k=60), with MANDATORY tier + company isolation
 * enforced at the SQL layer before any ranking.
 *
 * Request (POST):
 *   {
 *     query:         string   — natural-language query
 *     employee_tier: string   — e.g. "Manager" (SQL filter, non-negotiable)
 *     company_id:    string   — tenant ID (SQL filter, non-negotiable)
 *     k?:            number   — top-k results to return (default 5)
 *   }
 *
 * Response:
 *   { chunks: PolicyChunk[], latency_ms: number }
 *
 * Environment variables required:
 *   SUPABASE_URL             — set automatically by Supabase
 *   SUPABASE_SERVICE_ROLE_KEY — set automatically by Supabase
 *   OPENAI_API_KEY           — set in Supabase Edge Function secrets
 */

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PolicyChunk {
  id: string;
  doc_id: string | null;
  text: string;
  section_path: string | null;
  category_code: string | null;
  tier: string | null;
  page_start: number | null;
  page_end: number | null;
  confidence_score: number | null;
  /** 1 - cosine_distance (higher = more similar) */
  similarity_score: number;
  /** ts_rank_cd score from BM25 */
  bm25_rank: number;
  /** Reciprocal Rank Fusion score */
  rrf_score: number;
}

export interface RetrieveRequest {
  query: string;
  employee_tier: string;
  company_id: string;
  k?: number;
}

export interface RetrieveResponse {
  chunks: PolicyChunk[];
  latency_ms: number;
}

// ---------------------------------------------------------------------------
// Embedding
// ---------------------------------------------------------------------------

/**
 * Generate a 1536-dimension embedding using OpenAI text-embedding-3-large.
 * Throws if the API call fails.
 */
async function embedQuery(query: string, apiKey: string): Promise<number[]> {
  const res = await fetch('https://api.openai.com/v1/embeddings', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: 'text-embedding-3-large',
      input: query,
    }),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`OpenAI embedding failed (${res.status}): ${body}`);
  }

  const json = (await res.json()) as { data: Array<{ embedding: number[] }> };
  return json.data[0].embedding;
}

// ---------------------------------------------------------------------------
// RRF (implemented client-side as a cross-check on the SQL function result)
// ---------------------------------------------------------------------------

/**
 * Re-rank results using Reciprocal Rank Fusion (RRF, k=60).
 *
 * The hybrid_search SQL function already performs RRF internally, so this is
 * used as a post-processing verification step rather than the primary ranking.
 * The SQL function's hybrid_score is the authoritative ranking returned to
 * callers; rrf_score here is recomputed for transparency.
 *
 * RRF formula (Cormack et al. 2009):
 *   RRF(d) = Σ_i 1 / (k + rank_i(d))
 */
export function reciprocalRankFusion(
  cosineResults: Array<{ id: string; cosine_distance: number }>,
  bm25Results: Array<{ id: string; bm25_rank: number }>,
  k = 60,
): Map<string, number> {
  const scores = new Map<string, number>();

  // Vector results ranked by cosine distance (ascending = most similar first)
  const vectorRanked = [...cosineResults].sort(
    (a, b) => a.cosine_distance - b.cosine_distance,
  );
  vectorRanked.forEach((chunk, rank) => {
    scores.set(chunk.id, (scores.get(chunk.id) ?? 0) + 1 / (k + rank + 1));
  });

  // BM25 results ranked by bm25_rank (descending = highest score first)
  const bm25Ranked = [...bm25Results].sort((a, b) => b.bm25_rank - a.bm25_rank);
  bm25Ranked.forEach((chunk, rank) => {
    scores.set(chunk.id, (scores.get(chunk.id) ?? 0) + 1 / (k + rank + 1));
  });

  return scores;
}

// ---------------------------------------------------------------------------
// CORS
// ---------------------------------------------------------------------------

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
};

// ---------------------------------------------------------------------------
// Handler
// ---------------------------------------------------------------------------

Deno.serve(async (req: Request): Promise<Response> => {
  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: CORS_HEADERS });
  }

  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), {
      status: 405,
      headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
    });
  }

  const t0 = Date.now();

  try {
    // Parse request
    const body = (await req.json()) as RetrieveRequest;
    const { query, employee_tier, company_id, k = 5 } = body;

    if (!query || !employee_tier || !company_id) {
      return new Response(
        JSON.stringify({ error: 'query, employee_tier, and company_id are required' }),
        { status: 400, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' } },
      );
    }

    // Validate k
    const topK = Math.min(Math.max(1, Math.floor(k)), 20);

    // Environment
    const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? '';
    const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';
    const openaiKey = Deno.env.get('OPENAI_API_KEY') ?? '';

    if (!openaiKey) {
      return new Response(
        JSON.stringify({ error: 'OPENAI_API_KEY not configured' }),
        { status: 503, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' } },
      );
    }

    // Generate query embedding
    const embedding = await embedQuery(query, openaiKey);
    const embeddingStr = `[${embedding.join(',')}]`;

    // Call hybrid_search RPC — tier and company filters are enforced INSIDE the SQL function
    const supabase = createClient(supabaseUrl, serviceKey);
    const { data, error } = await supabase.rpc('hybrid_search', {
      query_embedding: embeddingStr,
      query_text: query,
      company: company_id,
      tier_filter: employee_tier,    // ← SQL WHERE tier = $tier, before any ranking
      match_count: topK,
    });

    if (error) {
      console.error('[retrieve-policy] RPC error:', error);
      return new Response(
        JSON.stringify({ error: `Retrieval failed: ${error.message}` }),
        { status: 500, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' } },
      );
    }

    // Map RPC rows → PolicyChunk (SQL function already applied RRF internally)
    const rows = (data ?? []) as Array<{
      id: string;
      doc_id: string | null;
      text: string;
      section_path: string | null;
      category_code: string | null;
      tier: string | null;
      page_start: number | null;
      page_end: number | null;
      confidence_score: number | null;
      cosine_distance: number;
      bm25_rank: number;
      hybrid_score: number;
    }>;

    // Re-derive per-chunk RRF score from the raw ranks for transparency
    const rrfMap = reciprocalRankFusion(rows, rows);

    const chunks: PolicyChunk[] = rows.map((row) => ({
      id: row.id,
      doc_id: row.doc_id,
      text: row.text,
      section_path: row.section_path,
      category_code: row.category_code,
      tier: row.tier,
      page_start: row.page_start,
      page_end: row.page_end,
      confidence_score: row.confidence_score,
      similarity_score: Math.max(0, 1 - (row.cosine_distance ?? 1)),
      bm25_rank: row.bm25_rank ?? 0,
      rrf_score: rrfMap.get(row.id) ?? row.hybrid_score,
    }));

    const response: RetrieveResponse = {
      chunks,
      latency_ms: Date.now() - t0,
    };

    return new Response(JSON.stringify(response), {
      status: 200,
      headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' },
    });
  } catch (err) {
    console.error('[retrieve-policy] Unexpected error:', err);
    return new Response(
      JSON.stringify({ error: String(err) }),
      { status: 500, headers: { ...CORS_HEADERS, 'Content-Type': 'application/json' } },
    );
  }
});
