/**
 * nightly-aggregation — Supabase Edge Function
 *
 * Scheduled at 02:00 UTC daily via pg_cron + pg_net (see migration
 * 20260523010000_nightly_aggregation_cron.sql).
 *
 * Pipeline:
 *   1. Query yesterday's events from public.events
 *   2. Aggregate counts by event_type and entity_type
 *   3. Detect anomalies (error spike, assignment decline rate, zero activity)
 *   4. Call Claude Haiku to generate a plain-English daily digest (~300 words)
 *   5. Upsert three rows into public.daily_summaries:
 *        - user_behaviour
 *        - assignments
 *        - platform_health
 *
 * Handles zero-event days gracefully (writes a "quiet day" summary, no error).
 * Completes within 30 seconds for up to 10,000 events (aggregation is SQL-side).
 *
 * Environment variables:
 *   SUPABASE_URL              — auto-set by Supabase
 *   SUPABASE_SERVICE_ROLE_KEY — auto-set by Supabase
 *   ANTHROPIC_API_KEY         — stored in Supabase vault
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// ─── Constants ────────────────────────────────────────────────────────────────

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
};

const ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages";
const HAIKU_MODEL = "claude-haiku-4-5-20251001";

// Anomaly thresholds
const ERROR_RATE_THRESHOLD = 0.05;       // >5% of events are api_error
const DECLINE_RATE_THRESHOLD = 0.20;     // >20% of assignment events are declines
const ZERO_ACTIVITY_MIN_7DAY_AVG = 1;    // fire if 7-day avg > 0 but today = 0

// ─── Types ────────────────────────────────────────────────────────────────────

interface EventCount { event_type: string; cnt: number }
interface Anomaly { type: string; message: string; severity: "low" | "medium" | "high" }

// ─── Helpers ──────────────────────────────────────────────────────────────────

function yesterday(): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}

async function callHaiku(apiKey: string, prompt: string): Promise<string> {
  const res = await fetch(ANTHROPIC_API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: HAIKU_MODEL,
      max_tokens: 600,
      messages: [{ role: "user", content: prompt }],
    }),
  });

  if (!res.ok) {
    throw new Error(`Anthropic API error: ${res.status} ${await res.text()}`);
  }

  const data = await res.json();
  return data?.content?.[0]?.text ?? "";
}

function detectAnomalies(
  counts: EventCount[],
  totalEvents: number,
  sevenDayAvg: number,
): Anomaly[] {
  const anomalies: Anomaly[] = [];
  const byType = Object.fromEntries(counts.map((r) => [r.event_type, r.cnt]));

  // Error spike
  const errorCount = (byType["api_error"] ?? 0) + (byType["edge_function_error"] ?? 0);
  if (totalEvents > 0 && errorCount / totalEvents > ERROR_RATE_THRESHOLD) {
    anomalies.push({
      type: "error_spike",
      message: `Error events: ${errorCount} / ${totalEvents} (${(errorCount / totalEvents * 100).toFixed(1)}% > ${ERROR_RATE_THRESHOLD * 100}% threshold)`,
      severity: errorCount / totalEvents > 0.15 ? "high" : "medium",
    });
  }

  // Assignment decline rate
  const assignmentEvents =
    (byType["assignment.created"] ?? 0) +
    (byType["assignment.supplier_accepted"] ?? 0) +
    (byType["assignment.supplier_declined"] ?? 0);
  const declined = byType["assignment.supplier_declined"] ?? 0;
  if (assignmentEvents > 5 && declined / assignmentEvents > DECLINE_RATE_THRESHOLD) {
    anomalies.push({
      type: "high_decline_rate",
      message: `Assignment decline rate: ${(declined / assignmentEvents * 100).toFixed(1)}% > ${DECLINE_RATE_THRESHOLD * 100}% threshold`,
      severity: "medium",
    });
  }

  // Zero activity when 7-day avg is positive
  if (totalEvents === 0 && sevenDayAvg > ZERO_ACTIVITY_MIN_7DAY_AVG) {
    anomalies.push({
      type: "zero_activity",
      message: `No events recorded today, but 7-day average is ${sevenDayAvg.toFixed(1)} events/day`,
      severity: "medium",
    });
  }

  return anomalies;
}

// ─── Handler ──────────────────────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: CORS_HEADERS });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  const anthropicKey = Deno.env.get("ANTHROPIC_API_KEY");

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false },
  });

  const date = yesterday();
  const dateStart = `${date}T00:00:00Z`;
  const dateEnd = `${date}T23:59:59Z`;

  try {
    // ── 1. Aggregate yesterday's events ─────────────────────────────────────
    const { data: rawCounts, error: countErr } = await supabase
      .from("events")
      .select("event_type")
      .gte("created_at", dateStart)
      .lte("created_at", dateEnd);

    if (countErr) throw new Error(`events query failed: ${countErr.message}`);

    const countMap: Record<string, number> = {};
    for (const row of rawCounts ?? []) {
      countMap[row.event_type] = (countMap[row.event_type] ?? 0) + 1;
    }
    const eventCounts: EventCount[] = Object.entries(countMap).map(
      ([event_type, cnt]) => ({ event_type, cnt })
    );
    const totalEvents = (rawCounts ?? []).length;

    // ── 2. 7-day average for zero-activity anomaly ───────────────────────────
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setUTCDate(sevenDaysAgo.getUTCDate() - 7);
    const { count: weekCount } = await supabase
      .from("events")
      .select("id", { count: "exact", head: true })
      .gte("created_at", sevenDaysAgo.toISOString());
    const sevenDayAvg = (weekCount ?? 0) / 7;

    // ── 3. Detect anomalies ──────────────────────────────────────────────────
    const anomalies = detectAnomalies(eventCounts, totalEvents, sevenDayAvg);

    // ── 4. Partition counts by summary type ──────────────────────────────────
    const USER_BEHAVIOUR_EVENTS = new Set([
      "page_view", "page_exit", "user_signed_in", "user_signed_out", "user_signed_up",
      "employee_portal_opened", "employee_document_uploaded", "employee_task_completed",
      "policy_question_asked", "policy_answer_rated", "policy_document_viewed",
    ]);
    const ASSIGNMENT_EVENTS = new Set([
      "assignment.created", "assignment.submitted", "assignment.in_progress",
      "assignment.completed", "assignment.cancelled", "assignment.disputed",
      "assignment.supplier_assigned", "assignment.supplier_accepted", "assignment.supplier_declined",
      "support_ticket.created", "support_ticket.resolved",
    ]);

    const userCounts: Record<string, number> = {};
    const assignmentCounts: Record<string, number> = {};
    const healthCounts: Record<string, number> = {};

    for (const { event_type, cnt } of eventCounts) {
      if (USER_BEHAVIOUR_EVENTS.has(event_type)) userCounts[event_type] = cnt;
      else if (ASSIGNMENT_EVENTS.has(event_type)) assignmentCounts[event_type] = cnt;
      else healthCounts[event_type] = cnt;
    }

    // ── 5. Generate AI digest via Claude Haiku ───────────────────────────────
    const generateDigest = async (
      summaryType: string,
      counts: Record<string, number>,
    ): Promise<string> => {
      if (!anthropicKey) {
        return totalEvents === 0
          ? `Quiet day on ${date} — no ${summaryType.replace("_", " ")} activity recorded.`
          : `${summaryType.replace("_", " ")} activity on ${date}: ${JSON.stringify(counts)}`;
      }

      const eventList = Object.entries(counts)
        .sort(([, a], [, b]) => b - a)
        .map(([k, v]) => `  - ${k}: ${v}`)
        .join("\n");

      const prompt = totalEvents === 0
        ? `Write a one-sentence "quiet day" summary for the ReloPass platform on ${date} — no events were recorded for ${summaryType.replace("_", " ")}.`
        : `You are a ReloPass platform analyst. Write a concise, plain-English summary (max 200 words) of the following ${summaryType.replace("_", " ")} events that occurred on ${date}. Focus on what's notable, not just the numbers. Be direct and factual.

Events:
${eventList}

${anomalies.length > 0 ? `Anomalies detected:\n${anomalies.map(a => `  - [${a.severity.toUpperCase()}] ${a.message}`).join("\n")}` : "No anomalies detected."}`;

      try {
        return await callHaiku(anthropicKey, prompt);
      } catch (err) {
        console.error(`Haiku call failed for ${summaryType}:`, err);
        return `Summary generation failed for ${date}. Raw counts: ${JSON.stringify(counts)}`;
      }
    };

    // Generate all three in parallel
    const [userText, assignmentText, healthText] = await Promise.all([
      generateDigest("user_behaviour", userCounts),
      generateDigest("assignments", assignmentCounts),
      generateDigest("platform_health", healthCounts),
    ]);

    // ── 6. Upsert to daily_summaries ─────────────────────────────────────────
    const rows = [
      {
        date,
        summary_type: "user_behaviour",
        summary_text: userText,
        raw_counts: userCounts,
        anomalies: anomalies.filter(a => ["zero_activity"].includes(a.type)),
      },
      {
        date,
        summary_type: "assignments",
        summary_text: assignmentText,
        raw_counts: assignmentCounts,
        anomalies: anomalies.filter(a => a.type === "high_decline_rate"),
      },
      {
        date,
        summary_type: "platform_health",
        summary_text: healthText,
        raw_counts: healthCounts,
        anomalies: anomalies.filter(a => a.type === "error_spike"),
      },
    ];

    const { error: upsertErr } = await supabase
      .from("daily_summaries")
      .upsert(rows, { onConflict: "date,summary_type" });

    if (upsertErr) throw new Error(`daily_summaries upsert failed: ${upsertErr.message}`);

    // ── 7. Refresh supplier_stats materialised view (MATCHING-5F) ────────────
    // Best-effort: a failure here must not block the rest of the nightly job.
    let supplierStatsRefreshed = false;
    try {
      const { error: refreshErr } = await supabase.rpc("refresh_supplier_stats");
      if (refreshErr) {
        console.warn("nightly-aggregation: refresh_supplier_stats failed:", refreshErr.message);
      } else {
        supplierStatsRefreshed = true;
      }
    } catch (refreshEx) {
      console.warn("nightly-aggregation: refresh_supplier_stats threw:", refreshEx);
    }

    const result = {
      ok: true,
      date,
      total_events: totalEvents,
      anomaly_count: anomalies.length,
      summaries_written: rows.length,
      supplier_stats_refreshed: supplierStatsRefreshed,
    };

    console.log("nightly-aggregation complete:", JSON.stringify(result));
    return Response.json(result, { headers: CORS_HEADERS });

  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("nightly-aggregation error:", message);
    return Response.json(
      { ok: false, error: message },
      { status: 500, headers: CORS_HEADERS }
    );
  }
});
