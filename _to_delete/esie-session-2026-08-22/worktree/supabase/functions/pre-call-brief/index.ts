/**
 * pre-call-brief — Supabase Edge Function (HUMAN-7B)
 * ─────────────────────────────────────────────────────────────────────────────
 * Scheduled every 15 minutes via pg_cron.
 * Scans Google Calendar for meetings tagged 'ReloPass' or 'HR call' starting
 * in the next 30 minutes. For each match, generates an AI pre-call brief using
 * Claude Haiku (no PII — company name and role only) and creates a Notion page
 * in the Pre-Call Briefs section.
 *
 * Pipeline:
 *   1. Fetch upcoming calendar events (next 30-min lookahead window)
 *   2. Filter: event summary contains 'relopass' or 'hr call' (case-insensitive)
 *   3. Skip if brief already exists in Notion (deduplication by title)
 *   4. Extract company name from event title (no attendee PII)
 *   5. Fetch Company Brain context from Notion (BRAIN-3D page, Sections 3 + 6)
 *   6. Call Claude Haiku → 3+ talking points, 1+ anticipated objection
 *   7. Create Notion page with structured brief
 *
 * Environment variables:
 *   GOOGLE_CALENDAR_TOKEN    — OAuth 2.0 bearer token (Google Calendar API)
 *   ANTHROPIC_API_KEY        — Claude API key
 *   NOTION_TOKEN             — Notion integration secret
 *   NOTION_BRAIN_PAGE        — BRAIN-3D page ID (optional; falls back to hardcoded default)
 *   NOTION_BRIEFS_PARENT_ID  — Parent page ID for new Pre-Call Brief pages
 *                              (default: AI Work Queue overview page)
 * ─────────────────────────────────────────────────────────────────────────────
 */

// ─── Constants ────────────────────────────────────────────────────────────────

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
};

const NOTION_VERSION = "2022-06-28";

/** Default BRAIN-3D page ID — the master Company Brain document */
const DEFAULT_BRAIN_PAGE_ID = "369887c64d48818eb478f7298fd3063c";

/** Default parent for brief pages — AI Work Queue overview */
const DEFAULT_BRIEFS_PARENT_ID = "35c887c64d4881ac9b40eb253c86cf29";

/** Keywords that mark a calendar event as a pre-call brief candidate */
const BRIEF_TRIGGERS = ["relopass", "hr call", "hr demo", "mobility call", "relocation call"];

/** Lookahead window in minutes */
const LOOKAHEAD_MINUTES = 30;

// ─── Types ────────────────────────────────────────────────────────────────────

interface CalendarEvent {
  id: string;
  summary: string;          // event title
  description?: string;
  start: { dateTime?: string; date?: string };
  end: { dateTime?: string; date?: string };
  attendees?: Array<{ email: string; displayName?: string; organizer?: boolean }>;
  htmlLink?: string;
}

interface BriefInput {
  companyName: string;
  meetingTitle: string;
  meetingDate: string;       // ISO date string
  brainContext: string;      // excerpt from Company Brain
}

interface GeneratedBrief {
  quickContext: string;
  talkingPoints: string[];
  objections: Array<{ objection: string; response: string }>;
}

// ─── Google Calendar helpers ──────────────────────────────────────────────────

/**
 * Fetch events from the primary calendar starting in the next LOOKAHEAD_MINUTES.
 * Returns only events whose summary contains at least one BRIEF_TRIGGERS keyword.
 */
async function fetchUpcomingTaggedEvents(token: string): Promise<CalendarEvent[]> {
  const now = new Date();
  const timeMax = new Date(now.getTime() + LOOKAHEAD_MINUTES * 60 * 1000);

  const params = new URLSearchParams({
    timeMin: now.toISOString(),
    timeMax: timeMax.toISOString(),
    singleEvents: "true",
    orderBy: "startTime",
    maxResults: "20",
  });

  const res = await fetch(
    `https://www.googleapis.com/calendar/v3/calendars/primary/events?${params}`,
    {
      headers: { "Authorization": `Bearer ${token}` },
      signal: AbortSignal.timeout(8000),
    },
  );

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Google Calendar API error: ${res.status} ${err}`);
  }

  const data = await res.json() as { items?: CalendarEvent[] };
  const events = data.items ?? [];

  // Filter to events whose title contains a trigger keyword
  return events.filter((evt) => {
    const title = (evt.summary ?? "").toLowerCase();
    return BRIEF_TRIGGERS.some((kw) => title.includes(kw));
  });
}

/**
 * Derive a sanitised company name from the event title.
 * Strips trigger keywords and returns the remainder, or "Unknown Company".
 *
 * Examples:
 *   "ReloPass — Aurora Energy"     → "Aurora Energy"
 *   "HR call with Acme Corp"       → "Acme Corp"
 *   "ReloPass demo"                → "Unknown Company"
 */
function extractCompanyName(eventTitle: string): string {
  let title = eventTitle;

  // Remove leading/trailing trigger keywords and common prefixes
  const removePatterns = [
    /^relopass\s*(demo|call|meeting|discussion|intro|pitch|presentation)?\s*[:\-–—|]/i,
    /^(hr call|hr demo|mobility call|relocation call)\s*(with|:|-|–|—)?\s*/i,
    /^(call|demo|meeting|intro|pitch)\s*(with|at)?\s*/i,
  ];

  for (const pattern of removePatterns) {
    title = title.replace(pattern, "").trim();
  }

  // Also strip trailing noise like "(30 min)", "- zoom", etc.
  title = title.replace(/\s*[-–—|]\s*(zoom|teams|meet|google meet|video|call|30\s*min|60\s*min).*$/i, "").trim();
  title = title.replace(/\s*\(.*?\)\s*$/, "").trim();

  // If we stripped everything meaningful, return fallback
  if (!title || title.toLowerCase() === eventTitle.toLowerCase()) {
    return "Unknown Company";
  }

  return title;
}

// ─── Notion helpers ───────────────────────────────────────────────────────────

/**
 * Fetch a compact excerpt from the Company Brain page.
 * Extracts the HR Buyer Personas section (Section 3) and Operating Principles
 * (Section 6) — the most relevant for a sales pre-call brief.
 */
async function fetchBrainContext(token: string, brainPageId: string): Promise<string> {
  const FALLBACK = `
ReloPass is an AI-powered global mobility platform for HR teams at mid-size companies (200–2,000 employees).
Core buyers: Stretched HR Director, Head of Global Mobility, CHRO, HR Ops Manager.
Key pains: relocation firefighting, spreadsheet coordination, compliance risk, no visibility.
Value prop: Relocation without the firefighting — HR sets up the case, employees self-service, suppliers get structured briefs.
Operating principle: Professional-but-warm communication, human review on all high-stakes actions.
`.trim();

  try {
    const res = await fetch(`https://api.notion.com/v1/blocks/${brainPageId}/children?page_size=100`, {
      headers: {
        "Authorization": `Bearer ${token}`,
        "Notion-Version": NOTION_VERSION,
      },
      signal: AbortSignal.timeout(6000),
    });

    if (!res.ok) return FALLBACK;

    const data = await res.json() as { results?: Array<Record<string, unknown>> };
    const blocks = data.results ?? [];

    // Extract text content from blocks, focus on sections 3 and 6
    const excerpts: string[] = [];
    let inTargetSection = false;
    let charCount = 0;
    const MAX_CHARS = 1500;

    for (const block of blocks) {
      if (charCount >= MAX_CHARS) break;

      const type = block.type as string;

      // Detect section headings
      if (type === "heading_2" || type === "heading_1") {
        const heading = extractBlockText(block);
        const lower = heading.toLowerCase();
        inTargetSection = lower.includes("buyer persona") || lower.includes("operating principle") || lower.includes("quick context");
        if (inTargetSection) excerpts.push(`\n### ${heading}`);
        continue;
      }

      if (!inTargetSection) continue;

      const text = extractBlockText(block);
      if (text) {
        excerpts.push(text);
        charCount += text.length;
      }
    }

    const result = excerpts.join("\n").trim();
    return result.length > 100 ? result : FALLBACK;

  } catch {
    return FALLBACK;
  }
}

function extractBlockText(block: Record<string, unknown>): string {
  const type = block.type as string;
  const content = block[type] as Record<string, unknown> | undefined;
  if (!content) return "";

  const richText = content.rich_text as Array<{ plain_text?: string }> | undefined;
  if (!richText) return "";

  return richText.map((rt) => rt.plain_text ?? "").join("").trim();
}

/**
 * Check if a brief for this event already exists in Notion.
 * Searches by title prefix to avoid generating duplicate briefs.
 */
async function briefAlreadyExists(
  token: string,
  parentId: string,
  briefTitle: string,
): Promise<boolean> {
  try {
    const res = await fetch("https://api.notion.com/v1/search", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: briefTitle,
        filter: { value: "page", property: "object" },
        page_size: 5,
      }),
      signal: AbortSignal.timeout(5000),
    });

    if (!res.ok) return false;

    const data = await res.json() as { results: Array<{ properties?: Record<string, unknown> }> };
    const results = data.results ?? [];

    // Check for an exact title match
    return results.some((page) => {
      const titleProp = page.properties?.title ?? page.properties?.["Task Title"];
      if (!titleProp) return false;
      const titlePropTyped = titleProp as Record<string, unknown>;
      const titleArr = (titlePropTyped.title ?? []) as Array<{ plain_text?: string }>;
      const title = titleArr.map((t) => t.plain_text ?? "").join("");
      return title === briefTitle;
    });
  } catch {
    return false;  // If check fails, proceed with creation (better a duplicate than missing a brief)
  }
}

/**
 * Create a Pre-Call Brief page in Notion under the specified parent.
 */
async function createBriefPage(
  token: string,
  parentId: string,
  briefTitle: string,
  input: BriefInput,
  brief: GeneratedBrief,
  eventLink?: string,
): Promise<string | null> {
  const talkingPointsText = brief.talkingPoints
    .map((pt, i) => `${i + 1}. ${pt}`)
    .join("\n");

  const objectionsText = brief.objections
    .map((o) => `**${o.objection}** → ${o.response}`)
    .join("\n\n");

  const bodyBlocks = [
    // Metadata callout
    {
      object: "block", type: "callout",
      callout: {
        icon: { type: "emoji", emoji: "📋" },
        color: "blue_background",
        rich_text: [{
          type: "text",
          text: { content: `Meeting: ${input.meetingTitle}\nDate: ${input.meetingDate}${eventLink ? `\nCalendar: ${eventLink}` : ""}` },
        }],
      },
    },
    // Section: Quick Context
    {
      object: "block", type: "heading_2",
      heading_2: { rich_text: [{ type: "text", text: { content: "Quick Context" } }] },
    },
    {
      object: "block", type: "paragraph",
      paragraph: { rich_text: [{ type: "text", text: { content: brief.quickContext } }] },
    },
    // Section: Suggested Talking Points
    {
      object: "block", type: "heading_2",
      heading_2: { rich_text: [{ type: "text", text: { content: "Suggested Talking Points" } }] },
    },
    {
      object: "block", type: "paragraph",
      paragraph: { rich_text: [{ type: "text", text: { content: talkingPointsText } }] },
    },
    // Section: Key Objections to Anticipate
    {
      object: "block", type: "heading_2",
      heading_2: { rich_text: [{ type: "text", text: { content: "Key Objections to Anticipate" } }] },
    },
    {
      object: "block", type: "paragraph",
      paragraph: { rich_text: [{ type: "text", text: { content: objectionsText } }] },
    },
    // Footer divider
    { object: "block", type: "divider", divider: {} },
    {
      object: "block", type: "paragraph",
      paragraph: {
        rich_text: [{
          type: "text",
          text: { content: `Generated by ReloPass AI · ${new Date().toISOString().slice(0, 16)} UTC` },
          annotations: { color: "gray" },
        }],
      },
    },
  ];

  try {
    const res = await fetch("https://api.notion.com/v1/pages", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        parent: { page_id: parentId },
        icon: { type: "emoji", emoji: "📞" },
        properties: {
          title: { title: [{ text: { content: briefTitle } }] },
        },
        children: bodyBlocks,
      }),
      signal: AbortSignal.timeout(10000),
    });

    if (!res.ok) {
      const err = await res.text();
      console.error(`pre-call-brief: Notion page creation failed: ${res.status} ${err}`);
      return null;
    }

    const data = await res.json() as { id: string; url: string };
    console.log(`pre-call-brief: created brief page ${data.id} — ${data.url}`);
    return data.id;

  } catch (e) {
    console.error("pre-call-brief: Notion error:", e instanceof Error ? e.message : String(e));
    return null;
  }
}

// ─── Claude Haiku helpers ─────────────────────────────────────────────────────

const SYSTEM_PROMPT = (brainContext: string) => `
You are a sales preparation assistant for Romain Lecomte, founder of ReloPass.
ReloPass is an AI-powered global mobility platform for HR teams at mid-size companies.

Company Brain context (use this to tailor your talking points):
${brainContext}

Your job: generate a concise, high-quality pre-call brief for an upcoming HR sales call.
- NEVER include personal names, email addresses, or other PII in your response.
- Use only the company name and the meeting title as identifiers.
- Format your response as valid JSON matching this exact schema:
{
  "quickContext": "2-3 sentences: what type of company this likely is, which buyer persona they match, and the likely trigger for this conversation",
  "talkingPoints": ["point 1", "point 2", "point 3"],
  "objections": [
    {"objection": "objection text", "response": "suggested response"},
    {"objection": "objection text 2", "response": "suggested response 2"}
  ]
}
`.trim();

async function generateBrief(
  apiKey: string,
  input: BriefInput,
): Promise<GeneratedBrief> {
  const userMessage = `
Generate a pre-call brief for the following meeting:
Company: ${input.companyName}
Meeting title: ${input.meetingTitle}
Date: ${input.meetingDate}

Produce 3-4 specific, actionable talking points tailored to this company type.
Anticipate 1-2 objections Romain is likely to face and provide concise responses.
`.trim();

  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: "claude-haiku-4-5-20251001",
      max_tokens: 800,
      temperature: 0.3,
      system: SYSTEM_PROMPT(input.brainContext),
      messages: [{ role: "user", content: userMessage }],
    }),
    signal: AbortSignal.timeout(15000),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Anthropic API error: ${res.status} ${err}`);
  }

  const data = await res.json();
  const raw = (data.content ?? [])
    .filter((b: { type: string }) => b.type === "text")
    .map((b: { text: string }) => b.text)
    .join("")
    .trim();

  // Extract JSON from the response (may be wrapped in markdown code block)
  const jsonMatch = raw.match(/```(?:json)?\s*([\s\S]*?)```/) ?? raw.match(/(\{[\s\S]*\})/);
  const jsonStr = jsonMatch ? jsonMatch[1].trim() : raw;

  try {
    const parsed = JSON.parse(jsonStr) as {
      quickContext?: string;
      talkingPoints?: string[];
      objections?: Array<{ objection?: string; response?: string }>;
    };

    return {
      quickContext: parsed.quickContext ?? "Context not available.",
      talkingPoints: (parsed.talkingPoints ?? []).filter(Boolean),
      objections: (parsed.objections ?? []).map((o) => ({
        objection: o.objection ?? "Objection",
        response: o.response ?? "Response",
      })),
    };
  } catch {
    // Fallback: treat raw as plain text and extract manually
    const lines = raw.split("\n").filter((l: string) => l.trim().startsWith("-") || /^\d+\./.test(l.trim()));
    return {
      quickContext: "AI-generated context (parsing failed — review raw output).",
      talkingPoints: lines.slice(0, 4).map((l: string) => l.replace(/^[-\d.]\s*/, "").trim()).filter(Boolean),
      objections: [{ objection: "Why do we need a dedicated tool?", response: "See Company Brain Section 6 for brand voice guidance." }],
    };
  }
}

// ─── Edge Function handler ────────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS_HEADERS });

  const calendarToken  = Deno.env.get("GOOGLE_CALENDAR_TOKEN");
  const anthropicKey   = Deno.env.get("ANTHROPIC_API_KEY");
  const notionToken    = Deno.env.get("NOTION_TOKEN");
  const brainPageId    = Deno.env.get("NOTION_BRAIN_PAGE") ?? DEFAULT_BRAIN_PAGE_ID;
  const briefsParentId = Deno.env.get("NOTION_BRIEFS_PARENT_ID") ?? DEFAULT_BRIEFS_PARENT_ID;

  // Required env var checks
  if (!calendarToken) {
    return Response.json(
      { ok: false, error: "GOOGLE_CALENDAR_TOKEN is required — set this in Supabase vault" },
      { status: 500, headers: CORS_HEADERS },
    );
  }
  if (!anthropicKey) {
    return Response.json({ ok: false, error: "ANTHROPIC_API_KEY is required" }, { status: 500, headers: CORS_HEADERS });
  }
  if (!notionToken) {
    return Response.json({ ok: false, error: "NOTION_TOKEN is required" }, { status: 500, headers: CORS_HEADERS });
  }

  console.log(`pre-call-brief: scanning calendar, lookahead=${LOOKAHEAD_MINUTES}min, brainPage=${brainPageId}`);

  const results: Array<{ event: string; company: string; briefId: string | null; skipped?: string }> = [];

  try {
    // ── 1. Fetch tagged calendar events ──────────────────────────────────────
    let taggedEvents: CalendarEvent[] = [];
    try {
      taggedEvents = await fetchUpcomingTaggedEvents(calendarToken);
      console.log(`pre-call-brief: found ${taggedEvents.length} tagged event(s)`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error("pre-call-brief: calendar fetch failed:", msg);
      return Response.json(
        { ok: false, error: `Google Calendar error: ${msg}` },
        { status: 502, headers: CORS_HEADERS },
      );
    }

    if (taggedEvents.length === 0) {
      return Response.json(
        { ok: true, message: "No tagged meetings in the next 30 minutes.", briefs_generated: 0 },
        { headers: CORS_HEADERS },
      );
    }

    // ── 2. Fetch Company Brain context once (shared across all briefs) ────────
    const brainContext = await fetchBrainContext(notionToken, brainPageId);
    console.log(`pre-call-brief: brain context loaded (${brainContext.length} chars)`);

    // ── 3. Process each tagged event ─────────────────────────────────────────
    for (const event of taggedEvents) {
      const companyName = extractCompanyName(event.summary ?? "");
      const meetingDate = (event.start.dateTime ?? event.start.date ?? new Date().toISOString()).slice(0, 16);
      const briefTitle  = `Pre-Call Brief: ${companyName} — ${meetingDate.slice(0, 10)}`;

      console.log(`pre-call-brief: processing "${event.summary}" → company="${companyName}"`);

      // ── 3a. Deduplication ─────────────────────────────────────────────────
      const exists = await briefAlreadyExists(notionToken, briefsParentId, briefTitle);
      if (exists) {
        console.log(`pre-call-brief: brief already exists for "${briefTitle}", skipping`);
        results.push({ event: event.summary, company: companyName, briefId: null, skipped: "duplicate" });
        continue;
      }

      // ── 3b. Generate brief with Claude Haiku ─────────────────────────────
      let brief: GeneratedBrief;
      try {
        brief = await generateBrief(anthropicKey, {
          companyName,
          meetingTitle: event.summary,
          meetingDate,
          brainContext,
        });
        console.log(`pre-call-brief: generated ${brief.talkingPoints.length} talking points for "${companyName}"`);
      } catch (err) {
        console.error(`pre-call-brief: Haiku error for "${companyName}":`, err instanceof Error ? err.message : String(err));
        results.push({ event: event.summary, company: companyName, briefId: null, skipped: "ai_error" });
        continue;
      }

      // ── 3c. Create Notion page ────────────────────────────────────────────
      const briefId = await createBriefPage(
        notionToken,
        briefsParentId,
        briefTitle,
        { companyName, meetingTitle: event.summary, meetingDate, brainContext },
        brief,
        event.htmlLink,
      );

      results.push({ event: event.summary, company: companyName, briefId });
    }

    const generated = results.filter((r) => r.briefId !== null).length;
    const skipped   = results.filter((r) => r.briefId === null).length;

    console.log(`pre-call-brief: complete — ${generated} generated, ${skipped} skipped`);

    return Response.json(
      {
        ok: true,
        briefs_generated: generated,
        briefs_skipped: skipped,
        lookahead_minutes: LOOKAHEAD_MINUTES,
        results,
      },
      { headers: CORS_HEADERS },
    );

  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("pre-call-brief: unexpected error:", message);
    return Response.json({ ok: false, error: message }, { status: 500, headers: CORS_HEADERS });
  }
});
