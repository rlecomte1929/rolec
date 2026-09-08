/**
 * gap-detection-weekly — P5-7: Policy calibration gap detection
 *
 * Scheduled weekly (configure via Supabase cron dashboard or pg_cron).
 * Recommended schedule: every Monday at 06:00 UTC.
 *
 * Algorithm:
 *   1. Query policy_cap_requests (pending + approved, last 30 days)
 *      grouped by (organization_id, category, tier_name from employee_tiers).
 *   2. Flag groups where:
 *        exception_count >= 3  AND  avg_excess_pct > 0.10 (10 %)
 *   3. Deduplicate: skip if a non-dismissed alert for the same
 *      (organization_id, category, tier_name) was created in the last 7 days.
 *   4. Insert new policy_calibration_alerts rows.
 *   5. For each newly inserted alert, find HR/Admin users for the affected org
 *      and write rows into notification_outbox for email delivery.
 *
 * Env vars required:
 *   SUPABASE_URL           — project URL (auto-set in Edge Functions)
 *   SUPABASE_SERVICE_ROLE_KEY — service role key (auto-set in Edge Functions)
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GapRow {
  organization_id: string;
  category: string;
  tier_name: string | null;
  exception_count: number;
  avg_excess_pct: number;
}

interface AlertRow {
  id: string;
  organization_id: string;
  category: string;
  tier_name: string | null;
  exception_count: number;
  avg_excess_pct: number;
  alert_message: string;
}

// ---------------------------------------------------------------------------
// Helper: build a human-readable alert message
// ---------------------------------------------------------------------------
function buildAlertMessage(gap: GapRow): string {
  const pct = Math.round(gap.avg_excess_pct * 100);
  const tierLabel = gap.tier_name ? ` (tier: ${gap.tier_name})` : "";
  return (
    `Policy gap detected in "${gap.category}"${tierLabel}: ` +
    `${gap.exception_count} exception requests in the last 30 days ` +
    `with an average ${pct}% overage above the policy cap. ` +
    `Consider revising the cap for this benefit category.`
  );
}

// ---------------------------------------------------------------------------
// Main handler
// ---------------------------------------------------------------------------
Deno.serve(async (_req: Request): Promise<Response> => {
  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false },
  });

  // -------------------------------------------------------------------------
  // Step 1: Gap detection query
  // -------------------------------------------------------------------------
  // Join policy_cap_requests → profiles → employee_tiers to get tier_name.
  // employee_tiers has at most one active row per employee (WHERE end_date IS NULL).
  const { data: gaps, error: gapError } = await supabase.rpc(
    "detect_policy_calibration_gaps"
  );

  if (gapError) {
    // Fall back to inline SQL if the RPC doesn't exist yet
    console.error("RPC not available, using inline query:", gapError.message);
  }

  // Use inline SQL via raw postgrest query as a fallback / primary approach.
  // Supabase JS client doesn't support GROUP BY natively, so we use the
  // execute-sql approach via the management API or a raw fetch.
  const gapRows: GapRow[] = await runGapDetectionSQL(supabaseUrl, serviceRoleKey);

  if (gapRows.length === 0) {
    console.log("gap-detection-weekly: no gaps found, nothing to do");
    return new Response(JSON.stringify({ inserted: 0, skipped: 0 }), {
      headers: { "Content-Type": "application/json" },
    });
  }

  // -------------------------------------------------------------------------
  // Step 2: Deduplication — skip groups that already have a recent alert
  // -------------------------------------------------------------------------
  const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();

  const { data: recentAlerts, error: recentErr } = await supabase
    .from("policy_calibration_alerts")
    .select("organization_id, category, tier_name")
    .gt("created_at", sevenDaysAgo)
    .is("dismissed_at", null);

  if (recentErr) {
    console.error("gap-detection-weekly: failed to fetch recent alerts:", recentErr.message);
    return new Response(JSON.stringify({ error: recentErr.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  const recentSet = new Set(
    (recentAlerts ?? []).map(
      (r: { organization_id: string; category: string; tier_name: string | null }) =>
        `${r.organization_id}::${r.category}::${r.tier_name ?? "__none__"}`
    )
  );

  const newGaps = gapRows.filter(
    (g) =>
      !recentSet.has(
        `${g.organization_id}::${g.category}::${g.tier_name ?? "__none__"}`
      )
  );

  if (newGaps.length === 0) {
    console.log(
      `gap-detection-weekly: ${gapRows.length} gap(s) found but all already alerted recently`
    );
    return new Response(
      JSON.stringify({ inserted: 0, skipped: gapRows.length }),
      { headers: { "Content-Type": "application/json" } }
    );
  }

  // -------------------------------------------------------------------------
  // Step 3: Insert new policy_calibration_alerts rows
  // -------------------------------------------------------------------------
  const alertsToInsert = newGaps.map((g) => ({
    organization_id: g.organization_id,
    category: g.category,
    tier_name: g.tier_name,
    exception_count: g.exception_count,
    avg_excess_pct: g.avg_excess_pct,
    alert_message: buildAlertMessage(g),
  }));

  const { data: insertedAlerts, error: insertErr } = await supabase
    .from("policy_calibration_alerts")
    .insert(alertsToInsert)
    .select();

  if (insertErr) {
    console.error("gap-detection-weekly: insert failed:", insertErr.message);
    return new Response(JSON.stringify({ error: insertErr.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  console.log(
    `gap-detection-weekly: inserted ${insertedAlerts?.length ?? 0} alert(s)`
  );

  // -------------------------------------------------------------------------
  // Step 4: Queue email notifications for HR/Admin users in affected orgs
  // -------------------------------------------------------------------------
  const affectedOrgIds = [
    ...new Set((insertedAlerts as AlertRow[]).map((a) => a.organization_id)),
  ];

  let emailsQueued = 0;
  for (const orgId of affectedOrgIds) {
    // Find HR and admin profiles for this org
    const { data: hrUsers, error: hrErr } = await supabase
      .from("profiles")
      .select("id, email")
      .eq("company_id", orgId)
      .in("role", ["hr", "admin", "HR", "ADMIN"]);

    if (hrErr || !hrUsers?.length) {
      console.warn(
        `gap-detection-weekly: no HR users found for org ${orgId}:`,
        hrErr?.message ?? "empty result"
      );
      continue;
    }

    // Build a summary of alerts for this org
    const orgAlerts = (insertedAlerts as AlertRow[]).filter(
      (a) => a.organization_id === orgId
    );
    const alertSummary = orgAlerts
      .map((a) => `  • ${a.alert_message}`)
      .join("\n");

    const subject = `[ReloPass] Policy calibration alert — ${orgAlerts.length} benefit cap gap(s) detected`;
    const body =
      `Hi,\n\n` +
      `The weekly policy gap analysis has detected ${orgAlerts.length} benefit category gap(s) ` +
      `that may need your attention:\n\n${alertSummary}\n\n` +
      `Log in to your ReloPass HR dashboard to review and dismiss these alerts.\n\n` +
      `— ReloPass Policy Engine`;

    // Write one outbox row per HR user
    const outboxRows = hrUsers.map((u: { id: string; email: string }) => ({
      user_id: u.id,
      to_email: u.email,
      type: "policy_calibration_alert",
      payload: {
        // send-notification-email reads payload.title for subject and payload.body for text
        title: subject,
        body,
        alert_count: orgAlerts.length,
        organization_id: orgId,
      },
      status: "pending",
    }));

    const { error: outboxErr } = await supabase
      .from("notification_outbox")
      .insert(outboxRows);

    if (outboxErr) {
      console.error(
        `gap-detection-weekly: outbox insert failed for org ${orgId}:`,
        outboxErr.message
      );
    } else {
      emailsQueued += outboxRows.length;
    }
  }

  return new Response(
    JSON.stringify({
      inserted: insertedAlerts?.length ?? 0,
      skipped: gapRows.length - newGaps.length,
      emails_queued: emailsQueued,
    }),
    { headers: { "Content-Type": "application/json" } }
  );
});

// ---------------------------------------------------------------------------
// Gap detection SQL — run as a service-role raw query
// ---------------------------------------------------------------------------
// Supabase Edge Functions can call the Supabase REST/PostgREST but GROUP BY
// with HAVING isn't exposed through the JS client. We call the DB via the
// pg REST endpoint using the service role.
async function runGapDetectionSQL(
  supabaseUrl: string,
  serviceRoleKey: string
): Promise<GapRow[]> {
  /**
   * Detection logic:
   *   - Only pending + approved requests (rejected/countered are resolved)
   *   - Last 30 days
   *   - Join to employee_tiers for tier_name (NULL if no active tier)
   *   - Group by org, category, tier_name
   *   - Threshold: >= 3 exceptions AND avg overage > 10%
   *
   * avg_excess_pct = AVG( (requested_amount - cap_amount) / cap_amount )
   * We use NULLIF(cap_amount, 0) to avoid division by zero.
   */
  const sql = `
    SELECT
      pcr.organization_id,
      pcr.category,
      et.tier_name,
      COUNT(*)::int                                                    AS exception_count,
      AVG(
        (pcr.requested_amount - pcr.cap_amount)
        / NULLIF(pcr.cap_amount, 0)
      )                                                                AS avg_excess_pct
    FROM public.policy_cap_requests pcr
    LEFT JOIN public.profiles prof
           ON prof.id = pcr.requested_by_user_id
    LEFT JOIN public.employee_tiers et
           ON et.employee_id = prof.id
          AND et.end_date IS NULL
    WHERE pcr.status IN ('pending', 'approved')
      AND pcr.created_at > NOW() - INTERVAL '30 days'
    GROUP BY pcr.organization_id, pcr.category, et.tier_name
    HAVING COUNT(*) >= 3
       AND AVG(
             (pcr.requested_amount - pcr.cap_amount)
             / NULLIF(pcr.cap_amount, 0)
           ) > 0.10
    ORDER BY exception_count DESC, avg_excess_pct DESC
  `;

  // Use the Supabase Management API SQL endpoint (requires service role)
  const projectRef = supabaseUrl.replace("https://", "").split(".")[0];
  const res = await fetch(
    `https://api.supabase.com/v1/projects/${projectRef}/database/query`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${serviceRoleKey}`,
      },
      body: JSON.stringify({ query: sql }),
    }
  );

  if (!res.ok) {
    // Fallback: try the PostgREST RPC approach by calling the DB directly
    // via the project's Postgres connection string isn't available in Edge Functions,
    // so we create a simple wrapper RPC or use the pg-meta endpoint.
    console.error(
      "gap-detection-weekly: management API query failed, status:",
      res.status
    );
    const errText = await res.text();
    console.error("gap-detection-weekly: error body:", errText);
    return [];
  }

  const json = await res.json();
  // Management API returns { rows: [...] } or just the array depending on version
  const rows: Record<string, unknown>[] = Array.isArray(json)
    ? json
    : (json.rows ?? []);

  return rows.map((r) => ({
    organization_id: r.organization_id as string,
    category: r.category as string,
    tier_name: (r.tier_name as string) ?? null,
    exception_count: Number(r.exception_count),
    avg_excess_pct: Number(r.avg_excess_pct),
  }));
}
