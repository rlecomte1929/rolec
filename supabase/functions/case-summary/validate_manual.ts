/**
 * case-summary — MANUAL validation harness (AIQ-1693 criterion: 5 records, zero fabrication).
 *
 * NOT a test (not *.test.ts, so `deno test` ignores it) and NOT run in CI: it makes a
 * real Claude call, so it needs a key. It feeds 5 real-shaped, NON-PII operational field
 * sets straight through the same generateSummary() the function uses, and prints the input
 * beside the output so a human can confirm every statement is grounded and nothing is
 * fabricated.
 *
 * Run:
 *   ANTHROPIC_API_KEY=sk-ant-... deno run --allow-net --allow-env \
 *     supabase/functions/case-summary/validate_manual.ts
 *
 * Sign-off: for each of the 5, confirm status/blockers/next_actions/cost_variance reference
 * ONLY facts present in the printed input (no invented dates, costs, names, or reasons).
 */
import { buildSummaryInput, generateSummary, type Row } from "./summary.ts";

// 5 real-shaped cases spanning distinct states. Values are synthetic + non-PII, matching
// the operational columns of case_assignments (a) and relocation_cases (rc).
const RECORDS: Array<{ label: string; a: Row; rc: Row }> = [
  {
    label: "1 · on-track, mid-intake, under budget",
    a: { status: "in_progress", coordination_status: "active", risk_status: "on_track", budget_limit: 20000, budget_estimated: 17500, expected_start_date: "2026-09-01", submitted_at: "2026-07-20T10:00:00Z", intake_step: 4, intake_total_steps: 6, created_at: "2026-07-01T09:00:00Z" },
    rc: { status: "active", stage: "housing", risk_status: "on_track", delay_reason: null, compliance_flag: false, budget_limit: 20000, budget_estimated: 17500, host_country: "Germany", home_country: "France", host_city: "Berlin", home_city: "Paris", corridor: "FR_DE", target_start_date: "2026-09-01", payment_status: "roadmap_paid", access_tier: "roadmap", paid_amount_cents: 80000, paid_currency: "EUR" },
  },
  {
    label: "2 · at-risk, blocked on work permit",
    a: { status: "in_progress", coordination_status: "active", risk_status: "at_risk", budget_limit: 30000, budget_estimated: 31200, expected_start_date: "2026-08-15", submitted_at: "2026-06-30T10:00:00Z", intake_step: 6, intake_total_steps: 6, created_at: "2026-06-01T09:00:00Z" },
    rc: { status: "active", stage: "immigration", risk_status: "at_risk", delay_reason: "awaiting_work_permit", compliance_flag: true, budget_limit: 30000, budget_estimated: 31200, host_country: "United States", home_country: "India", host_city: "Austin", home_city: "Bangalore", corridor: "IN_US", target_start_date: "2026-08-15", payment_status: "roadmap_paid", access_tier: "roadmap", paid_amount_cents: 80000, paid_currency: "USD" },
  },
  {
    label: "3 · pre-intake, not yet submitted, free tier",
    a: { status: "assigned", coordination_status: "pending", risk_status: "on_track", budget_limit: null, budget_estimated: null, expected_start_date: null, submitted_at: null, intake_step: 0, intake_total_steps: 6, created_at: "2026-07-24T09:00:00Z" },
    rc: { status: "draft", stage: "intake", risk_status: "on_track", delay_reason: null, compliance_flag: false, budget_limit: null, budget_estimated: null, host_country: "Netherlands", home_country: "Spain", host_city: "Amsterdam", home_city: "Madrid", corridor: "ES_NL", target_start_date: null, payment_status: "unpaid", access_tier: "free", paid_amount_cents: null, paid_currency: null },
  },
  {
    label: "4 · over budget, delayed",
    a: { status: "in_progress", coordination_status: "active", risk_status: "at_risk", budget_limit: 15000, budget_estimated: 19800, expected_start_date: "2026-07-01", submitted_at: "2026-05-20T10:00:00Z", intake_step: 6, intake_total_steps: 6, created_at: "2026-05-01T09:00:00Z" },
    rc: { status: "active", stage: "settling_in", risk_status: "at_risk", delay_reason: "vendor_capacity", compliance_flag: false, budget_limit: 15000, budget_estimated: 19800, host_country: "Singapore", home_country: "United Kingdom", host_city: "Singapore", home_city: "London", corridor: "UK_SG", target_start_date: "2026-07-01", payment_status: "roadmap_paid", access_tier: "roadmap", paid_amount_cents: 80000, paid_currency: "GBP" },
  },
  {
    label: "5 · complete / on budget",
    a: { status: "completed", coordination_status: "closed", risk_status: "on_track", budget_limit: 25000, budget_estimated: 24100, expected_start_date: "2026-06-01", submitted_at: "2026-04-10T10:00:00Z", intake_step: 6, intake_total_steps: 6, created_at: "2026-03-15T09:00:00Z" },
    rc: { status: "completed", stage: "complete", risk_status: "on_track", delay_reason: null, compliance_flag: false, budget_limit: 25000, budget_estimated: 24100, host_country: "Germany", home_country: "Poland", host_city: "Munich", home_city: "Warsaw", corridor: "PL_DE", target_start_date: "2026-06-01", payment_status: "roadmap_paid", access_tier: "roadmap", paid_amount_cents: 80000, paid_currency: "EUR" },
  },
];

if (import.meta.main) {
  const key = Deno.env.get("ANTHROPIC_API_KEY");
  if (!key) {
    console.error("Set ANTHROPIC_API_KEY to run the 5-record validation.");
    Deno.exit(1);
  }
  for (const rec of RECORDS) {
    const input = buildSummaryInput(rec.a, rec.rc);
    console.log("\n" + "═".repeat(72) + "\n" + rec.label);
    console.log("INPUT:", JSON.stringify(input));
    try {
      const summary = await generateSummary(key, input);
      console.log("OUTPUT:", JSON.stringify(summary, null, 2));
    } catch (e) {
      console.error("FAILED:", e instanceof Error ? e.message : String(e));
    }
  }
  console.log("\nSign-off: confirm every statement above traces to a field in its INPUT.");
}
