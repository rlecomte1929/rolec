/**
 * weekly-support-digest — Supabase Edge Function (SUPPORT-4E)
 * ─────────────────────────────────────────────────────────────────────────────
 * Scheduled every Monday at 08:00 UTC via pg_cron.
 * Queries the past 7 days of support_tickets, computes support health stats,
 * and delivers:
 *   1. A digest block appended to the Notion AI Work Queue overview page
 *   2. A plain-text digest email to Romain via Postmark
 *
 * Digest sections:
 *   - Volume overview (total, by source)
 *   - Resolution rates (auto-resolved, AI-replied, escalated, pending)
 *   - Top 3 recurring issues (by frequency, anonymised, no raw content)
 *   - Auto-fixes shipped to Dev Loop
 *   - Escalations handled
 *
 * Handles zero-ticket week gracefully ("No support tickets this week").
 *
 * Environment variables:
 *   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY — auto-injected
 *   NOTION_TOKEN            — Notion integration secret
 *   NOTION_OVERVIEW_PAGE    — AI Work Queue overview page ID
 *   POSTMARK_SERVER_TOKEN   ��� Postmark API token
 *   DIGEST_EMAIL_TO         — recipient (default: romain_lecomte@hotmail.com)
 *   DIGEST_EMAIL_FROM       — sender (default: ai@relopass.com)
 * ─────────────────────────────────────────────────────────────────────────────
 */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const NOTION_VERSION = "2022-06-28";

// ─── Types ────────────────────────────────────────────────────────────────────

interface SupportTicket {
  id: string;
  created_at: string;
  status: string;
  source: string;
  subject: string | null;
  triage_result: {
    issue_category?: string;
    root_cause_hypothesis?: string;
    fix_difficulty?: string;
    suggested_action?: string;
    draft_reply?: string;
  } | null;
}

interface DigestStats {
  total: number;
  bySource: { email: number; "in-app": number };
  byStatus: { new: number; triaged: number; resolved: number; escalated: number; other: number };
  byAction: { auto_fix: number; notion_task: number; ai_reply: number; escalate: number; other: number };
  autoResolvedPct: number;
  aiRepliedPct: number;
  escalatedPct: number;
  topIssues: Array<{ hypothesis: string; count: number; category: string }>;
}

// ─── Supabase query ───────────────────────────────────────────────────────────

async function fetchWeeklyTickets(supabaseUrl: string, serviceKey: string, since: string): Promise<SupportTicket[]> {
  const url = `${supabaseUrl}/rest/v1/support_tickets?created_at=gte.${since}&select=id,created_at,status,source,subject,triage_result&order=created_at.desc&limit=500`;
  const res = await fetch(url, {
    headers: {
      "apikey": serviceKey,
      "Authorization": `Bearer ${serviceKey}`,
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) throw new Error(`Supabase query failed: ${res.status} ${await res.text()}`);
  return await res.json() as SupportTicket[];
}

// ─── Stats computation ────────────────────────────────────────��───────────────

function computeStats(tickets: SupportTicket[]): DigestStats {
  const total = tickets.length;

  const bySource = { email: 0, "in-app": 0 };
  const byStatus = { new: 0, triaged: 0, resolved: 0, escalated: 0, other: 0 };
  const byAction = { auto_fix: 0, notion_task: 0, ai_reply: 0, escalate: 0, other: 0 };

  // For top issues: group by root_cause_hypothesis
  const hypothesisMap = new Map<string, { count: number; category: string }>();

  for (const t of tickets) {
    // Source
    if (t.source === "email") bySource.email++;
    else if (t.source === "in-app") bySource["in-app"]++;

    // Status
    const st = t.status as keyof typeof byStatus;
    if (st in byStatus) byStatus[st]++;
    else byStatus.other++;

    // Triage action
    const action = t.triage_result?.suggested_action ?? "other";
    if (action in byAction) byAction[action as keyof typeof byAction]++;
    else byAction.other++;

    // Root cause hypothesis deduplication (first 80 chars as key)
    const hypothesis = t.triage_result?.root_cause_hypothesis?.trim();
    if (hypothesis && hypothesis.length > 5) {
      const key = hypothesis.slice(0, 80).toLowerCase().replace(/[^a-z0-9\s]/g, "");
      const existing = hypothesisMap.get(key);
      if (existing) {
        existing.count++;
      } else {
        hypothesisMap.set(key, {
          count: 1,
          category: t.triage_result?.issue_category ?? "other",
        });
      }
    }
  }

  // Percentages (rounded to 1dp)
  const pct = (n: number) => total > 0 ? Math.round((n / total) * 1000) / 10 : 0;
  const autoResolved = byAction.auto_fix + byAction.ai_reply;
  const autoResolvedPct = pct(autoResolved);
  const aiRepliedPct = pct(byAction.ai_reply);
  const escalatedPct = pct(byAction.escalate);

  // Top 3 issues by frequency
  const topIssues = Array.from(hypothesisMap.entries())
    .sort(([, a], [, b]) => b.count - a.count)
    .slice(0, 3)
    .map(([key, v]) => ({
      hypothesis: key.charAt(0).toUpperCase() + key.slice(1),
      count: v.count,
      category: v.category,
    }));

  return { total, bySource, byStatus, byAction, autoResolvedPct, aiRepliedPct, escalatedPct, topIssues };
}

// ─── Digest text builder ──────────────────────────────────────────────────────

function buildDigestText(stats: DigestStats, weekLabel: string): string {
  const lines: string[] = [];

  lines.push(`Weekly Support Digest — ${weekLabel}`);
  lines.push("─".repeat(50));
  lines.push("");

  if (stats.total === 0) {
    lines.push("No support tickets this week. Queue is clear.");
    lines.push("");
    lines.push("─".repeat(50));
    lines.push("ReloPass AI Support · SUPPORT-4E");
    return lines.join("\n");
  }

  // Volume overview
  lines.push(`📊 Volume: ${stats.total} ticket${stats.total !== 1 ? "s" : ""} this week`);
  lines.push(`   Email: ${stats.bySource.email}  |  In-app: ${stats.bySource["in-app"]}`);
  lines.push("");

  // Resolution rates
  lines.push("📈 Resolution rates:");
  lines.push(`   Auto-resolved   : ${stats.autoResolvedPct}%  (${stats.byAction.auto_fix + stats.byAction.ai_reply} tickets)`);
  lines.push(`   AI-replied      : ${stats.aiRepliedPct}%  (${stats.byAction.ai_reply} tickets)`);
  lines.push(`   Escalated       : ${stats.escalatedPct}%  (${stats.byStatus.escalated} tickets)`);
  lines.push(`   Still open      : ${stats.byStatus.new + stats.byStatus.triaged} tickets`);
  lines.push("");

  // Routing breakdown
  lines.push("🔀 Routing breakdown:");
  lines.push(`   Dev Loop (auto_fix)  : ${stats.byAction.auto_fix}`);
  lines.push(`   Notion tasks         : ${stats.byAction.notion_task}`);
  lines.push(`   AI replies sent      : ${stats.byAction.ai_reply}`);
  lines.push(`   Escalated to Romain  : ${stats.byAction.escalate}`);
  lines.push("");

  // Top recurring issues
  if (stats.topIssues.length > 0) {
    lines.push("🔁 Top recurring issues (by frequency):");
    for (let i = 0; i < stats.topIssues.length; i++) {
      const issue = stats.topIssues[i];
      lines.push(`   ${i + 1}. [${issue.category}] ${issue.hypothesis} (${issue.count}×)`);
    }
    lines.push("");
  }

  lines.push("─".repeat(50));
  lines.push("ReloPass AI Support · SUPPORT-4E");

  return lines.join("\n");
}

// ─── Notion page update ────────────────────────────────────────��──────────────

async function postDigestToNotion(
  token: string,
  overviewPageId: string,
  digestText: string,
  weekLabel: string,
): Promise<void> {
  const chunkSize = 1900;
  const chunks: string[] = [];
  for (let i = 0; i < digestText.length; i += chunkSize) {
    chunks.push(digestText.slice(i, i + chunkSize));
  }

  const blocks = [
    {
      object: "block", type: "heading_3",
      heading_3: { rich_text: [{ type: "text", text: { content: `📬 Weekly Support Digest — ${weekLabel}` } }], color: "default" },
    },
    {
      object: "block", type: "code",
      code: {
        language: "plain text",
        rich_text: chunks.slice(0, 1).map((c) => ({ type: "text", text: { content: c } })),
      },
    },
    ...chunks.slice(1).map((c) => ({
      object: "block", type: "paragraph",
      paragraph: { rich_text: [{ type: "text", text: { content: c } }] },
    })),
    { object: "block", type: "divider", divider: {} },
  ];

  const res = await fetch(`https://api.notion.com/v1/blocks/${overviewPageId}/children`, {
    method: "PATCH",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Notion-Version": NOTION_VERSION,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ children: blocks }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Notion block append failed: ${res.status} ${err}`);
  }
}

// ─── Postmark email ───────────────────────────────────────────────────────────

async function sendDigestEmail(
  postmarkToken: string,
  to: string,
  from: string,
  weekLabel: string,
  digestText: string,
): Promise<void> {
  const res = await fetch("https://api.postmarkapp.com/email", {
    method: "POST",
    headers: {
      "Accept": "application/json",
      "Content-Type": "application/json",
      "X-Postmark-Server-Token": postmarkToken,
    },
    body: JSON.stringify({
      From: from,
      To: to,
      Subject: `ReloPass Weekly Support Digest — ${weekLabel}`,
      TextBody: digestText,
      MessageStream: "outbound",
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Postmark email failed: ${res.status} ${err}`);
  }
  const result = await res.json() as { MessageID?: string };
  console.log(`weekly-support-digest: email sent, MessageID=${result.MessageID}`);
}

// ─── Edge Function handler ───────────────────────────────────────��────────────

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS_HEADERS });

  const supabaseUrl    = Deno.env.get("SUPABASE_URL") ?? "";
  const serviceKey     = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  const notionToken    = Deno.env.get("NOTION_TOKEN");
  const overviewPageId = Deno.env.get("NOTION_OVERVIEW_PAGE") ?? "35c887c64d4881ac9b40eb253c86cf29";
  const postmarkToken  = Deno.env.get("POSTMARK_SERVER_TOKEN");
  const emailTo        = Deno.env.get("DIGEST_EMAIL_TO") ?? "romain_lecomte@hotmail.com";
  const emailFrom      = Deno.env.get("DIGEST_EMAIL_FROM") ?? "ai@relopass.com";

  if (!supabaseUrl || !serviceKey) {
    return Response.json({ ok: false, error: "SUPABASE credentials required" }, { status: 500, headers: CORS_HEADERS });
  }

  const now = new Date();
  const since = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();
  const weekLabel = `${since.slice(0, 10)} → ${now.toISOString().slice(0, 10)}`;

  console.log(`weekly-support-digest: generating for week ${weekLabel}`);

  try {
    // 1. Query tickets
    const tickets = await fetchWeeklyTickets(supabaseUrl, serviceKey, since);
    console.log(`weekly-support-digest: found ${tickets.length} tickets`);

    // 2. Compute stats
    const stats = computeStats(tickets);

    // 3. Build digest
    const digestText = buildDigestText(stats, weekLabel);
    console.log("weekly-support-digest: digest built");

    // 4. Post to Notion
    let notionPosted = false;
    if (notionToken) {
      try {
        await postDigestToNotion(notionToken, overviewPageId, digestText, weekLabel);
        notionPosted = true;
        console.log("weekly-support-digest: Notion post ✓");
      } catch (err) {
        console.error("weekly-support-digest: Notion post failed:", err instanceof Error ? err.message : err);
      }
    } else {
      console.warn("weekly-support-digest: NOTION_TOKEN not set — skipping Notion");
    }

    // 5. Send email
    let emailSent = false;
    if (postmarkToken) {
      try {
        await sendDigestEmail(postmarkToken, emailTo, emailFrom, weekLabel, digestText);
        emailSent = true;
        console.log(`weekly-support-digest: email sent to ${emailTo} ✓`);
      } catch (err) {
        console.error("weekly-support-digest: email failed:", err instanceof Error ? err.message : err);
      }
    } else {
      console.warn("weekly-support-digest: POSTMARK_SERVER_TOKEN not set — skipping email");
    }

    const result = {
      ok: true,
      week: weekLabel,
      total_tickets: stats.total,
      auto_resolved_pct: stats.autoResolvedPct,
      escalated_pct: stats.escalatedPct,
      top_issues_count: stats.topIssues.length,
      notion_posted: notionPosted,
      email_sent: emailSent,
      digest_preview: digestText.slice(0, 300) + (digestText.length > 300 ? "..." : ""),
    };

    console.log("weekly-support-digest complete:", JSON.stringify({ ...result, digest_preview: undefined }));
    return Response.json(result, { headers: CORS_HEADERS });

  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("weekly-support-digest error:", message);
    return Response.json({ ok: false, error: message }, { status: 500, headers: CORS_HEADERS });
  }
});
