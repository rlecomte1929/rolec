/**
 * support-templates.ts — SUPPORT-4D
 * ─────────────────────────────────────────────────────────────────────────────
 * Five brand-voice email templates for automated support replies.
 * Each template wraps the AI-generated draft_reply from the triage model
 * with a consistent, on-brand structure.
 *
 * Categories:
 *   bug_acknowledged       — bug / ux_confusion with auto_fix or notion_task action
 *   policy_question        — policy_question category → AI-generated answer
 *   feature_noted          — feature_request category
 *   billing_escalated      — billing category (escalate action)
 *   general_acknowledgment — other / fallback
 *
 * ReloPass brand voice rules:
 *   ✓ Professional but warm
 *   ✓ First-person plural ("we", "our team")
 *   ✓ No jargon ("ping", "syncing", "looping in")
 *   ✓ Clear next steps
 *   ✓ Signed "The ReloPass Team"
 * ─────────────────────────────────────────────────────────────────────────────
 */

export type TemplateCategory =
  | "bug_acknowledged"
  | "policy_question"
  | "feature_noted"
  | "billing_escalated"
  | "general_acknowledgment";

export interface TemplateInput {
  category: TemplateCategory;
  /** Subject of the original ticket */
  originalSubject?: string | null;
  /** AI-generated personalised draft from triage model */
  draftReply: string;
  /** Recipient name or role fallback */
  recipientName?: string | null;
  /** Company domain for sign-off context */
  companyDomain?: string | null;
}

export interface RenderedTemplate {
  subject: string;
  textBody: string;
  htmlBody: string;
  /** Human-readable category label */
  categoryLabel: string;
}

// ─── Subject line templates ───────────────────────────────────────────────────

const SUBJECT_TEMPLATES: Record<TemplateCategory, string> = {
  bug_acknowledged:       "We've received your report — our team is on it",
  policy_question:        "Re: Your relocation policy question",
  feature_noted:          "Thanks for your suggestion — we've noted it",
  billing_escalated:      "Your billing enquiry has been escalated",
  general_acknowledgment: "We've received your message",
};

const CATEGORY_LABELS: Record<TemplateCategory, string> = {
  bug_acknowledged:       "Bug / Issue Reported",
  policy_question:        "Policy Question",
  feature_noted:          "Feature Request Noted",
  billing_escalated:      "Billing — Escalated",
  general_acknowledgment: "General Acknowledgment",
};

// ─── Opening lines ────────────────────────────────────────────────────────────

function openingLine(name: string | null | undefined): string {
  const greeting = name && name !== "[user]" ? `Hi ${name},` : "Hello,";
  return greeting;
}

// ─── Brand voice validator ────────────────────────────────────────────────────

export interface BrandVoiceResult {
  passed: boolean;
  issues: string[];
  sanitised: string;
}

/**
 * Inline brand-voice check (mirrors relopass-brand-voice skill rules).
 * Returns sanitised text and a list of any issues found.
 */
export function validateBrandVoice(text: string): BrandVoiceResult {
  const issues: string[] = [];
  let sanitised = text.trim();

  // 1. No unfilled placeholders
  if (/\{\{[^}]+\}\}/.test(sanitised) || /\[PLACEHOLDER\]/i.test(sanitised)) {
    issues.push("Contains unfilled placeholder text");
    sanitised = sanitised.replace(/\{\{[^}]+\}\}/g, "").replace(/\[PLACEHOLDER\]/gi, "").trim();
  }

  // 2. No informal jargon
  const JARGON = ["ping me", "syncing", "looping in", "circling back", "touch base", "reach out to us"];
  for (const jargon of JARGON) {
    if (sanitised.toLowerCase().includes(jargon)) {
      issues.push(`Contains informal jargon: "${jargon}"`);
      // Light fix: replace common offenders
      sanitised = sanitised.replace(new RegExp(jargon, "gi"), jargon === "reach out to us" ? "contact us" : "get in touch");
    }
  }

  // 3. Must use first-person plural at least once in responses longer than 50 chars
  if (sanitised.length > 50 && !/\bwe\b|\bour\b|\bour team\b/i.test(sanitised)) {
    issues.push("Missing first-person plural voice (we/our)");
  }

  // 4. Length check: not too short, not too long
  const wordCount = sanitised.split(/\s+/).filter(Boolean).length;
  if (wordCount < 15) issues.push(`Reply too short (${wordCount} words; minimum 15)`);
  if (wordCount > 200) issues.push(`Reply too long (${wordCount} words; maximum 200)`);

  // 5. No all-caps words (shouting)
  if (/\b[A-Z]{4,}\b/.test(sanitised)) {
    issues.push("Contains all-caps words (unprofessional tone)");
    sanitised = sanitised.replace(/\b([A-Z]{4,})\b/g, (m) => m.charAt(0) + m.slice(1).toLowerCase());
  }

  return { passed: issues.length === 0, issues, sanitised };
}

// ─── Template renderer ────────────────────────────────────────────────────────

export function renderTemplate(input: TemplateInput): RenderedTemplate {
  const { category, originalSubject, draftReply, recipientName, companyDomain } = input;

  // Validate and sanitise draft
  const { sanitised: body, issues } = validateBrandVoice(draftReply);
  if (issues.length > 0) {
    console.warn(`support-templates: brand voice issues in ${category}:`, issues.join("; "));
  }

  const greeting = openingLine(recipientName);
  const contextNote = originalSubject ? `\nRe: ${originalSubject}\n` : "";

  let textBody: string;
  let htmlSubject: string;

  switch (category) {
    case "bug_acknowledged":
      htmlSubject = originalSubject
        ? `Re: ${originalSubject}`
        : SUBJECT_TEMPLATES.bug_acknowledged;
      textBody = [
        greeting,
        contextNote,
        body,
        "",
        "We'll keep you updated as we make progress. You don't need to take any action.",
        "",
        "Best regards,",
        "The ReloPass Team",
        "support@relopass.com",
      ].join("\n");
      break;

    case "policy_question":
      htmlSubject = originalSubject
        ? `Re: ${originalSubject}`
        : SUBJECT_TEMPLATES.policy_question;
      textBody = [
        greeting,
        contextNote,
        body,
        "",
        "If you have any follow-up questions, simply reply to this email and we'll be happy to help.",
        "",
        "Best regards,",
        "The ReloPass Team",
        "support@relopass.com",
      ].join("\n");
      break;

    case "feature_noted":
      htmlSubject = originalSubject
        ? `Re: ${originalSubject}`
        : SUBJECT_TEMPLATES.feature_noted;
      textBody = [
        greeting,
        contextNote,
        body,
        "",
        "We share all product suggestions with our team and take them seriously when planning new features.",
        "",
        "Best regards,",
        "The ReloPass Team",
        "support@relopass.com",
      ].join("\n");
      break;

    case "billing_escalated":
      htmlSubject = originalSubject
        ? `Re: ${originalSubject}`
        : SUBJECT_TEMPLATES.billing_escalated;
      textBody = [
        greeting,
        contextNote,
        body,
        "",
        "Our team will be in touch within one business day with a full response.",
        "",
        "Best regards,",
        "The ReloPass Team",
        "support@relopass.com",
      ].join("\n");
      break;

    default: // general_acknowledgment
      htmlSubject = originalSubject
        ? `Re: ${originalSubject}`
        : SUBJECT_TEMPLATES.general_acknowledgment;
      textBody = [
        greeting,
        contextNote,
        body,
        "",
        "We aim to respond to all enquiries within one business day.",
        "",
        "Best regards,",
        "The ReloPass Team",
        "support@relopass.com",
      ].join("\n");
      break;
  }

  // Simple HTML version (preserves line structure)
  const htmlBody = `<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:600px;margin:0 auto;padding:20px">
<p>${textBody.replace(/\n\n/g, "</p><p>").replace(/\n/g, "<br>")}</p>
<hr style="border:none;border-top:1px solid #eee;margin:20px 0">
<p style="font-size:11px;color:#888">This message was sent by the ReloPass automated support system.<br>
${companyDomain ? `Account: ${companyDomain}` : ""}</p>
</body></html>`;

  return {
    subject: htmlSubject,
    textBody,
    htmlBody,
    categoryLabel: CATEGORY_LABELS[category],
  };
}

// ─── Category selector ────────────────────────────────────────────────────────

/** Map triage result to the correct template category */
export function selectTemplateCategory(
  issueCategory: string,
  suggestedAction: string,
): TemplateCategory {
  if (suggestedAction === "escalate" || issueCategory === "billing") return "billing_escalated";
  if (issueCategory === "feature_request") return "feature_noted";
  if (issueCategory === "policy_question") return "policy_question";
  if (issueCategory === "bug" || issueCategory === "ux_confusion") return "bug_acknowledged";
  return "general_acknowledgment";
}
