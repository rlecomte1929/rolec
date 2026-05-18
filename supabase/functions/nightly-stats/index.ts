/**
 * nightly-stats Edge Function
 *
 * Runs nightly at 02:00 UTC via pg_cron job 2 ("nightly-benchmarking-stats").
 *
 * What it computes (from real schema):
 *   workspace_stats — one row per org per run:
 *     - total_cases_in_window   : mobility_cases created in last 90 days
 *     - closed_cases_in_window  : those with an archived case_assignment
 *     - avg_completion_days     : mean(archived_at - ca.created_at) for archived assignments
 *     - corridor_breakdown      : JSONB — [{corridor, avg_days, case_count}]
 *     - top_delay_causes        : [] (no delay_reason column yet)
 *     - compliance_incident_rate: null (no compliance_flag column yet)
 *
 *   industry_benchmarks — one row per run (is_valid = total cases >= 50):
 *     - median_completion_days  : median across all valid workspace avg_completion_days
 *     - median_compliance_rate  : null (no data yet)
 *     - case_count              : total cases across all orgs
 *     - workspace_count         : number of distinct orgs
 *
 * After writing, purges workspace_stats rows older than 90 days.
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
};

const WINDOW_DAYS = 90;
const MIN_CASES_FOR_VALID_BENCHMARK = 50;

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: CORS_HEADERS });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

  // Use service role to bypass RLS
  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false },
  });

  const now = new Date();
  const windowStart = new Date(now.getTime() - WINDOW_DAYS * 86_400_000);

  console.log(
    `[nightly-stats] Starting run at ${now.toISOString()}, window: ${windowStart.toISOString()} → ${now.toISOString()}`,
  );

  // ── Step 1: Fetch all mobility_cases in window ────────────────────────────
  // Paginate to handle large datasets
  const PAGE = 1000;
  type CaseRow = {
    id: string;
    company_id: string;
    origin_country: string | null;
    destination_country: string | null;
    created_at: string;
  };
  const cases: CaseRow[] = [];
  let from = 0;
  while (true) {
    const { data, error } = await supabase
      .from("mobility_cases")
      .select("id, company_id, origin_country, destination_country, created_at")
      .gte("created_at", windowStart.toISOString())
      .order("created_at", { ascending: true })
      .range(from, from + PAGE - 1);

    if (error) {
      console.error("[nightly-stats] Failed to fetch mobility_cases:", error);
      return Response.json(
        { ok: false, error: "mobility_cases query failed", details: error.message },
        { status: 500, headers: CORS_HEADERS },
      );
    }
    if (!data || data.length === 0) break;
    cases.push(...(data as CaseRow[]));
    if (data.length < PAGE) break;
    from += PAGE;
  }
  console.log(`[nightly-stats] ${cases.length} cases in window`);

  if (cases.length === 0) {
    return Response.json(
      { ok: true, message: "No cases in window — nothing to compute", rows_processed: 0 },
      { headers: CORS_HEADERS },
    );
  }

  // ── Step 2: Fetch case_assignments for completion time ────────────────────
  // We only care about archived assignments (proxy for "case closed")
  type AssignmentRow = {
    case_id: string;
    created_at: string;
    archived_at: string | null;
  };
  const caseIds = cases.map((c) => c.id);
  const assignments: AssignmentRow[] = [];
  from = 0;
  while (true) {
    // case_assignments.case_id is TEXT, mobility_cases.id is UUID — match as string
    const { data, error } = await supabase
      .from("case_assignments")
      .select("case_id, created_at, archived_at")
      .in("case_id", caseIds.slice(from, from + PAGE))
      .range(0, PAGE - 1);

    if (error) {
      console.error("[nightly-stats] Failed to fetch case_assignments:", error);
      // Non-fatal — continue without completion time data
      break;
    }
    if (!data || data.length === 0) break;
    assignments.push(...(data as AssignmentRow[]));
    if (caseIds.slice(from, from + PAGE).length < PAGE) break;
    from += PAGE;
  }

  // Build a map: caseId → archived_at (for completion time calc)
  const archivedAt = new Map<string, Date>();
  const assignmentCreatedAt = new Map<string, Date>();
  for (const a of assignments) {
    if (a.archived_at) {
      archivedAt.set(a.case_id, new Date(a.archived_at));
      assignmentCreatedAt.set(a.case_id, new Date(a.created_at));
    }
  }

  // ── Step 3: Group by company_id ───────────────────────────────────────────
  type OrgBucket = {
    cases: CaseRow[];
    completionDays: number[];
  };
  const byOrg = new Map<string, OrgBucket>();
  for (const c of cases) {
    if (!c.company_id) continue;
    const bucket = byOrg.get(c.company_id) ?? { cases: [], completionDays: [] };
    bucket.cases.push(c);
    // Completion time: archived_at - assignment created_at in days
    const archived = archivedAt.get(c.id);
    const created = assignmentCreatedAt.get(c.id);
    if (archived && created) {
      const days = (archived.getTime() - created.getTime()) / 86_400_000;
      if (days >= 0 && days < 3650) bucket.completionDays.push(days); // sanity cap 10 years
    }
    byOrg.set(c.company_id, bucket);
  }

  // ── Step 4: Compute per-org stats and upsert workspace_stats ─────────────
  const errors: string[] = [];
  const workspaceAvgDays: number[] = []; // for industry median

  for (const [orgId, bucket] of byOrg) {
    const totalCases = bucket.cases.length;
    const closedCases = bucket.cases.filter((c) => archivedAt.has(c.id)).length;

    const avgCompletionDays =
      bucket.completionDays.length > 0
        ? bucket.completionDays.reduce((a, b) => a + b, 0) / bucket.completionDays.length
        : null;

    if (avgCompletionDays !== null) workspaceAvgDays.push(avgCompletionDays);

    // Corridor breakdown: group by origin→dest
    type CorridorAcc = { totalDays: number; count: number };
    const corridorMap = new Map<string, CorridorAcc>();
    for (const c of bucket.cases) {
      const origin = c.origin_country ?? "Unknown";
      const dest = c.destination_country ?? "Unknown";
      const key = `${origin}→${dest}`;
      const acc = corridorMap.get(key) ?? { totalDays: 0, count: 0 };
      acc.count += 1;
      const days = archivedAt.has(c.id) && assignmentCreatedAt.has(c.id)
        ? (archivedAt.get(c.id)!.getTime() - assignmentCreatedAt.get(c.id)!.getTime()) / 86_400_000
        : null;
      if (days !== null && days >= 0) acc.totalDays += days;
      corridorMap.set(key, acc);
    }
    const corridorBreakdown = [...corridorMap.entries()]
      .map(([corridor, acc]) => ({
        corridor,
        avg_days: acc.count > 0 ? Math.round((acc.totalDays / acc.count) * 10) / 10 : 0,
        case_count: acc.count,
      }))
      .sort((a, b) => b.case_count - a.case_count);

    const { error: wsError } = await supabase.from("workspace_stats").insert({
      org_id: orgId,
      computed_at: now.toISOString(),
      avg_completion_days: avgCompletionDays !== null ? Math.round(avgCompletionDays * 10) / 10 : null,
      compliance_incident_rate: null, // no compliance_flag column yet
      total_cases_in_window: totalCases,
      closed_cases_in_window: closedCases,
      top_delay_causes: [], // no delay_reason column yet
      corridor_breakdown: corridorBreakdown,
    });

    if (wsError) {
      const msg = `workspace_stats insert failed for org ${orgId}: ${wsError.message}`;
      console.error(`[nightly-stats] ${msg}`);
      errors.push(msg);
    } else {
      console.log(
        `[nightly-stats] org ${orgId}: ${totalCases} cases, ${closedCases} closed, avg ${avgCompletionDays?.toFixed(1) ?? "—"} days, ${corridorBreakdown.length} corridors`,
      );
    }
  }

  // ── Step 5: Industry benchmarks ───────────────────────────────────────────
  const totalCasesAllOrgs = cases.length;
  const workspaceCount = byOrg.size;
  const isValid = totalCasesAllOrgs >= MIN_CASES_FOR_VALID_BENCHMARK;

  let medianCompletionDays: number | null = null;
  if (workspaceAvgDays.length > 0) {
    const sorted = [...workspaceAvgDays].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    medianCompletionDays =
      sorted.length % 2 === 0
        ? Math.round(((sorted[mid - 1] + sorted[mid]) / 2) * 10) / 10
        : Math.round(sorted[mid] * 10) / 10;
  }

  const { error: ibError } = await supabase.from("industry_benchmarks").insert({
    computed_at: now.toISOString(),
    case_count: totalCasesAllOrgs,
    workspace_count: workspaceCount,
    median_completion_days: medianCompletionDays,
    median_compliance_rate: null, // no data yet
    corridor_benchmarks: {},
    is_valid: isValid,
  });

  if (ibError) {
    console.error("[nightly-stats] industry_benchmarks insert failed:", ibError);
    errors.push(`industry_benchmarks insert failed: ${ibError.message}`);
  } else {
    console.log(
      `[nightly-stats] Industry benchmark: ${totalCasesAllOrgs} cases, ${workspaceCount} orgs, median ${medianCompletionDays ?? "—"} days, is_valid=${isValid}`,
    );
  }

  // ── Step 6: Purge workspace_stats rows older than 90 days ─────────────────
  const purgeThreshold = new Date(now.getTime() - WINDOW_DAYS * 86_400_000);
  const { error: purgeError } = await supabase
    .from("workspace_stats")
    .delete()
    .lt("computed_at", purgeThreshold.toISOString());

  if (purgeError) {
    console.warn("[nightly-stats] Purge failed (non-fatal):", purgeError.message);
  }

  const status = errors.length === 0 ? 200 : 207;
  return Response.json(
    {
      ok: errors.length === 0,
      rows_processed: cases.length,
      orgs_computed: byOrg.size,
      is_valid_benchmark: isValid,
      median_completion_days: medianCompletionDays,
      errors: errors.length > 0 ? errors : undefined,
    },
    { status, headers: CORS_HEADERS },
  );
});
