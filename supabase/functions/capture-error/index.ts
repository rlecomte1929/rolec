/**
 * Receives frontend error reports, deduplicates by fingerprint,
 * and writes to error_logs + error_tickets tables.
 *
 * Public endpoint — no auth required. Rate-limited per fingerprint.
 * Only writes; reads go through admin UI with service role.
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// Max events per fingerprint per hour — prevents flooding from a single bug
const RATE_LIMIT_PER_FINGERPRINT_PER_HOUR = 20;

interface ErrorPayload {
  fingerprint: string;
  message: string;
  stack: string | null;
  url: string;
  user_id: string | null;
  component_name: string | null;
  browser: string;
  breadcrumbs: { type: string; message: string; timestamp: string }[];
  severity: "error" | "warning";
}

function isValidPayload(body: unknown): body is ErrorPayload {
  if (!body || typeof body !== "object") return false;
  const b = body as Record<string, unknown>;
  return (
    typeof b.fingerprint === "string" && b.fingerprint.length > 0 &&
    typeof b.message === "string" && b.message.length > 0 &&
    typeof b.url === "string" &&
    typeof b.browser === "string" &&
    Array.isArray(b.breadcrumbs)
  );
}

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

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json(
      { ok: false, error: "Invalid JSON." },
      { status: 400, headers: CORS_HEADERS }
    );
  }

  if (!isValidPayload(body)) {
    return Response.json(
      { ok: false, error: "Invalid payload." },
      { status: 400, headers: CORS_HEADERS }
    );
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
  );

  // Rate limit: max 20 events per fingerprint per hour
  const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000).toISOString();
  const { count: recentCount } = await supabase
    .from("error_logs")
    .select("id", { count: "exact", head: true })
    .eq("fingerprint", body.fingerprint)
    .gte("created_at", oneHourAgo);

  if ((recentCount ?? 0) >= RATE_LIMIT_PER_FINGERPRINT_PER_HOUR) {
    // Throttled — return 200 so the client does not retry
    return Response.json(
      { ok: true, throttled: true },
      { headers: CORS_HEADERS }
    );
  }

  // Insert raw event
  const { error: logError } = await supabase.from("error_logs").insert({
    fingerprint: body.fingerprint,
    message:     body.message.slice(0, 1000),
    stack:       body.stack?.slice(0, 5000) ?? null,
    url:         body.url.slice(0, 500),
    user_id:     body.user_id ?? null,
    component_name: body.component_name ?? null,
    browser:     body.browser.slice(0, 300),
    breadcrumbs: body.breadcrumbs.slice(0, 10),
    severity:    body.severity ?? "error",
  });

  if (logError) {
    console.error("[capture-error] Insert error_logs failed:", logError);
    return Response.json(
      { ok: false, error: "Storage error." },
      { status: 500, headers: CORS_HEADERS }
    );
  }

  // Upsert ticket: insert on first occurrence, update count + last_seen on repeat
  const { data: existing } = await supabase
    .from("error_tickets")
    .select("id, event_count")
    .eq("fingerprint", body.fingerprint)
    .maybeSingle();

  if (existing) {
    await supabase
      .from("error_tickets")
      .update({
        last_seen:   new Date().toISOString(),
        event_count: existing.event_count + 1,
      })
      .eq("fingerprint", body.fingerprint);
  } else {
    await supabase.from("error_tickets").insert({
      fingerprint: body.fingerprint,
      message:     body.message.slice(0, 1000),
    });
  }

  return Response.json({ ok: true }, { headers: CORS_HEADERS });
});
