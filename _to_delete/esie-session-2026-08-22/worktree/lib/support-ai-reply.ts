/**
 * support-ai-reply.ts — HUMAN-7C
 * ─────────────────────────────────────────────────────────────────────────────
 * Generates a Claude Haiku draft reply for support tickets routed to the
 * 'ai_reply' path. Drafts are stored in the support_drafts table for human
 * review before any email is sent — nothing auto-sends from this module.
 *
 * Key constraints:
 *   - Model: claude-haiku-4-5-20251001 (fast, cost-effective for drafts)
 *   - Max 150 words per draft body
 *   - No raw PII in prompts — anonymise() scrubs email/phone/names
 *   - High-priority tickets (fix_difficulty='high') always requiresHumanReview
 *   - Drafts never sent automatically — status starts as 'pending_review'
 *
 * Environment variables:
 *   ANTHROPIC_API_KEY — required; graceful fallback if missing
 *   SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY — for saveDraft()
 * ─────────────────────────────────────────────────────────────────────────────
 */

import type { TriageResult } from "./support-router";

// ─── Constants ────────────────────────────────────────────────────────────────

const HAIKU_MODEL = "claude-haiku-4-5-20251001";
const ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages";
const MAX_WORDS = 150;

// ─── Types ────────────────────────────────────────────────────────────────────

export interface SupportTicket {
  id: string;
  subject?: string | null;
  rawContent: string;
  fromEmail?: string | null;
  fromName?: string | null;
  companyId?: string | null;
  source: "email" | "in-app";
  triageResult: TriageResult;
}

export interface DraftReply {
  subject: string;
  body: string;
  requiresHumanReview: boolean;
}

export interface SavedDraft {
  id: string;
  ticketId: string;
  subject: string;
  body: string;
  requiresHumanReview: boolean;
  status: "pending_review" | "approved" | "rejected" | "sent";
  createdAt: string;
}

// ─── PII anonymisation (mirrors support-router.ts) ────────────────────────────

function anonymise(text: string): string {
  if (!text) return text;

  // Email → domain only
  text = text.replace(
    /\b[A-Za-z0-9._%+\-]+@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b/g,
    "[*@$1]",
  );

  // Phone numbers
  text = text.replace(/\+?[\d\s\-().]{7,15}\d/g, (match) => {
    if (/\d{5,}/.test(match)) return "[phone]";
    return match;
  });

  // Name patterns
  text = text.replace(
    /\b(my name is|i'm|i am|signed,?|regards,?|best,?|from,?)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b/gi,
    "$1 [user]",
  );

  return text.trim();
}

// ─── Word-count enforcer ──────────────────────────────────────────────────────

function truncateToWordLimit(text: string, limit: number): string {
  const words = text.trim().split(/\s+/);
  if (words.length <= limit) return text.trim();
  return words.slice(0, limit).join(" ") + "…";
}

// ─── High-priority detection ──────────────────────────────────────────────────

/**
 * Returns true if the ticket warrants mandatory human review before sending.
 * - fix_difficulty 'high' → always human review
 * - billing category → always human review (shouldn't reach ai_reply, but safe)
 * - ux_confusion with high difficulty → human review
 */
function isHighPriority(triageResult: TriageResult): boolean {
  return (
    triageResult.fix_difficulty === "high" ||
    triageResult.issue_category === "billing"
  );
}

// ─── Subject line builder ─────────────────────────────────────────────────────

function buildSubjectLine(
  originalSubject: string | null | undefined,
  issueCategory: string,
): string {
  const prefix = originalSubject ? `Re: ${originalSubject}` : null;

  if (prefix) return prefix;

  const subjectMap: Record<string, string> = {
    bug: "We've received your report — our team is on it",
    ux_confusion: "Re: Your question about ReloPass",
    policy_question: "Re: Your relocation policy question",
    feature_request: "Thanks for your suggestion — we've noted it",
    billing: "Your billing enquiry has been escalated",
    other: "We've received your message",
  };

  return subjectMap[issueCategory] ?? "We've received your message";
}

// ─── Haiku prompt builder ─────────────────────────────────────────────────────

function buildPrompt(ticket: SupportTicket): string {
  const anonContent = anonymise(ticket.rawContent).slice(0, 800);
  const { triageResult } = ticket;

  const categoryDescriptions: Record<string, string> = {
    bug: "a bug or technical issue",
    ux_confusion: "confusion about how to use a feature",
    policy_question: "a question about relocation policies or compliance",
    feature_request: "a feature suggestion",
    billing: "a billing or payment question",
    other: "a general enquiry",
  };

  const categoryDesc =
    categoryDescriptions[triageResult.issue_category] ?? "an enquiry";

  return [
    `You are the ReloPass support team writing a reply to a user ticket about ${categoryDesc}.`,
    ``,
    `ReloPass brand voice rules (follow strictly):`,
    `- Professional but warm — no jargon ("ping", "syncing", "looping in")`,
    `- First-person plural: "we", "our team", "we'll"`,
    `- Acknowledge the issue, state clear next steps`,
    `- Maximum ${MAX_WORDS} words — be concise`,
    `- Do NOT include a greeting line or sign-off — those are added separately`,
    `- Do NOT include any placeholder text like [name] or {{company}}`,
    ``,
    `Ticket summary (anonymised):`,
    anonContent,
    ``,
    `Triage assessment:`,
    `- Category: ${triageResult.issue_category}`,
    `- Root cause: ${triageResult.root_cause_hypothesis}`,
    `- Difficulty: ${triageResult.fix_difficulty}`,
    ``,
    `Suggested reply direction from triage AI:`,
    triageResult.draft_reply.slice(0, 300),
    ``,
    `Write only the body of the reply (no greeting, no sign-off). Stay under ${MAX_WORDS} words.`,
  ].join("\n");
}

// ─── Core: draftReply ─────────────────────────────────────────────────────────

/**
 * Generate a Claude Haiku draft reply for a support ticket.
 *
 * Falls back to the triage model's draft_reply if ANTHROPIC_API_KEY is missing
 * or the API call fails — ensuring the ai_reply path always produces a draft.
 */
export async function draftReply(
  ticket: SupportTicket,
  anthropicApiKey?: string,
): Promise<DraftReply> {
  const apiKey = anthropicApiKey ?? (
    typeof process !== "undefined"
      ? process.env.ANTHROPIC_API_KEY
      : // Deno environment
        (globalThis as unknown as { Deno?: { env: { get: (k: string) => string | undefined } } })
          .Deno?.env.get("ANTHROPIC_API_KEY")
  );

  const requiresHumanReview = isHighPriority(ticket.triageResult);
  const subject = buildSubjectLine(ticket.subject, ticket.triageResult.issue_category);

  // Fallback: use triage model's draft_reply if Haiku unavailable
  if (!apiKey) {
    console.warn("support-ai-reply: ANTHROPIC_API_KEY not set — using triage draft as fallback");
    const fallbackBody = truncateToWordLimit(
      ticket.triageResult.draft_reply || "Thank you for contacting us. Our team will be in touch shortly.",
      MAX_WORDS,
    );
    return { subject, body: fallbackBody, requiresHumanReview };
  }

  const prompt = buildPrompt(ticket);

  try {
    const res = await fetch(ANTHROPIC_API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: HAIKU_MODEL,
        max_tokens: 256,
        temperature: 0.3,
        messages: [{ role: "user", content: prompt }],
      }),
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Anthropic API ${res.status}: ${errText}`);
    }

    const data = await res.json() as {
      content?: Array<{ type: string; text?: string }>;
    };

    const rawBody = (data.content ?? [])
      .filter((b) => b.type === "text")
      .map((b) => b.text ?? "")
      .join("")
      .trim();

    const body = truncateToWordLimit(rawBody || ticket.triageResult.draft_reply, MAX_WORDS);

    return { subject, body, requiresHumanReview };

  } catch (err) {
    console.error("support-ai-reply: Haiku call failed, using triage fallback:", err);
    const body = truncateToWordLimit(
      ticket.triageResult.draft_reply ||
        "Thank you for reaching out. We've received your message and our team will be in touch shortly.",
      MAX_WORDS,
    );
    return { subject, body, requiresHumanReview };
  }
}

// ─── Persist draft to Supabase ────────────────────────────────────────────────

/**
 * Insert a draft into the support_drafts table via Supabase REST API.
 * Returns the saved draft row, or null on failure (non-fatal — logs error).
 */
export async function saveDraft(
  ticketId: string,
  draft: DraftReply,
  supabaseUrl: string,
  serviceRoleKey: string,
): Promise<SavedDraft | null> {
  try {
    const res = await fetch(`${supabaseUrl}/rest/v1/support_drafts`, {
      method: "POST",
      headers: {
        "apikey": serviceRoleKey,
        "Authorization": `Bearer ${serviceRoleKey}`,
        "Content-Type": "application/json",
        "Prefer": "return=representation",
      },
      body: JSON.stringify({
        ticket_id: ticketId,
        subject: draft.subject,
        body: draft.body,
        requires_human_review: draft.requiresHumanReview,
        status: "pending_review",
      }),
    });

    if (!res.ok) {
      const err = await res.text();
      console.error(`support-ai-reply: saveDraft failed (${res.status}): ${err}`);
      return null;
    }

    const rows = await res.json() as SavedDraft[];
    return rows[0] ?? null;
  } catch (err) {
    console.error("support-ai-reply: saveDraft error:", err);
    return null;
  }
}
