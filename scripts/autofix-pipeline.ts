#!/usr/bin/env -S npx ts-node --esm
/**
 * autofix-pipeline.ts — DEV-LOOP-2C CLI runner
 * ─────────────────────────────────────────────────────────────────────────────
 * Runs the auto-fix pipeline from the command line.
 * Also called by GitHub Actions nightly at 01:00 UTC.
 *
 * Required environment variables:
 *   ANTHROPIC_API_KEY    — Claude API key
 *   GITHUB_TOKEN         — GitHub personal access token (repo + pull_requests scope)
 *   GITHUB_OWNER         — Repo owner, e.g. "relopass"
 *   GITHUB_REPO          — Repo name, e.g. "rolec"
 *   NOTION_TOKEN         — Notion integration secret
 *   NOTION_DATABASE_ID   — AI Work Queue database ID
 *
 * Optional:
 *   DRY_RUN=true         — Run without creating branches/PRs
 *   MAX_BUGS=10          — Override default of 5 bugs per run
 *   BASE_BRANCH=main     — Override base branch
 *
 * Run:
 *   ANTHROPIC_API_KEY=sk-... GITHUB_TOKEN=ghp_... npx ts-node scripts/autofix-pipeline.ts
 *   DRY_RUN=true npx ts-node scripts/autofix-pipeline.ts
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { runPipeline } from '../lib/autofix-pipeline.ts';
import type { PipelineConfig } from '../lib/autofix-pipeline.ts';

function required(key: string): string {
  const val = process.env[key];
  if (!val) throw new Error(`Missing required environment variable: ${key}`);
  return val;
}

async function main() {
  console.log('\n════════════════════════════════════════════════════════════');
  console.log('  ReloPass Autofix Pipeline — DEV-LOOP-2C');
  console.log(`  ${new Date().toISOString()}`);
  console.log('════════════════════════════════════════════════════════════\n');

  const config: PipelineConfig = {
    anthropicApiKey:  required('ANTHROPIC_API_KEY'),
    githubToken:      required('GITHUB_TOKEN'),
    githubOwner:      required('GITHUB_OWNER'),
    githubRepo:       required('GITHUB_REPO'),
    notionToken:      required('NOTION_TOKEN'),
    notionDatabaseId: required('NOTION_DATABASE_ID'),
    dryRun:           process.env.DRY_RUN === 'true',
    maxBugsPerRun:    parseInt(process.env.MAX_BUGS ?? '5', 10),
    baseBranch:       process.env.BASE_BRANCH ?? 'main',
  };

  if (config.dryRun) {
    console.log('  ⚠️  DRY RUN MODE — no branches or PRs will be created\n');
  }

  try {
    const summary = await runPipeline(config);

    console.log('\n════════════════════════════════════════════════════════════');
    console.log('  SUMMARY');
    console.log('════════════════════════════════════════════════════════════');
    console.log(`  Fetched:   ${summary.total_fetched} candidate bug(s)`);
    console.log(`  Fixed:     ${summary.fixed}`);
    console.log(`  Skipped:   ${summary.skipped}`);
    console.log(`  Errors:    ${summary.errors}`);

    if (summary.results.length > 0) {
      console.log('\n  Results:');
      for (const r of summary.results) {
        const icon = r.outcome === 'fixed' ? '✅' : r.outcome === 'error' ? '❌' : '⏭️';
        console.log(`    ${icon} [${r.notionId.slice(0, 8)}] ${r.title.slice(0, 60)}`);
        console.log(`       → ${r.outcome}: ${r.reason.slice(0, 80)}`);
        if (r.prUrl) console.log(`       → PR: ${r.prUrl}`);
      }
    }

    console.log('\n════════════════════════════════════════════════════════════\n');
    process.exit(summary.errors > 0 ? 1 : 0);

  } catch (err) {
    console.error('\n❌ Pipeline failed:', err instanceof Error ? err.message : String(err));
    process.exit(1);
  }
}

main();
