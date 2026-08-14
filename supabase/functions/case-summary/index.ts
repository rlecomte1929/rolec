/**
 * case-summary — Supabase Edge Function (AIQ-1693)
 * ─────────────────────────────────────────────────────────────────────────────
 * Request-triggered. Given { assignment_id, company_id }, returns a
 * Claude-generated, HR-ready case summary in four sections:
 *   status · blockers · next_actions · cost_variance
 *
 * Pure summary logic (field whitelist, prompt, Claude call, parsing) lives in
 * ./summary.ts — see its header for the GROUNDING + COMPLIANCE contract (only
 * non-PII operational fields ever reach the prompt). This file wires that to the
 * DB read, tenant scoping, and HTTP handler.
 *
 * TENANT ISOLATION:
 *   The caller (the authenticated ReloPass backend) passes the tenant `company_id`
 *   — the same contract as `retrieve-policy`. The assignment's linked
 *   relocation_case must belong to that company; any mismatch or unknown id
 *   returns 404 with no data (no cross-tenant leak, no existence oracle).
 *
 * Environment variables:
 *   SUPABASE_URL                — project URL
 *   SUPABASE_SERVICE_ROLE_KEY   — service role (reads scoped in code, not by RLS)
 *   ANTHROPIC_API_KEY           — Claude API key
 *
 * Test:  deno test supabase/functions/case-summary/   (pure logic; no network)
 * Call:  curl -sX POST "$FN_URL/case-summary" -H "content-type: application/json" \
 *          -d '{"assignment_id":"<id>","company_id":"<tenant>"}'
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { type CaseSummary, generateSummary } from "./summary.ts";
import { fetchAssignmentAndCase } from "./db.ts";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

interface SummaryRequest {
  assignment_id: string;
  company_id: string;
}

export async function handler(req: Request): Promise<Response> {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS_HEADERS });
  if (req.method !== "POST") {
    return Response.json({ error: "Method not allowed" }, { status: 405, headers: CORS_HEADERS });
  }

  let body: SummaryRequest;
  try {
    body = (await req.json()) as SummaryRequest;
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400, headers: CORS_HEADERS });
  }

  const assignmentId = (body.assignment_id ?? "").trim();
  const companyId = (body.company_id ?? "").trim();
  if (!assignmentId || !companyId) {
    return Response.json(
      { error: "assignment_id and company_id are required" },
      { status: 400, headers: CORS_HEADERS },
    );
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const anthropicKey = Deno.env.get("ANTHROPIC_API_KEY");
  if (!supabaseUrl || !serviceRoleKey) {
    return Response.json(
      { error: "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required" },
      { status: 500, headers: CORS_HEADERS },
    );
  }
  if (!anthropicKey) {
    return Response.json({ error: "ANTHROPIC_API_KEY is required" }, { status: 500, headers: CORS_HEADERS });
  }

  try {
    const supabase = createClient(supabaseUrl, serviceRoleKey, {
      auth: { persistSession: false },
    });

    const input = await fetchAssignmentAndCase(supabase, assignmentId, companyId);
    if (!input) {
      // Unknown id OR wrong tenant — same response, no existence oracle.
      return Response.json({ error: "Case not found" }, { status: 404, headers: CORS_HEADERS });
    }

    let summary: CaseSummary;
    try {
      summary = await generateSummary(anthropicKey, input);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error("case-summary: Anthropic error:", msg);
      return Response.json({ error: "Summary generation failed" }, { status: 502, headers: CORS_HEADERS });
    }

    return Response.json(
      { assignment_id: assignmentId, company_id: companyId, summary, generated_at: new Date().toISOString() },
      { headers: CORS_HEADERS },
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error("case-summary: unexpected error:", msg);
    return Response.json({ error: "Internal error" }, { status: 500, headers: CORS_HEADERS });
  }
}

// Only serve when run as the entrypoint, so `deno test` can import without a server.
if (import.meta.main) {
  Deno.serve(handler);
}
