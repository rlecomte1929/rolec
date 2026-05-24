/**
 * support-router.ts — SUPPORT-4C
 * ─────────────────────────────────────────────────────────────────────────────
 * Reads triage_result.suggested_action and routes a support ticket to the
 * correct destination:
 *
 *   auto_fix    → Create "Ready for AI" Notion task → Dev Loop picks it up
 *   notion_task → Create Notion AI Work Queue task (PII-scrubbed)
 *   ai_reply    → Mark ticket ai_reply_pending (SUPPORT-4D handles the reply)
 *   escalate    → Send Postmark alert email + mark ticket escalated
 *
 * All routing decisions are logged to the Supabase events table.
 *
 * Usage:
 *   const router = new SupportRouter(config);
 *   const result = await router.route(input);
 *
 * Config environment variables:
 *   SUPABASE_URL              — Supabase project URL
 *   SUPABASE_SERVICE_ROLE_KEY — service-role key (bypasses RLS)
 *   NOTION_TOKEN              — Notion integration secret
 *   NOTION_DATABASE_ID        — AI Work Queue database ID
 *   POSTMARK_SERVER_TOKEN     — Postmark API token (for escalation emails)
 *   ESCALATION_EMAIL          — recipient for escalation alerts (default: romain_lecomte@hotmail.com)
 *   ESCALATION_EMAIL_FROM     — sender (default: ai@relopass.com)
 * ─────────────────────────────────────────────────────────────────────────────
 */

// HUMAN-7C: AI draft generation + persistence
import { draftReply, saveDraft } from "./support-ai-reply";

export interface TriageResult {
  issue_category: "bug" | "ux_confusion" | "policy_question" | "billing" | "feature_request" | "other";
  root_cause_hypothesis: string;
  fix_difficulty: "trivial" | "low" | "medium" | "high";
  suggested_action: "auto_fix" | "notion_task" | "ai_reply" | "escalate";
  draft_reply: string;
}

export interface RouterInput {
  ticketId: string;
  subject?: string | null;
  rawContent: string;
  fromEmail?: string | null;
  fromName?: string | null;
  companyId?: string | null;
  userId?: string | null;
  source: "email" | "in-app";
  triageResult: TriageResult;
}

export interface RouterOutput {
  action_taken: "auto_fix" | "notion_task" | "ai_reply" | "escalate";
  notion_task_id?: string;
  email_sent?: boolean;
  draft_id?: string;
  requires_human_review?: boolean;
  ticket_status: string;
  details?: string;
}

export interface RouterConfig {
  supabaseUrl: string;
  serviceRoleKey: string;
  notionToken: string;
  notionDatabaseId: string;
  postmarkToken?: string;
  escalationEmailTo?: string;
  escalationEmailFrom?: string;
  anthropicApiKey?: string;   // HUMAN-7C: forwarded to support-ai-reply
}

// ─── PII anonymisation ────────────────────────────────────────────────────────

/** Scrub raw user content of PII before writing to Notion or logs. */
export function anonymise(text: string): string {
  if (!text) return text;

  // Email: keep only the domain → user@company.com → [*@company.com]
  text = text.replace(/\b[A-Za-z0-9._%+\-]+@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b/g, "[*@$1]");

  // Phone numbers (international and local formats)
  text = text.replace(/\+?[\d\s\-().]{7,15}\d/g, (match) => {
    if (/\d{5,}/.test(match)) return "[phone]";
    return match;
  });

  // Common name patterns: "My name is John Smith" / "I'm Alice Dupont"
  text = text.replace(/\b(my name is|i'm|i am|signed,?|regards,?|best,?|from,?)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b/gi,
    "$1 [user]");

  return text.trim();
}

/** Extract company domain from email for Notion task context */
export function extractDomain(email: string | null | undefined): string {
  if (!email) return "unknown company";
  const m = email.match(/@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})$/);
  return m ? m[1] : "unknown company";
}

// ─── Complexity mapping ───────────────────────────────────────────────────────

const DIFFICULTY_TO_NOTION: Record<string, string> = {
  trivial: "Trivial",
  low: "Low",
  medium: "Medium",
  high: "High",
};

const CATEGORY_TO_AREA: Record<string, string> = {
  bug: "Core Product",
  ux_confusion: "Core Product",
  feature_request: "Core Product",
  billing: "Operations",
  policy_question: "Operations",
  other: "Core Product",
};

// ─── SupportRouter ────────────────────────────────────────────────────────────

export class SupportRouter {
  private cfg: RouterConfig;

  constructor(cfg: RouterConfig) {
    this.cfg = cfg;
  }

  async route(input: RouterInput): Promise<RouterOutput> {
    const { triageResult, ticketId } = input;
    const action = triageResult.suggested_action;

    let output: RouterOutput;

    switch (action) {
      case "auto_fix":
        output = await this._routeAutoFix(input);
        break;
      case "notion_task":
        output = await this._routeNotionTask(input);
        break;
      case "ai_reply":
        output = await this._routeAiReply(input);
        break;
      case "escalate":
        output = await this._routeEscalate(input);
        break;
      default:
        output = await this._routeAiReply(input); // safe fallback
        break;
    }

    // Log routing decision to Supabase events table
    await this._logEvent(ticketId, action, input.companyId ?? null, output);

    return output;
  }

  // ── auto_fix: create a "Ready for AI" Notion task for the Dev Loop ──────────

  private async _routeAutoFix(input: RouterInput): Promise<RouterOutput> {
    const { triageResult, ticketId, fromEmail, subject } = input;
    const domain = extractDomain(fromEmail);
    const anonContent = anonymise(input.rawContent).slice(0, 500);
    const bugTitle = subject
      ? `Bug: ${anonymise(subject).slice(0, 80)}`
      : `Bug reported by user at ${domain}`;

    const notionTaskId = await this._createNotionTask({
      title: bugTitle,
      description: [
        `**Source:** Support ticket ${ticketId} (from ${domain})`,
        `**Root cause hypothesis:** ${triageResult.root_cause_hypothesis}`,
        `**User report (anonymised):** ${anonContent}`,
        `**Fix difficulty:** ${triageResult.fix_difficulty}`,
        `**Auto-routed by SUPPORT-4C for Dev Loop**`,
      ].join("\n\n"),
      status: "Ready for AI",
      complexity: DIFFICULTY_TO_NOTION[triageResult.fix_difficulty] ?? "Low",
      taskType: "Bug Fix",
      priority: triageResult.fix_difficulty === "trivial" || triageResult.fix_difficulty === "low" ? "P2" : "P1",
      productArea: "Core Product",
    });

    await this._updateTicketStatus(input.ticketId, "triaged");

    return {
      action_taken: "auto_fix",
      notion_task_id: notionTaskId ?? undefined,
      ticket_status: "triaged",
      details: `Notion task created for Dev Loop: ${notionTaskId ?? "unknown"}`,
    };
  }

  // ── notion_task: create a Notion AI Work Queue task (anonymised) ─────────────

  private async _routeNotionTask(input: RouterInput): Promise<RouterOutput> {
    const { triageResult, ticketId, fromEmail, subject } = input;
    const domain = extractDomain(fromEmail);
    const anonContent = anonymise(input.rawContent).slice(0, 600);
    const anonSubject = subject ? anonymise(subject).slice(0, 80) : undefined;

    const title = triageResult.issue_category === "feature_request"
      ? `Feature Request: ${anonSubject ?? "from user at " + domain}`
      : `Bug (${triageResult.fix_difficulty}): ${anonSubject ?? "from user at " + domain}`;

    const notionTaskId = await this._createNotionTask({
      title,
      description: [
        `**Source:** Support ticket ${ticketId} (user at ${domain})`,
        `**Category:** ${triageResult.issue_category}`,
        `**Root cause hypothesis:** ${triageResult.root_cause_hypothesis}`,
        `**User report (anonymised):** ${anonContent}`,
        `**Fix difficulty:** ${triageResult.fix_difficulty}`,
        `**Auto-routed by SUPPORT-4C**`,
      ].join("\n\n"),
      status: "Needs Decomposition",
      complexity: DIFFICULTY_TO_NOTION[triageResult.fix_difficulty] ?? "Medium",
      taskType: triageResult.issue_category === "feature_request" ? "Feature" : "Bug Fix",
      priority: triageResult.fix_difficulty === "high" ? "P1" : "P2",
      productArea: CATEGORY_TO_AREA[triageResult.issue_category] ?? "Core Product",
    });

    await this._updateTicketStatus(ticketId, "triaged");

    return {
      action_taken: "notion_task",
      notion_task_id: notionTaskId ?? undefined,
      ticket_status: "triaged",
      details: `Notion task created: ${notionTaskId ?? "unknown"}`,
    };
  }

  // ── ai_reply: generate Haiku draft + save to support_drafts (HUMAN-7C) ──────

  private async _routeAiReply(input: RouterInput): Promise<RouterOutput> {
    // 1. Generate a Claude Haiku draft (PII-safe, ≤150 words)
    const draft = await draftReply(
      {
        id: input.ticketId,
        subject: input.subject,
        rawContent: input.rawContent,
        fromEmail: input.fromEmail,
        fromName: input.fromName,
        companyId: input.companyId,
        source: input.source,
        triageResult: input.triageResult,
      },
      this.cfg.anthropicApiKey,
    );

    // 2. Persist draft to support_drafts (status: pending_review — never auto-sends)
    const saved = await saveDraft(
      input.ticketId,
      draft,
      this.cfg.supabaseUrl,
      this.cfg.serviceRoleKey,
    );

    // 3. Update ticket status to ai_reply_pending so SUPPORT-4D knows a draft
    //    is waiting for human approval
    await this._updateTicketStatus(input.ticketId, "triaged");
    await this._supabasePatch(`support_tickets?id=eq.${input.ticketId}`, {
      resolution_notes: saved
        ? `AI draft created (id=${saved.id}; requires_human_review=${draft.requiresHumanReview})`
        : `AI draft generated but not persisted; triage draft: ${input.triageResult.draft_reply.slice(0, 200)}`,
    });

    return {
      action_taken: "ai_reply",
      draft_id: saved?.id,
      requires_human_review: draft.requiresHumanReview,
      ticket_status: "triaged",
      details: saved
        ? `Draft saved (id=${saved.id}; requires_human_review=${draft.requiresHumanReview})`
        : "Draft generated but save failed — see resolution_notes",
    };
  }

  // ── escalate: send immediate email alert + mark ticket escalated ─────────────

  private async _routeEscalate(input: RouterInput): Promise<RouterOutput> {
    const { triageResult, ticketId, fromEmail, subject, source } = input;
    const to = this.cfg.escalationEmailTo ?? "romain_lecomte@hotmail.com";
    const from = this.cfg.escalationEmailFrom ?? "ai@relopass.com";

    const emailSubject = `[ESCALATION] ${triageResult.issue_category.toUpperCase()} ticket — ${subject?.slice(0, 60) ?? ticketId}`;
    const body = [
      `A support ticket has been automatically escalated.`,
      ``,
      `Ticket ID : ${ticketId}`,
      `Source    : ${source}`,
      `Category  : ${triageResult.issue_category}`,
      `Subject   : ${subject ?? "(no subject)"}`,
      ``,
      `Root cause hypothesis:`,
      triageResult.root_cause_hypothesis,
      ``,
      `Suggested draft reply:`,
      triageResult.draft_reply,
      ``,
      `Sender domain: ${extractDomain(fromEmail)}`,
      ``,
      `─────────────────────────────────────────`,
      `ReloPass AI Support · SUPPORT-4C`,
    ].join("\n");

    let emailSent = false;
    if (this.cfg.postmarkToken) {
      emailSent = await this._sendPostmarkEmail(to, from, emailSubject, body);
    }

    await this._updateTicketStatus(ticketId, "escalated");

    return {
      action_taken: "escalate",
      email_sent: emailSent,
      ticket_status: "escalated",
      details: emailSent ? `Alert sent to ${to}` : "Email skipped (no POSTMARK_SERVER_TOKEN)",
    };
  }

  // ─── Notion helpers ──────────────────────────────────────────────────────────

  private async _createNotionTask(opts: {
    title: string;
    description: string;
    status: string;
    complexity: string;
    taskType: string;
    priority: string;
    productArea: string;
  }): Promise<string | null> {
    try {
      const body = {
        parent: { database_id: this.cfg.notionDatabaseId },
        properties: {
          "Task Title": { title: [{ text: { content: opts.title } }] },
          "Status": { select: { name: opts.status } },
          "Estimated Complexity": { select: { name: opts.complexity } },
          "Task Type": { select: { name: opts.taskType } },
          "Priority": { select: { name: opts.priority } },
          "Product Area": { select: { name: opts.productArea } },
          "Assigned AI Agent": { select: { name: "Claude Code" } },
        },
        children: [
          {
            object: "block",
            type: "paragraph",
            paragraph: {
              rich_text: [{ type: "text", text: { content: opts.description.slice(0, 2000) } }],
            },
          },
        ],
      };

      const res = await fetch("https://api.notion.com/v1/pages", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${this.cfg.notionToken}`,
          "Notion-Version": "2022-06-28",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.text();
        console.error(`support-router: Notion task creation failed: ${res.status} ${err}`);
        return null;
      }

      const data = await res.json();
      return (data as { id: string }).id;
    } catch (err) {
      console.error("support-router: Notion create error:", err);
      return null;
    }
  }

  // ─── Supabase helpers ────────────────────────────────────────────────────────

  private async _supabasePatch(path: string, payload: Record<string, unknown>): Promise<void> {
    const res = await fetch(`${this.cfg.supabaseUrl}/rest/v1/${path}`, {
      method: "PATCH",
      headers: {
        "apikey": this.cfg.serviceRoleKey,
        "Authorization": `Bearer ${this.cfg.serviceRoleKey}`,
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.text();
      console.error(`support-router: Supabase PATCH ${path} failed: ${res.status} ${err}`);
    }
  }

  private async _updateTicketStatus(ticketId: string, status: string): Promise<void> {
    await this._supabasePatch(`support_tickets?id=eq.${ticketId}`, { status });
  }

  private async _logEvent(
    ticketId: string,
    action: string,
    companyId: string | null,
    output: RouterOutput,
  ): Promise<void> {
    try {
      await fetch(`${this.cfg.supabaseUrl}/rest/v1/events`, {
        method: "POST",
        headers: {
          "apikey": this.cfg.serviceRoleKey,
          "Authorization": `Bearer ${this.cfg.serviceRoleKey}`,
          "Content-Type": "application/json",
          "Prefer": "return=minimal",
        },
        body: JSON.stringify({
          event_type: "support_ticket.routed",
          entity_type: "support_ticket",
          entity_id: ticketId,
          company_id: companyId,
          source: "support-router",
          properties: {
            action_taken: action,
            notion_task_id: output.notion_task_id ?? null,
            email_sent: output.email_sent ?? null,
            ticket_status: output.ticket_status,
          },
        }),
      });
    } catch (err) {
      console.error("support-router: events log failed:", err);
    }
  }

  // ─── Postmark helper ─────────────────────────────────────────────────────────

  private async _sendPostmarkEmail(
    to: string,
    from: string,
    subject: string,
    textBody: string,
  ): Promise<boolean> {
    try {
      const res = await fetch("https://api.postmarkapp.com/email", {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
          "X-Postmark-Server-Token": this.cfg.postmarkToken!,
        },
        body: JSON.stringify({
          From: from,
          To: to,
          Subject: subject,
          TextBody: textBody,
          MessageStream: "outbound",
        }),
      });
      if (!res.ok) {
        const err = await res.text();
        console.error(`support-router: Postmark send failed: ${res.status} ${err}`);
        return false;
      }
      return true;
    } catch (err) {
      console.error("support-router: Postmark error:", err);
      return false;
    }
  }
}

// ─── Factory helper ───────────────────────────────────────────────────────────

export function createRouterFromEnv(): SupportRouter {
  return new SupportRouter({
    supabaseUrl: process.env.SUPABASE_URL ?? "",
    serviceRoleKey: process.env.SUPABASE_SERVICE_ROLE_KEY ?? "",
    notionToken: process.env.NOTION_TOKEN ?? "",
    notionDatabaseId: process.env.NOTION_DATABASE_ID ?? "75d7ed78-91f4-46b6-b805-12e43abbecce",
    postmarkToken: process.env.POSTMARK_SERVER_TOKEN,
    escalationEmailTo: process.env.ESCALATION_EMAIL ?? "romain_lecomte@hotmail.com",
    escalationEmailFrom: process.env.ESCALATION_EMAIL_FROM ?? "ai@relopass.com",
    anthropicApiKey: process.env.ANTHROPIC_API_KEY,  // HUMAN-7C
  });
}
