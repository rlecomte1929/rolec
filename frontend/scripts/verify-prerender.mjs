#!/usr/bin/env node
/**
 * [AIQ-1797] Objective gate on the prerendered PUBLIC marketing routes.
 *
 * WHY THIS EXISTS
 * ---------------
 * `prerender.mjs` already throws on empty markup, but "not empty" is a weak claim. Before
 * this file, the build could emit a page containing nothing but the loading splash and the
 * asset tags and still pass — which is precisely the shape of the ADS-3 near-miss, where
 * prerendered HTML existed, returned HTTP 200, and showed a blank document to every ad
 * crawler.
 *
 * So this asserts on VISIBLE TEXT, not bytes and not status. A page's byte count is
 * dominated by markup and inline styles; the number that matters is how much a client
 * which does not run JavaScript can actually read. Baseline for every one of these routes
 * was ~82 characters.
 *
 * WHAT IT DOES NOT DO
 * -------------------
 * It checks FILES ON DISK. That is necessary and not sufficient: on 2026-08-10 the files
 * were correct and production still served the shell, because Render only resolves
 * `dist/<route>/index.html` when the request carries a trailing slash. The served-response
 * half is `scripts/check_public_prerender.sh`, which runs against a real origin. Both, or
 * neither is worth much.
 */
import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DIST = path.join(FRONTEND, 'dist');
const SRC = path.join(FRONTEND, 'src');

/** Visible-text floor. Baseline was ~82 chars ('ReloPass' + 'Loading ReloPass…'). */
const MIN_VISIBLE = 500;

/**
 * route -> [source file whose usePageMeta is the source of truth, golden phrase]
 *
 * The golden phrase must appear in the PRERENDERED markup and never in the shell, so a
 * page that renders the splash and nothing else fails on it even if some other route's
 * copy leaked in. One phrase per route, deliberately distinct between routes.
 */
const TARGETS = [
  ['/', 'pages/Landing.tsx', 'Cut the cost of every cross-border move'],
  ['/platform', 'pages/public/PlatformPage.tsx', 'One connected system'],
  ['/why', 'pages/public/WhyReloPassPage.tsx', 'Relocation fails in the handoffs'],
  ['/how-it-works', 'pages/public/HowItWorksPage.tsx', 'Four steps from fragmented to structured'],
  ['/get-started', 'pages/public/GetStartedPage.tsx', 'Book a demo, sign in, or create an account'],
  ['/security', 'pages/public/SecurityPage.tsx', 'Built to handle sensitive relocation data'],
  ['/privacy', 'pages/public/PrivacyPage.tsx', 'Privacy Policy'],
  ['/access', 'pages/public/AccessPage.tsx', 'Three ways in'],
];

/** Strip scripts, styles and tags, then collapse whitespace — what a non-JS client reads. */
function visibleText(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<noscript[\s\S]*?<\/noscript>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&[a-z]+;/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function titleOf(html) {
  const m = html.match(/<title>([\s\S]*?)<\/title>/i);
  return m ? m[1].trim() : null;
}

/**
 * The title each page passes to usePageMeta.
 *
 * These pages call usePageMeta with INLINE literals rather than exporting a meta object
 * (unlike the ad landing pages, which read adLandingContent.ts). So prerender-entry.tsx
 * necessarily restates them, and two copies of a string drift. Rather than refactor eight
 * components, this reads the literal back out of the source and asserts the emitted
 * <title> matches — the same parity trick used for the data-sheet section labels, where a
 * comment saying "keep these in step" had failed to keep them in step.
 */
async function usePageMetaTitle(relSrc) {
  const src = await readFile(path.join(SRC, relSrc), 'utf8');
  const block = src.split('usePageMeta({')[1];
  if (!block) return null;
  const m = block.match(/title:\s*'((?:[^'\\]|\\.)*)'/) || block.match(/title:\s*"((?:[^"\\]|\\.)*)"/);
  return m ? m[1].replace(/\\'/g, "'") : null;
}

const rows = [];
const failures = [];

for (const [route, relSrc, phrase] of TARGETS) {
  // `/` IS dist/index.html — a rewrite cannot serve the root while a file exists there.
  // The shell moved to dist/app.html; see the write-site comment in prerender.mjs.
  const file = path.join(DIST, route === '/' ? 'index.html' : `${route.slice(1)}/index.html`);
  if (!existsSync(file)) {
    failures.push(`${route}: ${path.relative(FRONTEND, file)} was not emitted`);
    rows.push([route, '—', '—', 'MISSING']);
    continue;
  }

  const html = await readFile(file, 'utf8');
  const text = visibleText(html);
  const title = titleOf(html);
  const expectedTitle = await usePageMetaTitle(relSrc);

  const problems = [];
  if (text.length < MIN_VISIBLE) {
    problems.push(`only ${text.length} visible chars (floor ${MIN_VISIBLE}) — this is the shell`);
  }
  if (!title) {
    problems.push('no <title>');
  } else if (expectedTitle && title !== expectedTitle) {
    // Drift between prerender-entry.tsx and the page's own usePageMeta call.
    problems.push(
      `<title> is "${title}" but ${relSrc} sets "${expectedTitle}" — ` +
        'update prerender-entry.tsx to match the page',
    );
  }
  if (/Loading ReloPass/.test(text)) {
    problems.push('the loading splash is still the visible content');
  }
  // The golden phrase proves the BODY rendered, not just the <head>. Cross-route
  // contamination is caught by the title-parity check above, not by this.
  if (phrase && !text.includes(phrase)) {
    problems.push(`golden phrase "${phrase}" is absent — the page body did not render`);
  }

  rows.push([route, String(text.length), title ?? '—', problems.length ? 'FAIL' : 'ok']);
  for (const p of problems) failures.push(`${route}: ${p}`);
}

const w = [14, 8, 46];
console.log('\n[verify-prerender] visible text in dist/<route>/index.html\n');
console.log(
  'route'.padEnd(w[0]) + 'visible'.padEnd(w[1]) + '<title>'.padEnd(w[2]) + 'result',
);
console.log('-'.repeat(w[0] + w[1] + w[2] + 6));
for (const [a, b, c, d] of rows) {
  console.log(a.padEnd(w[0]) + b.padEnd(w[1]) + c.slice(0, w[2] - 2).padEnd(w[2]) + d);
}
console.log('');

// The catch-all document — served to /auth and every authenticated route — must stay the
// SHELL. Marketing copy there means an HR user opening /hr/dashboard receives the landing
// page, sees it, and then watches createRoot replace it.
//
// That document used to be dist/index.html, and this guard asserted index.html was empty.
// It now asserts the swap that replaced that arrangement, because the old one could not
// work: Render skips rewrite rules whenever a resource exists at the path, so
// `source: / -> /landing.html` was unreachable and the homepage served the shell to every
// crawler. index.html is now the homepage and app.html is the shell.
//
// Both halves are checked. Asserting only that app.html is empty would pass just as well if
// app.html were missing entirely and every authenticated route 404'd.
const shell = path.join(DIST, 'app.html');
if (!existsSync(shell)) {
  failures.push(
    'dist/app.html was not emitted — it is the /* catch-all document for /auth and every ' +
      'authenticated route. Without it those paths have nothing to serve.',
  );
} else {
  const shellText = visibleText(await readFile(shell, 'utf8'));
  if (shellText.length > MIN_VISIBLE) {
    failures.push(
      `dist/app.html has ${shellText.length} visible chars — it must be the SPA shell, not a ` +
        'prerendered page. It is served to every authenticated route, where marketing copy ' +
        'flashes before the app mounts. prerender.mjs must write it from the pristine ' +
        'template BEFORE the route loop overwrites index.html.',
    );
  } else {
    console.log(
      `[verify-prerender] dist/app.html is the shell (${shellText.length} visible chars) — ` +
        'authenticated routes unaffected.\n',
    );
  }
}

if (failures.length) {
  console.error(`[verify-prerender] FAILED — ${failures.length} problem(s):`);
  for (const f of failures) console.error(`  • ${f}`);
  console.error(
    '\nA route that cannot render real content should be removed from prerender-entry.tsx\n' +
      'and reported as UNDER-TARGET — never shipped as a snapshot of a loading state.\n' +
      'Blank beats wrong: a crawler that reads "Loading…" learns nothing and may cache it.\n',
  );
  process.exit(1);
}

console.log(`[verify-prerender] OK — ${TARGETS.length}/${TARGETS.length} routes above the ${MIN_VISIBLE}-char floor, titles match their pages.\n`);
