/**
 * brain-update — Supabase Edge Function (BRAIN-3E)
 * ─────────────────────────────────────────────────────────────────────────────
 * Monthly pipeline that keeps the ReloPass Company Brain (BRAIN-3D) current as
 * new customer insights are gathered through interviews.
 *
 * Two modes of operation (controlled by POST body):
 *
 * MODE 1 — Generate delta (body: {} or { since: "YYYY-MM-DD" }):
 *   1. Fetch recent Pain Points, Opportunities, Feature Requests from Notion
 *      (since last applied update or last 30 days)
 *   2. Fetch current BRAIN-3D content from Notion
 *   3. Use Claude Haiku to identify: new insights / contradictions / already covered
 *   4. Create a "Brain Update Review — YYYY-MM" sub-page under BRAIN-3D
 *      with an approval checkbox at the top
 *   5. Store review record in public.brain_update_reviews
 *
 * MODE 2 — Apply approved deltas (body: { check_approvals: true }):
 *   1. Query brain_update_reviews for status = 'pending'
 *   2. For each, fetch the Notion review page and check the approval checkbox
 *   3. If approved: use Claude Haiku to append insights to BRAIN-3D sections
 *   4. Mark review as applied in brain_update_reviews
 *
 * pg_cron schedule (see migration 20260524140000_brain_update.sql):
 *   - Monthly:  0 8 1 * *  → Mode 1 (generate delta on 1st of each month)
 *   - Daily:    0 9 * * *  → Mode 2 (check approvals daily at 9am UTC)
 *
 * Environment variables (set in Supabase vault):
 *   NOTION_TOKEN            — Notion integration secret
 *   ANTHROPIC_API_KEY       — Claude Haiku API key
 *   BRAIN_PAGE_ID           — BRAIN-3D page/task ID (default: AIQ-324 page)
 *   PAIN_POINTS_DB_ID       — Notion Pain Points database ID
 *   OPPORTUNITIES_DB_ID     — Notion Opportunities database ID
 *   FEATURES_DB_ID          — Notion Feature Requests database ID
 *   SUPABASE_URL            — auto-set
 *   SUPABASE_SERVICE_ROLE_KEY — auto-set
 * ─────────────────────────────────────────────────────────────────────────────
 */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
};

const NOTION_VERSION = "2022-06-28";
const ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages";
const HAIKU_MODEL = "claude-haiku-4-5-20251001";

// Default database IDs from relopass-interview-intake skill
const DEFAULT_PAIN_POINTS_DB_ID   = "11ef02cf6ad545a1b709877e3f56e37f";
const DEFAULT_OPPORTUNITIES_DB_ID = "bde8520a27f14e21b6e5e2b75fe3b6c4";
const DEFAULT_FEATURES_DB_ID      = "ac0228b6213e44d99ebd99b40a848ed9";

// Default BRAIN-3D page (AIQ-324 task page which IS the Company Brain document)
const DEFAULT_BRAIN_PAGE_ID = "369887c64d48818eb478f7298fd3063c";

// Default look-back window when no previous applied update exists
const DEFAULT_LOOKBACK_DAYS = 30;

// ─── Types ────────────────────────────────────────────────────────────────────

interface NotionInsight {
  id: string;
  title: string;
  description: string;
  category: "pain_point" | "opportunity" | "feature_request";
  severity?: string;         // for pain points
  confidence?: string;       // for opportunities
  priority?: string;         // for feature requests
  created_time: string;
  notion_url: string;
}

interface DeltaInsight {
  title: string;
  description: string;
  category: string;
  relevantBrainSection: string;
  rationale: string;
}

interface Contradiction {
  insightTitle: string;
  conflictDescription: string;
  existingContent: string;
}

interface DeltaReport {
  monthLabel: string;
  sinceDate: string;
  newInsights: DeltaInsight[];
  contradictions: Contradiction[];
  alreadyCoveredCount: number;
  totalInsightsProcessed: number;
  summary: string;
}

interface ReviewRecord {
  month_label: string;
  notion_page_id: string;
  notion_page_url: string;
  insights_count: number;
  status: "pending" | "applied" | "rejected";
}

interface PendingReview {
  id: string;
  month_label: string;
  notion_page_id: string;
  notion_page_url: string;
  insights_count: number;
  created_at: string;
}

// ─── Notion helpers ───────────────────────────────────────────────────────────

function getTitle(props: Record<string, Record<string, unknown>>, field: string): string {
  const titleBlocks = (props[field]?.title ?? []) as Array<{ plain_text: string }>;
  return titleBlocks.map((t: { plain_text: string }) => t.plain_text).join("").trim() || "(untitled)";
}

function getRichText(props: Record<string, Record<string, unknown>>, field: string): string {
  const rtBlocks = (props[field]?.rich_text ?? []) as Array<{ plain_text: string }>;
  return rtBlocks.map((t: { plain_text: string }) => t.plain_text).join("").trim();
}

function getSelect(props: Record<string, Record<string, unknown>>, field: string): string {
  return (props[field]?.select as { name?: string })?.name ?? "";
}

async function queryNotionDatabase(
  token: string,
  dbId: string,
  sinceDate: string,
  titleField: string,
): Promise<NotionInsight[]> {
  const body = {
    page_size: 100,
    filter: {
      timestamp: "created_time",
      created_time: { after: sinceDate },
    },
    sorts: [{ timestamp: "created_time", direction: "descending" }],
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
    console.error(`Notion DB query failed (${dbId}): ${res.status} ${await res.text()}`);
    return [];
  }

  const data = await res.json();
  return (data.results ?? []).map((page: Record<string, unknown>) => {
    const props = (page.properties ?? {}) as Record<string, Record<string, unknown>>;
    const category: NotionInsight["category"] =
      titleField === "Pain Point" ? "pain_point"
      : titleField === "Opportunity" ? "opportunity"
      : "feature_request";

    return {
      id: page.id as string,
      title: getTitle(props, titleField),
      description: getRichText(props, "Description") || getRichText(props, "Verbatim Request"),
      category,
      severity: getSelect(props, "Severity"),
      confidence: getSelect(props, "Confidence"),
      priority: getSelect(props, "Priority"),
      created_time: page.created_time as string,
      notion_url: (page as Record<string, string>).url ?? "",
    } satisfies NotionInsight;
  }).filter((i: NotionInsight) => i.title !== "(untitled)");
}

async function fetchRecentInsights(
  token: string,
  sinceDate: string,
  painPointsDbId: string,
  opportunitiesDbId: string,
  featuresDbId: string,
): Promise<NotionInsight[]> {
  const [painPoints, opportunities, features] = await Promise.all([
    queryNotionDatabase(token, painPointsDbId, sinceDate, "Pain Point"),
    queryNotionDatabase(token, opportunitiesDbId, sinceDate, "Opportunity"),
    queryNotionDatabase(token, featuresDbId, sinceDate, "Feature Request"),
  ]);

  console.log(`Fetched insights since ${sinceDate}: ${painPoints.length} pain points, ${opportunities.length} opportunities, ${features.length} features`);
  return [...painPoints, ...opportunities, ...features];
}

// ─── BRAIN-3D content fetcher ─────────────────────────────────────────────────

async function fetchBrainContent(token: string, brainPageId: string): Promise<string> {
  // Fetch blocks from the BRAIN-3D page to extract text for comparison
  const res = await fetch(`https://api.notion.com/v1/blocks/${brainPageId}/children?page_size=100`, {
    headers: {
      "Authorization": `Bearer ${token}`,
      "Notion-Version": NOTION_VERSION,
    },
  });

  if (!res.ok) {
    console.error(`Failed to fetch BRAIN-3D blocks: ${res.status}`);
    return "(Brain content unavailable — proceeding without comparison)";
  }

  const data = await res.json();
  const blocks = (data.results ?? []) as Array<Record<string, unknown>>;
  const lines: string[] = [];

  for (const block of blocks) {
    const type = block.type as string;
    const content = (block[type] as Record<string, unknown>);
    if (!content) continue;

    const richText = (content.rich_text ?? []) as Array<{ plain_text: string }>;
    const text = richText.map((t: { plain_text: string }) => t.plain_text).join("");

    if (type === "heading_1") lines.push(`# ${text}`);
    else if (type === "heading_2") lines.push(`## ${text}`);
    else if (type === "heading_3") lines.push(`### ${text}`);
    else if (type === "paragraph" && text) lines.push(text);
    else if (type === "bulleted_list_item") lines.push(`- ${text}`);
    else if (type === "numbered_list_item") lines.push(`- ${text}`);
  }

  // Cap at 6,000 chars to stay within Haiku context budget
  const full = lines.join("\n");
  return full.length > 6000 ? full.slice(0, 6000) + "\n...[truncated for brevity]" : full;
}

// ─── Claude delta generation ──────────────────────────────────────────────────

async function generateDelta(
  apiKey: string,
  insights: NotionInsight[],
  brainContent: string,
  monthLabel: string,
): Promise<DeltaReport> {
  if (insights.length === 0) {
    return {
      monthLabel,
      sinceDate: "",
      newInsights: [],
      contradictions: [],
      alreadyCoveredCount: 0,
      totalInsightsProcessed: 0,
      summary: "No new insights found since last update. Company Brain is current.",
    };
  }

  const insightsList = insights.map((i: NotionInsight) =>
    `[${i.category.toUpperCase()}] ${i.title}\nDescription: ${i.description || "(none)"}\n${i.severity ? `Severity: ${i.severity}` : ""}${i.confidence ? `Confidence: ${i.confidence}` : ""}${i.priority ? `Priority: ${i.priority}` : ""}`
  ).join("\n\n");

  const systemPrompt = `You are a knowledge management agent for ReloPass, an AI-powered global mobility platform. Your job is to compare new customer insights against the existing Company Brain and identify what's new, what contradicts existing knowledge, and what's already covered.

You MUST respond with a valid JSON object. No markdown, no prose, only the JSON.`;

  const userPrompt = `Here are ${insights.length} new insights gathered from recent customer interviews:

${insightsList}

Here is the current ReloPass Company Brain content (sections summary):
${brainContent}

Analyse these insights and return a JSON object with exactly this structure:
{
  "newInsights": [
    {
      "title": "short title of the insight",
      "description": "1-2 sentence description of the insight and why it matters for ReloPass",
      "category": "pain_point|opportunity|feature_request",
      "relevantBrainSection": "which Company Brain section this updates (e.g. 'Section 3: HR Buyer Personas', 'Section 4: Supplier Taxonomy', 'Section 2: Domain Model')",
      "rationale": "1 sentence: why this is genuinely new and not already in the Brain"
    }
  ],
  "contradictions": [
    {
      "insightTitle": "title of the contradicting insight",
      "conflictDescription": "what specifically conflicts with existing knowledge",
      "existingContent": "brief quote of the existing Brain content that's contradicted"
    }
  ],
  "alreadyCoveredCount": 3,
  "summary": "2-3 sentence plain English summary of what was found and the most important addition to make"
}

Rules:
- Only include genuinely new information in newInsights (not already covered by the Brain)
- Be conservative: when in doubt, omit (Romain will review)
- Contradictions should be flagged but NOT included in newInsights (they need manual resolution)
- alreadyCoveredCount is the count of insights you're NOT including because they're already in the Brain
- Maximum 10 items in newInsights (prioritise highest-value insights)`;

  try {
    const res = await fetch(ANTHROPIC_API_URL, {
      method: "POST",
      headers: {
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: HAIKU_MODEL,
        max_tokens: 2000,
        temperature: 0.1,
        system: systemPrompt,
        messages: [{ role: "user", content: userPrompt }],
      }),
    });

    if (!res.ok) {
      throw new Error(`Haiku API error: ${res.status} ${await res.text()}`);
    }

    const data = await res.json();
    const raw = (data.content?.[0]?.text ?? "").trim();

    // Parse JSON — strip markdown code fences if present
    const jsonStr = raw.replace(/^```json\s*/i, "").replace(/\s*```$/, "");
    const parsed = JSON.parse(jsonStr);

    return {
      monthLabel,
      sinceDate: "",
      newInsights: parsed.newInsights ?? [],
      contradictions: parsed.contradictions ?? [],
      alreadyCoveredCount: parsed.alreadyCoveredCount ?? 0,
      totalInsightsProcessed: insights.length,
      summary: parsed.summary ?? "Delta analysis complete.",
    };
  } catch (err) {
    console.error("Delta generation failed:", err);
    // Fallback: treat all insights as new
    return {
      monthLabel,
      sinceDate: "",
      newInsights: insights.slice(0, 10).map((i: NotionInsight) => ({
        title: i.title,
        description: i.description || "(no description)",
        category: i.category,
        relevantBrainSection: i.category === "pain_point" ? "Section 3: HR Buyer Personas"
          : i.category === "opportunity" ? "Section 2: Domain Model"
          : "Section 5: Linked Documents",
        rationale: "Fallback — manual review required",
      })),
      contradictions: [],
      alreadyCoveredCount: 0,
      totalInsightsProcessed: insights.length,
      summary: "Delta generation fell back to raw list (JSON parse failed). Please review manually.",
    };
  }
}

// ─── Review page creation ─────────────────────────────────────────────────────

function buildReviewPageBlocks(delta: DeltaReport): Array<Record<string, unknown>> {
  const blocks: Array<Record<string, unknown>> = [];

  // Approval checkbox — Romain checks this to trigger the apply step
  blocks.push({
    object: "block",
    type: "to_do",
    to_do: {
      rich_text: [{
        type: "text",
        text: { content: "APPROVED — apply delta to Company Brain (check this box to approve)" },
      }],
      checked: false,
    },
  });

  // Summary callout
  blocks.push({
    object: "block",
    type: "callout",
    callout: {
      rich_text: [{ type: "text", text: { content: delta.summary } }],
      icon: { emoji: "🧠" },
      color: "blue_background",
    },
  });

  // Stats
  blocks.push({
    object: "block",
    type: "paragraph",
    paragraph: {
      rich_text: [{
        type: "text",
        text: {
          content: `Processed ${delta.totalInsightsProcessed} new insights | ${delta.newInsights.length} new | ${delta.contradictions.length} contradictions flagged | ${delta.alreadyCoveredCount} already covered`,
        },
      }],
    },
  });

  blocks.push({ object: "block", type: "divider", divider: {} });

  // New insights section
  if (delta.newInsights.length > 0) {
    blocks.push({
      object: "block",
      type: "heading_2",
      heading_2: { rich_text: [{ type: "text", text: { content: `✅ New Insights to Add (${delta.newInsights.length})` } }] },
    });

    for (const insight of delta.newInsights) {
      blocks.push({
        object: "block",
        type: "heading_3",
        heading_3: { rich_text: [{ type: "text", text: { content: `${insight.category === "pain_point" ? "🔴" : insight.category === "opportunity" ? "💡" : "🔧"} ${insight.title}` } }] },
      });
      blocks.push({
        object: "block",
        type: "paragraph",
        paragraph: { rich_text: [{ type: "text", text: { content: insight.description } }] },
      });
      blocks.push({
        object: "block",
        type: "bulleted_list_item",
        bulleted_list_item: { rich_text: [{ type: "text", text: { content: `Category: ${insight.category.replace(/_/g, " ")}` } }] },
      });
      blocks.push({
        object: "block",
        type: "bulleted_list_item",
        bulleted_list_item: { rich_text: [{ type: "text", text: { content: `→ ${insight.relevantBrainSection}` } }] },
      });
      blocks.push({
        object: "block",
        type: "bulleted_list_item",
        bulleted_list_item: { rich_text: [{ type: "text", text: { content: `Rationale: ${insight.rationale}` } }] },
      });
    }

    blocks.push({ object: "block", type: "divider", divider: {} });
  } else {
    blocks.push({
      object: "block",
      type: "paragraph",
      paragraph: { rich_text: [{ type: "text", text: { content: "✅ No new insights found — Company Brain is already up to date." } }] },
    });
  }

  // Contradictions section
  if (delta.contradictions.length > 0) {
    blocks.push({
      object: "block",
      type: "heading_2",
      heading_2: { rich_text: [{ type: "text", text: { content: `⚠️ Contradictions to Resolve Manually (${delta.contradictions.length})` } }] },
    });
    blocks.push({
      object: "block",
      type: "callout",
      callout: {
        rich_text: [{ type: "text", text: { content: "These items conflict with existing Company Brain content. They will NOT be auto-applied — please resolve them manually." } }],
        icon: { emoji: "⚠️" },
        color: "yellow_background",
      },
    });

    for (const c of delta.contradictions) {
      blocks.push({
        object: "block",
        type: "heading_3",
        heading_3: { rich_text: [{ type: "text", text: { content: `⚡ ${c.insightTitle}` } }] },
      });
      blocks.push({
        object: "block",
        type: "paragraph",
        paragraph: { rich_text: [{ type: "text", text: { content: `Conflict: ${c.conflictDescription}` } }] },
      });
      blocks.push({
        object: "block",
        type: "quote",
        quote: { rich_text: [{ type: "text", text: { content: `Existing Brain content: "${c.existingContent}"` } }] },
      });
    }
  }

  return blocks;
}

async function createReviewPage(
  token: string,
  brainPageId: string,
  delta: DeltaReport,
): Promise<{ pageId: string; pageUrl: string } | null> {
  const title = `Brain Update Review — ${delta.monthLabel}`;
  const blocks = buildReviewPageBlocks(delta);

  const res = await fetch("https://api.notion.com/v1/pages", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Notion-Version": NOTION_VERSION,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      parent: { type: "page_id", page_id: brainPageId },
      properties: {
        title: { title: [{ type: "text", text: { content: title } }] },
      },
      children: blocks,
    }),
  });

  if (!res.ok) {
    console.error(`Failed to create review page: ${res.status} ${await res.text()}`);
    return null;
  }

  const data = await res.json();
  return {
    pageId: data.id,
    pageUrl: data.url ?? `https://notion.so/${data.id.replace(/-/g, "")}`,
  };
}

// ─── Supabase table helpers ───────────────────────────────────────────────────

async function getLastAppliedDate(supabaseUrl: string, serviceKey: string): Promise<string> {
  const res = await fetch(
    `${supabaseUrl}/rest/v1/brain_update_reviews?status=eq.applied&order=applied_at.desc&limit=1`,
    {
      headers: {
        "Authorization": `Bearer ${serviceKey}`,
        "apikey": serviceKey,
      },
    },
  );

  if (!res.ok) {
    // Table may not exist yet — fall back to default look-back
    return new Date(Date.now() - DEFAULT_LOOKBACK_DAYS * 86400000).toISOString();
  }

  const data = await res.json();
  if (Array.isArray(data) && data.length > 0 && data[0].applied_at) {
    return data[0].applied_at;
  }

  return new Date(Date.now() - DEFAULT_LOOKBACK_DAYS * 86400000).toISOString();
}

async function storeReviewRecord(
  supabaseUrl: string,
  serviceKey: string,
  record: ReviewRecord,
): Promise<string | null> {
  const res = await fetch(`${supabaseUrl}/rest/v1/brain_update_reviews`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${serviceKey}`,
      "apikey": serviceKey,
      "Content-Type": "application/json",
      "Prefer": "return=representation",
    },
    body: JSON.stringify(record),
  });

  if (!res.ok) {
    console.error(`Failed to store review record: ${res.status} ${await res.text()}`);
    return null;
  }

  const data = await res.json();
  return Array.isArray(data) ? data[0]?.id ?? null : data?.id ?? null;
}

async function getPendingReviews(
  supabaseUrl: string,
  serviceKey: string,
): Promise<PendingReview[]> {
  const res = await fetch(
    `${supabaseUrl}/rest/v1/brain_update_reviews?status=eq.pending&order=created_at.asc`,
    {
      headers: {
        "Authorization": `Bearer ${serviceKey}`,
        "apikey": serviceKey,
      },
    },
  );

  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

async function markReviewApplied(
  supabaseUrl: string,
  serviceKey: string,
  reviewId: string,
): Promise<void> {
  await fetch(
    `${supabaseUrl}/rest/v1/brain_update_reviews?id=eq.${reviewId}`,
    {
      method: "PATCH",
      headers: {
        "Authorization": `Bearer ${serviceKey}`,
        "apikey": serviceKey,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ status: "applied", applied_at: new Date().toISOString() }),
    },
  );
}

// ─── Approval checker ─────────────────────────────────────────────────────────

async function isApproved(token: string, pageId: string): Promise<boolean> {
  // Check if the first block (approval checkbox) is checked
  const res = await fetch(
    `https://api.notion.com/v1/blocks/${pageId}/children?page_size=5`,
    {
      headers: {
        "Authorization": `Bearer ${token}`,
        "Notion-Version": NOTION_VERSION,
      },
    },
  );

  if (!res.ok) return false;

  const data = await res.json();
  const blocks = (data.results ?? []) as Array<Record<string, unknown>>;

  for (const block of blocks) {
    if (block.type === "to_do") {
      const td = block.to_do as Record<string, unknown>;
      return td.checked === true;
    }
  }

  return false;
}

// ─── Delta applier ────────────────────────────────────────────────────────────

async function applyDeltaToBrain(
  token: string,
  apiKey: string,
  brainPageId: string,
  reviewPageId: string,
  monthLabel: string,
): Promise<void> {
  // Fetch the review page content to extract new insights
  const pageRes = await fetch(`https://api.notion.com/v1/blocks/${reviewPageId}/children?page_size=100`, {
    headers: {
      "Authorization": `Bearer ${token}`,
      "Notion-Version": NOTION_VERSION,
    },
  });

  if (!pageRes.ok) {
    console.error(`Failed to fetch review page blocks: ${pageRes.status}`);
    return;
  }

  const pageData = await pageRes.json();
  const blocks = (pageData.results ?? []) as Array<Record<string, unknown>>;

  // Extract new insights text from the review page
  const insightLines: string[] = [];
  let inNewInsightsSection = false;

  for (const block of blocks) {
    const type = block.type as string;
    const content = (block[type] as Record<string, unknown>);
    if (!content) continue;

    const richText = (content.rich_text ?? []) as Array<{ plain_text: string }>;
    const text = richText.map((t: { plain_text: string }) => t.plain_text).join("");

    if (type === "heading_2" && text.includes("New Insights to Add")) {
      inNewInsightsSection = true;
      continue;
    }
    if (type === "heading_2" && inNewInsightsSection) {
      // Stop at the next h2 (contradictions section)
      break;
    }

    if (inNewInsightsSection && type === "heading_3" && text) {
      insightLines.push(`\n### ${text}`);
    }
    if (inNewInsightsSection && type === "paragraph" && text) {
      insightLines.push(text);
    }
    if (inNewInsightsSection && type === "bulleted_list_item" && text) {
      insightLines.push(`- ${text}`);
    }
  }

  if (insightLines.length === 0) {
    console.log("No new insights found in review page — nothing to apply.");
    return;
  }

  // Append a "New Insights — YYYY-MM" section to BRAIN-3D
  const appendBlocks: Array<Record<string, unknown>> = [
    {
      object: "block",
      type: "divider",
      divider: {},
    },
    {
      object: "block",
      type: "heading_2",
      heading_2: {
        rich_text: [{
          type: "text",
          text: { content: `📥 New Insights from Customer Interviews — ${monthLabel}` },
        }],
        color: "green_background",
      },
    },
    {
      object: "block",
      type: "callout",
      callout: {
        rich_text: [{
          type: "text",
          text: { content: `Applied automatically from Brain Update Review — ${monthLabel}. Approved by Romain via Notion checkbox. Pending integration into the relevant sections during the next BRAIN-3B/3C/3D guided session.` },
        }],
        icon: { emoji: "✅" },
        color: "green_background",
      },
    },
  ];

  // Add each insight as a structured block
  for (const line of insightLines) {
    if (line.startsWith("\n### ")) {
      appendBlocks.push({
        object: "block",
        type: "heading_3",
        heading_3: { rich_text: [{ type: "text", text: { content: line.replace("\n### ", "") } }] },
      });
    } else if (line.startsWith("- ")) {
      appendBlocks.push({
        object: "block",
        type: "bulleted_list_item",
        bulleted_list_item: { rich_text: [{ type: "text", text: { content: line.slice(2) } }] },
      });
    } else if (line.trim()) {
      appendBlocks.push({
        object: "block",
        type: "paragraph",
        paragraph: { rich_text: [{ type: "text", text: { content: line } }] },
      });
    }
  }

  // Append source link
  appendBlocks.push({
    object: "block",
    type: "paragraph",
    paragraph: {
      rich_text: [{
        type: "text",
        text: { content: `Source: Brain Update Review — ${monthLabel}` },
      }],
    },
  });

  // Append to BRAIN-3D
  const appendRes = await fetch(`https://api.notion.com/v1/blocks/${brainPageId}/children`, {
    method: "PATCH",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Notion-Version": NOTION_VERSION,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ children: appendBlocks }),
  });

  if (!appendRes.ok) {
    console.error(`Failed to append to BRAIN-3D: ${appendRes.status} ${await appendRes.text()}`);
    return;
  }

  console.log(`✅ Applied ${insightLines.length} insight lines to BRAIN-3D for ${monthLabel}`);

  // Update the last-updated timestamp note on BRAIN-3D via its properties
  // (The Execution Notes field tracks updates)
  const updateNote = `Brain auto-update applied for ${monthLabel} on ${new Date().toISOString().slice(0, 10)}.`;
  await fetch(`https://api.notion.com/v1/pages/${brainPageId}`, {
    method: "PATCH",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Notion-Version": NOTION_VERSION,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      properties: {
        "Last Updated": { date: { start: new Date().toISOString().slice(0, 10) } },
      },
    }),
  }).catch(() => {
    // Silently ignore if the property update fails (BRAIN-3D is a task page, field may not exist)
    console.log("Note: could not update Last Updated property on BRAIN-3D (expected for task pages)");
  });

  void updateNote; // suppress unused warning
}

// ─── Main handlers ────────────────────────────────────────────────────────────

async function handleGenerateDelta(
  notionToken: string,
  anthropicKey: string,
  supabaseUrl: string,
  serviceKey: string,
  brainPageId: string,
  painPointsDbId: string,
  opportunitiesDbId: string,
  featuresDbId: string,
  sinceOverride?: string,
): Promise<Response> {
  // 1. Determine look-back date
  const sinceDate = sinceOverride ?? await getLastAppliedDate(supabaseUrl, serviceKey);
  const monthLabel = new Date().toISOString().slice(0, 7); // YYYY-MM

  console.log(`Generating brain delta for ${monthLabel}, since ${sinceDate}`);

  // 2. Check for duplicate — don't generate twice for the same month
  const existing = await fetch(
    `${supabaseUrl}/rest/v1/brain_update_reviews?month_label=eq.${monthLabel}&limit=1`,
    {
      headers: { "Authorization": `Bearer ${serviceKey}`, "apikey": serviceKey },
    },
  );
  if (existing.ok) {
    const existingData = await existing.json();
    if (Array.isArray(existingData) && existingData.length > 0) {
      return new Response(JSON.stringify({
        skipped: true,
        reason: `Brain update review for ${monthLabel} already exists`,
        existing_page_url: existingData[0].notion_page_url,
      }), {
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      });
    }
  }

  // 3. Fetch recent insights
  const insights = await fetchRecentInsights(
    notionToken, sinceDate, painPointsDbId, opportunitiesDbId, featuresDbId,
  );

  // 4. Fetch current BRAIN-3D content for comparison
  const brainContent = await fetchBrainContent(notionToken, brainPageId);

  // 5. Generate delta
  const delta = await generateDelta(anthropicKey, insights, brainContent, monthLabel);
  delta.sinceDate = sinceDate;

  // 6. Create review page as sub-page of BRAIN-3D
  const reviewPage = await createReviewPage(notionToken, brainPageId, delta);

  if (!reviewPage) {
    return new Response(JSON.stringify({ error: "Failed to create review page" }), {
      status: 500,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  // 7. Store review record
  await storeReviewRecord(supabaseUrl, serviceKey, {
    month_label: monthLabel,
    notion_page_id: reviewPage.pageId,
    notion_page_url: reviewPage.pageUrl,
    insights_count: delta.newInsights.length,
    status: "pending",
  });

  return new Response(JSON.stringify({
    success: true,
    month_label: monthLabel,
    since_date: sinceDate,
    insights_processed: delta.totalInsightsProcessed,
    new_insights: delta.newInsights.length,
    contradictions: delta.contradictions.length,
    already_covered: delta.alreadyCoveredCount,
    summary: delta.summary,
    review_page_url: reviewPage.pageUrl,
    message: `Brain Update Review for ${monthLabel} created. Open ${reviewPage.pageUrl} to review and check the approval box to apply.`,
  }), {
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
}

async function handleCheckApprovals(
  notionToken: string,
  anthropicKey: string,
  supabaseUrl: string,
  serviceKey: string,
  brainPageId: string,
): Promise<Response> {
  const pendingReviews = await getPendingReviews(supabaseUrl, serviceKey);
  console.log(`Checking ${pendingReviews.length} pending brain update reviews`);

  const applied: string[] = [];
  const stillPending: string[] = [];

  for (const review of pendingReviews) {
    const approved = await isApproved(notionToken, review.notion_page_id);

    if (approved) {
      console.log(`Review ${review.month_label} approved — applying delta to BRAIN-3D`);
      await applyDeltaToBrain(notionToken, anthropicKey, brainPageId, review.notion_page_id, review.month_label);
      await markReviewApplied(supabaseUrl, serviceKey, review.id);
      applied.push(review.month_label);
    } else {
      stillPending.push(review.month_label);
    }
  }

  return new Response(JSON.stringify({
    success: true,
    checked: pendingReviews.length,
    applied,
    still_pending: stillPending,
    message: applied.length > 0
      ? `Applied ${applied.length} brain update(s): ${applied.join(", ")}`
      : "No approved updates found. Check back after reviewing the pending Brain Update pages.",
  }), {
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
}

// ─── Deno.serve entry point ───────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: CORS_HEADERS });
  }

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "POST required" }), {
      status: 405,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  // Load environment variables
  const notionToken      = Deno.env.get("NOTION_TOKEN") ?? "";
  const anthropicKey     = Deno.env.get("ANTHROPIC_API_KEY") ?? "";
  const supabaseUrl      = Deno.env.get("SUPABASE_URL") ?? "";
  const serviceKey       = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  const brainPageId      = Deno.env.get("BRAIN_PAGE_ID") ?? DEFAULT_BRAIN_PAGE_ID;
  const painPointsDbId   = Deno.env.get("PAIN_POINTS_DB_ID") ?? DEFAULT_PAIN_POINTS_DB_ID;
  const opportunitiesDbId = Deno.env.get("OPPORTUNITIES_DB_ID") ?? DEFAULT_OPPORTUNITIES_DB_ID;
  const featuresDbId     = Deno.env.get("FEATURES_DB_ID") ?? DEFAULT_FEATURES_DB_ID;

  if (!notionToken) {
    return new Response(JSON.stringify({ error: "NOTION_TOKEN not set" }), {
      status: 500,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }
  if (!anthropicKey) {
    return new Response(JSON.stringify({ error: "ANTHROPIC_API_KEY not set" }), {
      status: 500,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  let body: Record<string, unknown> = {};
  try {
    const text = await req.text();
    if (text) body = JSON.parse(text);
  } catch { /* empty body is fine */ }

  try {
    if (body.check_approvals === true) {
      return await handleCheckApprovals(
        notionToken, anthropicKey, supabaseUrl, serviceKey, brainPageId,
      );
    }

    // Default: generate delta
    return await handleGenerateDelta(
      notionToken, anthropicKey, supabaseUrl, serviceKey, brainPageId,
      painPointsDbId, opportunitiesDbId, featuresDbId,
      typeof body.since === "string" ? body.since : undefined,
    );
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("brain-update unhandled error:", message);
    return new Response(JSON.stringify({ error: message }), {
      status: 500,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }
});
