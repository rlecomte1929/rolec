/**
 * autofix-pipeline.ts — DEV-LOOP-2C
 * ─────────────────────────────────────────────────────────────────────────────
 * End-to-end automated bug fix pipeline.
 *
 * Flow per bug:
 *   1. Fetch Notion tasks: Status="Ready for AI" + Complexity in [Trivial, Low]
 *   2. Classify with bug-classifier (Haiku)
 *   3. Check blocklist (path + keyword)
 *   4. Ask Claude to identify the file to fix + generate the fix
 *   5. Create branch autofix/bug-{notion-id} via GitHub API
 *   6. Commit fix via GitHub Contents API (no local git required)
 *   7. Open draft PR
 *   8. Update Notion task → "AI in Progress"
 *
 * Environment variables required:
 *   ANTHROPIC_API_KEY    — Claude API key
 *   GITHUB_TOKEN         — Personal access token or GitHub App token
 *   GITHUB_OWNER         — Repository owner (e.g. "relopass")
 *   GITHUB_REPO          — Repository name (e.g. "rolec")
 *   NOTION_TOKEN         — Notion integration secret
 *   NOTION_DATABASE_ID   — AI Work Queue database ID
 *
 * Usage (CLI):
 *   ANTHROPIC_API_KEY=... GITHUB_TOKEN=... npx ts-node scripts/autofix-pipeline.ts
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { classifyBug } from './bug-classifier.ts';
import { checkBugSafety, isBlockedPath } from './autofix-blocklist.ts';

// ─── Types ────────────────────────────────────────────────────────────────────

export interface PipelineConfig {
  anthropicApiKey: string;
  githubToken: string;
  githubOwner: string;
  githubRepo: string;
  notionToken: string;
  notionDatabaseId: string;
  /** Default 5 — max bugs to process per run */
  maxBugsPerRun?: number;
  /** If true, skip branch/PR creation (useful for testing) */
  dryRun?: boolean;
  /** Base branch to branch off from (default: main) */
  baseBranch?: string;
}

export interface BugTask {
  notionId: string;
  title: string;
  description: string;
  complexity: string;
  priority: string;
  notionUrl: string;
  taskType: string;
}

export type PipelineOutcome =
  | 'fixed'
  | 'skipped_classifier'    // classifier said not auto-fixable
  | 'skipped_blocklist'     // blocklist rejected (keyword or path)
  | 'skipped_no_file'       // Claude couldn't identify a file to fix
  | 'skipped_no_fix'        // Claude couldn't generate a valid fix
  | 'skipped_dry_run'       // dry run mode — would have fixed
  | 'error';                // unexpected error

export interface PipelineResult {
  notionId: string;
  title: string;
  outcome: PipelineOutcome;
  prUrl?: string;
  branchName?: string;
  fixedFile?: string;
  reason: string;
  elapsedMs: number;
}

export interface PipelineRunSummary {
  date: string;
  total_fetched: number;
  total_processed: number;
  fixed: number;
  skipped: number;
  errors: number;
  results: PipelineResult[];
}

interface GitHubFileInfo {
  path: string;
  content: string;   // decoded from base64
  sha: string;       // needed for update
  size: number;
}

interface IdentifiedFile {
  file_path: string | null;
  reasoning: string;
}

interface GeneratedFix {
  fixed_content: string | null;
  diff_summary: string;
}

// ─── Notion API helpers ───────────────────────────────────────────────────────

async function fetchReadyBugs(config: PipelineConfig): Promise<BugTask[]> {
  const { notionToken, notionDatabaseId, maxBugsPerRun = 5 } = config;

  const body = {
    page_size: maxBugsPerRun,
    filter: {
      and: [
        { property: 'Status', select: { equals: 'Ready for AI' } },
        {
          or: [
            { property: 'Estimated Complexity', select: { equals: 'Trivial' } },
            { property: 'Estimated Complexity', select: { equals: 'Low' } },
          ],
        },
      ],
    },
    sorts: [{ property: 'Priority', direction: 'ascending' }],
  };

  const resp = await fetch(`https://api.notion.com/v1/databases/${notionDatabaseId}/query`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${notionToken}`,
      'Notion-Version': '2022-06-28',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    throw new Error(`Notion query failed: ${resp.status} ${await resp.text()}`);
  }

  const data = await resp.json() as { results: unknown[] };

  return (data.results as Array<Record<string, unknown>>).map((page) => {
    const props = (page as Record<string, { title?: Array<{ plain_text: string }>, rich_text?: Array<{ plain_text: string }>, select?: { name: string }, url?: string }>).properties ?? {};

    const titleParts = props['Task Title']?.title ?? props['title']?.title ?? [];
    const title = titleParts.map((t) => t.plain_text).join('');

    const descParts = props['Description']?.rich_text ?? [];
    const description = descParts.map((t: { plain_text: string }) => t.plain_text).join('');

    return {
      notionId: (page as { id: string }).id,
      title,
      description,
      complexity: props['Estimated Complexity']?.select?.name ?? '',
      priority: props['Priority']?.select?.name ?? '',
      notionUrl: (page as { url: string }).url ?? '',
      taskType: props['Task Type']?.select?.name ?? '',
    };
  }).filter((t) => t.title.length > 0);
}

async function updateNotionStatus(
  notionId: string,
  status: string,
  executionNotes: string,
  config: PipelineConfig,
): Promise<void> {
  const { notionToken } = config;

  await fetch(`https://api.notion.com/v1/pages/${notionId}`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${notionToken}`,
      'Notion-Version': '2022-06-28',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      properties: {
        Status: { select: { name: status } },
        'Execution Notes': { rich_text: [{ type: 'text', text: { content: executionNotes.slice(0, 2000) } }] },
      },
    }),
  });
}

// ─── GitHub API helpers ───────────────────────────────────────────────────────

const GH_API = 'https://api.github.com';

async function githubGet<T>(path: string, config: PipelineConfig): Promise<T> {
  const resp = await fetch(`${GH_API}${path}`, {
    headers: {
      'Authorization': `Bearer ${config.githubToken}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
    },
  });
  if (!resp.ok) throw new Error(`GitHub GET ${path} failed: ${resp.status} ${await resp.text()}`);
  return resp.json() as Promise<T>;
}

async function githubPost<T>(path: string, body: unknown, config: PipelineConfig): Promise<T> {
  const resp = await fetch(`${GH_API}${path}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${config.githubToken}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`GitHub POST ${path} failed: ${resp.status} ${await resp.text()}`);
  return resp.json() as Promise<T>;
}

async function githubPut<T>(path: string, body: unknown, config: PipelineConfig): Promise<T> {
  const resp = await fetch(`${GH_API}${path}`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${config.githubToken}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`GitHub PUT ${path} failed: ${resp.status} ${await resp.text()}`);
  return resp.json() as Promise<T>;
}

async function getBaseBranchSha(config: PipelineConfig): Promise<string> {
  const base = config.baseBranch ?? 'main';
  const { owner, repo } = { owner: config.githubOwner, repo: config.githubRepo };
  const data = await githubGet<{ object: { sha: string } }>(
    `/repos/${owner}/${repo}/git/refs/heads/${base}`,
    config,
  );
  return data.object.sha;
}

async function createBranch(branchName: string, baseSha: string, config: PipelineConfig): Promise<void> {
  const { owner, repo } = { owner: config.githubOwner, repo: config.githubRepo };
  await githubPost(
    `/repos/${owner}/${repo}/git/refs`,
    { ref: `refs/heads/${branchName}`, sha: baseSha },
    config,
  );
}

async function getFileContent(filePath: string, branchName: string, config: PipelineConfig): Promise<GitHubFileInfo | null> {
  const { owner, repo } = { owner: config.githubOwner, repo: config.githubRepo };
  try {
    const data = await githubGet<{ content: string; sha: string; size: number }>(
      `/repos/${owner}/${repo}/contents/${filePath}?ref=${branchName}`,
      config,
    );
    // GitHub returns base64-encoded content with newlines
    const content = atob(data.content.replace(/\n/g, ''));
    return { path: filePath, content, sha: data.sha, size: data.size };
  } catch {
    return null;
  }
}

async function commitFileFix(
  filePath: string,
  newContent: string,
  fileSha: string,
  commitMessage: string,
  branchName: string,
  config: PipelineConfig,
): Promise<void> {
  const { owner, repo } = { owner: config.githubOwner, repo: config.githubRepo };
  // GitHub requires base64-encoded content
  const encoded = btoa(unescape(encodeURIComponent(newContent)));
  await githubPut(
    `/repos/${owner}/${repo}/contents/${filePath}`,
    {
      message: commitMessage,
      content: encoded,
      sha: fileSha,
      branch: branchName,
    },
    config,
  );
}

async function createDraftPR(
  branchName: string,
  bug: BugTask,
  diffSummary: string,
  fixedFile: string,
  config: PipelineConfig,
): Promise<string> {
  const { owner, repo } = { owner: config.githubOwner, repo: config.githubRepo };
  const base = config.baseBranch ?? 'main';

  const body = `## Auto-fix: ${bug.title}

**Notion task:** ${bug.notionUrl}
**Fixed file:** \`${fixedFile}\`
**Change:** ${diffSummary}

---
*Generated by ReloPass autofix-pipeline at ${new Date().toISOString()}.*
*This PR requires human review before merging.*`;

  const data = await githubPost<{ html_url: string }>(
    `/repos/${owner}/${repo}/pulls`,
    {
      title: `fix: ${bug.title.slice(0, 72)}`,
      head: branchName,
      base,
      body,
      draft: true,
    },
    config,
  );
  return data.html_url;
}

// ─── Claude helpers ───────────────────────────────────────────────────────────

async function callClaude(
  systemPrompt: string,
  userMessage: string,
  maxTokens: number,
  config: PipelineConfig,
): Promise<string> {
  const resp = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': config.anthropicApiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: maxTokens,
      system: systemPrompt,
      messages: [{ role: 'user', content: userMessage }],
    }),
  });
  if (!resp.ok) throw new Error(`Claude API error: ${resp.status} ${await resp.text()}`);
  const data = await resp.json() as { content: Array<{ type: string; text: string }> };
  return data.content?.[0]?.text?.trim() ?? '';
}

function parseJson<T>(raw: string, fallback: T): T {
  const cleaned = raw.replace(/^```(?:json)?\n?/m, '').replace(/\n?```$/m, '').trim();
  try { return JSON.parse(cleaned) as T; } catch { return fallback; }
}

async function identifyFileToFix(bug: BugTask, config: PipelineConfig): Promise<IdentifiedFile> {
  const system = `You are a ReloPass codebase expert. Given a bug report, identify the single most likely file to contain the issue.
ReloPass is a Next.js 14 + TypeScript SaaS. Key directories:
  frontend/src/components/  — React UI components
  frontend/src/pages/       — Next.js pages
  frontend/src/styles/      — CSS / Tailwind
  frontend/src/constants/   — static data (cities, countries, etc.)
  frontend/src/lib/         — utility libraries
  lib/                      — shared TypeScript utilities
  backend/app/routers/      — FastAPI routers

Respond with ONLY valid JSON, no markdown:
{"file_path": "relative/path/to/file.tsx", "reasoning": "one concise sentence"}
If you cannot determine the file with confidence, respond:
{"file_path": null, "reasoning": "reason why not determinable"}`;

  const user = `Bug title: ${bug.title}\nBug description: ${bug.description}`;
  const raw = await callClaude(system, user, 256, config);
  return parseJson<IdentifiedFile>(raw, { file_path: null, reasoning: raw.slice(0, 200) });
}

async function generateFix(
  bug: BugTask,
  filePath: string,
  fileContent: string,
  config: PipelineConfig,
): Promise<GeneratedFix> {
  // Truncate file content to stay within token budget (~4000 tokens max context)
  const maxContentLen = 12000; // ~3000 tokens
  const truncatedContent = fileContent.length > maxContentLen
    ? fileContent.slice(0, maxContentLen) + '\n// ... [truncated for context window]'
    : fileContent;

  const system = `You are a ReloPass codebase expert. Make a MINIMAL, PRECISE fix to a single file.
Rules:
- Only change what is needed to fix the reported bug
- Preserve ALL existing code, imports, formatting, and comments
- Do NOT add new features or refactor
- The fix must be safe to deploy without human review
Respond with ONLY valid JSON, no markdown:
{"fixed_content": "...complete corrected file content...", "diff_summary": "one sentence: what changed and why"}
If you cannot generate a safe fix, respond:
{"fixed_content": null, "diff_summary": "reason: why a safe fix cannot be generated automatically"}`;

  const user = `Bug title: ${bug.title}
Bug description: ${bug.description}

File to fix: ${filePath}
\`\`\`
${truncatedContent}
\`\`\``;

  const raw = await callClaude(system, user, 4096, config);
  return parseJson<GeneratedFix>(raw, { fixed_content: null, diff_summary: raw.slice(0, 200) });
}

// ─── Core pipeline logic ──────────────────────────────────────────────────────

async function processBug(bug: BugTask, config: PipelineConfig): Promise<PipelineResult> {
  const start = Date.now();

  const base: Omit<PipelineResult, 'outcome' | 'reason' | 'elapsedMs'> = {
    notionId: bug.notionId,
    title: bug.title,
  };

  try {
    // ── Step 1: Update Notion to AI in Progress ─────────────────────────────
    await updateNotionStatus(
      bug.notionId,
      'AI in Progress',
      `Auto-fix pipeline picked up this task at ${new Date().toISOString()}`,
      config,
    );

    // ── Step 2: Classify bug ────────────────────────────────────────────────
    const classification = await classifyBug(
      { title: bug.title, description: bug.description },
      config.anthropicApiKey,
    );

    if (!classification.auto_fixable) {
      const reason = `Classifier: not auto-fixable (${classification.fix_category}) — ${classification.reason}`;
      await updateNotionStatus(bug.notionId, 'Ready for AI', reason, config);
      return { ...base, outcome: 'skipped_classifier', reason, elapsedMs: Date.now() - start };
    }

    // ── Step 3: Keyword safety check (bug description) ─────────────────────
    const safety = checkBugSafety(`${bug.title}\n${bug.description}`);
    if (!safety.safe) {
      const reason = `Blocklist: ${safety.reason}`;
      await updateNotionStatus(bug.notionId, 'Ready for AI', reason, config);
      return { ...base, outcome: 'skipped_blocklist', reason, elapsedMs: Date.now() - start };
    }

    // ── Step 4: Identify file to fix ────────────────────────────────────────
    const identified = await identifyFileToFix(bug, config);
    if (!identified.file_path) {
      const reason = `File identification failed: ${identified.reasoning}`;
      await updateNotionStatus(bug.notionId, 'Ready for AI', reason, config);
      return { ...base, outcome: 'skipped_no_file', reason, elapsedMs: Date.now() - start };
    }

    // ── Step 5: Path blocklist check ────────────────────────────────────────
    if (isBlockedPath(identified.file_path)) {
      const reason = `Blocklist: file path "${identified.file_path}" is in a protected directory`;
      await updateNotionStatus(bug.notionId, 'Ready for AI', reason, config);
      return { ...base, outcome: 'skipped_blocklist', reason, elapsedMs: Date.now() - start };
    }

    // ── Step 6: Dry-run gate ────────────────────────────────────────────────
    if (config.dryRun) {
      const reason = `[DRY RUN] Would fix: file=${identified.file_path}, reasoning=${identified.reasoning}`;
      await updateNotionStatus(bug.notionId, 'Ready for AI', reason, config);
      return { ...base, outcome: 'skipped_dry_run', reason, fixedFile: identified.file_path, elapsedMs: Date.now() - start };
    }

    // ── Step 7: Get base branch SHA ─────────────────────────────────────────
    const baseSha = await getBaseBranchSha(config);

    // ── Step 8: Fetch file content from GitHub ──────────────────────────────
    const fileInfo = await getFileContent(identified.file_path, config.baseBranch ?? 'main', config);
    if (!fileInfo) {
      const reason = `File not found in repo: ${identified.file_path}`;
      await updateNotionStatus(bug.notionId, 'Ready for AI', reason, config);
      return { ...base, outcome: 'skipped_no_file', reason, elapsedMs: Date.now() - start };
    }

    // File size guard — skip large files (>50KB) to avoid runaway token usage
    if (fileInfo.size > 50000) {
      const reason = `File too large for auto-fix: ${fileInfo.size} bytes (max 50KB)`;
      await updateNotionStatus(bug.notionId, 'Ready for AI', reason, config);
      return { ...base, outcome: 'skipped_no_fix', reason, elapsedMs: Date.now() - start };
    }

    // ── Step 9: Generate fix via Claude ─────────────────────────────────────
    const fix = await generateFix(bug, identified.file_path, fileInfo.content, config);
    if (!fix.fixed_content) {
      const reason = `Fix generation failed: ${fix.diff_summary}`;
      await updateNotionStatus(bug.notionId, 'Ready for AI', reason, config);
      return { ...base, outcome: 'skipped_no_fix', reason, elapsedMs: Date.now() - start };
    }

    // Sanity check: fixed_content must be non-trivially different
    if (fix.fixed_content.trim() === fileInfo.content.trim()) {
      const reason = 'Fix generation produced identical content — no change made';
      await updateNotionStatus(bug.notionId, 'Ready for AI', reason, config);
      return { ...base, outcome: 'skipped_no_fix', reason, elapsedMs: Date.now() - start };
    }

    // ── Step 10: Create branch ───────────────────────────────────────────────
    const branchName = `autofix/bug-${bug.notionId.replace(/-/g, '').slice(0, 16)}`;
    await createBranch(branchName, baseSha, config);

    // ── Step 11: Commit fix ──────────────────────────────────────────────────
    const commitMessage = `fix: ${bug.title.slice(0, 72)}\n\n${fix.diff_summary}\n\nNotion: ${bug.notionUrl}`;
    await commitFileFix(
      identified.file_path,
      fix.fixed_content,
      fileInfo.sha,
      commitMessage,
      branchName,
      config,
    );

    // ── Step 12: Open draft PR ───────────────────────────────────────────────
    const prUrl = await createDraftPR(branchName, bug, fix.diff_summary, identified.file_path, config);

    // ── Step 13: Update Notion with PR link ──────────────────────────────────
    await updateNotionStatus(
      bug.notionId,
      'Human Review',
      `Auto-fix generated. PR: ${prUrl}\nFile: ${identified.file_path}\nChange: ${fix.diff_summary}`,
      config,
    );

    return {
      ...base,
      outcome: 'fixed',
      prUrl,
      branchName,
      fixedFile: identified.file_path,
      reason: fix.diff_summary,
      elapsedMs: Date.now() - start,
    };

  } catch (err) {
    const reason = `Unexpected error: ${err instanceof Error ? err.message : String(err)}`;
    // Best-effort: try to reset Notion status
    try { await updateNotionStatus(bug.notionId, 'Ready for AI', reason, config); } catch { /* ignore */ }
    return { ...base, outcome: 'error', reason, elapsedMs: Date.now() - start };
  }
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Run the auto-fix pipeline.
 *
 * Fetches ready Notion bugs, classifies, generates fixes, creates PRs.
 * Conservative by design: skips on any uncertainty.
 */
export async function runPipeline(config: PipelineConfig): Promise<PipelineRunSummary> {
  const date = new Date().toISOString().slice(0, 10);

  // Fetch candidate bugs from Notion
  let bugs: BugTask[];
  try {
    bugs = await fetchReadyBugs(config);
  } catch (err) {
    throw new Error(`Failed to fetch Notion tasks: ${err instanceof Error ? err.message : String(err)}`);
  }

  console.log(`[autofix-pipeline] ${date}: fetched ${bugs.length} candidate bug(s)`);

  const results: PipelineResult[] = [];

  for (const bug of bugs) {
    console.log(`[autofix-pipeline] Processing: "${bug.title.slice(0, 60)}" (${bug.notionId})`);
    // Small delay between bugs to avoid rate limiting
    if (results.length > 0) await new Promise((r) => setTimeout(r, 1000));

    const result = await processBug(bug, config);
    results.push(result);

    const icon = result.outcome === 'fixed' ? '✅' :
                 result.outcome === 'error' ? '❌' : '⏭️';
    console.log(`  ${icon} ${result.outcome}: ${result.reason.slice(0, 80)}`);
    if (result.prUrl) console.log(`     PR: ${result.prUrl}`);
  }

  const summary: PipelineRunSummary = {
    date,
    total_fetched: bugs.length,
    total_processed: results.length,
    fixed: results.filter((r) => r.outcome === 'fixed').length,
    skipped: results.filter((r) => r.outcome.startsWith('skipped')).length,
    errors: results.filter((r) => r.outcome === 'error').length,
    results,
  };

  console.log(`[autofix-pipeline] Done: fixed=${summary.fixed} skipped=${summary.skipped} errors=${summary.errors}`);
  return summary;
}
