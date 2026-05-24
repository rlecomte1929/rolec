/**
 * support-router — Supabase Edge Function (SUPPORT-4C)
 * ─────────────────────────────────────────────────────────────────────────────
 * Receives a triaged support ticket and routes it to the correct destination:
 *
 *   auto_fix    → Creates "Ready for AI" Notion task → Dev Loop picks it up
 *   notion_task → Creates Notion AI Work Queue task (PII-scrubbed)
 *   ai_reply    → Marks ticket ai_reply_pending (SUPPORT-4D sends the reply)
 *   escalate    → Sends Postmark alert + marks ticket escalated
 *
 * Called by support-triage after successful classification.
 *
 * Body: {
 *   ticket_id: string,
 *   triage_result: { issue_category, root_cause_hypothesis, fix_difficulty, suggested_action, draft_reply },
 *   subject?: string,
 *   from_email?: string,
 *   company_id?: string,
 *   source?: "email" | "in-app"
 * }
 *
 * Environment variables:
 *   SUPABASE_URL              — auto-injected
 *   SUPABASE_SERVICE_ROLE_KEY — auto-injected
 *   NOTION_TOKEN              — Notion integration secret
 *   NOTION_DATABASE_ID        — AI Work Queue database ID
 *   POSTMARK_SERVER_TOKEN     — Postmark API token
 *   ESCALATION_EMAIL          — alert recipient (default: romain_lecomte@hotmail.com)
 *   ESCALATION_EMAIL_FROM     — sender (default: ai@relopass.com)
 * ─────────────────────────────────────────────────────────────────────────────
 */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const DIFFICULTY_TO_NOTION: Record<string, string> = {
  trivial: "Trivial", low: "Low", medium: "Medium", high: "High",
};
const CATEGORY_TO_AREA: Record<string, string> = {
  bug: "Core Product", ux_confusion: "Core Product",
  feature_request: "Core Product", billing: "Operations",
  policy_question: "Operations", other: "Core Product",
};

// ─── PII anonymisation ────────────────────────────────────────────────────────

function anonymise(text: string): string {
  if (!text) return text;
  // Email → keep domain only
  text = text.replace(/\b[A-Za-z0-9._%+\-]+@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b/g, "[*@$1]");
  // Phone numbers
  text = text.replace(/\+?[\d\s\-().]{7,15}\d/g, (m) => /\d{5,}/.test(m) ? "[phone]" : m);
  // "My name is / I'm / Regards, FirstName LastName"
  text = text.replace(
    /\b(my name is|i'm|i am|signed,?|regards,?|best,?|from,?)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b/gi,
    "$1 [user]",
  );
  return text.trim();
}

function extractDomain(email: string | null | undefined): string {
  if (!email) return "unknown company";
  const m = email.match(/@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})$/);
  return m ? m[1] : "unknown company";
}

// ─── Supabase helpers ─────────────────────────────────────────────────────────

async function supabasePatch(url: string, key: string, path: string, payload: Record<string, unknown>) {
  const res = await fetch(`${url}/rest/v1/${path}`, {
    method: "PATCH",
    headers: {
      "apikey": key, "Authorization": `Bearer ${key}`,
      "Content-Type": "application/json", "Prefer": "return=minimal",
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) console.error(`support-router: PATCH ${path} failed: ${res.status}`);
}

async function logEvent(
  url: string, key: string,
  ticketId: string, action: string, companyId: string | null,
  extra: Record<string, unknown>,
) {
  try {
    await fetch(`${url}/rest/v1/events`, {
      method: "POST",
      headers: {
        "apikey": key, "Authorization": `Bearer ${key}`,
        "Content-Type": "application/json", "Prefer": "return=minimal",
      },
      body: JSON.stringify({
        event_type: "support_ticket.routed",
        entity_type: "support_ticket",
        entity_id: ticketId,
        company_id: companyId,
        source: "support-router",
        properties: { action_taken: action, ...extra },
      }),
    });
  } catch (e) {
    console.error("support-router: logEvent failed:", e);
  }
}

// ─── Notion helpers ───────────────────────────────────────────────────────────

async function createNotionTask(
  token: string, dbId: string,
  opts: { title: string; description: string; status: string; complexity: string; taskType: string; priority: string; productArea: string },
): Promise<string | null> {
  try {
    const res = await fetch("https://api.notion.com/v1/pages", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        parent: { database_id: dbId },
        properties: {
          "Task Title": { title: [{ text: { content: opts.title } }] },
          "Status": { select: { name: opts.status } },
          "Estimated Complexity": { select: { name: opts.complexity } },
          "Task Type": { select: { name: opts.taskType } },
          "Priority": { select: { name: opts.priority } },
          "Product Area": { select: { name: opts.productArea } },
          "Assigned AI Agent": { select: { name: "Claude Code" } },
        },
        children: [{
          object: "block", type: "paragraph",
          paragraph: { rich_text: [{ type: "text", text: { content: opts.description.slice(0, 2000) } }] },
        }],
      }),
    });
    if (!res.ok) {
      console.error(`support-router: Notion create failed ${res.status}: ${await res.text()}`);
      return null;
    }
    const data = await res.json() as { id: string };
    return data.id;
  } catch (e) {
    console.error("support-router: Notion error:", e);
    return null;
  }
}

// ─── Postmark helper ──────────────────────────────────────────────────────────

async function sendEscalationEmail(
  postmarkToken: string, to: string, from: string,
  subject: string, body: string,
): Promise<boolean> {
  try {
    const res = await fetch("https://api.postmarkapp.com/email", {
      method: "POST",
      headers: {
        "Accept": "application/json", "Content-Type": "application/json",
        "X-Postmark-Server-Token": postmarkToken,
      },
      body: JSON.stringify({ From: from, To: to, Subject: subject, TextBody: body, MessageStream: "outbound" }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

// ─── Routing actions ──────────────────────────────────────────────────────────

interface TriageResult {
  issue_category: string;
  root_cause_hypothesis: string;
  fix_difficulty: string;
  suggested_action: string;
  draft_reply: string;
}

interface RouterContext {
  supabaseUrl: string; serviceKey: string;
  notionToken: string; notionDbId: string;
  postmarkToken: string; escalationTo: string; escalationFrom: string;
  ticketId: string; subject: string | null; fromEmail: string | null;
  companyId: string | null; source: string; triage: TriageResult;
}

async function handleAutoFix(ctx: RouterContext): Promise<Record<string, unknown>> {
  const domain = extractDomain(ctx.fromEmail);
  const anonContent = anonymise(ctx.triage.root_cause_hypothesis).slice(0, 500);
  const title = ctx.subject
    ? `Bug: ${anonymise(ctx.subject).slice(0, 80)}`
    : `Bug reported by user at ${domain}`;

  const notionTaskId = await createNotionTask(ctx.notionToken, ctx.notionDbId, {
    title,
    description: [
      `**Source:** Support ticket ${ctx.ticketId} (from ${domain})`,
      `**Root cause hypothesis:** ${ctx.triage.root_cause_hypothesis}`,
      `**Fix difficulty:** ${ctx.triage.fix_difficulty}`,
      `**Content summary:** ${anonContent}`,
      `**Auto-routed by SUPPORT-4C for Dev Loop**`,
    ].join("\n\n"),
    status: "Ready for AI",
    complexity: DIFFICULTY_TO_NOTION[ctx.triage.fix_difficulty] ?? "Low",
    taskType: "Bug Fix",
    priority: ["trivial","low"].includes(ctx.triage.fix_difficulty) ? "P2" : "P1",
    productArea: "Core Product",
  });

  await supabasePatch(ctx.supabaseUrl, ctx.serviceKey, `support_tickets?id=eq.${ctx.ticketId}`, { status: "triaged" });

  return { action_taken: "auto_fix", notion_task_id: notionTaskId, ticket_status: "triaged" };
}

async function handleNotionTask(ctx: RouterContext): Promise<Record<string, unknown>> {
  const domain = extractDomain(ctx.fromEmail);
  const anonContent = anonymise(ctx.triage.root_cause_hypothesis).slice(0, 600);
  const anonSubject = ctx.subject ? anonymise(ctx.subject).slice(0, 80) : undefined;
  const isFeature = ctx.triage.issue_category === "feature_request";

  const title = isFeature
    ? `Feature Request: ${anonSubject ?? "from user at " + domain}`
    : `Bug (${ctx.triage.fix_difficulty}): ${anonSubject ?? "from user at " + domain}`;

  const notionTaskId = await createNotionTask(ctx.notionToken, ctx.notionDbId, {
    title,
    description: [
      `**Source:** Support ticket ${ctx.ticketId} (user at ${domain})`,
      `**Category:** ${ctx.triage.issue_category}`,
      `**Root cause hypothesis:** ${ctx.triage.root_cause_hypothesis}`,
      `**Content summary (anonymised):** ${anonContent}`,
      `**Fix difficulty:** ${ctx.triage.fix_difficulty}`,
      `**Auto-routed by SUPPORT-4C**`,
    ].join("\n\n"),
    status: "Needs Decomposition",
    complexity: DIFFICULTY_TO_NOTION[ctx.triage.fix_difficulty] ?? "Medium",
    taskType: isFeature ? "Feature" : "Bug Fix",
    priority: ctx.triage.fix_difficulty === "high" ? "P1" : "P2",
    productArea: CATEGORY_TO_AREA[ctx.triage.issue_category] ?? "Core Product",
  });

  await supabasePatch(ctx.supabaseUrl, ctx.serviceKey, `support_tickets?id=eq.${ctx.ticketId}`, { status: "triaged" });

  return { action_taken: "notion_task", notion_task_id: notionTaskId, ticket_status: "triaged" };
}

async function handleAiReply(ctx: RouterContext): Promise<Record<string, unknown>> {
  // Stage draft reply for SUPPORT-4D to dispatch
  await supabasePatch(ctx.supabaseUrl, ctx.serviceKey, `support_tickets?id=eq.${ctx.ticketId}`, {
    status: "triaged",
    resolution_notes: ctx.triage.draft_reply,
  });
  return { action_taken: "ai_reply", ticket_status: "triaged", details: "Draft staged for SUPPORT-4D" };
}

async function handleEscalate(ctx: RouterContext): Promise<Record<string, unknown>> {
  const emailSubject = `[ESCALATION] ${ctx.triage.issue_category.toUpperCase()} ticket — ${(ctx.subject ?? ctx.ticketId).slice(0, 60)}`;
  const emailBody = [
    "A support ticket has been automatically escalated.",
    "",
    `Ticket ID : ${ctx.ticketId}`,
    `Source    : ${ctx.source}`,
    `Category  : ${ctx.triage.issue_category}`,
    `Subject   : ${ctx.subject ?? "(no subject)"}`,
    "",
    "Root cause hypothesis:",
    ctx.triage.root_cause_hypothesis,
    "",
    "Suggested draft reply:",
    ctx.triage.draft_reply,
    "",
    `Sender domain: ${extractDomain(ctx.fromEmail)}`,
    "",
    "─────────────────────────────────────────",
    "ReloPass AI Support · SUPPORT-4C",
  ].join("\n");

  let emailSent = false;
  if (ctx.postmarkToken) {
    emailSent = await sendEscalationEmail(ctx.postmarkToken, ctx.escalationTo, ctx.escalationFrom, emailSubject, emailBody);
  }

  await supabasePatch(ctx.supabaseUrl, ctx.serviceKey, `support_tickets?id=eq.${ctx.ticketId}`, { status: "escalated" });

  return {
    action_taken: "escalate",
    email_sent: emailSent,
    ticket_status: "escalated",
    details: emailSent ? `Alert sent to ${ctx.escalationTo}` : "Email skipped (no POSTMARK_SERVER_TOKEN)",
  };
}

// ─── Edge Function handler ────────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS_HEADERS });

  const supabaseUrl  = Deno.env.get("SUPABASE_URL") ?? "";
  const serviceKey   = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  const notionToken  = Deno.env.get("NOTION_TOKEN") ?? "";
  const notionDbId   = Deno.env.get("NOTION_DATABASE_ID") ?? "75d7ed78-91f4-46b6-b805-12e43abbecce";
  const postmarkToken = Deno.env.get("POSTMARK_SERVER_TOKEN") ?? "";
  const escalationTo = Deno.env.get("ESCALATION_EMAIL") ?? "romain_lecomte@hotmail.com";
  const escalationFrom = Deno.env.get("ESCALATION_EMAIL_FROM") ?? "ai@relopass.com";

  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch (e) {
    return Response.json({ ok: false, error: `Invalid JSON: ${e}` }, { status: 400, headers: CORS_HEADERS });
  }

  const ticketId = body.ticket_id as string;
  const triage = body.triage_result as TriageResult;
  if (!ticketId || !triage?.suggested_action) {
    return Response.json({ ok: false, error: "ticket_id and triage_result.suggested_action are required" }, { status: 400, headers: CORS_HEADERS });
  }

  console.log(`support-router: routing ticket=${ticketId} action=${triage.suggested_action}`);

  const ctx: RouterContext = {
    supabaseUrl, serviceKey, notionToken, notionDbId,
    postmarkToken, escalationTo, escalationFrom,
    ticketId,
    subject: (body.subject as string) ?? null,
    fromEmail: (body.from_email as string) ?? null,
    companyId: (body.company_id as string) ?? null,
    source: (body.source as string) ?? "unknown",
    triage,
  };

  try {
    let result: Record<string, unknown>;
    switch (triage.suggested_action) {
      case "auto_fix":    result = await handleAutoFix(ctx); break;
      case "notion_task": result = await handleNotionTask(ctx); break;
      case "ai_reply":    result = await handleAiReply(ctx); break;
      case "escalate":    result = await handleEscalate(ctx); break;
      default:            result = await handleAiReply(ctx); break;
    }

    await logEvent(supabaseUrl, serviceKey, ticketId, triage.suggested_action, ctx.companyId, result);

    console.log(`support-router: ticket=${ticketId} routed → ${triage.suggested_action} ✓`);
    return Response.json({ ok: true, ticket_id: ticketId, ...result }, { headers: CORS_HEADERS });

  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`support-router error: ticket=${ticketId}`, message);
    return Response.json({ ok: false, error: message }, { status: 500, headers: CORS_HEADERS });
  }
});
