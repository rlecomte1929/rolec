/**
 * Launch Authenticated Portal QA (GitHub Actions)
 *
 * The Audos-native trigger for ReloPass's authenticated-portal test suite. QA Guru
 * itself cannot sign into the Admin/HR/Employee portals (no credential injection), so
 * the actual test is a Playwright suite that runs in GitHub Actions. This tool lets an
 * agent (QA Guru / Otto) LAUNCH that suite on demand via the workflow_dispatch API and
 * report back the run URL (and, with --watch, the pass/fail result).
 *
 * What it runs: the `portals-nightly.yml` workflow (frontend/e2e/portals/*) — signs in
 * as each role via a saved session and smoke-checks each portal. See
 * docs/e2e-live-portals.md.
 *
 * Required environment variable (paste in Space settings → Connect Integrations):
 *   - GITHUB_DISPATCH_TOKEN: a GitHub token that may dispatch workflows on the repo.
 *       Fine-grained PAT scoped to rlecomte1929/rolec with "Actions: Read and write"
 *       (+ "Contents: Read"), or a classic PAT with the `repo` + `workflow` scopes.
 *
 * Optional environment variables:
 *   - GITHUB_REPO       (default: rlecomte1929/rolec)
 *   - PORTALS_WORKFLOW  (default: portals-nightly.yml)
 *
 * Usage:
 *   ts-node tools/github-dispatch-portals-qa.ts [--ref <branch>] [--watch]
 *
 * Examples:
 *   ts-node tools/github-dispatch-portals-qa.ts            # launch on main, return run URL
 *   ts-node tools/github-dispatch-portals-qa.ts --watch    # launch and wait for pass/fail
 *
 * Note: the suite is gated in CI by the repo variable E2E_PORTALS_NIGHTLY_ENABLED and
 * the six E2E_* credential secrets; if those are not set the run fails loudly with a
 * clear message rather than a false green.
 */

import fetch from 'node-fetch';

const REPO = process.env.GITHUB_REPO || 'rlecomte1929/rolec';
const WORKFLOW = process.env.PORTALS_WORKFLOW || 'portals-nightly.yml';
const TOKEN = process.env.GITHUB_DISPATCH_TOKEN || '';
const API = 'https://api.github.com';

function ghHeaders() {
  return {
    Authorization: `Bearer ${TOKEN}`,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'relopass-audos-portals-qa',
    'Content-Type': 'application/json',
  };
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function dispatch(ref: string): Promise<void> {
  const res = await fetch(`${API}/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: 'POST',
    headers: ghHeaders(),
    body: JSON.stringify({ ref }),
  });
  if (res.status !== 204) {
    const body = await res.text();
    throw new Error(`workflow_dispatch failed: HTTP ${res.status} ${res.statusText} — ${body}`);
  }
}

interface Run {
  id: number;
  html_url: string;
  status: string;
  conclusion: string | null;
  created_at: string;
}

// workflow_dispatch returns 204 with no run id, so find the run it just created.
async function findNewRun(sinceMs: number): Promise<Run | null> {
  for (let i = 0; i < 12; i++) {
    await sleep(5000);
    const res = await fetch(
      `${API}/repos/${REPO}/actions/workflows/${WORKFLOW}/runs?event=workflow_dispatch&per_page=5`,
      { headers: ghHeaders() },
    );
    if (!res.ok) continue;
    const data = (await res.json()) as any;
    const runs: Run[] = data.workflow_runs || [];
    // Allow 60s of clock skew between us and GitHub.
    const match = runs.find((r) => new Date(r.created_at).getTime() >= sinceMs - 60_000);
    if (match) return match;
  }
  return null;
}

async function watchRun(id: number): Promise<Run> {
  // ~15 min cap (the suite is a few minutes; leave headroom for a Render cold start).
  for (let i = 0; i < 60; i++) {
    const res = await fetch(`${API}/repos/${REPO}/actions/runs/${id}`, { headers: ghHeaders() });
    if (res.ok) {
      const run = (await res.json()) as Run;
      if (run.status === 'completed') return run;
    }
    await sleep(15000);
  }
  throw new Error('timed out waiting for the run to complete');
}

async function main() {
  const args = process.argv.slice(2);
  const refIdx = args.indexOf('--ref');
  const ref = refIdx >= 0 ? args[refIdx + 1] : 'main';
  const watch = args.includes('--watch');

  if (!TOKEN) {
    console.error(
      'Error: GITHUB_DISPATCH_TOKEN is not set. Add it in Space settings → Connect ' +
        'Integrations (a GitHub PAT that may dispatch workflows on ' +
        `${REPO}: fine-grained "Actions: Read and write", or classic repo+workflow).`,
    );
    process.exit(1);
  }

  console.log(`🚀 Launching authenticated portal QA — ${WORKFLOW} on ${REPO}@${ref} …`);
  const startedMs = Date.now();

  try {
    await dispatch(ref);
    console.log('✔ workflow_dispatch accepted (HTTP 204). Locating the run …');

    const run = await findNewRun(startedMs);
    if (!run) {
      // Dispatched fine; we just couldn't correlate the run in time.
      const out = {
        dispatched: true,
        ref,
        run: null,
        note: 'Dispatched, but the run did not appear within ~60s. Check the Actions tab.',
        actions_url: `https://github.com/${REPO}/actions/workflows/${WORKFLOW}`,
      };
      console.log(`\n${out.note}\n${out.actions_url}`);
      console.log('\n--- JSON Output ---');
      console.log(JSON.stringify(out, null, 2));
      return;
    }

    console.log(`▶ Run #${run.id}: ${run.html_url}`);

    let finalRun = run;
    if (watch) {
      console.log('⏳ Watching until it finishes …');
      finalRun = await watchRun(run.id);
      const ok = finalRun.conclusion === 'success';
      console.log(`${ok ? '✅' : '❌'} Run ${finalRun.conclusion}: ${finalRun.html_url}`);
    } else {
      console.log('ℹ Launched. Re-run with --watch to wait for the pass/fail result.');
    }

    const out = {
      dispatched: true,
      ref,
      watched: watch,
      run: {
        id: finalRun.id,
        html_url: finalRun.html_url,
        status: finalRun.status,
        conclusion: finalRun.conclusion,
      },
    };
    console.log('\n--- JSON Output ---');
    console.log(JSON.stringify(out, null, 2));

    if (watch && finalRun.conclusion !== 'success') process.exit(1);
  } catch (error) {
    console.error('Launch failed:', error instanceof Error ? error.message : error);
    process.exit(1);
  }
}

main();
