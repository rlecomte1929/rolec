/**
 * support-triage — Supabase Edge Function (SUPPORT-4B)
 * ─────────────────────────────────────────────────────────────────────────────
 * Called by a Supabase trigger (via pg_net) immediately after a row is inserted
 * into public.support_tickets.
 *
 * Pipeline:
 *   1. Receive { ticket_id } from the pg trigger
 *   2. Fetch ticket content from Supabase (service-role client)
 *   3. Optionally load Company Brain context from Notion (BRAIN-3D)
 *   4. Call Claude Sonnet for classification + draft reply
 *   5. Write triage_result back to support_tickets
 *   6. Return triage result JSON
 *
 * Environment variables (set in Supabase vault):
 *   SUPABASE_URL            — auto-injected
 *   SUPABASE_SERVICE_ROLE_KEY — auto-injected
 *   ANTHROPIC_API_KEY       — Claude API key
 *   NOTION_TOKEN            — Notion integration secret (for Company Brain)
 *   NOTION_BRAIN_PAGE       — BRAIN-3D page ID (optional, falls back to hardcoded context)
 * ─────────────────────────────────────────────────────────────────────────────
 */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const RELOPASS_FALLBACK_CONTEXT = `
ReloPass is a B2B SaaS platform that automates employee relocation for HR teams.
Core features: relocation case management, supplier marketplace, employee wizard,
policy management, AI-driven supplier matching, document handling, and multi-country
compliance support. Users are HR managers, mobility admins, and relocating employees.
Pricing is subscription-based (invoiced to companies).
`.trim();

const TRIAGE_SYSTEM = (domainContext: string) => `
You are the ReloPass support triage AI. Classify incoming support tickets and route them correctly.

ReloPass context:
${domainContext}

Classification rules:
1. issue_category: "bug" | "ux_confusion" | "policy_question" | "billing" | "feature_request" | "other"
2. fix_difficulty: "trivial" | "low" | "medium" | "high"
3. suggested_action:
   - "auto_fix"    — trivial/low bug fixable by autofix pipeline
   - "notion_task" — medium/high bug or feature request needing dev
   - "ai_reply"    — ux_confusion, policy_question, or feature_request with clear AI answer
   - "escalate"    — ALWAYS for billing; also data loss, security, legal issues
   CRITICAL: billing MUST always map to "escalate".
4. draft_reply: empathetic, professional response in ReloPass brand voice. Max 120 words.

Return ONLY valid JSON (no markdown fences):
{
  "issue_category": "...",
  "root_cause_hypothesis": "...",
  "fix_difficulty": "...",
  "suggested_action": "...",
  "draft_reply": "..."
}
`.trim();

const VALID_CATEGORIES = new Set(["bug","ux_confusion","policy_question","billing","feature_request","other"]);
const VALID_DIFFICULTIES = new Set(["trivial","low","medium","high"]);
const VALID_ACTIONS = new Set(["auto_fix","notion_task","ai_reply","escalate"]);

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function fetchTicket(supabaseUrl: string, serviceKey: string, ticketId: string) {
  const res = await fetch(
    `${supabaseUrl}/rest/v1/support_tickets?id=eq.${ticketId}&select=raw_content,subject,company_id,status`,
    {
      headers: {
        "apikey": serviceKey,
        "Authorization": `Bearer ${serviceKey}`,
        "Content-Type": "application/json",
      },
    },
  );
  if (!res.ok) throw new Error(`Supabase fetch failed: ${res.status}`);
  const rows = await res.json();
  if (!rows || rows.length === 0) throw new Error(`Ticket ${ticketId} not found`);
  return rows[0] as { raw_content: string; subject: string | null; company_id: string | null; status: string };
}

async function writeTriage(
  supabaseUrl: string,
  serviceKey: string,
  ticketId: string,
  triagedResult: Record<string, unknown>,
) {
  const res = await fetch(
    `${supabaseUrl}/rest/v1/support_tickets?id=eq.${ticketId}`,
    {
      method: "PATCH",
      headers: {
        "apikey": serviceKey,
        "Authorization": `Bearer ${serviceKey}`,
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
      },
      body: JSON.stringify({ triage_result: triagedResult, status: "triaged" }),
    },
  );
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Supabase PATCH failed: ${res.status} ${err}`);
  }
}

async function fetchCompanyBrainContext(notionToken: string, brainPageId: string): Promise<string> {
  if (!notionToken || !brainPageId) return RELOPASS_FALLBACK_CONTEXT;
  try {
    const res = await fetch(
      `https://api.notion.com/v1/blocks/${brainPageId}/children?page_size=10`,
      {
        headers: {
          "Authorization": `Bearer ${notionToken}`,
          "Notion-Version": "2022-06-28",
        },
        signal: AbortSignal.timeout(3000),
      },
    );
    if (!res.ok) return RELOPASS_FALLBACK_CONTEXT;
    const data = await res.json();
    const texts: string[] = [];
    for (const block of (data.results ?? []).slice(0, 5)) {
      const rt = block?.paragraph?.rich_text ?? block?.callout?.rich_text ?? [];
      for (const chunk of rt) texts.push(chunk?.plain_text ?? "");
    }
    const combined = texts.join(" ").trim();
    return combined.length > 100 ? combined : RELOPASS_FALLBACK_CONTEXT;
  } catch {
    return RELOPASS_FALLBACK_CONTEXT;
  }
}

async function callTriageModel(
  anthropicApiKey: string,
  content: string,
  subject: string | null,
  domainContext: string,
): Promise<Record<string, string>> {
  const userParts: string[] = [];
  if (subject) userParts.push(`Subject: ${subject}`);
  userParts.push(`\nTicket content:\n${content.slice(0, 3000)}`);

  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": anthropicApiKey,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: "claude-sonnet-4-6",
      max_tokens: 512,
      temperature: 0.1,
      system: TRIAGE_SYSTEM(domainContext),
      messages: [{ role: "user", content: userParts.join("\n") }],
    }),
    signal: AbortSignal.timeout(9000),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Anthropic API error: ${res.status} ${err}`);
  }

  const data = await res.json();
  let raw = (data.content ?? [])
    .filter((b: { type: string }) => b.type === "text")
    .map((b: { text: string }) => b.text)
    .join("")
    .trim();

  // Strip markdown fences if present
  raw = raw.replace(/^```[a-z]*\n?/, "").replace(/\n?```$/, "");

  const result = JSON.parse(raw) as Record<string, string>;

  // Validate and enforce rules
  if (!VALID_CATEGORIES.has(result.issue_category)) result.issue_category = "other";
  if (!VALID_DIFFICULTIES.has(result.fix_difficulty)) result.fix_difficulty = "medium";
  if (!VALID_ACTIONS.has(result.suggested_action)) result.suggested_action = "escalate";
  if (result.issue_category === "billing") result.suggested_action = "escalate";

  return result;
}

// ─── Edge Function handler ────────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS_HEADERS });

  const anthropicApiKey = Deno.env.get("ANTHROPIC_API_KEY");
  const supabaseUrl     = Deno.env.get("SUPABASE_URL") ?? "";
  const serviceKey      = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  const notionToken     = Deno.env.get("NOTION_TOKEN") ?? "";
  const brainPageId     = Deno.env.get("NOTION_BRAIN_PAGE") ?? "";

  if (!anthropicApiKey) {
    return Response.json({ ok: false, error: "ANTHROPIC_API_KEY is required" }, { status: 500, headers: CORS_HEADERS });
  }
  if (!supabaseUrl || !serviceKey) {
    return Response.json({ ok: false, error: "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY required" }, { status: 500, headers: CORS_HEADERS });
  }

  let ticketId: string;
  try {
    const body = await req.json();
    ticketId = body.ticket_id;
    if (!ticketId) throw new Error("ticket_id is required");
  } catch (err) {
    return Response.json({ ok: false, error: String(err) }, { status: 400, headers: CORS_HEADERS });
  }

  console.log(`support-triage: starting triage for ticket=${ticketId}`);

  try {
    // 1. Fetch ticket
    const ticket = await fetchTicket(supabaseUrl, serviceKey, ticketId);

    if (!ticket.raw_content) {
      return Response.json({ ok: false, error: "Ticket has no content" }, { status: 422, headers: CORS_HEADERS });
    }

    // Already triaged — idempotent skip
    if (ticket.status === "triaged") {
      console.log(`support-triage: ticket=${ticketId} already triaged — skipping`);
      return Response.json({ ok: true, skipped: true, reason: "already_triaged" }, { headers: CORS_HEADERS });
    }

    // 2. Load Company Brain context
    const domainContext = await fetchCompanyBrainContext(notionToken, brainPageId);
    const brainSource = domainContext === RELOPASS_FALLBACK_CONTEXT ? "fallback" : "brain";
    console.log(`support-triage: domain context source=${brainSource}`);

    // 3. Call Claude Sonnet
    const result = await callTriageModel(anthropicApiKey, ticket.raw_content, ticket.subject, domainContext);
    console.log(`support-triage: ticket=${ticketId} category=${result.issue_category} action=${result.suggested_action}`);

    // 4. Write back
    await writeTriage(supabaseUrl, serviceKey, ticketId, result);

    console.log(`support-triage: ticket=${ticketId} triage_result written ✓`);
    return Response.json({
      ok: true,
      ticket_id: ticketId,
      issue_category: result.issue_category,
      suggested_action: result.suggested_action,
      fix_difficulty: result.fix_difficulty,
      brain_source: brainSource,
    }, { headers: CORS_HEADERS });

  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`support-triage error: ticket=${ticketId}`, message);
    return Response.json({ ok: false, error: message }, { status: 500, headers: CORS_HEADERS });
  }
});
