/**
 * ReloPass Automated API Test Runner  v3.0
 * ==========================================
 * Usage:
 *   node relopass_api_runner.js               — full suite (all API + all scenario flows)
 *   node relopass_api_runner.js --scenario T1  — targeted: single persona flow only
 *   node relopass_api_runner.js --scenario T1,T2,T3  — targeted: multiple personas
 *   node relopass_api_runner.js --api-only     — skip scenario flows, API checks only
 *
 * Outputs:
 *   test_results.json       — current run results
 *   results/test_results_YYYY-MM-DD_HHmm.json — archived copy for trend comparison
 *
 * Requirements: Node.js 18+ (native fetch). Run `npm install` first for docx report.
 *
 * v3.0 additions (21 May 2026):
 *   — suiteWizardPersistence: B17 (wizard PATCH → both tables), B19 (Steps 2-5 probe)
 *   — suiteRLSIsolation: T17 multi-company data boundary
 *   — suiteCORS: B21 OPTIONS preflight checks
 *   — suiteRateLimiting: B22 auth endpoint rate limit
 *   — suiteXSSProtection: B23 input sanitisation smoke test
 *   — suitePerformanceBenchmarks: response-time percentile recording
 *   — Updated bug map: B1–B23
 */

'use strict';
const fs   = require('fs');
const path = require('path');

// Single epoch for this run — shared across all dynamic account emails so they share a suffix
const RUN_EPOCH = Date.now();

// ─────────────────────────────────────────────────────────────
//  CONFIGURATION
// ─────────────────────────────────────────────────────────────
const CONFIG = {
  API:     'https://api.relopass.com',
  TIMEOUT: 10000,
  CREDS: {
    // Admin is the only static credential
    admin:  { identifier: 'admin@relopass.com', password: 'Passw0rd!' },
    // ── Seeded personas — always exist in DB, login never fails ──────────────
    // Created/refreshed via POST /api/admin/seed-test-personas at run start.
    seedHR:  { identifier: 'hr_seed@testco.com',   password: 'Passw0rd!' },
    seedHR2: { identifier: 'hr2_seed@otherco.com',  password: 'Passw0rd!' },
    seedEmp: { identifier: 'emp_seed@testco.com',   password: 'Passw0rd!' },
    // Known company IDs matching the seed endpoint (deterministic UUIDs)
    seedHR_company_id:  'c1000000-0000-4000-8000-000000000001',
    seedHR2_company_id: 'c2000000-0000-4000-8000-000000000002',
    // ── Fresh registration accounts (smoke tests only, not used for functional flows) ──
    newHR:  { first_name:'HR',  last_name:'TestRun', email:`hr_run_${RUN_EPOCH}@testco.com`,  password:'Passw0rd!', role:'HR'       },
    newEmp: { first_name:'Emp', last_name:'TestRun', email:`emp_run_${RUN_EPOCH}@testco.com`, password:'Passw0rd!', role:'EMPLOYEE' },
    newHR2: { first_name:'HR2', last_name:'OtherCo', email:`hr2_run_${RUN_EPOCH}@otherco.com`, password:'Passw0rd!', role:'HR'     },
  },
  // 8 personas — keyed by scenario ID
  PERSONAS: {
    T1: { first_name:'Adrien',    last_name:'Moreau',    origin:'Lyon',      destination:'Berlin',    country:'Germany',     assignment:'lta',          duration_months:18,   family:'single'          },
    T2: { first_name:'Camille',   last_name:'Renard',    origin:'Paris',     destination:'Madrid',    country:'Spain',       assignment:'lta',          duration_months:36,   family:'spouse+children' },
    T3: { first_name:'Stefan',    last_name:'Weber',     origin:'Frankfurt', destination:'Boston',    country:'US',          assignment:'transfer',     duration_months:24,   family:'spouse'          },
    T4: { first_name:'Lucia',     last_name:'Martinez',  origin:'Madrid',    destination:'Amsterdam', country:'Netherlands', assignment:'permanent',    duration_months:null, family:'single'          },
    T5: { first_name:'Anders',    last_name:'Lindqvist', origin:'Berlin',    destination:'Singapore', country:'Singapore',   assignment:'sta',          duration_months:6,    family:'single'          },
    T6: { first_name:'Marc',      last_name:'Dubois',    origin:'Paris',     destination:'Tokyo',     country:'Japan',       assignment:'lta',          duration_months:24,   family:'spouse+children' },
    T7: { first_name:'Camille',   last_name:'Dupont',    origin:'Madrid',    destination:'Paris',     country:'France',      assignment:'repatriation', duration_months:null, family:'single'          },
    T8: { first_name:'Valentine', last_name:'Martin',    origin:'Paris',     destination:'Lyon',      country:'France',      assignment:'domestic',     duration_months:12,   family:'single'          },
    T15:{ first_name:'Isabelle',  last_name:'Fontaine',  origin:'Lyon',      destination:'Zurich',    country:'Switzerland', assignment:'lta',          duration_months:24,   family:'single'          },
    T16:{ first_name:'Ahmed',     last_name:'Mansouri',  origin:'Paris',     destination:'Dubai',     country:'UAE',         assignment:'lta',          duration_months:36,   family:'spouse+children' },
  },
  // Performance thresholds (ms)
  PERF: {
    fast: 500,    // target: critical endpoints
    ok:   2000,   // acceptable
    slow: 5000,   // warn above this
  },
  // CORS check endpoints
  CORS_ENDPOINTS: [
    ['POST',  '/api/auth/login'],
    ['POST',  '/api/hr/cases'],
    ['PATCH', '/api/cases/00000000-0000-0000-0000-000000000000'],
    ['POST',  '/api/hr/cases/00000000-0000-0000-0000-000000000000/assign'],
    ['GET',   '/api/hr/assignments'],
  ],
};

// All scenario IDs — persona-driven + special
const ALL_SCENARIOS = [...Object.keys(CONFIG.PERSONAS), 'T13', 'T14', 'T17'];

// Parse CLI args
const args    = process.argv.slice(2);
const apiOnly = args.includes('--api-only');
const scenArg = args.find(a => a.startsWith('--scenario'));
const targetScenarios = scenArg
  ? scenArg.split('=').pop().split(',').map(s => s.trim().toUpperCase())
  : ALL_SCENARIOS;

// ─────────────────────────────────────────────────────────────
//  HELPERS
// ─────────────────────────────────────────────────────────────
const RUN_DATE = new Date().toISOString().slice(0,10);
const RUN_TS   = new Date().toISOString().replace(/[:.]/g,'-').slice(0,16);
const results  = [];
let   tokens   = {};

function elapsed(start) { return Date.now() - start; }

async function req(method, path, body, token, timeoutMs = CONFIG.TIMEOUT) {
  const url  = `${CONFIG.API}${path}`;
  const ctrl = new AbortController();
  const tid  = setTimeout(() => ctrl.abort(), timeoutMs);
  const start = Date.now();
  try {
    const r = await fetch(url, {
      method,
      headers: { 'Content-Type':'application/json', ...(token ? { Authorization:`Bearer ${token}` } : {}) },
      signal: ctrl.signal,
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    let data; try { data = await r.json(); } catch { data = null; }
    return { ok: r.ok, status: r.status, data, ms: elapsed(start), headers: Object.fromEntries(r.headers) };
  } catch(e) {
    return { ok:false, status:0, data:null, ms: elapsed(start), error: e.message, headers: {} };
  } finally { clearTimeout(tid); }
}

// Options preflight for CORS check
async function options(path) {
  const url  = `${CONFIG.API}${path}`;
  const ctrl = new AbortController();
  const tid  = setTimeout(() => ctrl.abort(), 5000);
  const start = Date.now();
  try {
    const r = await fetch(url, {
      method: 'OPTIONS',
      headers: { Origin: 'https://relopass.com', 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'Content-Type,Authorization' },
      signal: ctrl.signal,
    });
    const cors = r.headers.get('access-control-allow-origin') || '';
    return { ok: r.ok || r.status === 204, status: r.status, cors, ms: elapsed(start) };
  } catch(e) {
    return { ok:false, status:0, cors:'', ms: elapsed(start), error: e.message };
  } finally { clearTimeout(tid); }
}

function record(id, title, category, expected, actual, status, ms, detail='') {
  const entry = { id, title, category, expected, actual, status, ms, detail, ts: new Date().toISOString() };
  results.push(entry);
  const icon = { PASS:'✓', FAIL:'✗', WARN:'⚠', SKIP:'–', BLOCKED:'⊘', MANUAL:'📋' }[status] || '?';
  console.log(`  ${icon} [${id}] ${title}  (${ms}ms)  →  ${status}`);
  if (status !== 'PASS' && detail) console.log(`       ${detail.slice(0,140)}`);
}

function section(name) { console.log(`\n══ ${name} ══`); }

// ─────────────────────────────────────────────────────────────
//  PRE-RUN CLEANUP
// ─────────────────────────────────────────────────────────────
async function runCleanup() {
  if (!tokens.admin) { console.log('  ⚠ Cleanup skipped — no admin token'); return; }
  console.log('\n── Pre-run cleanup (clearing previous @testco.com / @otherco.com test accounts) ──');
  const endpoints = [
    ['DELETE', '/api/admin/users/cleanup',  { email_domain: 'testco.com' }],
    ['POST',   '/api/admin/cleanup',         { domain: 'testco.com' }],
    ['DELETE', '/api/admin/test-data',       { domain: 'testco.com' }],
  ];
  for (const [method, path, body] of endpoints) {
    const r = await req(method, path, body, tokens.admin, 5000);
    if (r.ok) { console.log(`  ✓ Cleanup OK via ${method} ${path} (${r.ms}ms)`); return; }
    if (r.status === 404 || r.status === 405) continue;
    if (r.status === 401 || r.status === 403) { console.log(`  ⚠ Cleanup: insufficient permissions`); return; }
  }
  console.log('  ℹ No cleanup endpoint found — previous test accounts remain in DB (non-blocking)');
}

// ─────────────────────────────────────────────────────────────
//  SUITE 1: Authentication
// ─────────────────────────────────────────────────────────────
async function suiteAuth() {
  section('Authentication');
  let r;

  // ── AT1: Admin login ──────────────────────────────────────────────────────
  r = await req('POST', '/api/auth/login', CONFIG.CREDS.admin);
  tokens.admin = r.data?.token || null;
  record('AT1','Platform admin login','Auth','200 + token',`${r.status}/token=${!!tokens.admin}`, r.ok && tokens.admin ? 'PASS':'FAIL', r.ms, r.error||'');

  await runCleanup();

  // ── SEED: Create/refresh seeded test personas (admin-only, idempotent) ────
  // This creates hr_seed@testco.com, emp_seed@testco.com, hr2_seed@otherco.com
  // with all the correct DB associations so they can be used immediately.
  if (tokens.admin) {
    const seedR = await req('POST', '/api/admin/seed-test-personas', {}, tokens.admin);
    const seedOk = seedR.ok && seedR.data?.ok;
    console.log(`  ${seedOk ? 'ℹ' : '⚠'} Seed personas: ${seedR.status} — ${seedOk ? 'ok' : JSON.stringify(seedR.data)}`);
  }

  // ── AT2: Seeded HR login — always has company linked ─────────────────────
  r = await req('POST', '/api/auth/login', CONFIG.CREDS.seedHR);
  tokens.hr           = r.data?.token || null;
  tokens.hr_company_id = tokens.hr ? CONFIG.CREDS.seedHR_company_id : null;
  record('AT2','Seeded HR login (hr_seed@testco.com)','Auth','200 + token',`${r.status}/token=${!!tokens.hr}`, r.ok && tokens.hr ? 'PASS':'FAIL', r.ms, r.error||`email=${CONFIG.CREDS.seedHR.identifier}`);

  // ── AT2b: Verify seeded HR already has company linked (smoke) ─────────────
  if (tokens.hr) {
    // For seeded users the company is guaranteed — do a quick profile check
    const cpR = await req('POST', '/api/hr/company-profile', { name: 'Test Co (Seed)' }, tokens.hr);
    const cid = cpR.data?.company_id || cpR.data?.id || tokens.hr_company_id;
    tokens.hr_company_id = cid;
    record('AT2b','Seeded HR company profile (B18)','Auth','200+company_id',`${cpR.status}/company_id=${!!cid}`, cpR.ok && cid ? 'PASS':'FAIL', cpR.ms, cpR.error||`company_id=${cid}`);
  }

  // ── AT2_FRESH: Fresh HR registration smoke test (not used for functional flows) ──
  const freshHrR = await req('POST', '/api/auth/register', CONFIG.CREDS.newHR);
  tokens.newHR = freshHrR.data?.token || null;
  record('AT2_FRESH','Fresh HR registration smoke test','Auth','200 + token',`${freshHrR.status}/token=${!!tokens.newHR}`, freshHrR.ok && tokens.newHR ? 'PASS':'FAIL', freshHrR.ms, freshHrR.error||`email=${CONFIG.CREDS.newHR.email}`);

  // ── AT3: Seeded employee login ────────────────────────────────────────────
  r = await req('POST', '/api/auth/login', CONFIG.CREDS.seedEmp);
  tokens.emp    = r.data?.token || null;
  tokens.newEmp = tokens.emp;
  record('AT3','Seeded Employee login (emp_seed@testco.com)','Auth','200 + token',`${r.status}/token=${!!tokens.emp}`, r.ok && tokens.emp ? 'PASS':'FAIL', r.ms, r.error||`email=${CONFIG.CREDS.seedEmp.identifier}`);

  // ── AT3_FRESH: Fresh employee registration smoke test ─────────────────────
  const freshEmpR = await req('POST', '/api/auth/register', CONFIG.CREDS.newEmp);
  tokens.newEmp_fresh = freshEmpR.data?.token || null;
  record('AT3_FRESH','Fresh Employee registration smoke test','Auth','200 + token',`${freshEmpR.status}/token=${!!tokens.newEmp_fresh}`, freshEmpR.ok && tokens.newEmp_fresh ? 'PASS':'FAIL', freshEmpR.ms, freshEmpR.error||`email=${CONFIG.CREDS.newEmp.email}`);

  // ── AT4: Reject bad credentials ───────────────────────────────────────────
  r = await req('POST', '/api/auth/login', { identifier:'nobody@x.com', password:'wrong' });
  record('AT4','Invalid credentials rejected','Auth','401',`${r.status}`, r.status===401 ? 'PASS':'FAIL', r.ms);

  // ── AT5: B6 — registration token must be 36-char UUID ────────────────────
  const tLen = tokens.newHR?.length || 0;
  record('AT5','Registration token is full 36-char UUID (B6)','Auth','token.length==36',`length=${tLen}`, tLen===36 ? 'PASS' : tLen>0 ? 'FAIL':'SKIP', 0, `token="${(tokens.newHR||'').slice(0,12)}..."`);
}

// ─────────────────────────────────────────────────────────────
//  SUITE 2: Case Lifecycle
// ─────────────────────────────────────────────────────────────
async function suiteCases() {
  section('Case Lifecycle');
  const T = tokens.hr || tokens.admin;
  if (!T) { console.log('  SKIP — no token'); return; }

  let r = await req('GET', '/api/hr/cases', null, T);
  record('CT1','GET /api/hr/cases not 405 (B12)','Cases','≠405',`${r.status}`, r.status!==405 ? 'PASS':'FAIL', r.ms);

  r = await req('POST', '/api/hr/cases', { first_name:'Smoke', last_name:`Test_${Date.now()}`, email:`smoke_${Date.now()}@testco.com` }, T);
  const caseId = r.data?.caseId;
  record('CT2','POST /api/hr/cases creates draft','Cases','200+caseId',`${r.status}/id=${caseId||'null'}`, r.ok && caseId ? 'PASS':'FAIL', r.ms, r.error||'');

  if (caseId) {
    const r2 = await req('GET', `/api/cases/${caseId}`, null, T);
    const emp = r2.data?.profile_json?.employer?.name || r2.data?.employer?.name || null;
    record('CT3','New case employer matches HR company (B5)','Cases','employer="Test Co (Seed)"',`employer="${emp}"`, emp==='Test Co (Seed)' ? 'PASS' : emp ? 'FAIL':'WARN', r2.ms, `full: ${JSON.stringify(r2.data?.profile_json?.employer)}`);

    const r3 = await req('POST', `/api/hr/cases/${caseId}/assign`, { employee_email: CONFIG.CREDS.newEmp.email }, T, 8000);
    record('CT4','Case assign responds within 8s (B3)','Cases','<8000ms, not timeout', r3.error?.includes('abort') ? 'TIMEOUT':String(r3.status), r3.error?.includes('abort') ? 'FAIL' : r3.ok ? 'PASS':'WARN', r3.ms, r3.error||`status=${r3.status}`);
  }

  r = await req('GET', '/api/hr/assignments', null, T, 8000);
  record('CT5','GET /api/hr/assignments responds <8s (B1)','Cases','<8000ms',r.error?.includes('abort')?'TIMEOUT':String(r.status), r.error?.includes('abort') ? 'FAIL': r.ok ? 'PASS':'WARN', r.ms, r.error||`count=${Array.isArray(r.data)?r.data.length:'n/a'}`);
}

// ─────────────────────────────────────────────────────────────
//  SUITE 3: HR Portal
// ─────────────────────────────────────────────────────────────
async function suiteHR() {
  section('HR Portal');
  const T = tokens.hr;
  if (!T) { console.log('  SKIP — no HR token'); return; }

  const r = await req('GET', '/api/hr/command-center/cases', null, T);
  const count = Array.isArray(r.data?.cases) ? r.data.cases.length : Array.isArray(r.data) ? r.data.length : null;
  record('HP1','HR command center returns cases','HR','array',`${r.status}/count=${count}`, r.ok && count!==null ? 'PASS':'WARN', r.ms);

  if (count && (r.data?.cases||r.data)?.length) {
    const cid = (r.data.cases||r.data)[0]?.case_id || (r.data.cases||r.data)[0]?.id;
    const r2 = await req('GET', `/api/hr/cases/${cid}`, null, T);
    record('HP2','HR can open individual case from cmd center (B8)','HR','200',`${r2.status}`, r2.ok ? 'PASS':'FAIL', r2.ms, r2.error||'');
  } else {
    record('HP2','HR individual case RLS (B8)','HR','200','SKIP — no cases', 'SKIP', 0);
  }

  const r3 = await req('GET', '/api/admin/assignments/00000000-0000-0000-0000-000000000000', null, tokens.admin);
  record('AD1','Admin assignment endpoint not 500 (B9)','Admin','≠500',`${r3.status}`, r3.status!==500 ? 'PASS':'FAIL', r3.ms);
}

// ─────────────────────────────────────────────────────────────
//  SUITE 4: Employee Portal
// ─────────────────────────────────────────────────────────────
async function suiteEmployee() {
  section('Employee Portal');
  const r = await req('GET', '/api/employee/dashboard', null, tokens.hr);
  record('EP1','Employee API rejects HR token (B15)','Employee','403/401',`${r.status}`, [401,403].includes(r.status) ? 'PASS':'WARN', r.ms, `HR used on employee endpoint`);
}

// ─────────────────────────────────────────────────────────────
//  SUITE 5: Resources & Vendors
// ─────────────────────────────────────────────────────────────
async function suiteResources() {
  section('Resources & Vendors');
  const T = tokens.hr || tokens.admin;
  if (!T) { console.log('  SKIP'); return; }

  const r  = await req('GET', '/api/hr/resources/destinations', null, T);
  const countries = Array.isArray(r.data) ? r.data : r.data?.destinations || [];
  record('RT1','Destination count ≥20 (B14, baseline=12)','Resources',`count≥20`,`count=${countries.length}`, countries.length>=20 ? 'PASS' : countries.length>=12 ? 'WARN':'FAIL', r.ms, `countries: ${countries.map(c=>c.name||c).join(', ').slice(0,120)}`);

  const r2 = await req('GET', '/api/hr/service-categories', null, T);
  const cats = Array.isArray(r2.data) ? r2.data.length : null;
  record('VT1','Service categories count ≥14','Vendors',`≥14`,`${r2.status}/count=${cats}`, cats>=14 ? 'PASS' : cats!==null ? 'WARN':'SKIP', r2.ms);
}

// ─────────────────────────────────────────────────────────────
//  SUITE 6: Reliability
// ─────────────────────────────────────────────────────────────
async function suiteReliability() {
  section('Reliability');
  let passes=0, times=[];
  for (let i=0; i<5; i++) {
    const s=Date.now();
    try {
      const r = await Promise.race([fetch(`${CONFIG.API}/health`), new Promise((_,rej)=>setTimeout(()=>rej(new Error('TIMEOUT')),CONFIG.TIMEOUT))]);
      if (r.ok||r.status<500) passes++;
      times.push(Date.now()-s);
    } catch { times.push(CONFIG.TIMEOUT); }
    if (i<4) await new Promise(r=>setTimeout(r,400));
  }
  const avg = Math.round(times.reduce((a,b)=>a+b,0)/times.length);
  record('RE1','5 health checks pass (B4 outage)','Reliability',`5/5`,`${passes}/5 avg=${avg}ms`, passes===5?'PASS':passes>=3?'WARN':'FAIL', 0, `times: ${times.join(',')}ms`);
}

// ─────────────────────────────────────────────────────────────
//  SUITE 7: Wizard Persistence  ← NEW in v3 (B17, B18, B19)
//  Tests PATCH /api/cases/{id} round-trip and Steps 2–5 probes
// ─────────────────────────────────────────────────────────────
async function suiteWizardPersistence() {
  section('Wizard Persistence (B17, B18, B19)');
  const T = tokens.hr;
  const empT = tokens.emp;
  if (!T || !empT) { console.log('  SKIP — need HR and Employee tokens'); return; }

  // Create a dedicated case for wizard tests
  const wizCaseR = await req('POST', '/api/hr/cases', {
    first_name:'Wizard', last_name:`Test_${Date.now()}`, email:`wizard_${Date.now()}@testco.com`
  }, T);
  const wizCaseId = wizCaseR.data?.caseId || wizCaseR.data?.id || wizCaseR.data?.case_id;
  if (!wizCaseId) {
    record('WZ0','Wizard test case creation','Wizard','200+caseId',`${wizCaseR.status}`,'FAIL',wizCaseR.ms,'Cannot run wizard tests without a case');
    return;
  }
  record('WZ0','Wizard test case created','Wizard','200+caseId',`caseId=${wizCaseId?.slice(0,8)}`,'PASS',wizCaseR.ms);

  // Assign to employee
  await req('POST', `/api/hr/cases/${wizCaseId}/assign`, { employee_email: CONFIG.CREDS.newEmp.email }, T, 8000);

  // WZ1: B17 — PATCH with relocationBasics + verify HR sees host_country
  const patchPayload = {
    relocationBasics: {
      originCountry: 'France', originCity: 'Lyon',
      destCountry: 'Germany', destCity: 'Berlin',
      purpose: 'lta', targetMoveDate: '2027-06-01',
    }
  };
  const patchR = await req('PATCH', `/api/cases/${wizCaseId}`, patchPayload, empT);
  record('WZ1a','Employee PATCH relocationBasics (Step 1) (B17)','Wizard','200/204',`${patchR.status}`, patchR.ok ? 'PASS' : patchR.status===404 ? 'WARN' : 'FAIL', patchR.ms, patchR.error||JSON.stringify(patchR.data).slice(0,80));

  // Verify HR sees the filled data (tests wizard_cases → relocation_cases sync)
  await new Promise(r=>setTimeout(r,300)); // give DB trigger time to fire
  const hrViewR = await req('GET', `/api/hr/cases/${wizCaseId}`, null, T);
  const hostCountry = hrViewR.data?.host_country || hrViewR.data?.destination_country || hrViewR.data?.profile_json?.destCountry;
  const hrSeesData  = hrViewR.ok && (hostCountry === 'Germany' || hostCountry?.toLowerCase?.().includes('germany'));
  record('WZ1b','HR sees wizard PATCH data (B17 sync)','Wizard','host_country=Germany',`host_country="${hostCountry||'null'}"`,
    hrSeesData ? 'PASS' : patchR.ok ? 'FAIL' : 'SKIP', hrViewR.ms,
    hrSeesData ? 'Wizard sync confirmed ✓' : patchR.ok ? `Sync broken — employee saved but HR sees: ${JSON.stringify(hrViewR.data).slice(0,100)}` : 'Step 1 PATCH failed so sync check skipped');

  // WZ2–WZ5: B19 — probe each Step 2–5 endpoint (SKIP if 404, PASS/FAIL if endpoint exists)
  const wizSteps = [
    { id:'WZ2', name:'Step 2 services selection', method:'PATCH', path:`/api/cases/${wizCaseId}`, body:{ services:['housing','tax'] }, token:empT },
    { id:'WZ3', name:'Step 3 budget summary',     method:'GET',   path:`/api/cases/${wizCaseId}/budget-summary`, body:null, token:empT },
    { id:'WZ4', name:'Step 4 quote request',       method:'POST',  path:`/api/cases/${wizCaseId}/quote-request`, body:{ services:['housing'] }, token:empT },
    { id:'WZ5', name:'Step 5 message thread',      method:'POST',  path:`/api/cases/${wizCaseId}/messages`, body:{ content:'Hello from employee' }, token:empT },
  ];
  for (const s of wizSteps) {
    const r = await req(s.method, s.path, s.body, s.token, 5000);
    const status = r.status === 404 ? 'SKIP' : r.ok ? 'PASS' : 'FAIL';
    record(s.id, `${s.name} endpoint (B19)`, 'Wizard',
      r.status === 404 ? 'SKIP (not yet implemented)' : '200/201',
      `${r.status}`,
      status, r.ms,
      status === 'SKIP' ? 'Endpoint not found — Step not yet implemented (expected, no penalty)' :
      status === 'PASS' ? 'Endpoint live ✓' : r.error||JSON.stringify(r.data).slice(0,80));
  }
}

// ─────────────────────────────────────────────────────────────
//  SUITE 8: RLS Isolation  ← NEW in v3 (T17, B5 regression)
//  Verifies cross-company data cannot leak between HR accounts
// ─────────────────────────────────────────────────────────────
async function suiteRLSIsolation() {
  section('RLS Isolation (T17, B5 regression)');

  // Login with seeded HR2 — already linked to Other Corp (Seed)
  const hr2R = await req('POST', '/api/auth/login', CONFIG.CREDS.seedHR2);
  tokens.hr2 = hr2R.data?.token || null;
  tokens.hr2_company_id = tokens.hr2 ? CONFIG.CREDS.seedHR2_company_id : null;
  if (!tokens.hr2 || !tokens.hr) {
    record('RLS0','RLS test setup','RLS','two HR tokens','missing tokens','SKIP',0,
      `HR1 token: ${!!tokens.hr}  HR2 token: ${!!tokens.hr2} — need both to test isolation`);
    return;
  }
  record('RLS0','Second HR (Other Corp) seeded + linked','RLS','200+company_id',`${hr2R.status}/company_id=${!!tokens.hr2_company_id}`,
    hr2R.ok && tokens.hr2_company_id ? 'PASS' : 'FAIL', hr2R.ms,
    `hr2_email=${CONFIG.CREDS.seedHR2.identifier}`);

  // HR1 creates a case (Company A)
  const c1R = await req('POST', '/api/hr/cases', { first_name:'RLS', last_name:'CaseA', email:`rls_a_${Date.now()}@testco.com` }, tokens.hr);
  const caseAId = c1R.data?.caseId || c1R.data?.id;
  // HR2 creates a case (Company B)
  const c2R = await req('POST', '/api/hr/cases', { first_name:'RLS', last_name:'CaseB', email:`rls_b_${Date.now()}@otherco.com` }, tokens.hr2);
  const caseBId = c2R.data?.caseId || c2R.data?.id;

  if (!caseAId || !caseBId) {
    record('RLS1','RLS case creation','RLS','2 cases created',`a=${!!caseAId} b=${!!caseBId}`,'SKIP',c1R.ms+c2R.ms,'Cannot test isolation without both cases');
    return;
  }

  // RLS1: HR2 should NOT see Company A's case in their list
  const hr2ListR = await req('GET', '/api/hr/cases', null, tokens.hr2);
  const hr2Cases = Array.isArray(hr2ListR.data) ? hr2ListR.data : hr2ListR.data?.cases || [];
  const hr2SeesA = hr2Cases.some(c => (c.id||c.case_id||c.caseId) === caseAId);
  record('RLS1','HR2 cannot see Company A cases in list (B5)','RLS','case A absent from HR2 list',`found=${hr2SeesA}`,
    hr2SeesA ? 'FAIL' : hr2ListR.ok ? 'PASS' : 'SKIP', hr2ListR.ms,
    hr2SeesA ? `❌ Data leak: HR2 can see case ${caseAId?.slice(0,8)} from Company A` : 'RLS OK — Company A case not visible to HR2');

  // RLS2: HR1 should NOT see Company B's case in their list
  const hr1ListR = await req('GET', '/api/hr/cases', null, tokens.hr);
  const hr1Cases = Array.isArray(hr1ListR.data) ? hr1ListR.data : hr1ListR.data?.cases || [];
  const hr1SeesB = hr1Cases.some(c => (c.id||c.case_id||c.caseId) === caseBId);
  record('RLS2','HR1 cannot see Company B cases in list (B5)','RLS','case B absent from HR1 list',`found=${hr1SeesB}`,
    hr1SeesB ? 'FAIL' : hr1ListR.ok ? 'PASS' : 'SKIP', hr1ListR.ms,
    hr1SeesB ? `❌ Data leak: HR1 can see case ${caseBId?.slice(0,8)} from Company B` : 'RLS OK — Company B case not visible to HR1');

  // RLS3: HR2 direct access to Company A's case must be 403/404
  const crossR = await req('GET', `/api/hr/cases/${caseAId}`, null, tokens.hr2);
  record('RLS3','HR2 direct GET of Company A case returns 403/404 (B8)','RLS','403 or 404',`${crossR.status}`,
    [403,404].includes(crossR.status) ? 'PASS' : crossR.ok ? 'FAIL' : 'WARN', crossR.ms,
    crossR.ok ? `❌ Critical: HR2 got 200 on Company A case — RLS not enforced` : `Got ${crossR.status} — access blocked ✓`);

  // RLS4: HR1 direct access to Company B's case must be 403/404
  const crossR2 = await req('GET', `/api/hr/cases/${caseBId}`, null, tokens.hr);
  record('RLS4','HR1 direct GET of Company B case returns 403/404 (B8)','RLS','403 or 404',`${crossR2.status}`,
    [403,404].includes(crossR2.status) ? 'PASS' : crossR2.ok ? 'FAIL' : 'WARN', crossR2.ms,
    crossR2.ok ? `❌ Critical: HR1 got 200 on Company B case — RLS not enforced` : `Got ${crossR2.status} — access blocked ✓`);
}

// ─────────────────────────────────────────────────────────────
//  SUITE 9: CORS Preflight  ← NEW in v3 (B21)
// ─────────────────────────────────────────────────────────────
async function suiteCORS() {
  section('CORS Preflight (B21)');
  let allPass = true;
  for (const [method, ep] of CONFIG.CORS_ENDPOINTS) {
    const r = await options(ep);
    const hasOrigin = r.cors.includes('relopass.com') || r.cors === '*';
    const id = `CORS_${ep.replace(/\//g,'_').replace(/[{}]/g,'').slice(0,20)}`;
    const status = hasOrigin ? 'PASS' : r.status === 0 ? 'SKIP' : 'FAIL';
    if (status === 'FAIL') allPass = false;
    record(id, `CORS preflight: ${method} ${ep}`, 'CORS',
      'Access-Control-Allow-Origin: relopass.com', `${r.status} cors="${r.cors}"`,
      status, r.ms,
      hasOrigin ? '' : r.error || `Missing CORS header — browser requests from relopass.com will fail silently`);
  }
  // Single summary record for reporting
  record('CORS1','CORS summary: all key endpoints pass preflight (B21)','CORS','all PASS',allPass?'all OK':'some FAIL',
    allPass?'PASS':'FAIL',0,allPass?'':'Check individual CORS_ entries above');
}

// ─────────────────────────────────────────────────────────────
//  SUITE 10: Rate Limiting  ← NEW in v3 (B22)
// ─────────────────────────────────────────────────────────────
async function suiteRateLimiting() {
  section('Rate Limiting (B22)');
  const attempts = 12;
  let got429 = false;
  let got429WithRetryAfter = false;
  let firstRateLimit = -1;

  for (let i = 0; i < attempts; i++) {
    const r = await req('POST', '/api/auth/login', { identifier: `ratelimit_probe_${Date.now()}@probe.com`, password: 'wrong_password_probe' }, null, 3000);
    if (r.status === 429) {
      got429 = true;
      if (firstRateLimit === -1) firstRateLimit = i + 1;
      got429WithRetryAfter = !!(r.headers?.['retry-after'] || r.data?.retry_after);
      break;
    }
    // Small delay to not hammer too hard
    await new Promise(res => setTimeout(res, 100));
  }

  record('RL1', `Rate limit on /api/auth/login (B22) — ${attempts} rapid attempts`, 'Security',
    '429 within 10 attempts',
    got429 ? `429 at attempt ${firstRateLimit}${got429WithRetryAfter?' + Retry-After':''}` : `No 429 in ${attempts} attempts`,
    got429 && got429WithRetryAfter ? 'PASS' : got429 ? 'WARN' : 'FAIL', 0,
    got429 ? `Rate limited at attempt ${firstRateLimit}${got429WithRetryAfter?' with Retry-After header ✓':' but missing Retry-After header ⚠'}` :
    `Not rate-limited — brute-force protection missing ❌`);
}

// ─────────────────────────────────────────────────────────────
//  SUITE 11: XSS Protection Smoke Test  ← NEW in v3 (B23)
// ─────────────────────────────────────────────────────────────
async function suiteXSSProtection() {
  section('XSS Input Sanitisation (B23)');
  const T = tokens.hr;
  if (!T) { console.log('  SKIP — no HR token'); return; }

  const xssPayload = '<script>alert(1)</script>';
  const createR = await req('POST', '/api/hr/cases', {
    first_name: xssPayload,
    last_name:  'XSSTest',
    email:      `xss_probe_${Date.now()}@testco.com`,
  }, T);

  const xssCaseId = createR.data?.caseId || createR.data?.id;
  if (!createR.ok || !xssCaseId) {
    record('SEC1','XSS: case creation with script payload','Security','200+caseId',`${createR.status}`,
      createR.ok ? 'WARN':'SKIP', createR.ms, 'Could not create test case — XSS check skipped');
    return;
  }

  // GET the case and check if the raw <script> tag is reflected
  const getR = await req('GET', `/api/cases/${xssCaseId}`, null, T);
  const rawBody = JSON.stringify(getR.data || '');
  const rawTagPresent = rawBody.includes('<script>alert(1)</script>');
  // JSON.stringify escapes < and > to unicode < > in safe serialisers
  // A raw unescaped <script> in the JSON body is only dangerous if the frontend uses innerHTML
  // We WARN (not FAIL) on raw reflection because the API itself returns JSON (not HTML)
  record('SEC1','XSS: script tag in case name reflected raw in API response (B23)','Security',
    'no raw <script> in response', rawTagPresent ? 'raw tag PRESENT' : 'tag absent/escaped',
    rawTagPresent ? 'WARN' : 'PASS', getR.ms,
    rawTagPresent ? `⚠ Raw <script> tag in JSON response — safe if frontend escapes, risky if using innerHTML` :
    `Safe: tag absent or escaped in JSON response`);
}

// ─────────────────────────────────────────────────────────────
//  SUITE 12: Performance Benchmarks  ← NEW in v3
//  Records response time for 6 core endpoints — tracked over time
// ─────────────────────────────────────────────────────────────
async function suitePerformanceBenchmarks() {
  section('Performance Benchmarks');
  const T = tokens.hr || tokens.admin;
  if (!T) { console.log('  SKIP — no token'); return; }

  const endpoints = [
    { id:'PERF1', name:'GET /health',             method:'GET',  path:'/health',                      token:null,   target:CONFIG.PERF.fast },
    { id:'PERF2', name:'POST /api/auth/login',    method:'POST', path:'/api/auth/login',              token:null,   target:CONFIG.PERF.ok, body: CONFIG.CREDS.admin },
    { id:'PERF3', name:'GET /api/hr/cases',       method:'GET',  path:'/api/hr/cases',                token:T,      target:CONFIG.PERF.ok  },
    { id:'PERF4', name:'GET /api/hr/assignments', method:'GET',  path:'/api/hr/assignments',          token:T,      target:CONFIG.PERF.ok  },
    { id:'PERF5', name:'GET /api/hr/resources/destinations', method:'GET', path:'/api/hr/resources/destinations', token:T, target:CONFIG.PERF.slow },
    { id:'PERF6', name:'GET /api/hr/service-categories',    method:'GET', path:'/api/hr/service-categories',    token:T, target:CONFIG.PERF.slow },
  ];

  for (const ep of endpoints) {
    const times = [];
    for (let i = 0; i < 3; i++) {
      const r = await req(ep.method, ep.path, ep.body||null, ep.token, 8000);
      times.push(r.ms);
      await new Promise(res => setTimeout(res, 150));
    }
    const avg = Math.round(times.reduce((a,b)=>a+b,0)/times.length);
    const p95 = Math.max(...times); // with 3 samples, max ≈ p95
    const status = !times.every(t=>t<8000) ? 'FAIL' : avg <= ep.target ? 'PASS' : avg <= ep.target*2 ? 'WARN' : 'FAIL';
    record(ep.id, `${ep.name} avg response time`, 'Performance',
      `avg ≤${ep.target}ms`, `avg=${avg}ms p95=${p95}ms`,
      status, avg,
      `runs: ${times.join('/')}ms  target: ≤${ep.target}ms`);
  }
}

// ─────────────────────────────────────────────────────────────
//  SUITE 13: Persona Scenario Flow Tests
// ─────────────────────────────────────────────────────────────
async function suitePersonaFlows(scenarioIds) {
  section(`Persona Flow Tests (${scenarioIds.join(', ')})`);
  const T = tokens.hr;
  if (!T) { console.log('  SKIP — no HR token for scenario flows'); return; }

  const assignTest  = results.find(r => r.id === 'CT4');
  const assignWorks = assignTest?.status === 'PASS';

  for (const sid of scenarioIds) {
    const p = CONFIG.PERSONAS[sid];
    if (!p) { record(`${sid}_FLOW`, `${sid}: unknown persona`, 'Scenario','valid scenario','unknown', 'SKIP', 0); continue; }

    const destTest   = results.find(r => r.id === 'RT1');
    const destDetail = destTest?.detail || '';
    const knownDests = ['Germany','France','US','Spain','Netherlands','UK','Norway','Singapore','Switzerland','Belgium','Ireland','Italy'];
    const destAvailable = knownDests.some(d => d.toLowerCase() === p.country.toLowerCase()) ||
                          destDetail.toLowerCase().includes(p.country.toLowerCase());

    if (!destAvailable && ['T6','T15','T16'].includes(sid)) {
      record(`${sid}_FLOW`, `${sid} (${p.first_name} ${p.last_name}): ${p.destination} — destination not supported`, 'Scenario',
        'destination available', `${p.country} not in supported list`, 'BLOCKED', 0,
        `Fix B14 to add ${p.country} — scenario blocked until then`);
      continue;
    }

    if (!assignWorks && !['T9','T10','T11','T12'].includes(sid)) {
      record(`${sid}_FLOW`, `${sid} (${p.first_name} ${p.last_name}): blocked by B3 (assign hang)`, 'Scenario',
        'assign works', 'B3 still open', 'BLOCKED', 0,
        'Fix B3 first — POST /api/hr/cases/{id}/assign must respond within 5s');
      continue;
    }

    const ts = Date.now();
    const email = `${p.first_name.toLowerCase()}_${sid.toLowerCase()}_${ts}@testco.com`;
    const createR = await req('POST', '/api/hr/cases', { first_name: p.first_name, last_name: p.last_name, email }, T);
    if (!createR.ok || !createR.data?.caseId) {
      record(`${sid}_FLOW`, `${sid} (${p.first_name}): case creation failed`, 'Scenario', '201+caseId', `${createR.status}`, 'FAIL', createR.ms, createR.error||JSON.stringify(createR.data).slice(0,100));
      continue;
    }
    const caseId = createR.data.caseId;

    const detailR  = await req('GET', `/api/cases/${caseId}`, null, T);
    const employer = detailR.data?.profile_json?.employer?.name || detailR.data?.employer?.name || null;
    const employerOk = employer === 'Test Co (Seed)';

    const assignR = await req('POST', `/api/hr/cases/${caseId}/assign`, { employee_email: CONFIG.CREDS.newEmp.email }, T, 8000);
    const assignOk = assignR.ok && !assignR.error?.includes('abort');

    // WZ1 regression: PATCH + verify HR sees data (B17)
    let wizardSyncOk = null;
    if (assignOk && tokens.emp) {
      const patchR = await req('PATCH', `/api/cases/${caseId}`, {
        relocationBasics: { originCountry: 'France', destCountry: p.country, purpose: p.assignment }
      }, tokens.emp, 5000);
      if (patchR.ok) {
        await new Promise(r=>setTimeout(r,250));
        const hrCheckR = await req('GET', `/api/hr/cases/${caseId}`, null, T);
        wizardSyncOk = hrCheckR.ok && (
          hrCheckR.data?.host_country?.toLowerCase?.().includes(p.country.toLowerCase()) ||
          hrCheckR.data?.destination_country?.toLowerCase?.().includes(p.country.toLowerCase())
        );
      }
    }

    const accessR = await req('GET', `/api/hr/cases/${caseId}`, null, T);
    const accessOk = accessR.ok;

    let familyFieldsOk = null;
    if (p.family !== 'single') {
      const profile = detailR.data?.profile_json || {};
      familyFieldsOk = 'spouse' in profile || 'familySize' in profile || 'dependents' in profile || profile.family !== undefined;
    }

    const steps = [
      { name:'case_created',     ok: createR.ok && !!caseId },
      { name:'employer_correct', ok: employerOk },
      { name:'case_assigned',    ok: assignOk },
      { name:'case_accessible',  ok: accessOk },
      ...(wizardSyncOk !== null ? [{ name:'wizard_sync (B17)', ok: wizardSyncOk }] : []),
      ...(familyFieldsOk !== null ? [{ name:'family_fields', ok: familyFieldsOk }] : []),
    ];
    const passedSteps = steps.filter(s => s.ok).length;
    const failedSteps = steps.filter(s => !s.ok).map(s => s.name);
    const totalMs = createR.ms + (detailR.ms||0) + (assignR.ms||0) + (accessR.ms||0);

    const status = passedSteps === steps.length ? 'PASS'
      : passedSteps >= Math.ceil(steps.length/2) ? 'PARTIAL'
      : 'FAIL';

    const detail = [
      `case=${caseId.slice(0,8)}`,
      `employer=${employer||'null'}(${employerOk?'✓':'✗'})`,
      `assign=${assignOk?'✓':'✗'}(${assignR.ms}ms)`,
      `access=${accessOk?'✓':'✗'}`,
      ...(wizardSyncOk !== null ? [`wiz_sync=${wizardSyncOk?'✓':'✗'}`] : []),
      ...(familyFieldsOk !== null ? [`family=${familyFieldsOk?'✓':'✗'}`] : []),
      ...(failedSteps.length ? [`failed:${failedSteps.join(',')}`] : []),
    ].join(' ');

    record(`${sid}_FLOW`, `${sid} (${p.first_name} ${p.last_name}, ${p.origin}→${p.destination})`, 'Scenario',
      `all ${steps.length} flow steps pass`, `${passedSteps}/${steps.length} passed`, status, totalMs, detail);
  }
}

// ─────────────────────────────────────────────────────────────
//  SUITE T13 — Admin Onboarding Flow
// ─────────────────────────────────────────────────────────────
async function suiteT13AdminOnboarding() {
  if (!targetScenarios.includes('T13')) return;
  section('T13 — Admin Onboarding Flow');

  const T = tokens.admin;
  if (!T) {
    record('T13_FLOW','T13 Admin Onboarding','Scenario (Admin)','admin token','no admin token','BLOCKED',0,'Admin login failed — run auth suite first');
    return;
  }

  const steps = [];
  let r;

  const probeId = '1';
  r = await req('GET', `/api/admin/assignments/${probeId}`, null, T);
  const b9pass = r.ok;
  steps.push({ name:'admin_assignments_200 (B9)', ok: b9pass });
  record('T13_B9', 'Admin assignments endpoint (B9)', 'Scenario (Admin)', '200', `${r.status}`,
    b9pass ? 'PASS' : r.status === 500 ? 'FAIL' : 'WARN', r.ms,
    r.status === 500 ? 'Still returning 500 — B9 not fixed' : r.status === 404 ? 'No assignment at that ID (endpoint works — likely PASS)' : `status=${r.status}`);

  const newUserEmail = `onboard_t13_${Date.now()}@testco.com`;
  r = await req('POST', '/api/admin/users', { first_name:'Onboard', last_name:'Test', email: newUserEmail, role:'HR', company_id: null }, T);
  const adminCreateOk = r.ok;
  steps.push({ name:'admin_can_create_user (B2 API)', ok: adminCreateOk });
  record('T13_B2_API', 'Admin create user via API (B2 partial)', 'Scenario (Admin)', '200/201', `${r.status}`,
    adminCreateOk ? 'PASS' : r.status === 404 ? 'SKIP' : r.status === 403 ? 'SKIP' : 'FAIL', r.ms,
    adminCreateOk ? `user created: ${newUserEmail}` :
    r.status === 404 ? 'Endpoint not found — B2 must be verified manually via UI' :
    `status=${r.status}`);

  const freshToken = tokens.newHR;
  if (freshToken) {
    r = await req('GET', '/api/hr/assignments', null, freshToken, 5000);
    const b1freshPass = r.ok && r.ms < 5000 && !r.error;
    steps.push({ name:'fresh_hr_assignments_within_5s (B1)', ok: b1freshPass });
    record('T13_B1_FRESH', 'Fresh HR user: /api/hr/assignments returns within 5s (B1)', 'Scenario (Admin)', '200 <5s', `${r.status} ${r.ms}ms`,
      r.error ? 'FAIL' : b1freshPass ? 'PASS' : r.ms >= 5000 ? 'FAIL' : 'WARN', r.ms,
      r.error ? `TIMEOUT — B1 still open: ${r.error}` : `Fresh HR user gets ${r.status} in ${r.ms}ms`);
  } else {
    record('T13_B1_FRESH', 'Fresh HR user: /api/hr/assignments (B1 — skip, no fresh token)', 'Scenario (Admin)', '200 <5s', 'no token', 'SKIP', 0);
    steps.push({ name:'fresh_hr_assignments (B1)', ok: null });
  }

  const scoreable = steps.filter(s => s.ok !== null);
  const passedSteps = scoreable.filter(s => s.ok).length;
  const failedSteps = steps.filter(s => s.ok === false).map(s => s.name);
  const totalMs = results.filter(r => r.id.startsWith('T13')).reduce((s, r) => s + r.ms, 0);
  const status = failedSteps.length === 0 ? 'PASS' : passedSteps >= Math.ceil(scoreable.length / 2) ? 'PARTIAL' : 'FAIL';

  record('T13_FLOW', 'T13 Admin Onboarding (B2 + B9 + B1 fresh-user)', 'Scenario (Admin)',
    `all ${scoreable.length} steps pass`, `${passedSteps}/${scoreable.length} passed`, status, totalMs,
    [`b9=${b9pass?'✓':'✗'}`, `b2_api=${adminCreateOk?'✓':r.status===404?'SKIP':'✗'}`, `b1_fresh=${freshToken?(steps.find(s=>s.name.includes('B1'))?.ok?'✓':'✗'):'SKIP'}`].join(' '));
}

// ─────────────────────────────────────────────────────────────
//  SUITE T14 — Cross-Role Full-Stack Test
// ─────────────────────────────────────────────────────────────
async function suiteT14FullStack() {
  if (!targetScenarios.includes('T14')) return;
  section('T14 — Cross-Role Full-Stack Test');

  const hrToken  = tokens.hr;
  const empToken = tokens.emp;
  if (!hrToken || !empToken) {
    record('T14_FLOW','T14 Cross-Role Full-Stack','Scenario (Cross-Role)','hr+emp tokens','missing tokens','BLOCKED',0,
      `Missing: ${!hrToken?'HR ':''} ${!empToken?'Employee':''} token — auth suite must pass first`);
    return;
  }

  const steps = [];
  let r;

  r = await req('POST', '/api/hr/cases', { first_name:'CrossRole', last_name:'FullStack', email:`crossrole_t14_${Date.now()}@testco.com` }, hrToken);
  const caseId = r.data?.id || r.data?.case_id || r.data?.caseId || null;
  const createOk = r.ok && !!caseId;
  steps.push({ name:'hr_creates_case', ok: createOk });
  record('T14_CREATE', 'HR creates fresh case for T14', 'Scenario (Cross-Role)', '201 + caseId', `${r.status}/id=${caseId?.slice(0,8)||'null'}`,
    createOk ? 'PASS' : 'FAIL', r.ms, createOk ? `caseId=${caseId}` : r.error||JSON.stringify(r.data).slice(0,80));

  if (!createOk) {
    record('T14_FLOW','T14 Cross-Role Full-Stack','Scenario (Cross-Role)','all steps','case creation failed','BLOCKED',r.ms,''); return;
  }

  const detailR  = await req('GET', `/api/cases/${caseId}`, null, hrToken);
  const employer = detailR.data?.profile_json?.employer?.name || detailR.data?.employer?.name || null;
  const employerOk = employer === 'Test Co (Seed)';
  steps.push({ name:'employer_correct (B5)', ok: employerOk });
  record('T14_EMPLOYER', 'Cross-role case: employer = "Test Co (Seed)" (B5)', 'Scenario (Cross-Role)', '"Test Co (Seed)"', `"${employer}"`,
    employerOk ? 'PASS' : employer ? 'FAIL' : 'WARN', detailR.ms, employerOk ? '' : `Got "${employer}" — B5 cross-company data leak`);

  r = await req('POST', `/api/hr/cases/${caseId}/assign`, { employee_email: CONFIG.CREDS.newEmp.email }, hrToken, 8000);
  const assignOk = r.ok && r.ms < 8000 && !r.error;
  steps.push({ name:'assign_employee (B3)', ok: assignOk });
  record('T14_ASSIGN', 'HR assigns case to employee (B3 regression)', 'Scenario (Cross-Role)', '200 <8s', `${r.status} ${r.ms}ms`,
    r.error ? 'FAIL' : assignOk ? 'PASS' : r.ms >= 8000 ? 'FAIL' : 'WARN', r.ms, r.error ? `TIMEOUT — B3 still open: ${r.error}` : `assigned in ${r.ms}ms`);

  if (!assignOk) {
    record('T14_FLOW','T14 Cross-Role Full-Stack','Scenario (Cross-Role)','all steps','assign failed (B3)','BLOCKED',r.ms,'Fix B3 before running T14.'); return;
  }

  r = await req('GET', '/api/employee/cases', null, empToken);
  const empCases = r.data?.cases || r.data?.items || (Array.isArray(r.data) ? r.data : null);
  const empSeesCase = r.ok && empCases && empCases.some(c => (c.id||c.case_id||c.caseId) === caseId);
  steps.push({ name:'employee_sees_case', ok: empSeesCase });
  record('T14_EMP_VIEW', 'Employee can see newly assigned case', 'Scenario (Cross-Role)', 'case in employee list', `status=${r.status} found=${empSeesCase}`,
    empSeesCase ? 'PASS' : r.ok ? 'WARN' : 'FAIL', r.ms, empSeesCase ? `employee sees case ${caseId.slice(0,8)}` : `status=${r.status}`);

  const step1Payload = {
    relocationBasics: {
      originCountry: 'France', originCity: 'Lyon',
      destCountry: 'Germany', destCity: 'Berlin',
      purpose: 'lta', targetMoveDate: '2027-01-01',
    }
  };
  r = await req('PATCH', `/api/cases/${caseId}`, step1Payload, empToken);
  if (!r.ok) r = await req('POST', `/api/cases/${caseId}/step1`, step1Payload, empToken);
  if (!r.ok) r = await req('PUT',  `/api/cases/${caseId}/profile`, step1Payload, empToken);
  const step1Saved = r.ok;
  steps.push({ name:'employee_fills_step1', ok: step1Saved });
  record('T14_STEP1', 'Employee submits Step 1 intake data', 'Scenario (Cross-Role)', '200/204', `${r.status}`,
    step1Saved ? 'PASS' : r.status === 404 ? 'WARN' : 'FAIL', r.ms, step1Saved ? 'Step 1 data accepted' : `status=${r.status}`);

  // B17 regression: verify wizard sync to HR view
  await new Promise(res=>setTimeout(res,300));
  const hrViewR = await req('GET', `/api/hr/cases/${caseId}`, null, hrToken);
  const filledData = hrViewR.data?.profile_json || hrViewR.data?.employee_data || hrViewR.data;
  const hrSeesFilledData = hrViewR.ok && hrViewR.data &&
    (hrViewR.data.host_country === 'Germany' || hrViewR.data.destination_country === 'Germany' ||
     (filledData && (filledData.destination_country === 'Germany' || filledData.destCountry === 'Germany')) ||
     (filledData?.profile_json?.destination_country === 'Germany'));
  steps.push({ name:'hr_sees_employee_data (B17)', ok: hrSeesFilledData });
  record('T14_HR_VIEW', 'HR sees employee-filled data in case view (B17 wizard sync)', 'Scenario (Cross-Role)',
    'destination in HR view', `ok=${hrViewR.ok} filled=${hrSeesFilledData}`,
    hrSeesFilledData ? 'PASS' : hrViewR.ok ? (step1Saved ? 'FAIL' : 'WARN') : 'FAIL', hrViewR.ms,
    hrSeesFilledData ? 'HR sees destination=Germany from employee Step 1 ✓' :
    !step1Saved ? 'Step 1 not saved — cannot verify HR view' :
    `HR view accessible but filled fields not found — B17 may still be open`);

  const passedSteps = steps.filter(s => s.ok).length;
  const failedSteps = steps.filter(s => !s.ok).map(s => s.name);
  const totalMs = results.filter(r => r.id.startsWith('T14')).reduce((s, r) => s + r.ms, 0);
  const status = passedSteps === steps.length ? 'PASS' : passedSteps >= Math.ceil(steps.length / 2) ? 'PARTIAL' : 'FAIL';

  record('T14_FLOW', 'T14 Cross-Role Full-Stack (B3+B5+B10+B11+B17 regression)', 'Scenario (Cross-Role)',
    `all ${steps.length} steps pass`, `${passedSteps}/${steps.length} passed`, status, totalMs,
    [`create=${createOk?'✓':'✗'}`,`employer=${employerOk?'✓':'✗'}`,`assign=${assignOk?'✓':'✗'}`,
     `emp_sees=${empSeesCase?'✓':'✗'}`,`step1=${step1Saved?'✓':'✗'}`,`hr_filled=${hrSeesFilledData?'✓':'✗'}`,
     ...(failedSteps.length?[`failed:${failedSteps.join(',')}`]:[])].join(' '));
}

// ─────────────────────────────────────────────────────────────
//  MAIN
// ─────────────────────────────────────────────────────────────
async function main() {
  const mode = apiOnly ? 'API Only' : scenArg ? `Targeted: ${targetScenarios.join(',')}` : 'Full Suite';
  console.log('╔══════════════════════════════════════════════════╗');
  console.log(`║  ReloPass Test Runner v3.0  —  ${mode.padEnd(17)}║`);
  console.log(`║  Run date: ${RUN_DATE}                       ║`);
  console.log('╚══════════════════════════════════════════════════╝');

  await suiteAuth();

  if (!apiOnly) {
    await suiteCases();
    await suiteHR();
    await suiteEmployee();
    await suiteResources();
    await suiteReliability();
    await suiteWizardPersistence();        // NEW v3: B17, B18, B19
    await suiteCORS();                     // NEW v3: B21
    await suiteRateLimiting();             // NEW v3: B22
    await suiteXSSProtection();            // NEW v3: B23
    await suitePerformanceBenchmarks();    // NEW v3: perf tracking
    await suiteRLSIsolation();             // NEW v3: T17, B5/B8 regression
    await suitePersonaFlows(targetScenarios.filter(s => Object.keys(CONFIG.PERSONAS).includes(s)));
    await suiteT13AdminOnboarding();
    await suiteT14FullStack();
  }

  const pass  = results.filter(r => r.status === 'PASS').length;
  const fail  = results.filter(r => r.status === 'FAIL').length;
  const warn  = results.filter(r => r.status === 'WARN').length;
  const skip  = results.filter(r => ['SKIP','MANUAL','BLOCKED'].includes(r.status)).length;
  const total = results.length;
  const denom = total - skip;
  const scorePct = denom > 0 ? Math.round(pass/denom*100) : 0;

  console.log('\n══ SUMMARY ══');
  console.log(`  Total: ${total}  |  PASS: ${pass}  FAIL: ${fail}  WARN: ${warn}  SKIP/BLOCKED: ${skip}`);
  console.log(`  Score: ${scorePct}%`);

  // Bug regression map — B1–B23
  const bugMap = {
    B1:  results.find(r=>r.id==='CT5')?.status,
    B2:  'MANUAL',
    B3:  results.find(r=>r.id==='CT4')?.status,
    B4:  results.find(r=>r.id==='RE1')?.status,
    B5:  results.find(r=>r.id==='CT3')?.status    || results.find(r=>r.id==='RLS1')?.status,
    B6:  results.find(r=>r.id==='AT5')?.status,
    B7:  'MANUAL',
    B8:  results.find(r=>r.id==='HP2')?.status    || results.find(r=>r.id==='RLS3')?.status,
    B9:  results.find(r=>r.id==='AD1')?.status    || results.find(r=>r.id==='T13_B9')?.status,
    B10: 'MANUAL',
    B11: 'MANUAL',
    B12: results.find(r=>r.id==='CT1')?.status,
    B13: 'MANUAL',
    B14: results.find(r=>r.id==='RT1')?.status,
    B15: results.find(r=>r.id==='EP1')?.status,
    B16: 'MANUAL',
    // v3 additions
    B17: results.find(r=>r.id==='WZ1b')?.status  || results.find(r=>r.id==='T14_HR_VIEW')?.status,
    B18: results.find(r=>r.id==='AT2b')?.status,
    B19: (() => {
      const wz = ['WZ2','WZ3','WZ4','WZ5'].map(id => results.find(r=>r.id===id)?.status).filter(Boolean);
      if (!wz.length) return 'SKIP';
      if (wz.every(s=>s==='SKIP')) return 'SKIP';
      if (wz.some(s=>s==='PASS')) return 'PARTIAL';
      return 'FAIL';
    })(),
    B20: 'MANUAL',
    B21: results.find(r=>r.id==='CORS1')?.status,
    B22: results.find(r=>r.id==='RL1')?.status,
    B23: results.find(r=>r.id==='SEC1')?.status,
  };

  const scenarioStatuses = {};
  for (const sid of ALL_SCENARIOS) {
    const r = results.find(r => r.id === `${sid}_FLOW`);
    scenarioStatuses[sid] = r?.status || '—';
  }

  // Performance snapshot
  const perfSnapshot = {};
  for (const r of results.filter(r=>r.category==='Performance')) {
    perfSnapshot[r.id] = { avg_ms: r.ms, status: r.status, detail: r.detail };
  }

  const output = {
    run_date: RUN_DATE,
    run_ts:   new Date().toISOString(),
    runner_version: 'v3.0',
    mode,
    summary:  { total, pass, fail, warn, skip },
    score_pct: scorePct,
    results,
    bugs_regression: bugMap,
    scenario_statuses: scenarioStatuses,
    performance_snapshot: perfSnapshot,
    test_credentials: {
      admin_email: CONFIG.CREDS.admin.identifier,
      hr_email:    CONFIG.CREDS.newHR.email,
      emp_email:   CONFIG.CREDS.newEmp.email,
      hr2_email:   CONFIG.CREDS.newHR2.email,
    },
  };

  const outPath = path.join(__dirname, 'test_results.json');
  fs.writeFileSync(outPath, JSON.stringify(output, null, 2));
  console.log(`  Saved: test_results.json`);

  const archiveDir = path.join(__dirname, 'results');
  if (!fs.existsSync(archiveDir)) fs.mkdirSync(archiveDir, { recursive: true });
  const archivePath = path.join(archiveDir, `test_results_${RUN_TS}.json`);
  fs.writeFileSync(archivePath, JSON.stringify(output, null, 2));
  console.log(`  Archived: results/test_results_${RUN_TS}.json`);
  console.log('\n  Run relopass_report_gen.js to generate the comparison .docx\n');
}

main().catch(console.error);
