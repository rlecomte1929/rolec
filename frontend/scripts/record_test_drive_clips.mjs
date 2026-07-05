/**
 * TD-11 (AIQ-1429) — record the 3 /test-drive explainer clips (bounded v1).
 *
 * Headless Playwright recordVideo walks read-only screens on prod with the seeded
 * demo accounts (no data writes). Captions are drawn as an in-page overlay during
 * recording (this machine's ffmpeg lacks the drawtext/subtitles text filters), so
 * the resulting .webm already carries burned-in captions — a separate step just
 * transcodes webm -> mp4. Never throws on a flaky step; captures what rendered.
 *
 * Usage: node scripts/record_test_drive_clips.mjs [outDir]
 */
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.TD11_BASE_URL || 'https://relopass.com';
const OUT = process.argv[2] || path.resolve('public/test-drive/_raw');
const SIZE = { width: 1280, height: 720 };
const HR = { id: 'hr@testingapril.com', pw: 'HrPass!1' };
const EMP = { id: 'employee@testingapril.com', pw: 'EmpPass!1' };

fs.mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Injected into every page/navigation: a fixed lower-third caption bar + window.__setCap.
const CAPTION_INIT = () => {
  window.__setCap = (t) => {
    let d = document.getElementById('__td_cap');
    if (!d && document.body) {
      d = document.createElement('div');
      d.id = '__td_cap';
      d.style.cssText =
        'position:fixed;left:50%;transform:translateX(-50%);bottom:28px;max-width:82%;z-index:2147483647;' +
        'background:rgba(11,43,67,0.9);color:#fff;font:600 21px/1.35 Helvetica,Arial,sans-serif;' +
        'padding:11px 20px;border-radius:11px;text-align:center;box-shadow:0 6px 24px rgba(0,0,0,.35);pointer-events:none;';
      document.body.appendChild(d);
    }
    if (d) d.textContent = t;
  };
};

async function cap(page, text) {
  try { await page.evaluate((t) => window.__setCap && window.__setCap(t), text); } catch { /* mid-nav */ }
}

// Wait until the page's "Loading…" placeholders clear (prod data loads are slow).
async function waitLoaded(page) {
  try { await page.waitForFunction(() => !/Loading/i.test(document.body?.innerText || ''), { timeout: 12000 }); }
  catch { /* leave whatever rendered */ }
  await sleep(600);
}

async function login(page, who) {
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' });
  await page.fill('#auth-login-identifier', who.id);
  await page.fill('#auth-login-password', who.pw);
  await page.press('#auth-login-password', 'Enter');
  await page.waitForFunction(() => !!localStorage.getItem('relopass_token'), { timeout: 20000 });
}

async function record(name, fn) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: SIZE, recordVideo: { dir: OUT, size: SIZE } });
  await context.addInitScript(CAPTION_INIT);
  const page = await context.newPage();
  let note = 'ok';
  try { await fn(page); }
  catch (e) { note = 'partial: ' + String(e).split('\n')[0].slice(0, 120); console.warn(`[${name}] ${note}`); }
  await sleep(900);
  await context.close();
  fs.renameSync(await page.video().path(), path.join(OUT, `${name}.webm`));
  await browser.close();
  console.log(`[${name}] -> ${name}.webm (${note})`);
}

async function overview(page) {
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
  await sleep(1500);
  await cap(page, 'ReloPass — the operating layer for cross-border relocation.');
  await sleep(4500);
  await cap(page, 'Relocation fails in the handoffs — HR, employees, providers.');
  for (let i = 1; i <= 3; i++) { await page.evaluate((f) => window.scrollTo({ top: document.body.scrollHeight * f, behavior: 'smooth' }), i / 6); await sleep(2600); }
  await cap(page, 'ReloPass keeps the whole case in one place — visible, compliant, on-time.');
  for (let i = 4; i <= 6; i++) { await page.evaluate((f) => window.scrollTo({ top: document.body.scrollHeight * f, behavior: 'smooth' }), i / 6); await sleep(2600); }
}

async function hrSide(page) {
  await login(page, HR);
  await page.goto(`${BASE}/hr/command-center`, { waitUntil: 'domcontentloaded' });
  await cap(page, 'The HR side — one command center for every relocation.');
  await waitLoaded(page);
  await sleep(5000);
  await cap(page, 'Every case, its stage, and what needs attention — at a glance.');
  await page.evaluate(() => window.scrollTo({ top: 500, behavior: 'smooth' }));
  await sleep(5000);
  await page.evaluate(() => window.scrollTo({ top: 1000, behavior: 'smooth' }));
  await cap(page, 'Configure a case, apply your policy, and hand it to the employee.');
  await sleep(5500);
}

async function employeeSide(page) {
  await login(page, EMP);
  await page.goto(`${BASE}/employee/dashboard`, { waitUntil: 'domcontentloaded' });
  await sleep(1500);
  await cap(page, 'The employee side — from intake to roadmap.');
  await sleep(4500);
  let caseId = null;
  try {
    const href = await page.evaluate(() => {
      const a = [...document.querySelectorAll('a[href*="/employee/case/"]')][0];
      return a ? a.getAttribute('href') : null;
    });
    const m = href && href.match(/\/employee\/case\/([^/]+)/);
    caseId = m && m[1];
  } catch { /* ignore */ }
  await cap(page, 'Your cases, intake, roadmap, and services — all in one place.');
  await page.evaluate(() => window.scrollTo({ top: 400, behavior: 'smooth' }));
  await sleep(4500);
  if (caseId) {
    await page.goto(`${BASE}/employee/case/${caseId}/roadmap`, { waitUntil: 'domcontentloaded' });
    await cap(page, 'A guided roadmap lays out every step of the move.');
    await waitLoaded(page);
    await sleep(6500);
    await page.evaluate(() => window.scrollTo({ top: 500, behavior: 'smooth' }));
    await cap(page, 'Each step shows what to do, what it needs, and where it stands.');
    await sleep(5500);
  } else {
    await cap(page, 'Complete intake, then reach your roadmap.');
    await sleep(6000);
  }
}

async function main() {
  const only = (process.env.CLIPS || '').split(',').map((s) => s.trim()).filter(Boolean);
  const want = (n) => only.length === 0 || only.includes(n);
  console.log(`Recording against ${BASE} -> ${OUT}${only.length ? ` (only: ${only.join(',')})` : ''}`);
  if (want('overview')) await record('overview', overview);
  if (want('hr-side')) await record('hr-side', hrSide);
  if (want('employee-side')) await record('employee-side', employeeSide);
  console.log('DONE — webms (captions burned in) in', OUT);
}

main().catch((e) => { console.error(e); process.exit(1); });
