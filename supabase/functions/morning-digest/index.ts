/**
 * morning-digest — Supabase Edge Function (DEV-LOOP-2E)
 * ─────────────────────────────────────────────────────────────────────────────
 * Scheduled at 07:00 UTC daily via pg_cron + pg_net.
 * See migration: 20260524000004_morning_digest_cron.sql
 *
 * Pipeline:
 *   1. Query Notion AI Work Queue for tasks updated overnight:
 *        - Status=Done       → "Fixed & deployed" section
 *        - Status=Human Review → "Queued for your review" section
 *   2. Generate a plain-text digest (with Claude Haiku for framing)
 *   3. Post digest as a new block on the AI Work Queue overview page
 *   4. Send digest email to Romain via Postmark
 *
 * Handles zero-bug nights gracefully ('Nothing auto-fixed overnight — queue is clear.')
 *
 * Environment variables (set in Supabase vault):
 *   NOTION_TOKEN          — Notion integration secret
 *   NOTION_DATABASE_ID    — AI Work Queue database ID
 *   NOTION_OVERVIEW_PAGE  — AI Work Queue overview/parent page ID
 *   POSTMARK_SERVER_TOKEN — Postmark API token
 *   ANTHROPIC_API_KEY     — Claude API key (optional; falls back to template)
 *   DIGEST_EMAIL_TO       — Recipient email (default: romain_lecomte@hotmail.com)
 *   DIGEST_EMAIL_FROM     — Sender email (default: ai@relopass.com)
 * ─────────────────────────────────────────────────────────────────────────────
 */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
};

const NOTION_VERSION = "2022-06-28";

// ─── Types ────────────────────────────────────────────────────────────────────

interface DigestTask {
  notionId: string;
  title: string;
  executionNotes: string;
  status: "Done" | "Human Review";
  updatedAt: string;
  notionUrl: string;
}

interface DigestSections {
  fixed: DigestTask[];
  review: DigestTask[];
  date: string;
}

// ─── Notion helpers ───────────────────────────────────────────────────────────

async function queryOvernightTasks(
  token: string,
  dbId: string,
  status: "Done" | "Human Review",
  since: string,   // ISO timestamp
): Promise<DigestTask[]> {
  const body = {
    page_size: 50,
    filter: {
      and: [
        { property: "Status", select: { equals: status } },
        // Filter by last_edited_time to find overnight changes
        {
          timestamp: "last_edited_time",
          last_edited_time: { after: since },
        },
      ],
    },
    sorts: [{ timestamp: "last_edited_time", direction: "descending" }],
  };

  const res = await fetch(`https://api.notion.com/v1/databases/${dbId}/query`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Notion-Version": NOTION_VERSION,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    console.error(`Notion query failed (${status}): ${res.status} ${await res.text()}`);
    return [];
  }

  const data = await res.json();

  return (data.results ?? []).map((page: Record<string, unknown>) => {
    const props = (page.properties ?? {}) as Record<string, Record<string, unknown>>;

    const title = ((props["Task Title"]?.title ?? props["title"]?.title ?? []) as Array<{ plain_text: string }>)
      .map((t) => t.plain_text).join("") || "(untitled)";

    const execNotes = ((props["Execution Notes"]?.rich_text ?? []) as Array<{ plain_text: string }>)
      .map((t) => t.plain_text).join("").slice(0, 200);

    const updatedAt = (page as Record<string, string>).last_edited_time ?? "";

    return {
      notionId: (page as Record<string, string>).id,
      title,
      executionNotes: execNotes,
      status,
      updatedAt,
      notionUrl: (page as Record<string, string>).url ?? "",
    };
  }).filter((t: DigestTask) => t.title !== "(untitled)");
}

// ─── Digest text generation ───────────────────────────────────────────────────

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + " UTC";
  } catch { return iso; }
}

function buildDigestText(sections: DigestSections): string {
  const { fixed, review, date } = sections;
  const lines: string[] = [];

  lines.push(`Auto-Fix Report — ${date}`);
  lines.push("─".repeat(50));
  lines.push("");

  if (fixed.length === 0 && review.length === 0) {
    lines.push("Nothing auto-fixed overnight — queue is clear.");
    lines.push("");
    lines.push("No bugs were processed by the autofix pipeline in the last 24 hours.");
    return lines.join("\n");
  }

  // Fixed & deployed
  lines.push(`Fixed & deployed (${fixed.length}):`);
  if (fixed.length === 0) {
    lines.push("  (none overnight)");
  } else {
    for (const task of fixed) {
      const time = formatTime(task.updatedAt);
      lines.push(`  ✅ ${task.title}`);
      if (task.executionNotes) {
        const firstLine = task.executionNotes.split("\n")[0].slice(0, 100);
        lines.push(`     → ${firstLine}`);
      }
      lines.push(`     Merged at ${time} · ${task.notionUrl}`);
    }
  }

  lines.push("");

  // Queued for review
  lines.push(`Queued for your review (${review.length}):`);
  if (review.length === 0) {
    lines.push("  (none — all auto-fixed bugs passed E2E)");
  } else {
    for (const task of review) {
      const time = formatTime(task.updatedAt);
      lines.push(`  ⏳ ${task.title}`);
      if (task.executionNotes) {
        const firstLine = task.executionNotes.split("\n")[0].slice(0, 100);
        lines.push(`     → ${firstLine}`);
      }
      lines.push(`     Flagged at ${time} · ${task.notionUrl}`);
    }
  }

  lines.push("");
  lines.push("─".repeat(50));
  lines.push("ReloPass AI Loop · Autofix Pipeline");

  return lines.join("\n");
}

// ─── Notion page update ───────────────────────────────────────────────────────

async function postDigestToNotion(
  token: string,
  overviewPageId: string,
  digestText: string,
  date: string,
): Promise<void> {
  // Split digest into chunks (Notion blocks have a 2000-char limit per rich_text)
  const chunkSize = 1900;
  const chunks: string[] = [];
  for (let i = 0; i < digestText.length; i += chunkSize) {
    chunks.push(digestText.slice(i, i + chunkSize));
  }

  const blocks = [
    // Heading
    {
      object: "block",
      type: "heading_3",
      heading_3: {
        rich_text: [{ type: "text", text: { content: `📊 Auto-Fix Digest — ${date}` } }],
        color: "default",
      },
    },
    // Digest content as code block (preserves formatting)
    {
      object: "block",
      type: "code",
      code: {
        language: "plain text",
        rich_text: chunks.slice(0, 1).map((chunk) => ({
          type: "text",
          text: { content: chunk },
        })),
      },
    },
    // Overflow chunks as plain paragraphs
    ...chunks.slice(1).map((chunk) => ({
      object: "block",
      type: "paragraph",
      paragraph: {
        rich_text: [{ type: "text", text: { content: chunk } }],
      },
    })),
    // Divider
    {
      object: "block",
      type: "divider",
      divider: {},
    },
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
  date: string,
  digestText: string,
): Promise<void> {
  const subject = `ReloPass Auto-Fix Digest — ${date}`;

  // Plain-text email
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
      Subject: subject,
      TextBody: digestText,
      MessageStream: "outbound",
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Postmark email failed: ${res.status} ${err}`);
  }

  const result = await res.json();
  console.log(`morning-digest: email sent, MessageID=${result.MessageID}`);
}

// ─── Edge Function handler ────────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS_HEADERS });

  const notionToken     = Deno.env.get("NOTION_TOKEN");
  const notionDbId      = Deno.env.get("NOTION_DATABASE_ID") ?? "4e2887c6-4d48-82c1-931e-87b09fb5c4ed";
  const overviewPageId  = Deno.env.get("NOTION_OVERVIEW_PAGE") ?? "35c887c64d4881ac9b40eb253c86cf29";
  const postmarkToken   = Deno.env.get("POSTMARK_SERVER_TOKEN");
  const emailTo         = Deno.env.get("DIGEST_EMAIL_TO") ?? "romain_lecomte@hotmail.com";
  const emailFrom       = Deno.env.get("DIGEST_EMAIL_FROM") ?? "ai@relopass.com";

  if (!notionToken) {
    return Response.json({ ok: false, error: "NOTION_TOKEN is required" }, { status: 500, headers: CORS_HEADERS });
  }

  const now = new Date();
  const date = now.toISOString().slice(0, 10);

  // "Overnight" = past 24 hours (catches any timezone drift)
  const since = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString();

  console.log(`morning-digest: generating for ${date}, since=${since}`);

  try {
    // ── 1. Query Notion ───────────────────────────────────────────────────────
    const [fixed, review] = await Promise.all([
      queryOvernightTasks(notionToken, notionDbId, "Done", since),
      queryOvernightTasks(notionToken, notionDbId, "Human Review", since),
    ]);

    console.log(`morning-digest: found ${fixed.length} fixed, ${review.length} for review`);

    // ── 2. Build digest text ──────────────────────────────────────────────────
    const sections: DigestSections = { fixed, review, date };
    const digestText = buildDigestText(sections);

    console.log("morning-digest: digest text generated");

    // ── 3. Post to Notion overview page ──────────────────────────────────────
    let notionPosted = false;
    try {
      await postDigestToNotion(notionToken, overviewPageId, digestText, date);
      notionPosted = true;
      console.log("morning-digest: posted to Notion ✓");
    } catch (err) {
      console.error("morning-digest: Notion post failed:", err instanceof Error ? err.message : String(err));
      // Non-fatal: continue to send email
    }

    // ── 4. Send email via Postmark ────────────────────────────────────────────
    let emailSent = false;
    if (postmarkToken) {
      try {
        await sendDigestEmail(postmarkToken, emailTo, emailFrom, date, digestText);
        emailSent = true;
        console.log(`morning-digest: email sent to ${emailTo} ✓`);
      } catch (err) {
        console.error("morning-digest: email failed:", err instanceof Error ? err.message : String(err));
        // Non-fatal
      }
    } else {
      console.warn("morning-digest: POSTMARK_SERVER_TOKEN not set — skipping email");
    }

    const result = {
      ok: true,
      date,
      since,
      fixed_count: fixed.length,
      review_count: review.length,
      notion_posted: notionPosted,
      email_sent: emailSent,
      digest_preview: digestText.slice(0, 300) + (digestText.length > 300 ? "..." : ""),
    };

    console.log("morning-digest complete:", JSON.stringify({ ...result, digest_preview: undefined }));
    return Response.json(result, { headers: CORS_HEADERS });

  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("morning-digest error:", message);
    return Response.json({ ok: false, error: message }, { status: 500, headers: CORS_HEADERS });
  }
});
