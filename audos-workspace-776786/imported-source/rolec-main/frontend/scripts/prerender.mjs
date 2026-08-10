// frontend/scripts/prerender.mjs
// Build-time prerender: renders each PUBLIC marketing route in headless
// Chromium and writes the serialised HTML into dist/<route>/index.html so
// non-JS crawlers (ChatGPT-User, OAI-SearchBot, Googlebot fallback, etc.)
// receive real page content instead of the ~76-char "Loading ReloPass…" shell.
//
// Runs AFTER `vite build` (see the "build" script in package.json).
// Purely additive to build output:
//   - authenticated routes are never visited;
//   - only dist/index.html and dist/<route>/index.html files are written;
//   - 404.html and every other dist file are untouched;
//   - src/main.tsx keeps ReactDOM.createRoot — the client re-renders over the
//     snapshot on load, so runtime behaviour is unchanged.
//
// If headless Chromium cannot launch in the build environment the script logs
// a warning and exits 0, leaving the plain SPA build intact (a missing
// prerender must not fail the whole build). Use scripts/verify-prerender.mjs
// to enforce prerender quality where a browser IS available.
//
// Requires the Chromium browser binary: npx playwright install chromium --with-deps

import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
// Reuses the chromium bundled with the existing @playwright/test devDependency
// (no extra `playwright` package needed).
import { chromium } from '@playwright/test'

const __dirname = dirname(fileURLToPath(import.meta.url))
const FRONTEND_ROOT = join(__dirname, '..')
const DIST = join(FRONTEND_ROOT, 'dist')
const PORT = 4173
const ORIGIN = `http://localhost:${PORT}`

// PUBLIC MARKETING ROUTES — derived from ROUTE_DEFS in src/navigation/routes.ts:
// every route whose roles include 'PUBLIC' and whose path has no dynamic
// segment, EXCLUDING non-marketing public surfaces:
//   /auth, /login                    — auth screens (/login is an Auth alias)
//   /test-drive, /test-drive/survey  — interactive test-drive flow; content is
//                                      session-dependent, so a build-time
//                                      snapshot would capture the wrong state
//   /provider/portal, /supplier/quote — magic-link (JWT) surfaces that render
//                                      an error/empty state without a token
//                                      ("blank beats wrong")
const ROUTES = [
  '/',
  '/platform',
  '/why',
  '/how-it-works',
  '/get-started',
  '/security',
  '/privacy',
  '/compliance',
  '/access',
]

// Reject snapshots that are still the empty shell. The pre-prerender baseline
// is ~76 chars of visible text ("Loading ReloPass…").
const MIN_VISIBLE_CHARS = 200

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function visibleText(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

// Serve dist/ with `vite preview` (already a dependency; appType defaults to
// 'spa', so deep routes fall back to index.html). Spawned via the vite bin
// with process.execPath so it works without a shell and cross-platform.
async function startPreviewServer() {
  const viteBin = join(FRONTEND_ROOT, 'node_modules', 'vite', 'bin', 'vite.js')
  if (!existsSync(viteBin)) {
    throw new Error(`vite binary not found at ${viteBin} — run npm install first`)
  }
  const proc = spawn(
    process.execPath,
    [viteBin, 'preview', '--port', String(PORT), '--strictPort'],
    { cwd: FRONTEND_ROOT, stdio: 'pipe' },
  )
  proc.stdout.on('data', () => {})
  proc.stderr.on('data', (d) => process.stderr.write(`[vite preview] ${d}`))

  const deadline = Date.now() + 20000
  while (Date.now() < deadline) {
    if (proc.exitCode !== null) {
      throw new Error(`vite preview exited early with code ${proc.exitCode}`)
    }
    try {
      const res = await fetch(`${ORIGIN}/`)
      if (res.ok) {
        console.log(`Static server (vite preview) ready on ${ORIGIN}`)
        return proc
      }
    } catch {
      // not up yet
    }
    await sleep(250)
  }
  proc.kill()
  throw new Error('vite preview did not become ready within 20s')
}

async function prerender() {
  console.log('Starting prerender...')

  if (!existsSync(DIST)) {
    throw new Error('dist/ not found — run vite build first')
  }

  const server = await startPreviewServer()

  let browser
  try {
    browser = await chromium.launch({ headless: true })
  } catch (err) {
    server.kill()
    console.warn('\nWARNING: headless Chromium could not launch — skipping prerender.')
    console.warn('The plain SPA build is left intact. To enable prerendering, run:')
    console.warn('  npx playwright install chromium --with-deps')
    console.warn(`Launch error: ${err.message}\n`)
    // Missing browser must not fail the build (prerender is additive).
    process.exit(0)
  }

  const results = []

  for (const route of ROUTES) {
    const url = `${ORIGIN}${route}`
    console.log(`Rendering ${route}...`)

    const context = await browser.newContext({
      // Empty storage = unauthenticated marketing view.
      storageState: { cookies: [], origins: [] },
    })
    // Don't send analytics from build-time renders, and keep 'networkidle'
    // from hanging on long-polling analytics connections.
    await context.route(
      (u) => /posthog|sentry|ingest|analytics/i.test(u.href),
      (r) => r.abort(),
    )
    const page = await context.newPage()

    try {
      await page.goto(url, { waitUntil: 'load', timeout: 30000 })
      // Best effort: let data fetches settle; marketing copy is static so a
      // timeout here is not fatal.
      await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {})
      try {
        await page.waitForSelector('h1', { timeout: 10000 })
      } catch {
        console.warn(`  Warning: no h1 found on ${route}`)
      }

      const html = await page.evaluate(
        () => '<!DOCTYPE html>\n' + document.documentElement.outerHTML,
      )

      const visLen = visibleText(html).length
      if (visLen < MIN_VISIBLE_CHARS) {
        // Keep the vite-generated SPA fallback rather than shipping a shell
        // snapshot — blank beats wrong.
        console.error(
          `  UNDER-TARGET: ${route} visible text only ${visLen} chars — skipping`,
        )
        results.push({ route, status: 'UNDER-TARGET', visibleLength: visLen })
        continue
      }

      let outPath
      if (route === '/') {
        outPath = join(DIST, 'index.html')
      } else {
        const dir = join(DIST, route.slice(1))
        mkdirSync(dir, { recursive: true })
        outPath = join(dir, 'index.html')
      }

      writeFileSync(outPath, html, 'utf8')
      console.log(`  Written ${outPath} (${Math.round(html.length / 1024)}KB, ${visLen} visible chars)`)
      results.push({ route, status: 'OK', visibleLength: visLen, path: outPath })
    } catch (err) {
      console.error(`  ERROR on ${route}:`, err.message)
      results.push({ route, status: 'ERROR', error: err.message })
    } finally {
      await context.close()
    }
  }

  await browser.close()
  server.kill()

  console.log('\n=== Prerender Results ===')
  for (const r of results) {
    const icon = r.status === 'OK' ? '✓' : r.status === 'UNDER-TARGET' ? '⚠' : '✗'
    console.log(
      `${icon} ${r.route.padEnd(20)} ${r.status}${r.visibleLength ? ` (${r.visibleLength} chars)` : ''}`,
    )
  }

  const failed = results.filter((r) => r.status !== 'OK')
  if (failed.length > 0) {
    console.warn(`\n${failed.length} route(s) did not meet target.`)
    // Do not exit 1 — partial prerender is better than build failure.
    // Failed/UNDER-TARGET routes keep the SPA fallback behaviour.
  }

  return results
}

prerender().catch((err) => {
  console.error('Prerender failed:', err)
  process.exit(1)
})
