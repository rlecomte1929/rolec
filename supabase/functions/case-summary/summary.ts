/**
 * case-summary — pure summary logic (AIQ-1693).
 *
 * No imports, no I/O: field whitelists, prompt construction, the Claude call, and
 * response parsing. Kept free of the supabase-js import so `deno test` can exercise
 * it with a plain `deno test` (no --no-check, no node_modules). `index.ts` wires
 * this to the DB + HTTP handler.
 *
 * COMPLIANCE: the summary is built only from OPERATIONAL_* whitelists — structured,
 * non-PII fields. Names, emails, hr_notes, intake_draft and profile_json are never
 * included, so no raw PII leaves the platform in the LLM payload (root CLAUDE.md
 * GDPR gate). The Python mask_pii() can't run in Deno, so we avoid PII by
 * construction — same approach as pre-call-brief.
 */

// Claude Haiku — cheap + fast, sufficient for a grounded structured summary.
// Mirrors the model choice in pre-call-brief.
export const CLAUDE_MODEL = "claude-haiku-4-5-20251001";

/**
 * The only assignment columns read and passed to Claude. Every entry is a
 * structured operational value, never a personal identifier. Adding a column here
 * is a compliance decision: it must be non-PII.
 */
export const OPERATIONAL_ASSIGNMENT_FIELDS = [
  "status",
  "coordination_status",
  "risk_status",
  "budget_limit",
  "budget_estimated",
  "expected_start_date",
  "submitted_at",
  "intake_step",
  "intake_total_steps",
  "created_at",
] as const;

/** The only relocation_cases columns read and passed to Claude. Non-PII only. */
export const OPERATIONAL_CASE_FIELDS = [
  "status",
  "stage",
  "risk_status",
  "delay_reason",
  "compliance_flag",
  "budget_limit",
  "budget_estimated",
  "host_country",
  "home_country",
  "host_city",
  "home_city",
  "corridor",
  "target_start_date",
  "expected_start_date",
  "payment_status",
  "access_tier",
  "paid_amount_cents",
  "paid_currency",
] as const;

/**
 * Columns that must NEVER reach the prompt. Not selected by the query (the
 * whitelist is), but named so the test can assert none leak, and so the intent is
 * auditable.
 */
export const FORBIDDEN_PII_FIELDS = [
  "employee_first_name",
  "employee_last_name",
  "employee_identifier",
  "employee_contact_id",
  "employee_user_id",
  "hr_user_id",
  "hr_notes",
  "decision",
  "intake_draft",
  "profile_json",
] as const;

export type Row = Record<string, unknown>;

export interface SummaryInput {
  assignment: Row; // operational assignment fields only
  case: Row; // operational case fields only
}

export interface CaseSummary {
  status: string; // 1–2 sentence current status
  blockers: string[]; // active blockers (may be empty)
  next_actions: string[]; // recommended next actions
  cost_variance: string; // budget vs estimate/paid, plain language
}

/** Keep only whitelisted, non-null keys from a row (defense in depth over SELECT). */
export function pick(row: Row | null | undefined, keys: readonly string[]): Row {
  const out: Row = {};
  if (!row) return out;
  for (const k of keys) {
    if (row[k] !== undefined && row[k] !== null) out[k] = row[k];
  }
  return out;
}

/**
 * Build the exact object sent to Claude. Only operational fields; no ids, no PII.
 * Guaranteed by construction to exclude everything in FORBIDDEN_PII_FIELDS.
 */
export function buildSummaryInput(assignment: Row, caseRow: Row): SummaryInput {
  return {
    assignment: pick(assignment, OPERATIONAL_ASSIGNMENT_FIELDS),
    case: pick(caseRow, OPERATIONAL_CASE_FIELDS),
  };
}

export const SYSTEM_PROMPT = `
You are an HR case-summary assistant for ReloPass, a corporate relocation platform.
You write a concise, factual status summary of ONE relocation case for the HR manager
who owns it.

STRICT GROUNDING RULES — follow exactly:
- Use ONLY the fields in the JSON provided in the user message. Do NOT infer, assume,
  estimate, or add any fact that is not literally present in that JSON.
- If a field is missing or null, treat it as UNKNOWN. Never guess a value, a date, a
  cost, or a reason. Say "not recorded" rather than inventing one.
- The input intentionally contains NO personal identifiers. Never invent or reference a
  person's name, email, phone, address, or document details. Refer to "the employee".
- Do not recommend actions that depend on facts you were not given.

Respond with ONLY valid JSON matching this exact schema (no prose, no markdown fence):
{
  "status": "1-2 sentences describing the current stage/status of the case, grounded in the fields",
  "blockers": ["each active blocker as a short phrase; [] if none are evidenced in the fields"],
  "next_actions": ["each recommended next action as a short phrase, derived only from status/stage/dates/progress"],
  "cost_variance": "one plain-language sentence comparing budget_limit vs budget_estimated (and paid amount if present); 'not recorded' if the fields are absent"
}
`.trim();

export function buildUserMessage(input: SummaryInput): string {
  return [
    "Summarise this relocation case for its HR manager. Structured fields (the ONLY source of truth):",
    "",
    JSON.stringify(input, null, 2),
    "",
    "Return the four-section JSON. Ground every statement in the fields above; do not fabricate.",
  ].join("\n");
}

/** Robustly parse Claude's JSON reply into a CaseSummary (mirrors pre-call-brief). */
export function parseSummary(rawText: string): CaseSummary {
  const jsonMatch = rawText.match(/```(?:json)?\s*([\s\S]*?)```/) ?? rawText.match(/(\{[\s\S]*\})/);
  const jsonStr = jsonMatch ? jsonMatch[1].trim() : rawText.trim();
  let parsed: Partial<CaseSummary> = {};
  try {
    parsed = JSON.parse(jsonStr) as Partial<CaseSummary>;
  } catch {
    parsed = {};
  }
  const asStringArray = (v: unknown): string[] =>
    Array.isArray(v) ? v.map((x) => String(x)).filter((s) => s.trim().length > 0) : [];
  return {
    status: typeof parsed.status === "string" ? parsed.status : "Status not available.",
    blockers: asStringArray(parsed.blockers),
    next_actions: asStringArray(parsed.next_actions),
    cost_variance: typeof parsed.cost_variance === "string" ? parsed.cost_variance : "not recorded",
  };
}

/** Call Claude Messages API and parse the four-section summary. */
export async function generateSummary(apiKey: string, input: SummaryInput): Promise<CaseSummary> {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: CLAUDE_MODEL,
      max_tokens: 700,
      temperature: 0.1, // low — grounded factual summary, not creative
      system: SYSTEM_PROMPT,
      messages: [{ role: "user", content: buildUserMessage(input) }],
    }),
    signal: AbortSignal.timeout(15000),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Anthropic API error: ${res.status} ${err.slice(0, 300)}`);
  }

  const data = await res.json();
  const raw = (data.content ?? [])
    .filter((b: { type: string }) => b.type === "text")
    .map((b: { text: string }) => b.text)
    .join("")
    .trim();

  return parseSummary(raw);
}
