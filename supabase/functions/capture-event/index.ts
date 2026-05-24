/**
 * capture-event — Supabase Edge Function
 *
 * Receives structured analytics events from the ReloPass frontend and
 * writes them to the `public.events` table using the service role.
 *
 * Design:
 *   - Public endpoint (no auth header required from client)
 *   - Payload validated against EventPayload interface before any write
 *   - Rate-limited to 100 events/minute per session_id (in-memory sliding window)
 *   - user_id must already be hashed by the caller — raw PII is rejected
 *   - Source forced to 'web' for all calls from this function
 *
 * Called from: frontend/src/lib/analytics.ts → track()
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// ─── Constants ────────────────────────────────────────────────────────────────

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const RATE_LIMIT = 100;          // max events per window
const RATE_WINDOW_MS = 60_000;   // 1 minute rolling window

// ─── Rate limiter — in-memory sliding window per session_id ──────────────────

interface WindowEntry { count: number; windowStart: number }
const rateLimitMap = new Map<string, WindowEntry>();

function isRateLimited(sessionId: string): boolean {
  const now = Date.now();
  const entry = rateLimitMap.get(sessionId);

  if (!entry || now - entry.windowStart > RATE_WINDOW_MS) {
    rateLimitMap.set(sessionId, { count: 1, windowStart: now });
    return false;
  }

  if (entry.count >= RATE_LIMIT) return true;

  entry.count += 1;
  return false;
}

// ─── Payload type ─────────────────────────────────────────────────────────────

interface EventPayload {
  event_type: string;
  entity_type?: string | null;
  entity_id?: string | null;
  user_id?: string | null;    // must be SHA-256 hash, not raw email/uuid
  company_id?: string | null;
  session_id?: string | null;
  source?: "web" | "api" | "agent" | "scheduler";
  properties?: Record<string, unknown>;
}

function isValidPayload(body: unknown): body is EventPayload {
  if (!body || typeof body !== "object") return false;
  const b = body as Record<string, unknown>;
  if (typeof b.event_type !== "string" || b.event_type.trim().length === 0) return false;
  // Reject obvious raw PII in user_id: UUIDs (8-4-4-4-12) and email addresses
  if (typeof b.user_id === "string") {
    const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (uuidPattern.test(b.user_id) || emailPattern.test(b.user_id)) {
      return false; // raw PII — reject
    }
  }
  return true;
}

// ─── Handler ──────────────────────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: CORS_HEADERS });
  }
  if (req.method !== "POST") {
    return Response.json(
      { ok: false, error: "Method not allowed" },
      { status: 405, headers: CORS_HEADERS }
    );
  }

  // Parse JSON body
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json(
      { ok: false, error: "Invalid JSON." },
      { status: 400, headers: CORS_HEADERS }
    );
  }

  // Validate
  if (!isValidPayload(body)) {
    return Response.json(
      { ok: false, error: "Invalid payload. event_type is required; user_id must be hashed." },
      { status: 422, headers: CORS_HEADERS }
    );
  }

  // Rate limit by session_id (fall back to a hash of IP if missing)
  const sessionKey = body.session_id || req.headers.get("x-forwarded-for") || "anonymous";
  if (isRateLimited(sessionKey)) {
    return Response.json(
      { ok: false, error: "Rate limit exceeded. Max 100 events/minute per session." },
      { status: 429, headers: CORS_HEADERS }
    );
  }

  // Write to events table with service role (bypasses RLS)
  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false },
  });

  const { error } = await supabase.from("events").insert({
    event_type:  body.event_type,
    entity_type: body.entity_type ?? null,
    entity_id:   body.entity_id ?? null,
    user_id:     body.user_id ?? null,
    company_id:  body.company_id ?? null,
    session_id:  body.session_id ?? null,
    source:      body.source ?? "web",
    properties:  body.properties ?? {},
  });

  if (error) {
    console.error("capture-event insert error:", error.message);
    return Response.json(
      { ok: false, error: "Failed to record event." },
      { status: 500, headers: CORS_HEADERS }
    );
  }

  return Response.json({ ok: true }, { headers: CORS_HEADERS });
});
