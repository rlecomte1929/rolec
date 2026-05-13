import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

// ── Types ─────────────────────────────────────────────────────────────────────

interface RelocationCase {
  id: string;
  company_id: string | null;
  status: string | null;
  stage: string | null;
  home_country: string | null;
  host_country: string | null;
  archived_at: string | null;   // timestamptz
  created_at: string;           // stored as text ISO-8601
  compliance_flag: boolean;
  delay_reason: string | null;
}

interface CompanyStats {
  company_id: string;
  window_days: number;
  active_cases: number;
  closed_cases: number;
  compliance_flag_count: number;
  avg_days_to_close: number | null;
  top_host_countries: Array<{ country: string; count: number }>;
  top_home_countries: Array<{ country: string; count: number }>;
  top_delay_causes: Array<{ reason: string; count: number }>;
}

interface StatsResponse {
  computed_at: string;
  window_days: number;
  total_cases_in_window: number;
  companies: CompanyStats[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function topN<T extends string | null>(
  items: T[],
  n = 5
): Array<{ country: string; count: number }> {
  const counts: Record<string, number> = {};
  for (const item of items) {
    if (!item) continue;
    counts[item] = (counts[item] ?? 0) + 1;
  }
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([country, count]) => ({ country, count }));
}

function topNReasons(
  items: Array<string | null>,
  n = 5
): Array<{ reason: string; count: number }> {
  const counts: Record<string, number> = {};
  for (const item of items) {
    if (!item) continue;
    counts[item] = (counts[item] ?? 0) + 1;
  }
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([reason, count]) => ({ reason, count }));
}

/** Parse text ISO-8601 date safely — returns null on failure */
function parseTextDate(s: string | null): Date | null {
  if (!s) return null;
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

// ── Handler ───────────────────────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);

  // Parse optional window_days param (default 30)
  let window_days = 30;
  try {
    const body = await req.json();
    if (typeof body?.window_days === "number" && body.window_days > 0) {
      window_days = Math.min(body.window_days, 365);
    }
  } catch { /* no body — use default */ }

  const now = new Date();
  const windowStart = new Date(now.getTime() - window_days * 86_400_000);
  // created_at is stored as TEXT in ISO-8601 format; lexicographic comparison
  // works correctly for ISO strings with consistent timezone formatting.
  const windowStartIso = windowStart.toISOString();

  // Fetch all cases created within the window (or still active)
  const { data: cases, error } = await supabase
    .from("relocation_cases")
    .select(
      "id, company_id, status, stage, home_country, host_country, archived_at, created_at, compliance_flag, delay_reason"
    )
    .gte("created_at", windowStartIso);

  if (error) {
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }

  const allCases = (cases ?? []) as RelocationCase[];

  // Group by company
  const byCompany: Record<string, RelocationCase[]> = {};
  for (const c of allCases) {
    const cid = c.company_id ?? "__unknown__";
    (byCompany[cid] ??= []).push(c);
  }

  const companyStats: CompanyStats[] = [];

  for (const [company_id, companyCases] of Object.entries(byCompany)) {
    const activeCases = companyCases.filter(
      (c) => !c.archived_at && c.status !== "archived" && c.status !== "closed"
    );
    const closedCases = companyCases.filter(
      (c) => !!c.archived_at || c.status === "archived" || c.status === "closed"
    );

    // Avg days to close: (archived_at - created_at) in days
    const closeTimes: number[] = [];
    for (const c of closedCases) {
      const created = parseTextDate(c.created_at);
      const closed = c.archived_at ? new Date(c.archived_at) : null;
      if (created && closed) {
        const days = (closed.getTime() - created.getTime()) / 86_400_000;
        if (days >= 0) closeTimes.push(days);
      }
    }
    const avg_days_to_close =
      closeTimes.length > 0
        ? Math.round(closeTimes.reduce((a, b) => a + b, 0) / closeTimes.length)
        : null;

    companyStats.push({
      company_id,
      window_days,
      active_cases: activeCases.length,
      closed_cases: closedCases.length,
      compliance_flag_count: companyCases.filter((c) => c.compliance_flag).length,
      avg_days_to_close,
      top_host_countries: topN(companyCases.map((c) => c.host_country)),
      top_home_countries: topN(companyCases.map((c) => c.home_country)),
      top_delay_causes: topNReasons(companyCases.map((c) => c.delay_reason)),
    });
  }

  // Sort by total case volume descending
  companyStats.sort(
    (a, b) => (b.active_cases + b.closed_cases) - (a.active_cases + a.closed_cases)
  );

  const response: StatsResponse = {
    computed_at: now.toISOString(),
    window_days,
    total_cases_in_window: allCases.length,
    companies: companyStats,
  };

  return new Response(JSON.stringify(response, null, 2), {
    headers: { "Content-Type": "application/json" },
  });
});
