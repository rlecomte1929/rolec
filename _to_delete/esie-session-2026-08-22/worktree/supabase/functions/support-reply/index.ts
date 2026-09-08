/**
 * support-reply — Supabase Edge Function (SUPPORT-4D)
 * ─────────────────────────────────────────────────────────────────────────────
 * Selects the correct brand-voice template for a triaged support ticket,
 * personalises it with the AI-generated draft_reply, validates tone,
 * sends via Postmark, and marks the ticket as 'resolved'.
 *
 * Called by support-router when suggested_action is 'ai_reply'.
 * Also callable directly with a full payload for each of the 5 categories.
 *
 * Body: {
 *   ticket_id: string,
 *   to_email?: string,        // if omitted, fetched from support_tickets row
 *   draft_reply?: string,     // if omitted, taken from triage_result.draft_reply
 *   issue_category?: string,
 *   suggested_action?: string,
 *   original_subject?: string,
 *   recipient_name?: string,
 * }
 *
 * Environment variables:
 *   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY — auto-injected
 *   POSTMARK_SERVER_TOKEN — Postmark API token
 *   SUPPORT_EMAIL_FROM    — sender (default: support@relopass.com)
 * ─────────────────────────────────────────────────────────────────────────────
 */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const SUPPORT_FROM_DEFAULT = "support@relopass.com";

const TEMPLATE_SUBJECTS: Record<string, string> = {
  bug_acknowledged:       "We've received your report — our team is on it",
  policy_question:        "Re: Your relocation policy question",
  feature_noted:          "Thanks for your suggestion — we've noted it",
  billing_escalated:      "Your billing enquiry has been escalated",
  general_acknowledgment: "We've received your message",
};

const TEMPLATE_CLOSINGS: Record<string, string> = {
  bug_acknowledged:       "We’ll keep you updated as we make progress. You don’t need to take any action.",
  policy_question:        "If you have any follow-up questions, simply reply to this email and we’ll be happy to help.",
  feature_noted:          "We share all product suggestions with our team and take them seriously when planning new features.",
  billing_escalated:      "Our team will be in touch within one business day with a full response.",
  general_acknowledgment: "We aim to respond to all enquiries within one business day.",
};

// ─── Category selection ───────────────────────────────────────────────────────

function selectCategory(issueCategory: string, suggestedAction: string): string {
  if (suggestedAction === "escalate" || issueCategory === "billing") return "billing_escalated";
  if (issueCategory === "feature_request") return "feature_noted";
  if (issueCategory === "policy_question") return "policy_question";
  if (issueCategory === "bug" || issueCategory === "ux_confusion") return "bug_acknowledged";
  return "general_acknowledgment";
}

// ─── Brand voice validator ────────────────────────────────────────────────────

function validateBrandVoice(text: string): { passed: boolean; issues: string[]; sanitised: string } {
  const issues: string[] = [];
  let sanitised = text.trim();

  // Unfilled placeholders
  if (/\{\{[^}]+\}\}/.test(sanitised) || /\[PLACEHOLDER\]/i.test(sanitised)) {
    issues.push("Contains unfilled placeholder text");
    sanitised = sanitised.replace(/\{\{[^}]+\}\}/g, "").replace(/\[PLACEHOLDER\]/gi, "").trim();
  }

  // Jargon
  const JARGON = ["ping me", "syncing", "looping in", "circling back", "touch base"];
  for (const j of JARGON) {
    if (sanitised.toLowerCase().includes(j)) issues.push(`Contains informal jargon: "${j}"`);
  }

  // First-person plural
  if (sanitised.length > 50 && !/\bwe\b|\bour\b/i.test(sanitised)) {
    issues.push("Missing first-person plural voice (we/our)");
  }

  // Length
  const wordCount = sanitised.split(/\s+/).filter(Boolean).length;
  if (wordCount < 15) issues.push(`Reply too short (${wordCount} words)`);
  if (wordCount > 200) issues.push(`Reply too long (${wordCount} words)`);

  // All-caps
  if (/\b[A-Z]{4,}\b/.test(sanitised)) {
    issues.push("Contains all-caps words");
    sanitised = sanitised.replace(/\b([A-Z]{4,})\b/g, (m) => m[0] + m.slice(1).toLowerCase());
  }

  return { passed: issues.length === 0, issues, sanitised };
}

// ─── Email builder ────────────────────────────────────────────────────────────

function buildEmailBody(category: string, greeting: string, contextNote: string, body: string): string {
  const closing = TEMPLATE_CLOSINGS[category] ?? TEMPLATE_CLOSINGS.general_acknowledgment;
  const parts = [greeting, contextNote ? `\n${contextNote}` : "", `\n${body}`, "", closing, "", "Best regards,", "The ReloPass Team", SUPPORT_FROM_DEFAULT];
  return parts.filter((p) => p !== null).join("\n");
}

// ─── Supabase helpers ─────────────────────────────────────────────────────────

async function fetchTicketForReply(supabaseUrl: string, serviceKey: string, ticketId: string) {
  const res = await fetch(
    `${supabaseUrl}/rest/v1/support_tickets?id=eq.${ticketId}&select=from_email,from_name,subject,triage_result,source,status`,
    { headers: { "apikey": serviceKey, "Authorization": `Bearer ${serviceKey}`, "Content-Type": "application/json" } },
  );
  if (!res.ok) throw new Error(`Supabase fetch failed: ${res.status}`);
  const rows = await res.json();
  if (!rows || rows.length === 0) throw new Error(`Ticket ${ticketId} not found`);
  return rows[0] as { from_email: string|null; from_name: string|null; subject: string|null; triage_result: Record<string,string>|null; source: string; status: string };
}

async function markTicketReplied(supabaseUrl: string, serviceKey: string, ticketId: string, notes: string) {
  await fetch(`${supabaseUrl}/rest/v1/support_tickets?id=eq.${ticketId}`, {
    method: "PATCH",
    headers: { "apikey": serviceKey, "Authorization": `Bearer ${serviceKey}`, "Content-Type": "application/json", "Prefer": "return=minimal" },
    body: JSON.stringify({ status: "resolved", resolution_notes: notes }),
  });
}

async function logEvent(supabaseUrl: string, serviceKey: string, ticketId: string, category: string, passed: boolean, pmId: string) {
  try {
    await fetch(`${supabaseUrl}/rest/v1/events`, {
      method: "POST",
      headers: { "apikey": serviceKey, "Authorization": `Bearer ${serviceKey}`, "Content-Type": "application/json", "Prefer": "return=minimal" },
      body: JSON.stringify({
        event_type: "support_ticket.replied", entity_type: "support_ticket",
        entity_id: ticketId, source: "support-reply",
        properties: { category, brand_voice_passed: passed, postmark_message_id: pmId },
      }),
    });
  } catch (e) { console.error("support-reply: logEvent failed:", e); }
}

// ─── Postmark send ────────────────────────────────────────────────────────────

async function sendPostmarkEmail(token: string, to: string, from: string, replyTo: string, subject: string, textBody: string): Promise<string> {
  const res = await fetch("https://api.postmarkapp.com/email", {
    method: "POST",
    headers: { "Accept": "application/json", "Content-Type": "application/json", "X-Postmark-Server-Token": token },
    body: JSON.stringify({ From: from, To: to, ReplyTo: replyTo, Subject: subject, TextBody: textBody, MessageStream: "outbound" }),
    signal: AbortSignal.timeout(8000),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Postmark send failed: ${res.status} ${err}`);
  }
  const data = await res.json() as { MessageID?: string };
  return data.MessageID ?? "unknown";
}

// ─── Edge Function handler ────────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS_HEADERS });

  const supabaseUrl  = Deno.env.get("SUPABASE_URL") ?? "";
  const serviceKey   = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  const postmarkToken = Deno.env.get("POSTMARK_SERVER_TOKEN") ?? "";
  const supportFrom  = Deno.env.get("SUPPORT_EMAIL_FROM") ?? SUPPORT_FROM_DEFAULT;

  if (!supabaseUrl || !serviceKey) {
    return Response.json({ ok: false, error: "SUPABASE credentials required" }, { status: 500, headers: CORS_HEADERS });
  }
  if (!postmarkToken) {
    return Response.json({ ok: false, error: "POSTMARK_SERVER_TOKEN required" }, { status: 500, headers: CORS_HEADERS });
  }

  let payload: Record<string, unknown>;
  try { payload = await req.json(); } catch (e) {
    return Response.json({ ok: false, error: String(e) }, { status: 400, headers: CORS_HEADERS });
  }

  const ticketId = payload.ticket_id as string;
  if (!ticketId) return Response.json({ ok: false, error: "ticket_id is required" }, { status: 400, headers: CORS_HEADERS });

  console.log(`support-reply: processing ticket=${ticketId}`);

  try {
    let toEmail = payload.to_email as string | null ?? null;
    let draftReply = payload.draft_reply as string | null ?? null;
    let issueCategory = (payload.issue_category as string) ?? "other";
    let suggestedAction = (payload.suggested_action as string) ?? "ai_reply";
    let originalSubject = payload.original_subject as string | null ?? null;
    let recipientName = payload.recipient_name as string | null ?? null;

    // Load missing fields from DB
    if (!toEmail || !draftReply) {
      const ticket = await fetchTicketForReply(supabaseUrl, serviceKey, ticketId);
      toEmail = toEmail ?? ticket.from_email;
      recipientName = recipientName ?? ticket.from_name;
      originalSubject = originalSubject ?? ticket.subject;
      const triage = ticket.triage_result ?? {};
      draftReply = draftReply ?? triage.draft_reply ?? "";
      issueCategory = issueCategory !== "other" ? issueCategory : (triage.issue_category ?? "other");
      suggestedAction = suggestedAction !== "ai_reply" ? suggestedAction : (triage.suggested_action ?? "ai_reply");
    }

    if (!toEmail) return Response.json({ ok: false, error: "No recipient email available" }, { status: 422, headers: CORS_HEADERS });
    if (!draftReply) return Response.json({ ok: false, error: "No draft reply content available" }, { status: 422, headers: CORS_HEADERS });

    const category = selectCategory(issueCategory, suggestedAction);
    const { sanitised, passed, issues } = validateBrandVoice(draftReply);
    if (!passed) console.warn(`support-reply: brand voice issues for ${ticketId}:`, issues.join("; "));

    const greeting = (recipientName && recipientName !== "[user]") ? `Hi ${recipientName},` : "Hello,";
    const contextNote = originalSubject ? `Re: ${originalSubject}` : "";
    const subjectLine = originalSubject ? `Re: ${originalSubject}` : (TEMPLATE_SUBJECTS[category] ?? TEMPLATE_SUBJECTS.general_acknowledgment);
    const textBody = buildEmailBody(category, greeting, contextNote, sanitised);

    const pmMessageId = await sendPostmarkEmail(postmarkToken, toEmail, supportFrom, supportFrom, subjectLine, textBody);
    console.log(`support-reply: sent ticket=${ticketId} category=${category} postmark_id=${pmMessageId}`);

    await markTicketReplied(supabaseUrl, serviceKey, ticketId, `Auto-reply sent [${category}]. Postmark ID: ${pmMessageId}`);
    await logEvent(supabaseUrl, serviceKey, ticketId, category, passed, pmMessageId);

    return Response.json({
      ok: true, ticket_id: ticketId, category, to: toEmail,
      subject: subjectLine, brand_voice_passed: passed, brand_voice_issues: issues,
      postmark_message_id: pmMessageId,
    }, { headers: CORS_HEADERS });

  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`support-reply error: ticket=${ticketId}`, message);
    return Response.json({ ok: false, error: message }, { status: 500, headers: CORS_HEADERS });
  }
});
