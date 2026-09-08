/**
 * immigration-retention-cleanup — Supabase Edge Function
 *
 * Scheduled at 03:30 UTC daily via pg_cron + pg_net (see migration
 * 20260605700000_imm18_retention_automation.sql).
 *
 * Single responsibility: invoke the SQL function fn_immigration_retention_cleanup(),
 * which (within one transaction) anonymises immigration profiles past their
 * retention window and hard-deletes those more than 30 days past it. All the
 * GDPR logic lives in SQL — this function is just the scheduled trigger and a
 * thin HTTP surface so the run is observable from the function logs.
 *
 * Environment variables:
 *   SUPABASE_URL              — auto-set by Supabase
 *   SUPABASE_SERVICE_ROLE_KEY — auto-set by Supabase
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: CORS_HEADERS });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false },
  });

  try {
    const { data, error } = await supabase.rpc("fn_immigration_retention_cleanup");
    if (error) throw new Error(`fn_immigration_retention_cleanup failed: ${error.message}`);

    const result = { ok: true, ...(data ?? {}) };
    console.log("immigration-retention-cleanup complete:", JSON.stringify(result));
    return Response.json(result, { headers: CORS_HEADERS });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("immigration-retention-cleanup error:", message);
    return Response.json(
      { ok: false, error: message },
      { status: 500, headers: CORS_HEADERS }
    );
  }
});
