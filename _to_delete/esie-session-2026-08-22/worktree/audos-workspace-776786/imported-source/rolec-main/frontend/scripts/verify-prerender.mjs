// frontend/scripts/verify-prerender.mjs
// Verify the prerendered HTML files in dist/ contain real page content.
// Pass criteria per route: visible text > 500 chars AND golden phrase present.
// Run AFTER `npm run build`:  node scripts/verify-prerender.mjs
//
// Golden phrases are REAL copy verified against the content module each page
// actually imports (all under src/pages/...):
//   /             → landing/landingContent.ts        hero.headline
//   /platform     → public/platformContent.ts        hero.headline
//   /why          → public/whyReloPassContent.ts     hero.headline
//   /how-it-works → public/howItWorksContent.ts      hero.headline
//   /get-started  → public/getStartedContent.ts      hero.subheadline
//   /security     → public/securityContent.ts        hero.headline
//   /privacy      → public/privacyContent.ts         hero.headline
//   /compliance   → public/complianceContent.ts      hero.headline
//   /access       → public/accessContent.ts          hero.headline

import { readFileSync, existsSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const DIST = join(__dirname, '..', 'dist')

const TARGETS = [
  { route: '/',             file: 'index.html',              phrase: 'Cut the cost of every cross-border move' },
  { route: '/platform',     file: 'platform/index.html',     phrase: 'Every part of the relocation workflow' },
  { route: '/why',          file: 'why/index.html',          phrase: 'Relocation fails in the handoffs' },
  { route: '/how-it-works', file: 'how-it-works/index.html', phrase: 'Four steps from fragmented to structured' },
  { route: '/get-started',  file: 'get-started/index.html',  phrase: 'Tell us how your relocations run today' },
  { route: '/security',     file: 'security/index.html',     phrase: 'Built to handle sensitive relocation data' },
  { route: '/privacy',      file: 'privacy/index.html',      phrase: 'Privacy Policy' },
  { route: '/compliance',   file: 'compliance/index.html',   phrase: 'Mobility AI your auditor will trust' },
  { route: '/access',       file: 'access/index.html',       phrase: 'Three ways in' },
]

const MIN_VISIBLE = 500
let passed = 0
let failed = 0

console.log('\n=== Prerender Verification ===')
console.log(`${'Route'.padEnd(20)} ${'File'.padEnd(35)} ${'VisLen'.padEnd(8)} ${'Phrase'.padEnd(8)} Result`)
console.log('-'.repeat(90))

for (const t of TARGETS) {
  const filePath = join(DIST, t.file)

  if (!existsSync(filePath)) {
    console.log(`${('✗ ' + t.route).padEnd(20)} ${t.file.padEnd(35)} ${'MISSING'.padEnd(8)} ${'—'.padEnd(8)} FAIL`)
    failed++
    continue
  }

  const html = readFileSync(filePath, 'utf8')
  const visible = html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  const visLen = visible.length
  const phraseFound = visible.toLowerCase().includes(t.phrase.toLowerCase())
  const ok = visLen > MIN_VISIBLE && phraseFound

  if (ok) passed++
  else failed++

  const icon = ok ? '✓' : '✗'
  console.log(
    `${(icon + ' ' + t.route).padEnd(20)} ${t.file.padEnd(35)} ${String(visLen).padEnd(8)} ${(phraseFound ? 'Y' : 'N').padEnd(8)} ${ok ? 'PASS' : 'FAIL'}`,
  )
}

console.log('-'.repeat(90))
console.log(`\nResult: ${passed}/${TARGETS.length} passed, ${failed}/${TARGETS.length} failed`)
console.log('Baseline was: ~76 chars visible text ("Loading ReloPass…" shell)\n')

if (failed > 0) {
  process.exit(1)
}
