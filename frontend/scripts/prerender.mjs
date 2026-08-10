#!/usr/bin/env node
/**
 * [AIQ-1783] Prerender the paid-ad landing pages to static HTML.
 *
 * Runs AFTER `vite build`. Compiles src/prerender-entry.tsx with `vite build --ssr`,
 * renders each route, and writes dist/<route>/index.html using the built index.html as
 * the template — so the emitted pages carry the same hashed CSS/JS asset tags as the
 * rest of the app and hydrate into the normal SPA once JS loads.
 *
 * Deliberately NOT a headless browser: Render's static build should not have to
 * install Chromium.
 *
 * FAILS THE BUILD on error. A silent skip here would ship a blank page to paid traffic,
 * which is the exact failure this whole approach exists to prevent.
 */
import { build } from 'vite';
import react from '@vitejs/plugin-react';
import { mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DIST = path.join(ROOT, 'dist');
const SSR_OUT = path.join(ROOT, '.prerender-ssr');

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/**
 * Replace the CONTENTS of <div id="root"> with prerendered markup.
 *
 * The built index.html ships a loading splash inside the root div, so this is not a
 * simple `<div id="root"></div>` swap, and the splash itself contains nested divs — a
 * naive regex would close on the wrong tag and truncate the page. So scan forward from
 * the opening tag, tracking div depth, to find the real matching close.
 */
function replaceRootContents(html, markup) {
  const openTag = '<div id="root">';
  const start = html.indexOf(openTag);
  if (start === -1) return null;

  let i = start + openTag.length;
  let depth = 1;
  const contentStart = i;
  while (i < html.length && depth > 0) {
    const nextOpen = html.indexOf('<div', i);
    const nextClose = html.indexOf('</div>', i);
    if (nextClose === -1) return null;
    if (nextOpen !== -1 && nextOpen < nextClose) {
      depth += 1;
      i = nextOpen + 4;
    } else {
      depth -= 1;
      if (depth === 0) {
        return html.slice(0, contentStart) + markup + html.slice(nextClose);
      }
      i = nextClose + 6;
    }
  }
  return null;
}

/** Replace an existing <title>, or insert one if the template has none. */
function withTitle(html, title) {
  const tag = `<title>${escapeHtml(title)}</title>`;
  return /<title>[\s\S]*?<\/title>/.test(html)
    ? html.replace(/<title>[\s\S]*?<\/title>/, tag)
    : html.replace('</head>', `  ${tag}\n</head>`);
}

/** Replace an existing meta description, or insert one. */
function withDescription(html, description) {
  const tag = `<meta name="description" content="${escapeHtml(description)}">`;
  return /<meta\s+name="description"[^>]*>/i.test(html)
    ? html.replace(/<meta\s+name="description"[^>]*>/i, tag)
    : html.replace('</head>', `  ${tag}\n</head>`);
}

async function main() {
  const template = path.join(DIST, 'index.html');
  if (!existsSync(template)) {
    throw new Error(`prerender: ${template} not found — run \`vite build\` first.`);
  }

  // configFile: false is deliberate. vite.config.ts splits vendors (react, supabase,
  // axios) into manualChunks for the browser; in an SSR build those deps are
  // externalised and Rollup refuses to chunk an external, so inheriting that config
  // fails with `"react" cannot be included in manualChunks`. Overriding manualChunks to
  // undefined does NOT work — Vite merges rather than replaces. So skip the config file
  // and supply the one plugin this pass actually needs: the JSX transform.
  await build({
    root: ROOT,
    configFile: false,
    logLevel: 'warn',
    plugins: [react()],
    // Placeholder VITE_ values, mirroring the e2e job in ci.yml. `vite build` never
    // executes src/config/env.ts, but this pass IMPORTS it in Node (via analytics →
    // env), and it throws on missing Supabase vars. The frontend CI job runs
    // `npm run build` with no VITE_SUPABASE_* set, so without these the prerender
    // would fail every PR.
    //
    // Safe by construction: these values are used for API calls at runtime, never
    // rendered into markup. The prerendered HTML loads the real client bundle, which
    // carries the real values. A build-time prerender should not need deploy secrets.
    define: {
      'import.meta.env.VITE_SUPABASE_URL': JSON.stringify('https://prerender.placeholder.supabase.co'),
      // Spaces are intentional — never a real key, and it stays clear of gitleaks'
      // generic-api-key heuristic, which matches contiguous tokens only.
      'import.meta.env.VITE_SUPABASE_ANON_KEY': JSON.stringify('not a secret prerender placeholder'),
    },
    build: {
      ssr: path.join(ROOT, 'src/prerender-entry.tsx'),
      outDir: SSR_OUT,
      emptyOutDir: true,
      // The client build already emitted the real CSS; this pass only needs JS.
      cssCodeSplit: false,
    },
  });

  const { ROUTES } = await import(path.join(SSR_OUT, 'prerender-entry.js'));
  const baseHtml = await readFile(template, 'utf8');

  for (const route of ROUTES) {
    const markup = route.render();
    if (!markup || markup.length < 200) {
      throw new Error(`prerender: ${route.path} produced suspiciously empty markup`);
    }

    let html = replaceRootContents(baseHtml, markup);
    if (!html || !html.includes(markup)) {
      throw new Error(
        `prerender: could not inject markup for ${route.path} — could not locate the ` +
          'contents of <div id="root"> in dist/index.html.',
      );
    }
    html = withDescription(withTitle(html, route.title), route.description);

    const outDir = path.join(DIST, route.path.replace(/^\//, ''));
    await mkdir(outDir, { recursive: true });
    await writeFile(path.join(outDir, 'index.html'), html, 'utf8');
    console.log(`prerender: wrote ${path.relative(ROOT, path.join(outDir, 'index.html'))} (${markup.length} bytes of markup)`);
  }

  // KEEP_PRERENDER_SSR=1 leaves the intermediate bundle for inspection. Useful for
  // answering "what did the SSR graph actually pull in?" — which is how the
  // @supabase/supabase-js WebSocket failure on Node 20 was tracked down.
  if (!process.env.KEEP_PRERENDER_SSR) {
    await rm(SSR_OUT, { recursive: true, force: true });
  }
}

main().catch((err) => {
  console.error('[prerender] FAILED —', err?.message || err);
  process.exit(1);
});
