/**
 * case-summary — pure-logic tests (no network, no DB, no Claude).
 * Run: deno test supabase/functions/case-summary/
 *
 * The load-bearing test is `no PII reaches the prompt` — that is the compliance
 * guarantee (AIQ-1693): the summary is built only from a non-PII whitelist even
 * when the source rows contain names, notes, and the raw intake draft.
 */
import { assert, assertEquals } from "https://deno.land/std@0.224.0/assert/mod.ts";
import {
  buildSummaryInput,
  buildUserMessage,
  FORBIDDEN_PII_FIELDS,
  parseSummary,
  pick,
  SYSTEM_PROMPT,
} from "./summary.ts";
import { fetchAssignmentAndCase } from "./db.ts";

// A realistic assignment row that DELIBERATELY includes PII + free-text fields.
const ASSIGNMENT_ROW = {
  id: "assign-1",
  case_id: "case-1",
  canonical_case_id: "case-1",
  status: "in_progress",
  coordination_status: "active",
  risk_status: "on_track",
  budget_limit: 20000,
  budget_estimated: 18500,
  expected_start_date: "2026-09-01",
  submitted_at: "2026-07-20T10:00:00Z",
  intake_step: 4,
  intake_total_steps: 6,
  created_at: "2026-07-01T09:00:00Z",
  // PII / free-text — must never appear downstream:
  employee_first_name: "Amara",
  employee_last_name: "Okafor",
  employee_identifier: "amara.okafor@acme.com",
  employee_contact_id: "contact-xyz",
  employee_user_id: "user-uuid-123",
  hr_notes: "Amara's spouse visa is pending; passport N1234567.",
  decision: "approved by Jane",
  intake_draft: { passport: "N1234567", home_address: "12 Rue de Rivoli, Paris" },
};

const CASE_ROW = {
  id: "case-1",
  company_id: "acme",
  status: "active",
  stage: "immigration",
  risk_status: "at_risk",
  delay_reason: "awaiting_work_permit",
  compliance_flag: true,
  budget_limit: 20000,
  budget_estimated: 18500,
  host_country: "Germany",
  home_country: "France",
  host_city: "Berlin",
  home_city: "Paris",
  corridor: "FR_DE",
  target_start_date: "2026-09-01",
  payment_status: "roadmap_paid",
  access_tier: "roadmap",
  paid_amount_cents: 80000,
  paid_currency: "EUR",
  // PII / free-text:
  profile_json: '{"name":"Amara Okafor","dob":"1990-01-01"}',
};

Deno.test("pick keeps only whitelisted, non-null keys", () => {
  const out = pick({ a: 1, b: null, c: "x", d: undefined }, ["a", "b", "d", "z"]);
  assertEquals(out, { a: 1 }); // b null, d undefined, z absent all dropped
});

Deno.test("buildSummaryInput carries the operational fields", () => {
  const input = buildSummaryInput(ASSIGNMENT_ROW, CASE_ROW);
  assertEquals(input.assignment.status, "in_progress");
  assertEquals(input.assignment.budget_estimated, 18500);
  assertEquals(input.case.host_country, "Germany");
  assertEquals(input.case.delay_reason, "awaiting_work_permit");
  assertEquals(input.case.paid_amount_cents, 80000);
});

Deno.test("COMPLIANCE: no PII field or value reaches the prompt payload", () => {
  const input = buildSummaryInput(ASSIGNMENT_ROW, CASE_ROW);
  const serialized = buildUserMessage(input);

  // No forbidden KEY present in the built input.
  for (const key of FORBIDDEN_PII_FIELDS) {
    assert(!(key in input.assignment), `assignment leaked forbidden key: ${key}`);
    assert(!(key in input.case), `case leaked forbidden key: ${key}`);
  }

  // No PII VALUE present anywhere in the serialized prompt.
  const forbiddenValues = [
    "Amara",
    "Okafor",
    "amara.okafor@acme.com",
    "contact-xyz",
    "user-uuid-123",
    "N1234567",
    "Rue de Rivoli",
    "passport",
    "dob",
    "approved by Jane",
  ];
  for (const v of forbiddenValues) {
    assert(!serialized.includes(v), `prompt leaked PII value: ${v}`);
  }
});

Deno.test("SYSTEM_PROMPT enforces grounding + no-PII", () => {
  const p = SYSTEM_PROMPT.toLowerCase();
  assert(p.includes("do not infer"), "prompt must forbid inference");
  assert(p.includes("only the fields"), "prompt must restrict to provided fields");
  assert(p.includes("never invent"), "prompt must forbid inventing PII");
});

Deno.test("parseSummary handles clean JSON", () => {
  const s = parseSummary(
    '{"status":"Immigration stage.","blockers":["awaiting_work_permit"],"next_actions":["chase permit"],"cost_variance":"Under budget by 1,500 EUR."}',
  );
  assertEquals(s.status, "Immigration stage.");
  assertEquals(s.blockers, ["awaiting_work_permit"]);
  assertEquals(s.next_actions, ["chase permit"]);
  assert(s.cost_variance.includes("Under budget"));
});

Deno.test("parseSummary handles markdown-fenced JSON", () => {
  const s = parseSummary('```json\n{"status":"ok","blockers":[],"next_actions":[],"cost_variance":"not recorded"}\n```');
  assertEquals(s.status, "ok");
  assertEquals(s.blockers, []);
});

Deno.test("parseSummary degrades safely on garbage", () => {
  const s = parseSummary("the model rambled without json");
  assertEquals(s.status, "Status not available.");
  assertEquals(s.blockers, []);
  assertEquals(s.next_actions, []);
  assertEquals(s.cost_variance, "not recorded");
});

Deno.test("parseSummary coerces non-string array items and drops empties", () => {
  const s = parseSummary('{"status":"s","blockers":[1,"",  "real"],"next_actions":null,"cost_variance":"c"}');
  assertEquals(s.blockers, ["1", "real"]);
  assertEquals(s.next_actions, []);
});

// ── Tenant scoping (criterion #2) ─────────────────────────────────────────────

/** Minimal fake of the supabase-js query builder: from().select().eq().maybeSingle(). */
function fakeSupabase(tables: Record<string, Record<string, unknown>>) {
  return {
    from(table: string) {
      let lastValue = "";
      const builder = {
        select() {
          return builder;
        },
        eq(_col: string, value: string) {
          lastValue = value;
          return builder;
        },
        maybeSingle() {
          const row = (tables[table] ?? {})[lastValue] ?? null;
          return Promise.resolve({ data: row, error: null });
        },
      };
      return builder;
    },
  };
}

const OWNER_TABLES = {
  case_assignments: { "assign-1": { ...ASSIGNMENT_ROW } },
  relocation_cases: { "case-1": { ...CASE_ROW } },
};

Deno.test("tenant: owner company resolves the case", async () => {
  const input = await fetchAssignmentAndCase(fakeSupabase(OWNER_TABLES), "assign-1", "acme");
  assert(input !== null);
  assertEquals(input!.case.host_country, "Germany");
  // and still no PII leaked through the DB path
  for (const key of FORBIDDEN_PII_FIELDS) {
    assert(!(key in input!.assignment) && !(key in input!.case));
  }
});

Deno.test("tenant: WRONG company_id returns null (→ 404, no leak)", async () => {
  const input = await fetchAssignmentAndCase(fakeSupabase(OWNER_TABLES), "assign-1", "rival-corp");
  assertEquals(input, null);
});

Deno.test("tenant: unknown assignment id returns null (→ 404)", async () => {
  const input = await fetchAssignmentAndCase(fakeSupabase(OWNER_TABLES), "does-not-exist", "acme");
  assertEquals(input, null);
});

Deno.test("tenant: assignment with no resolvable case returns null", async () => {
  const orphan = {
    case_assignments: { "assign-x": { ...ASSIGNMENT_ROW, case_id: null, canonical_case_id: null } },
    relocation_cases: {},
  };
  const input = await fetchAssignmentAndCase(fakeSupabase(orphan), "assign-x", "acme");
  assertEquals(input, null);
});
