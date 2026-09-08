#!/usr/bin/env node
/**
 * Publish `content/blog/*.md` as static HTML, and emit a sitemap.
 *
 * WHY THIS EXISTS
 * ---------------
 * Five posts had been sitting in `content/` for weeks, reachable at no URL. `/blog`,
 * `/resources`, `/guides` and even `/sitemap.xml` all returned the 1,677-byte SPA shell,
 * because nothing rendered that directory and the Render catch-all answers every unmatched
 * path with `index.html`. Content nobody can fetch cannot be read, ranked, or cited — the
 * same defect that nearly ate the paid-ad test (see AIQ-1784 / #1761), one directory over.
 *
 * WHY STANDALONE HTML AND NOT AN SPA ROUTE
 * ----------------------------------------
 * The ad landing pages are prerendered *into* the SPA shell: markup goes inside `#root` and
 * React hydrates over it. That cannot work here. There is no client route for `/blog/<slug>`,
 * so the bundle would mount, match nothing, and wipe the article out of the DOM — the content
 * would render, flash, and disappear.
 *
 * These pages therefore ship as complete documents with no script tag at all. For
 * crawler-facing reference content that is not a downgrade, it is the better artifact:
 * nothing to hydrate, nothing to wait for, no entry-bundle budget consumed, and no route
 * wiring to keep in sync. Add an SPA route later if these ever need app chrome.
 *
 * Markdown is converted at BUILD TIME only. `marked` is a devDependency and never reaches
 * the client bundle.
 *
 * FAILS THE BUILD on error — a silent skip would quietly un-publish the content again, which
 * is the exact failure this script exists to end.
 */
import { marked } from 'marked';
import { mkdir, readFile, writeFile, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '..');
const REPO = path.resolve(FRONTEND, '..');
const DIST = path.join(FRONTEND, 'dist');
const CONTENT = path.join(REPO, 'content', 'blog');
const ORIGIN = 'https://relopass.com';

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/**
 * Palette and type from DESIGN.md — navy #0b2b43 primary, teal #1f8e8b accent, Inter for
 * body. Inlined rather than linked: one request, no bundle dependency, and these pages must
 * render correctly for a crawler that fetches the HTML and nothing else.
 */
const STYLE = `
:root{--navy:#0b2b43;--accent:#1f8e8b;--ink:#1f2937;--muted:#5b6b7a;--rule:#e3e8ee;--bg:#ffffff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:400 17px/1.65 Inter,system-ui,-apple-system,"Segoe UI",sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:44rem;margin:0 auto;padding:2.5rem 1.25rem 5rem}
header.site{border-bottom:1px solid var(--rule);margin-bottom:2.5rem;padding-bottom:1rem}
header.site a{color:var(--navy);font-weight:600;text-decoration:none;letter-spacing:-.01em}
h1{color:var(--navy);font-size:2.05rem;line-height:1.2;letter-spacing:-.02em;margin:0 0 1.25rem}
h2{color:var(--navy);font-size:1.35rem;line-height:1.3;letter-spacing:-.01em;margin:2.75rem 0 .85rem}
h3{color:var(--navy);font-size:1.1rem;margin:2rem 0 .6rem}
p,li{color:var(--ink)}
a{color:var(--accent);text-decoration:underline;text-underline-offset:2px}
blockquote{margin:1.5rem 0;padding:.85rem 0 .85rem 1.15rem;border-left:3px solid var(--accent);
  color:var(--muted);font-style:normal}
blockquote p{margin:.4rem 0}
code{font:0.9em/1.5 "JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  background:#f4f6f8;padding:.12em .38em;border-radius:3px}
table{border-collapse:collapse;width:100%;margin:1.5rem 0;font-size:.95rem;display:block;overflow-x:auto}
th,td{border:1px solid var(--rule);padding:.55rem .7rem;text-align:left;vertical-align:top}
th{background:#f7f9fb;color:var(--navy);font-weight:600}
hr{border:0;border-top:1px solid var(--rule);margin:2.5rem 0}
ul,ol{padding-left:1.35rem}
li{margin:.3rem 0}
footer.site{margin-top:4rem;padding-top:1.25rem;border-top:1px solid var(--rule);
  color:var(--muted);font-size:.9rem}
@media(max-width:640px){.wrap{padding:1.75rem 1rem 4rem}h1{font-size:1.7rem}}
`;

function page({ title, description, canonical, bodyHtml }) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)}</title>
<meta name="description" content="${escapeHtml(description)}">
<link rel="canonical" href="${escapeHtml(canonical)}">
<link rel="icon" type="image/png" href="/relopass-logo.png?v=2">
<meta property="og:title" content="${escapeHtml(title)}">
<meta property="og:description" content="${escapeHtml(description)}">
<meta property="og:url" content="${escapeHtml(canonical)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="ReloPass">
<meta name="twitter:card" content="summary_large_image">
<style>${STYLE}</style>
</head>
<body>
<div class="wrap">
<header class="site"><a href="/">ReloPass</a></header>
${bodyHtml}
<footer class="site">
<p><a href="/blog/">All guides</a> · <a href="/">ReloPass</a></p>
<p>ReloPass is coordination software. It does not provide legal, immigration, or tax advice.</p>
</footer>
</div>
</body>
</html>
`;
}

/** First `# ` heading is the title. Fail loudly rather than publishing an untitled page. */
function extractTitle(md, slug) {
  const m = md.match(/^#\s+(.+?)\s*$/m);
  if (!m) throw new Error(`prerender-content: ${slug}.md has no "# " heading to use as a title`);
  return m[1].trim();
}

/**
 * Description = the first real paragraph, trimmed to ~155 chars on a word boundary. This is
 * the string search results and link previews show, so an empty or truncated-mid-word one is
 * a real cost, not a cosmetic detail.
 */
function extractDescription(md) {
  const body = md.replace(/^#\s+.+?$/m, '');
  for (const block of body.split(/\n{2,}/)) {
    const t = block.trim();
    if (!t || t.startsWith('#') || t.startsWith('>') || t.startsWith('|') || t.startsWith('-') || t.startsWith('*')) continue;
    const flat = t.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/[*_`]/g, '').replace(/\s+/g, ' ').trim();
    if (flat.length < 40) continue;
    if (flat.length <= 155) return flat;
    return flat.slice(0, flat.lastIndexOf(' ', 155)).replace(/[,;:]$/, '') + '…';
  }
  throw new Error('prerender-content: could not derive a description from the first paragraph');
}

async function main() {
  if (!existsSync(DIST)) {
    throw new Error(`prerender-content: ${DIST} not found — run \`vite build\` first.`);
  }
  if (!existsSync(CONTENT)) {
    throw new Error(`prerender-content: ${CONTENT} not found.`);
  }

  const files = (await readdir(CONTENT)).filter((f) => f.endsWith('.md')).sort();
  if (files.length === 0) throw new Error('prerender-content: no posts found in content/blog');

  const posts = [];

  for (const file of files) {
    const slug = file.replace(/\.md$/, '');
    const md = await readFile(path.join(CONTENT, file), 'utf8');
    const title = extractTitle(md, slug);
    const description = extractDescription(md);
    const canonical = `${ORIGIN}/blog/${slug}/`;

    // Drop the H1 from the body — `page()` renders it from the parsed markdown, and the
    // template would otherwise show it twice.
    const article = marked.parse(md, { mangle: false, headerIds: false });
    if (article.length < 500) {
      throw new Error(`prerender-content: ${slug} produced suspiciously short HTML`);
    }

    const outDir = path.join(DIST, 'blog', slug);
    await mkdir(outDir, { recursive: true });
    await writeFile(path.join(outDir, 'index.html'), page({ title, description, canonical, bodyHtml: article }), 'utf8');

    posts.push({ slug, title, description });
    console.log(`prerender-content: wrote dist/blog/${slug}/index.html (${article.length} bytes)`);
  }

  // Index page — gives crawlers one hub that links every post, so none depends on being
  // discovered by URL guess.
  const items = posts
    .map((p) => `<li><h2 style="margin:1.5rem 0 .35rem"><a href="/blog/${p.slug}/">${escapeHtml(p.title)}</a></h2>
<p style="margin:0;color:var(--muted)">${escapeHtml(p.description)}</p></li>`)
    .join('\n');
  await writeFile(
    path.join(DIST, 'blog', 'index.html'),
    page({
      title: 'Relocation guides for HR and mobility teams · ReloPass',
      description:
        'Practical, source-cited guides to cross-border relocation: corridor requirements, work-permit timelines, and compliance obligations for HR teams.',
      canonical: `${ORIGIN}/blog/`,
      bodyHtml: `<h1>Relocation guides</h1>
<p>Corridor requirements, timelines, and the obligations that catch HR teams out. Every factual claim links to the official source it came from.</p>
<ul style="list-style:none;padding:0">\n${items}\n</ul>`,
    }),
    'utf8',
  );
  console.log(`prerender-content: wrote dist/blog/index.html (${posts.length} posts)`);

  // Sitemap. robots.txt has carried a "add a Sitemap: line once sitemap.xml ships" TODO
  // since AIQ-769; /sitemap.xml served the SPA shell until now.
  const urls = [
    { loc: `${ORIGIN}/`, priority: '1.0' },
    { loc: `${ORIGIN}/mobility-teams/`, priority: '0.9' },
    { loc: `${ORIGIN}/relocation-checklist/`, priority: '0.9' },
    { loc: `${ORIGIN}/blog/`, priority: '0.8' },
    ...posts.map((p) => ({ loc: `${ORIGIN}/blog/${p.slug}/`, priority: '0.7' })),
  ];
  const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((u) => `  <url><loc>${u.loc}</loc><priority>${u.priority}</priority></url>`).join('\n')}
</urlset>
`;
  await writeFile(path.join(DIST, 'sitemap.xml'), sitemap, 'utf8');
  console.log(`prerender-content: wrote dist/sitemap.xml (${urls.length} urls)`);
}

main().catch((err) => {
  console.error('[prerender-content] FAILED —', err?.message || err);
  process.exit(1);
});
