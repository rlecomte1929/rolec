/**
 * autofix-pipeline — Supabase Edge Function (DEV-LOOP-2C)
 * ─────────────────────────────────────────────────────────────────────────────
 * Scheduled at 01:00 UTC daily via pg_cron + pg_net.
 * See migration: 20260524000003_autofix_pipeline_cron.sql
 *
 * This is a self-contained Deno version of the pipeline.
 * It mirrors the logic in lib/autofix-pipeline.ts but avoids relative imports
 * outside the supabase/functions directory.
 *
 * Environment variables (set in Supabase vault):
 *   ANTHROPIC_API_KEY    — Claude API key
 *   GITHUB_TOKEN         — GitHub personal access token
 *   GITHUB_OWNER         — Repo owner
 *   GITHUB_REPO          — Repo name
 *   NOTION_TOKEN         — Notion integration secret
 *   NOTION_DATABASE_ID   — AI Work Queue database ID (75d7ed78-91f4-46b6-b805-12e43abbecce)
 * ─────────────────────────────────────────────────────────────────────────────
 */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
};

// ─── Sensitive keyword blocklist (mirrors autofix-blocklist.ts) ───────────────

const SAFETY_KEYWORDS = [
  "authentication", "auth bypass", "jwt", "json web token", "session token",
  "session cookie", "session", "login", "logout", "sign-in", "sign in",
  "sign out", "sign-out", "sso", "oauth", "saml", "mfa", "2fa", "two-factor",
  "single sign", "password", "passwd", "credential", "api key", "apikey",
  "api_key", "secret key", "access key", "private key", "token",
  "billing", "charge", "payment", "invoice", "subscription", "stripe",
  "webhook", "price", "pricing", "plan upgrade", "plan downgrade", "refund",
  "migration", "schema change", "schema migration", "alter table", "drop table",
  "drop column", "add column", "foreign key", "constraint", "supabase db push",
  "pii", "gdpr", "personal data", "personally identifiable", "email address",
  "phone number", "passport", "date of birth", "home address", "bank account",
  "credit card", "social security", "sql injection", "xss", "csrf",
  "cross-site", "security vulnerability", "vulnerability", "exploit",
  "privilege escalation", "admin bypass", "access control", "rbac",
  "unauthorized access", "unauthenticated", "encryption", "decryption",
  "certificate", "ssl", "tls", "race condition", "deadlock", "data integrity",
];

const BLOCKED_PATH_PATTERNS = [
  /^.*\/auth\//i, /^auth\//i, /^.*\/authenticate/i, /^.*\/authoriz/i,
  /^.*\/token/i, /^.*\/session/i, /^.*\/cookie/i, /^.*\/jwt/i, /^.*\/oauth/i,
  /^.*\/secret/i, /^.*\/credential/i, /^.*\/password/i, /^.*\/passwd/i,
  /^.*\/api[-_]key/i, /^.*\/apikey/i, /^.*\/\.env/i,
  /^.*\/billing/i, /^.*\/payment/i, /^.*\/invoice/i, /^.*\/subscription/i,
  /^.*\/stripe[-_/]/i, /^.*\/charge/i, /^.*\/webhook/i,
  /^.*\/migrations\//i, /^.*\/migration/i, /^.*\/schema/i,
  /^.*\/pii/i, /^.*\/gdpr/i, /^.*\/personal[-_]data/i,
  /^.*\/permission/i, /^.*\/rbac/i, /^.*\/acl/i, /^.*\/encrypt/i,
  /^.*\/decrypt/i, /^.*\/hash/i, /^.*\/certificate/i, /^.*\/crypto/i,
  /^.*\/deploy/i, /^.*\/infra/i, /^.*\/terraform/i, /^.*\/\.github\//i,
  /^.*\/cron/i,
];

function isBlockedPath(filePath: string): boolean {
  const norm = filePath.replace(/\\/g, "/").replace(/^\.\//, "").replace(/^\//, "");
  return BLOCKED_PATH_PATTERNS.some((p) => p.test(norm));
}

function checkKeywordSafety(text: string): { safe: boolean; keyword?: string } {
  const lower = text.toLowerCase();
  for (const kw of SAFETY_KEYWORDS) {
    if (lower.includes(kw)) return { safe: false, keyword: kw };
  }
  return { safe: true };
}

// ─── Claude helpers ───────────────────────────────────────────────────────────

async function callClaude(system: string, user: string, maxTokens: number, apiKey: string): Promise<string> {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: "claude-haiku-4-5-20251001",
      max_tokens: maxTokens,
      system,
      messages: [{ role: "user", content: user }],
    }),
  });
  if (!res.ok) throw new Error(`Claude error ${res.status}: ${await res.text()}`);
  const data = await res.json();
  return data?.content?.[0]?.text?.trim() ?? "";
}

function parseJson<T>(raw: string, fallback: T): T {
  const cleaned = raw.replace(/^```(?:json)?\n?/m, "").replace(/\n?```$/m, "").trim();
  try { return JSON.parse(cleaned) as T; } catch { return fallback; }
}

// ─── Notion helpers ───────────────────────────────────────────────────────────

async function fetchReadyBugs(token: string, dbId: string, max: number) {
  const body = {
    page_size: max,
    filter: {
      and: [
        { property: "Status", select: { equals: "Ready for AI" } },
        {
          or: [
            { property: "Estimated Complexity", select: { equals: "Trivial" } },
            { property: "Estimated Complexity", select: { equals: "Low" } },
          ],
        },
      ],
    },
    sorts: [{ property: "Priority", direction: "ascending" }],
  };

  const res = await fetch(`https://api.notion.com/v1/databases/${dbId}/query`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Notion-Version": "2022-06-28",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) throw new Error(`Notion query failed: ${res.status}`);
  const data = await res.json();

  return (data.results ?? []).map((page: Record<string, unknown>) => {
    const props = (page.properties ?? {}) as Record<string, Record<string, unknown>>;
    const title = ((props["Task Title"]?.title ?? props["title"]?.title ?? []) as Array<{ plain_text: string }>)
      .map((t) => t.plain_text).join("");
    const desc = ((props["Description"]?.rich_text ?? []) as Array<{ plain_text: string }>)
      .map((t) => t.plain_text).join("");
    return { notionId: page.id as string, title, description: desc, notionUrl: page.url as string };
  }).filter((t: { title: string }) => t.title.length > 0);
}

// Fetch a single Work Queue task by page id — the on-demand path used when an admin
// clicks "Auto-attempt" in the Feedback console (bypasses the Ready-for-AI batch filter).
async function fetchTaskById(token: string, pageId: string) {
  const res = await fetch(`https://api.notion.com/v1/pages/${pageId}`, {
    headers: {
      "Authorization": `Bearer ${token}`,
      "Notion-Version": "2022-06-28",
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) throw new Error(`Notion page fetch failed: ${res.status}`);
  const page = await res.json();
  const props = (page.properties ?? {}) as Record<string, Record<string, unknown>>;
  const title = ((props["fable"]?.title ?? props["Task Title"]?.title ?? props["title"]?.title ?? []) as Array<{ plain_text: string }>)
    .map((t) => t.plain_text).join("");
  const desc = ((props["Expected Output"]?.rich_text ?? props["Description"]?.rich_text ?? []) as Array<{ plain_text: string }>)
    .map((t) => t.plain_text).join("");
  return { notionId: page.id as string, title, description: desc, notionUrl: page.url as string };
}

async function updateNotionTask(id: string, status: string, notes: string, token: string) {
  await fetch(`https://api.notion.com/v1/pages/${id}`, {
    method: "PATCH",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Notion-Version": "2022-06-28",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      properties: {
        Status: { select: { name: status } },
        "Execution Notes": { rich_text: [{ type: "text", text: { content: notes.slice(0, 2000) } }] },
      },
    }),
  });
}

// ─── GitHub helpers ───────────────────────────────────────────────────────────

const GH = "https://api.github.com";

function ghHeaders(token: string) {
  return {
    "Authorization": `Bearer ${token}`,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Content-Type": "application/json",
  };
}

async function ghGet<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${GH}${path}`, { headers: ghHeaders(token) });
  if (!res.ok) throw new Error(`GitHub GET ${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

async function ghPost<T>(path: string, body: unknown, token: string): Promise<T> {
  const res = await fetch(`${GH}${path}`, { method: "POST", headers: ghHeaders(token), body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`GitHub POST ${path}: ${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

async function ghPut<T>(path: string, body: unknown, token: string): Promise<T> {
  const res = await fetch(`${GH}${path}`, { method: "PUT", headers: ghHeaders(token), body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`GitHub PUT ${path}: ${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

// ─── Pipeline processing ──────────────────────────────────────────────────────

interface Env {
  anthropicKey: string;
  githubToken: string;
  githubOwner: string;
  githubRepo: string;
  notionToken: string;
  notionDbId: string;
  baseBranch: string;
  dryRun: boolean;
}

async function processBug(bug: { notionId: string; title: string; description: string; notionUrl: string }, env: Env) {
  const log = (msg: string) => console.log(`  [${bug.notionId.slice(0, 8)}] ${msg}`);

  // Mark as in progress immediately
  await updateNotionTask(bug.notionId, "AI in Progress",
    `Pipeline started at ${new Date().toISOString()}`, env.notionToken);

  // 1. Classifier via Claude Haiku
  const classifySystem = `You are a conservative bug-triage AI. Decide if a bug can be safely auto-fixed without human review.
AUTO-FIXABLE: copy typos, wrong labels, broken links, CSS layout, null-checks, missing static data only.
NOT AUTO-FIXABLE: auth, tokens, billing, payments, schema, migrations, PII, GDPR, security, unclear root cause.
Respond ONLY with JSON: {"auto_fixable": true|false, "fix_category": "copy"|"link"|"css"|"null-check"|"static-content"|"not-fixable", "reason": "one sentence"}`;
  const classifyUser = `Bug: ${bug.title}\n\n${bug.description}`;
  const classifyRaw = await callClaude(classifySystem, classifyUser, 200, env.anthropicKey);
  const classification = parseJson(classifyRaw, { auto_fixable: false, fix_category: "not-fixable", reason: "parse error" });

  if (!classification.auto_fixable) {
    const reason = `Classifier: ${classification.fix_category} — ${classification.reason}`;
    log(reason);
    await updateNotionTask(bug.notionId, "Ready for AI", reason, env.notionToken);
    return { outcome: "skipped_classifier", reason };
  }

  // 2. Keyword safety check
  const safety = checkKeywordSafety(`${bug.title}\n${bug.description}`);
  if (!safety.safe) {
    const reason = `Blocklist: matched keyword "${safety.keyword}"`;
    log(reason);
    await updateNotionTask(bug.notionId, "Ready for AI", reason, env.notionToken);
    return { outcome: "skipped_blocklist", reason };
  }

  // 3. Identify file
  const fileSystem = `You are a ReloPass Next.js/TypeScript codebase expert. Given a bug, return the most likely file path to fix.
Key dirs: frontend/src/components/, frontend/src/pages/, frontend/src/constants/, frontend/src/styles/, lib/
Respond ONLY with JSON: {"file_path": "path/to/file.tsx"|null, "reasoning": "one sentence"}`;
  const fileUser = `Bug: ${bug.title}\n${bug.description}`;
  const fileRaw = await callClaude(fileSystem, fileUser, 256, env.anthropicKey);
  const identified = parseJson<{ file_path: string | null; reasoning: string }>(
    fileRaw, { file_path: null, reasoning: fileRaw.slice(0, 100) }
  );

  if (!identified.file_path) {
    const reason = `Could not identify file: ${identified.reasoning}`;
    log(reason);
    await updateNotionTask(bug.notionId, "Ready for AI", reason, env.notionToken);
    return { outcome: "skipped_no_file", reason };
  }

  // 4. Path safety check
  if (isBlockedPath(identified.file_path)) {
    const reason = `Blocked path: "${identified.file_path}"`;
    log(reason);
    await updateNotionTask(bug.notionId, "Ready for AI", reason, env.notionToken);
    return { outcome: "skipped_blocklist", reason };
  }

  if (env.dryRun) {
    const reason = `[DRY RUN] Would fix: ${identified.file_path}`;
    log(reason);
    await updateNotionTask(bug.notionId, "Ready for AI", reason, env.notionToken);
    return { outcome: "skipped_dry_run", reason };
  }

  // 5. Fetch file content from GitHub
  const { owner, repo } = { owner: env.githubOwner, repo: env.githubRepo };
  const fileData = await ghGet<{ content: string; sha: string; size: number }>(
    `/repos/${owner}/${repo}/contents/${identified.file_path}?ref=${env.baseBranch}`,
    env.githubToken,
  ).catch(() => null);

  if (!fileData) {
    const reason = `File not found in repo: ${identified.file_path}`;
    log(reason);
    await updateNotionTask(bug.notionId, "Ready for AI", reason, env.notionToken);
    return { outcome: "skipped_no_file", reason };
  }

  if (fileData.size > 50000) {
    const reason = `File too large: ${fileData.size} bytes`;
    log(reason);
    await updateNotionTask(bug.notionId, "Ready for AI", reason, env.notionToken);
    return { outcome: "skipped_no_fix", reason };
  }

  const fileContent = new TextDecoder().decode(
    Uint8Array.from(atob(fileData.content.replace(/\n/g, "")), (c) => c.charCodeAt(0))
  );

  // 6. Generate fix
  const maxLen = 12000;
  const truncated = fileContent.length > maxLen
    ? fileContent.slice(0, maxLen) + "\n// ... [truncated]"
    : fileContent;

  const fixSystem = `You are a ReloPass codebase expert. Make a MINIMAL fix. Only change what is needed. Preserve all existing code.
Respond ONLY with JSON: {"fixed_content": "...complete corrected file...", "diff_summary": "one sentence: what changed"}
If you cannot generate a safe fix: {"fixed_content": null, "diff_summary": "reason"}`;
  const fixUser = `Bug: ${bug.title}\n${bug.description}\n\nFile ${identified.file_path}:\n\`\`\`\n${truncated}\n\`\`\``;
  const fixRaw = await callClaude(fixSystem, fixUser, 4096, env.anthropicKey);
  const fix = parseJson<{ fixed_content: string | null; diff_summary: string }>(
    fixRaw, { fixed_content: null, diff_summary: fixRaw.slice(0, 200) }
  );

  if (!fix.fixed_content || fix.fixed_content.trim() === fileContent.trim()) {
    const reason = `Fix generation failed: ${fix.diff_summary}`;
    log(reason);
    await updateNotionTask(bug.notionId, "Ready for AI", reason, env.notionToken);
    return { outcome: "skipped_no_fix", reason };
  }

  // 7. Open-PR dedup — skip if an open autofix PR already exists for this task, so the same
  // bug never fans out into a second PR → CI run → deploy. (The branch-create below would 422
  // on an existing branch anyway; this makes the skip explicit + cheap.)
  const branchName = `autofix/bug-${bug.notionId.replace(/-/g, "").slice(0, 16)}`;
  const openPrs = await ghGet<Array<{ html_url: string }>>(
    `/repos/${owner}/${repo}/pulls?state=open&head=${owner}:${branchName}`, env.githubToken
  );
  if (Array.isArray(openPrs) && openPrs.length > 0) {
    const reason = `Skipped: open autofix PR already exists (${openPrs[0].html_url})`;
    log(reason);
    return { outcome: "skipped_duplicate_pr", reason };
  }

  // 8. Create branch
  const baseSha = await ghGet<{ object: { sha: string } }>(
    `/repos/${owner}/${repo}/git/refs/heads/${env.baseBranch}`, env.githubToken
  );
  await ghPost(`/repos/${owner}/${repo}/git/refs`,
    { ref: `refs/heads/${branchName}`, sha: baseSha.object.sha }, env.githubToken);

  // 8. Commit fix
  const encoded = btoa(unescape(encodeURIComponent(fix.fixed_content)));
  await ghPut(`/repos/${owner}/${repo}/contents/${identified.file_path}`, {
    message: `fix: ${bug.title.slice(0, 72)}\n\n${fix.diff_summary}\n\nNotion: ${bug.notionUrl}`,
    content: encoded,
    sha: fileData.sha,
    branch: branchName,
  }, env.githubToken);

  // 9. Open draft PR
  const pr = await ghPost<{ html_url: string }>(`/repos/${owner}/${repo}/pulls`, {
    title: `fix: ${bug.title.slice(0, 72)}`,
    head: branchName,
    base: env.baseBranch,
    body: `## Auto-fix: ${bug.title}\n\n**Notion:** ${bug.notionUrl}\n**File:** \`${identified.file_path}\`\n**Change:** ${fix.diff_summary}\n\n---\n*Auto-generated by ReloPass autofix-pipeline. Requires human review.*`,
    draft: true,
  }, env.githubToken);

  // 10. Update Notion
  await updateNotionTask(bug.notionId, "Human Review",
    `Auto-fix PR created: ${pr.html_url}\nFile: ${identified.file_path}\nChange: ${fix.diff_summary}`,
    env.notionToken);

  log(`✅ Fixed → PR: ${pr.html_url}`);
  return { outcome: "fixed", prUrl: pr.html_url, branchName, fixedFile: identified.file_path, reason: fix.diff_summary };
}

// ─── Mission Control P2: single-demand dispatch (no Notion) ───────────────────
// Additive — reuses the same helpers + safety gates as processBug, but fixes ONE
// work_item dispatched from the admin console instead of a Notion bug. The branch
// keeps the autofix/bug-<hex> shape so autofix-validate.yml runs (E2E → merge →
// deploy). Leaves the nightly Notion path above completely untouched.
async function processWorkItem(wi: { id: string; title: string; body: string }, env: Env) {
  const log = (msg: string) => console.log(`  [wi:${wi.id.slice(0, 8)}] ${msg}`);
  const { owner, repo } = { owner: env.githubOwner, repo: env.githubRepo };

  // 1. Classify (conservative, same prompt as the nightly path)
  const classifySystem = `You are a conservative bug-triage AI. Decide if a bug can be safely auto-fixed without human review.
AUTO-FIXABLE: copy typos, wrong labels, broken links, CSS layout, null-checks, missing static data only.
NOT AUTO-FIXABLE: auth, tokens, billing, payments, schema, migrations, PII, GDPR, security, unclear root cause.
Respond ONLY with JSON: {"auto_fixable": true|false, "fix_category": "copy"|"link"|"css"|"null-check"|"static-content"|"not-fixable", "reason": "one sentence"}`;
  const classification = parseJson(
    await callClaude(classifySystem, `Bug: ${wi.title}\n\n${wi.body}`, 200, env.anthropicKey),
    { auto_fixable: false, fix_category: "not-fixable", reason: "parse error" },
  );
  if (!classification.auto_fixable) return { outcome: "skipped_classifier", reason: classification.reason };

  // 2. Keyword safety
  const safety = checkKeywordSafety(`${wi.title}\n${wi.body}`);
  if (!safety.safe) return { outcome: "skipped_blocklist", reason: `matched keyword "${safety.keyword}"` };

  // 3. Identify file
  const fileSystem = `You are a ReloPass Next.js/TypeScript codebase expert. Given a bug, return the most likely file path to fix.
Key dirs: frontend/src/components/, frontend/src/pages/, frontend/src/constants/, frontend/src/styles/, lib/
Respond ONLY with JSON: {"file_path": "path/to/file.tsx"|null, "reasoning": "one sentence"}`;
  const identified = parseJson<{ file_path: string | null; reasoning: string }>(
    await callClaude(fileSystem, `Bug: ${wi.title}\n${wi.body}`, 256, env.anthropicKey),
    { file_path: null, reasoning: "no file" },
  );
  if (!identified.file_path) return { outcome: "skipped_no_file", reason: identified.reasoning };

  // 4. Path safety + dry-run
  if (isBlockedPath(identified.file_path)) return { outcome: "skipped_blocklist", reason: `blocked path "${identified.file_path}"` };
  if (env.dryRun) return { outcome: "skipped_dry_run", reason: `[DRY RUN] would fix ${identified.file_path}` };

  // 5. Fetch file
  const fileData = await ghGet<{ content: string; sha: string; size: number }>(
    `/repos/${owner}/${repo}/contents/${identified.file_path}?ref=${env.baseBranch}`, env.githubToken,
  ).catch(() => null);
  if (!fileData) return { outcome: "skipped_no_file", reason: `not in repo: ${identified.file_path}` };
  if (fileData.size > 50000) return { outcome: "skipped_no_fix", reason: `file too large: ${fileData.size}` };
  const fileContent = new TextDecoder().decode(
    Uint8Array.from(atob(fileData.content.replace(/\n/g, "")), (c) => c.charCodeAt(0)),
  );

  // 6. Generate minimal fix
  const maxLen = 12000;
  const truncated = fileContent.length > maxLen ? fileContent.slice(0, maxLen) + "\n// ... [truncated]" : fileContent;
  const fixSystem = `You are a ReloPass codebase expert. Make a MINIMAL fix. Only change what is needed. Preserve all existing code.
Respond ONLY with JSON: {"fixed_content": "...complete corrected file...", "diff_summary": "one sentence: what changed"}
If you cannot generate a safe fix: {"fixed_content": null, "diff_summary": "reason"}`;
  const fix = parseJson<{ fixed_content: string | null; diff_summary: string }>(
    await callClaude(fixSystem, `Bug: ${wi.title}\n${wi.body}\n\nFile ${identified.file_path}:\n\`\`\`\n${truncated}\n\`\`\``, 4096, env.anthropicKey),
    { fixed_content: null, diff_summary: "fix error" },
  );
  if (!fix.fixed_content || fix.fixed_content.trim() === fileContent.trim()) {
    return { outcome: "skipped_no_fix", reason: fix.diff_summary };
  }

  // 7. Open-PR dedup — skip if an open autofix PR already exists for this work_item.
  const branchName = `autofix/bug-${wi.id.replace(/-/g, "").slice(0, 16)}`;
  const openPrs = await ghGet<Array<{ html_url: string }>>(
    `/repos/${owner}/${repo}/pulls?state=open&head=${owner}:${branchName}`, env.githubToken,
  );
  if (Array.isArray(openPrs) && openPrs.length > 0) {
    const reason = `Skipped: open autofix PR already exists (${openPrs[0].html_url})`;
    log(reason);
    return { outcome: "skipped_duplicate_pr", reason };
  }

  // 8. Branch (autofix/bug-<16 hex> from the work_item uuid → validate fires)
  const baseSha = await ghGet<{ object: { sha: string } }>(
    `/repos/${owner}/${repo}/git/refs/heads/${env.baseBranch}`, env.githubToken,
  );
  await ghPost(`/repos/${owner}/${repo}/git/refs`, { ref: `refs/heads/${branchName}`, sha: baseSha.object.sha }, env.githubToken);

  // 8. Commit + 9. draft PR
  const encoded = btoa(unescape(encodeURIComponent(fix.fixed_content)));
  await ghPut(`/repos/${owner}/${repo}/contents/${identified.file_path}`, {
    message: `fix: ${wi.title.slice(0, 72)}\n\n${fix.diff_summary}\n\nMission Control work_item: ${wi.id}`,
    content: encoded, sha: fileData.sha, branch: branchName,
  }, env.githubToken);
  const pr = await ghPost<{ html_url: string }>(`/repos/${owner}/${repo}/pulls`, {
    title: `fix: ${wi.title.slice(0, 72)}`,
    head: branchName, base: env.baseBranch,
    body: `## Auto-fix (Mission Control)\n\n**work_item:** ${wi.id}\n**File:** \`${identified.file_path}\`\n**Change:** ${fix.diff_summary}\n\n---\n*Dispatched from the Mission Control console. Requires human review.*`,
    draft: true,
  }, env.githubToken);

  log(`✅ PR: ${pr.html_url}`);
  return { outcome: "fixed", prUrl: pr.html_url, branchName, fixedFile: identified.file_path, reason: fix.diff_summary };
}

// ─── Edge Function handler ────────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS_HEADERS });

  const anthropicKey = Deno.env.get("ANTHROPIC_API_KEY");
  const githubToken = Deno.env.get("GITHUB_TOKEN");
  const githubOwner = Deno.env.get("GITHUB_OWNER");
  const githubRepo = Deno.env.get("GITHUB_REPO");
  const notionToken = Deno.env.get("NOTION_TOKEN");
  const notionDbId = Deno.env.get("NOTION_DATABASE_ID") ?? "75d7ed78-91f4-46b6-b805-12e43abbecce";

  if (!anthropicKey || !githubToken || !githubOwner || !githubRepo || !notionToken) {
    return Response.json(
      { ok: false, error: "Missing required environment variables" },
      { status: 500, headers: CORS_HEADERS },
    );
  }

  // Autopilot governance gate: the fix lane is OFF until AUTOPILOT_FIX_ENABLED=true in the
  // Supabase vault. Brings the daily auto-merge-to-prod pipeline under the kill-switch
  // (default OFF) — nothing auto-ships until an operator enables it.
  if (Deno.env.get("AUTOPILOT_FIX_ENABLED") !== "true") {
    return Response.json(
      { ok: true, halted: true, reason: "AUTOPILOT_FIX_ENABLED off" },
      { headers: CORS_HEADERS },
    );
  }

  const body = req.method === "POST" ? await req.json().catch(() => ({})) : {};
  const dryRun = body.dry_run === true || Deno.env.get("DRY_RUN") === "true";
  const maxBugs = parseInt(body.max_bugs ?? Deno.env.get("MAX_BUGS") ?? "5", 10);
  // Single-task mode: fix exactly this Work Queue task instead of the Ready-for-AI batch.
  const singleTaskId = typeof body.notion_task_id === "string" && body.notion_task_id
    ? body.notion_task_id
    : null;

  const env: Env = {
    anthropicKey, githubToken, githubOwner, githubRepo, notionToken, notionDbId,
    baseBranch: Deno.env.get("BASE_BRANCH") ?? "main",
    dryRun,
  };

  const date = new Date().toISOString().slice(0, 10);

  // Mission Control P2 — single-demand dispatch from the admin console. Runs the
  // one work_item synchronously and returns its PR url (no Notion). Falls through
  // to the nightly Notion batch when no work_item is supplied.
  if (body.work_item && body.work_item.id) {
    const wi = body.work_item;
    const result = await processWorkItem(
      { id: String(wi.id), title: String(wi.title ?? ""), body: String(wi.body ?? "") },
      env,
    ).catch((err) => ({ outcome: "error", reason: err instanceof Error ? err.message : String(err) }));
    return Response.json(
      { ok: result.outcome === "fixed", pr_url: (result as { prUrl?: string }).prUrl ?? null, ...result },
      { headers: CORS_HEADERS },
    );
  }

  try {
    // Fetch candidate bugs — single task (on-demand) or the Ready-for-AI batch (cron).
    const bugs = singleTaskId
      ? [await fetchTaskById(notionToken, singleTaskId)].filter((t) => t.title.length > 0)
      : await fetchReadyBugs(notionToken, notionDbId, maxBugs);
    console.log(`autofix-pipeline: ${date}: ${singleTaskId ? `single-task ${singleTaskId}` : "batch"} → ${bugs.length} candidate(s)`);

    const results = [];
    for (const bug of bugs) {
      if (results.length > 0) await new Promise((r) => setTimeout(r, 1000));
      const result = await processBug(bug, env).catch((err) => ({
        outcome: "error",
        reason: err instanceof Error ? err.message : String(err),
      }));
      results.push({ notionId: bug.notionId, title: bug.title, ...result });
    }

    const summary = {
      ok: true,
      date,
      dry_run: dryRun,
      total_fetched: bugs.length,
      fixed: results.filter((r) => r.outcome === "fixed").length,
      skipped: results.filter((r) => (r.outcome as string).startsWith("skipped")).length,
      errors: results.filter((r) => r.outcome === "error").length,
      results,
    };

    console.log("autofix-pipeline complete:", JSON.stringify({ ...summary, results: undefined }));
    return Response.json(summary, { headers: CORS_HEADERS });

  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error("autofix-pipeline error:", message);
    return Response.json({ ok: false, error: message }, { status: 500, headers: CORS_HEADERS });
  }
});
