// ReloPass — Madrid → Dublin dual-persona journey test (T18)
// Persona A: Spanish national (EU free movement)
// Persona B: Indian national resident in Spain (non-EEA, Critical Skills Employment Permit)
// Both: leaving Amazon Spain -> Google Ireland, permanent local hire, relocation agent supported.
//
// [AIQ-2032] YOU CANNOT RUN THIS TWICE IN AN HOUR.
// Each run registers four throwaway accounts (HR + employee, per persona) and
// registration is capped at 5/hour (backend/app/routers/auth.py). A second run
// inside the window gets 429 on AUTH, persona B never receives a token, and the
// campaign aborts partway — producing a results file with roughly half the checks
// and a meaningless overall percentage. Wait out the window before re-scoring, and
// check `rows by persona` before quoting any number from a run.

import fs from 'fs';

const B = 'https://api.relopass.com';
const EPOCH = Date.now();
const results = [];
const evidence = {};
let ctx = {};

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function req(method, path, body, token, timeout = 20000) {
  const t = Date.now();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  try {
    const ctrl = new AbortController();
    const to = setTimeout(() => ctrl.abort(), timeout);
    const r = await fetch(B + path, {
      method, headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
    clearTimeout(to);
    const txt = await r.text();
    let data; try { data = JSON.parse(txt); } catch { data = txt.slice(0, 2000); }
    return { status: r.status, ok: r.ok, ms: Date.now() - t, data };
  } catch (e) {
    return { status: 0, ok: false, ms: Date.now() - t, data: null, error: e.message };
  }
}

function record(id, persona, area, title, expected, actual, verdict, ms, note = '') {
  const row = { id, persona, area, title, expected, actual, verdict, ms, note };
  results.push(row);
  const icon = { PASS: '✅', PARTIAL: '🟡', FAIL: '❌', BLOCKED: '⛔', INFO: 'ℹ️' }[verdict] || '·';
  console.log(`${icon} [${persona}] ${id.padEnd(10)} ${title.slice(0, 62).padEnd(62)} ${String(ms).padStart(5)}ms  ${actual}`.slice(0, 190));
  return row;
}

const PERSONAS = [
  {
    key: 'A',
    label: 'EU citizen',
    fullName: 'Lucía Fernández',
    first: 'Lucia', last: 'Fernandez',
    nationality: 'ES',
    nationalityLabel: 'Spanish (EU/EEA)',
    residenceCountry: 'ES',
    passportCountry: 'ES',
  },
  {
    key: 'B',
    label: 'Non-EEA (CSEP)',
    fullName: 'Priya Raghavan',
    first: 'Priya', last: 'Raghavan',
    nationality: 'IN',
    nationalityLabel: 'Indian (third country, resident in Spain)',
    residenceCountry: 'ES',
    passportCountry: 'IN',
  },
];

const MOVE = {
  originCountry: 'ES', originCity: 'Madrid',
  destCountry: 'IE', destCity: 'Dublin',
  purpose: 'employment',
  targetMoveDate: '2026-10-01',
  employerName: 'Google Ireland Limited',
  employerCountry: 'IE',
  workLocation: 'Google Dublin — Grand Canal Dock',
  jobTitle: 'Senior Software Engineer',
  contractType: 'permanent',
  assignmentType: 'PERMANENT',
  previousEmployer: 'Amazon Spain Services S.L.U.',
};

async function runPersona(p) {
  console.log(`\n${'='.repeat(100)}\n  PERSONA ${p.key} — ${p.fullName} · ${p.nationalityLabel} · Madrid → Dublin (Amazon → Google)\n${'='.repeat(100)}`);
  const ev = evidence[p.key] = {};
  const hrEmail = `romain+t18hr${p.key.toLowerCase()}_${EPOCH}@hotmail.com`;
  const empEmail = `romain+t18emp${p.key.toLowerCase()}_${EPOCH}@hotmail.com`;

  // ── 0. Public corridor content (no auth) ────────────────────────────────
  for (const type of ['PERMANENT', 'LTA']) {
    const r = await req('GET', `/api/public/corridor-requirements?from=ES&to=IE&employee_type=${type}&purpose=employment&nationality=${p.nationality}`);
    const reqs = r.data?.requirements || [];
    ev[`corridor_${type}`] = r.data;
    record(`PUB-${type}`, p.key, 'Documents', `Public ES→IE requirements (${type})`,
      '≥5 requirements, nationality_class set',
      `${r.status} · ${reqs.length} reqs · class=${r.data?.nationality_class}`,
      reqs.length >= 5 && r.data?.nationality_class ? 'PASS' : reqs.length > 0 ? 'PARTIAL' : 'FAIL', r.ms,
      r.data?.coverage_note || '');
  }

  // ── 1. HR registration (Google Ireland) ─────────────────────────────────
  await sleep(500);
  let r = await req('POST', '/api/auth/register', {
    email: hrEmail, password: 'Passw0rd!', role: 'HR',
    name: `T18 HR ${p.key}`, company_name: `Google Ireland T18-${p.key}-${EPOCH}`,
  });
  const hrTok = r.data?.token || null;
  record('AUTH-1', p.key, 'Setup', 'HR registers (Google Ireland)', '200 + token',
    `${r.status}/token=${!!hrTok}`, hrTok ? 'PASS' : 'FAIL', r.ms, r.error || '');
  if (!hrTok) { record('ABORT', p.key, 'Setup', 'Journey aborted — no HR token', '', 'no token', 'BLOCKED', 0); return; }

  await sleep(500);
  r = await req('POST', '/api/auth/register', {
    email: empEmail, password: 'Passw0rd!', role: 'EMPLOYEE', name: p.fullName,
  });
  const empTok = r.data?.token || null;
  record('AUTH-2', p.key, 'Setup', `Employee registers (${p.fullName})`, '200 + token',
    `${r.status}/token=${!!empTok}`, empTok ? 'PASS' : 'FAIL', r.ms, r.error || '');

  // ── 2. HR creates the case ──────────────────────────────────────────────
  r = await req('POST', '/api/hr/cases', { first_name: p.first, last_name: p.last, email: empEmail }, hrTok);
  const caseId = r.data?.caseId || r.data?.id || null;
  ev.caseCreate = r.data;
  record('CASE-1', p.key, 'Setup', 'HR creates the relocation case', '200 + caseId',
    `${r.status}/id=${caseId ? caseId.slice(0, 8) : 'null'}`, caseId ? 'PASS' : 'FAIL', r.ms, r.error || '');
  if (!caseId) { record('ABORT', p.key, 'Setup', 'Journey aborted — no case', '', 'no caseId', 'BLOCKED', 0); return; }

  // ── 3. Fill the real move detail ────────────────────────────────────────
  const draft = {
    relocationBasics: {
      originCountry: MOVE.originCountry, originCity: MOVE.originCity,
      destCountry: MOVE.destCountry, destCity: MOVE.destCity,
      purpose: MOVE.purpose, targetMoveDate: MOVE.targetMoveDate,
      durationMonths: null, hasDependents: false,
    },
    employeeProfile: {
      fullName: p.fullName, nationality: p.nationality,
      passportCountry: p.passportCountry, passportExpiry: '2031-05-20',
      residenceCountry: p.residenceCountry, email: empEmail,
    },
    assignmentContext: {
      employerName: MOVE.employerName, employerCountry: MOVE.employerCountry,
      workLocation: MOVE.workLocation, contractStartDate: MOVE.targetMoveDate,
      contractType: MOVE.contractType, jobTitle: MOVE.jobTitle,
      assignmentType: MOVE.assignmentType, commutePreference: 'public_transport',
    },
  };
  r = await req('PATCH', `/api/cases/${caseId}`, draft, hrTok);
  ev.patch = r.data;
  record('CASE-2', p.key, 'Setup', 'Save Madrid→Dublin detail + nationality onto case', '200, values persisted',
    `${r.status}`, r.ok ? 'PASS' : 'FAIL', r.ms, r.error || JSON.stringify(r.data).slice(0, 160));

  // read back — does nationality survive?
  r = await req('GET', `/api/cases/${caseId}`, null, hrTok);
  ev.caseRead = r.data;
  const pj = r.data?.profile_json || r.data || {};
  const rb = pj.relocationBasics || pj.relocation_basics || {};
  const ep = pj.employeeProfile || pj.employee_profile || {};
  const gotDest = (rb.destCity || rb.dest_city || '') + '/' + (rb.destCountry || rb.dest_country || '');
  const gotNat = ep.nationality || null;
  record('CASE-3', p.key, 'Setup', 'Round-trip: destination + nationality readable', 'Dublin/IE + nationality',
    `dest=${gotDest} nat=${gotNat}`,
    gotDest.includes('Dublin') && gotNat === p.nationality ? 'PASS' : gotDest.includes('Dublin') ? 'PARTIAL' : 'FAIL', r.ms,
    gotNat ? '' : 'nationality not surfaced on case read — immigration branching cannot key off it');

  // ── 4. Assign to the employee ───────────────────────────────────────────
  r = await req('POST', `/api/hr/cases/${caseId}/assign`, { employee_email: empEmail }, hrTok, 15000);
  const assignmentId = r.data?.assignment_id || r.data?.assignmentId || r.data?.id || null;
  ev.assign = r.data;
  record('CASE-4', p.key, 'Setup', 'Assign case to employee', '<3s, assignment created',
    `${r.status}/${r.ms}ms/aid=${assignmentId ? String(assignmentId).slice(0, 8) : 'null'}`,
    r.ok && r.ms < 3000 ? 'PASS' : r.ok ? 'PARTIAL' : 'FAIL', r.ms, r.error || '');

  // ══ AREA 1 — DOCUMENTS & IMMIGRATION PAPERS ═════════════════════════════
  r = await req('GET', `/api/hr/cases/${caseId}/immigration-requirements?corridor_from=ES&corridor_to=IE&employee_type=PERMANENT`, null, hrTok);
  ev.immReq = r.data;
  const ir = r.data?.requirements || r.data?.items || [];
  record('DOC-1', p.key, 'Documents', 'HR view: immigration requirements for this case', '≥5 IE-specific requirements',
    `${r.status} · ${Array.isArray(ir) ? ir.length : '?'} items`,
    Array.isArray(ir) && ir.length >= 5 ? 'PASS' : Array.isArray(ir) && ir.length ? 'PARTIAL' : 'FAIL', r.ms,
    JSON.stringify(r.data).slice(0, 200));

  r = await req('GET', `/api/cases/${caseId}/requirements`, null, hrTok);
  ev.caseReq = r.data;
  const cr = r.data?.requirements || r.data?.items || (Array.isArray(r.data) ? r.data : []);
  record('DOC-2', p.key, 'Documents', 'Case requirements checklist', 'non-empty checklist',
    `${r.status} · ${Array.isArray(cr) ? cr.length : '?'} items`,
    Array.isArray(cr) && cr.length ? 'PASS' : 'FAIL', r.ms, JSON.stringify(r.data).slice(0, 200));

  r = await req('GET', `/api/hr/cases/${caseId}/immigration/available-forms?corridor_to=IE`, null, hrTok);
  ev.forms = r.data;
  const forms = r.data?.forms || r.data?.templates || (Array.isArray(r.data) ? r.data : []);
  record('DOC-3', p.key, 'Documents', 'Fillable Irish forms available (permit/visa/PPSN)', '≥1 IE form template',
    `${r.status} · ${Array.isArray(forms) ? forms.length : '?'} forms`,
    Array.isArray(forms) && forms.length ? 'PASS' : 'FAIL', r.ms, JSON.stringify(r.data).slice(0, 250));

  r = await req('GET', `/api/hr/cases/${caseId}/immigration/milestones`, null, hrTok);
  ev.milestones = r.data;
  const ms = r.data?.milestones || (Array.isArray(r.data) ? r.data : []);
  record('DOC-4', p.key, 'Documents', 'Immigration milestones / deadline timeline', 'milestones seeded for corridor',
    `${r.status} · ${Array.isArray(ms) ? ms.length : '?'} milestones`,
    Array.isArray(ms) && ms.length ? 'PASS' : 'FAIL', r.ms, JSON.stringify(r.data).slice(0, 200));

  if (empTok) {
    r = await req('GET', `/api/employee/cases/${caseId}/immigration`, null, empTok);
    ev.empImm = r.data;
    record('DOC-5', p.key, 'Documents', 'Employee view: what SHE is told to file', 'her own document list',
      `${r.status}`, r.ok ? (JSON.stringify(r.data).length > 120 ? 'PASS' : 'PARTIAL') : 'FAIL', r.ms,
      JSON.stringify(r.data).slice(0, 300));

    r = await req('GET', `/api/employee/cases/${caseId}/immigration-snapshot`, null, empTok);
    ev.empSnap = r.data;
    record('DOC-6', p.key, 'Documents', 'Employee immigration snapshot (status at a glance)', 'populated snapshot',
      `${r.status}`, r.ok ? (JSON.stringify(r.data).length > 120 ? 'PASS' : 'PARTIAL') : 'FAIL', r.ms,
      JSON.stringify(r.data).slice(0, 300));
  }

  // ══ AREA 2 — THE JOURNEY / RELOCATION PLAN ══════════════════════════════
  r = await req('GET', `/api/relocation-plans/${caseId}/view`, null, empTok || hrTok);
  ev.plan = r.data;
  const phases = r.data?.phases || [];
  const taskCount = phases.reduce((n, ph) => n + ((ph.tasks || []).length), 0);
  record('PLAN-1', p.key, 'Journey', 'Full relocation plan (the journey she sees)', 'phases + tasks generated',
    `${r.status} · ${phases.length} phases / ${taskCount} tasks`,
    phases.length && taskCount ? 'PASS' : phases.length ? 'PARTIAL' : 'FAIL', r.ms,
    JSON.stringify(r.data).slice(0, 300));

  // ══ AREA 3 — NEIGHBOURHOOD CURATION ═════════════════════════════════════
  //
  // [AIQ-2032] These used to call GET /api/recommendations/housing?case_id=...
  // and /schools?case_id=... Those handlers (backend/main.py ~3843) take NO
  // case_id parameter — they read db.get_profile(user['id']), the CALLING USER's
  // own profile, and return [] when there is none. The query string was silently
  // ignored, so both checks reported "0 items" no matter what the corridor held.
  // Measured 2026-08-21: the real path returned 8 Dublin areas at the same moment
  // these reported zero.
  //
  // The product path is POST /api/recommendations/batch, keyed on the assignment.
  r = await req('POST', `/api/recommendations/batch`,
    { assignment_id: assignmentId || caseId, selected_services: ['housing', 'schools'] },
    empTok || hrTok);
  ev.recommendationsBatch = r.data;
  const batch = r.data?.results || {};
  const areas = batch.living_areas?.recommendations || [];
  const schools = batch.schools?.recommendations || [];

  record('AREA-1', p.key, 'Neighbourhood', 'Dublin area / housing recommendations',
    '≥3 real Dublin options', `${r.status} · ${areas.length} areas`,
    areas.length >= 3 ? 'PASS' : areas.length ? 'PARTIAL' : 'FAIL', r.ms,
    JSON.stringify(areas.slice(0, 3)).slice(0, 300));

  // Schools are legitimately gated on the case having school-age children
  // (recommendations/router.py ~219). Neither T18 persona has dependants, so zero
  // schools is the CORRECT answer, not a coverage gap.
  //
  // Recorded as BLOCKED rather than PASS on purpose. Scoring a gate as a failure
  // slanders the product; scoring it as a pass is a green check that measured
  // nothing and quietly inflates the headline number. BLOCKED is counted
  // separately from both, so the total stays honest and the reason is on record.
  const hasKids = (p.members || []).some(m => m.kind === 'child');
  record('AREA-2', p.key, 'Neighbourhood', 'Dublin schools recommendations',
    hasKids ? '≥3 real Dublin options' : 'n/a — schools gate on school-age dependants; this persona has none',
    `${r.status} · ${schools.length} schools${hasKids ? '' : ' (gated: no children on this case)'}`,
    hasKids
      ? (schools.length >= 3 ? 'PASS' : schools.length ? 'PARTIAL' : 'FAIL')
      : 'BLOCKED',
    r.ms, JSON.stringify(schools.slice(0, 3)).slice(0, 300));

  r = await req('GET', `/api/employee/geocode/autocomplete?q=Grand Canal Dock Dublin`, null, empTok || hrTok);
  ev.geo = r.data;
  const geo = r.data?.results || r.data?.predictions || (Array.isArray(r.data) ? r.data : []);
  record('AREA-3', p.key, 'Neighbourhood', 'Address autocomplete for Dublin (commute setup)', 'Dublin results returned',
    `${r.status} · ${Array.isArray(geo) ? geo.length : '?'} results`,
    Array.isArray(geo) && geo.length ? 'PASS' : 'FAIL', r.ms, JSON.stringify(r.data).slice(0, 200));

  r = await req('GET', '/api/employee/destinations', null, empTok || hrTok);
  ev.dests = r.data;
  const dl = r.data?.destinations || r.data?.items || (Array.isArray(r.data) ? r.data : []);
  const hasIE = JSON.stringify(r.data || '').match(/Ireland|Dublin/i);
  record('AREA-4', p.key, 'Neighbourhood', 'Ireland/Dublin present in destination catalog', 'Ireland selectable',
    `${r.status} · ${Array.isArray(dl) ? dl.length : '?'} dests · IE=${!!hasIE}`,
    hasIE ? 'PASS' : 'FAIL', r.ms, JSON.stringify(dl).slice(0, 300));

  // ══ AREA 4 — LOCAL SERVICES ═════════════════════════════════════════════
  r = await req('GET', `/api/cases/${caseId}/services-state`, null, hrTok);
  ev.svcState = r.data;
  record('SVC-1', p.key, 'Services', 'Services state for the case', '200 + service list',
    `${r.status}`, r.ok ? 'PASS' : 'FAIL', r.ms, JSON.stringify(r.data).slice(0, 250));

  r = await req('GET', `/api/cases/${caseId}/vendors`, null, hrTok);
  ev.vendors = r.data;
  const vs = r.data?.vendors || r.data?.items || (Array.isArray(r.data) ? r.data : []);
  record('SVC-2', p.key, 'Services', 'Vendors available for Dublin (bank, movers, health, utilities)', '≥3 IE vendors',
    `${r.status} · ${Array.isArray(vs) ? vs.length : '?'} vendors`,
    Array.isArray(vs) && vs.length >= 3 ? 'PASS' : Array.isArray(vs) && vs.length ? 'PARTIAL' : 'FAIL', r.ms,
    JSON.stringify(r.data).slice(0, 300));

  if (assignmentId) {
    r = await req('GET', `/api/employee/assignments/${assignmentId}/services`, null, empTok);
    ev.empSvc = r.data;
    record('SVC-3', p.key, 'Services', 'Employee: services she can pick', '200 + selectable services',
      `${r.status}`, r.ok ? 'PASS' : 'FAIL', r.ms, JSON.stringify(r.data).slice(0, 250));

    r = await req('GET', `/api/employee/assignments/${assignmentId}/marketplace`, null, empTok);
    ev.market = r.data;
    const mk = r.data?.suppliers || r.data?.items || r.data?.results || (Array.isArray(r.data) ? r.data : []);
    record('SVC-4', p.key, 'Services', 'Marketplace: real suppliers serving Dublin', '≥3 suppliers with IE coverage',
      `${r.status} · ${Array.isArray(mk) ? mk.length : '?'} suppliers`,
      Array.isArray(mk) && mk.length >= 3 ? 'PASS' : Array.isArray(mk) && mk.length ? 'PARTIAL' : 'FAIL', r.ms,
      JSON.stringify(r.data).slice(0, 300));
  } else {
    record('SVC-3', p.key, 'Services', 'Employee: services she can pick', '200', 'no assignment_id returned', 'BLOCKED', 0);
    record('SVC-4', p.key, 'Services', 'Marketplace: real suppliers serving Dublin', '200', 'no assignment_id returned', 'BLOCKED', 0);
  }

  r = await req('GET', `/api/resources/country?assignment_id=${assignmentId || caseId}`, null, empTok || hrTok);
  ev.countryRes = r.data;
  // [AIQ-2032] GET /api/resources/country returns
  // {profile, context, hints, sections, events, recommended, filters_applied} —
  // there is no top-level `resources` or `items`, so this read `[]` every run and
  // FAILed regardless of content. Measured 2026-08-21: 19 Irish resources were
  // present at the moment it reported zero. The resources live one level down, in
  // each section's content.
  const crr = Array.isArray(r.data?.sections)
    ? r.data.sections.flatMap(sec => (sec?.content?.items) || [])
    : (r.data?.resources || r.data?.items || (Array.isArray(r.data) ? r.data : []));
  record('SVC-5', p.key, 'Services', 'Country resource pack for Ireland', '≥5 Irish resources',
    `${r.status} · ${Array.isArray(crr) ? crr.length : '?'} resources`,
    Array.isArray(crr) && crr.length >= 5 ? 'PASS' : Array.isArray(crr) && crr.length ? 'PARTIAL' : 'FAIL', r.ms,
    JSON.stringify(r.data).slice(0, 300));

  // ══ AREA 5 — RELOCATION AGENT / COORDINATOR ═════════════════════════════
  r = await req('POST', '/api/advisors/match', {
    origin_country: 'ES', destination_country: 'IE', purpose: 'employment', case_id: caseId,
  }, hrTok);
  ev.advisors = r.data;
  const ad = r.data?.advisors || r.data?.matches || r.data?.items || (Array.isArray(r.data) ? r.data : []);
  record('AGT-1', p.key, 'Agent', 'Match a relocation advisor for ES→IE', '≥1 advisor matched',
    `${r.status} · ${Array.isArray(ad) ? ad.length : '?'} advisors`,
    Array.isArray(ad) && ad.length ? 'PASS' : 'FAIL', r.ms, JSON.stringify(r.data).slice(0, 300));

  r = await req('GET', `/api/cases/${caseId}/coordinator/session`, null, empTok || hrTok);
  ev.coord = r.data;
  record('AGT-2', p.key, 'Agent', 'Coordinator session on the case (agent workspace)', '200 + session',
    `${r.status}`, r.ok ? 'PASS' : 'FAIL', r.ms, JSON.stringify(r.data).slice(0, 250));

  r = await req('GET', `/api/hr/cases/${caseId}/providers`, null, hrTok);
  ev.providers = r.data;
  const pv = r.data?.providers || r.data?.items || (Array.isArray(r.data) ? r.data : []);
  record('AGT-3', p.key, 'Agent', 'Providers/agents attachable to her case', '≥1 provider',
    `${r.status} · ${Array.isArray(pv) ? pv.length : '?'} providers`,
    Array.isArray(pv) && pv.length ? 'PASS' : 'FAIL', r.ms, JSON.stringify(r.data).slice(0, 250));

  ctx[p.key] = { caseId, assignmentId, hrTok, empTok, hrEmail, empEmail };
}

for (const p of PERSONAS) {
  await runPersona(p);
  await sleep(1200);
}

const summary = {
  run_id: `T18_MADRID_DUBLIN_${EPOCH}`,
  generated_at: new Date(EPOCH).toISOString(),
  scenario: 'T18 — Madrid → Dublin, Amazon → Google, permanent local hire, agent-supported',
  personas: PERSONAS.map(p => ({ key: p.key, name: p.fullName, nationality: p.nationalityLabel })),
  totals: ['PASS', 'PARTIAL', 'FAIL', 'BLOCKED', 'INFO'].reduce((o, v) => (o[v] = results.filter(r => r.verdict === v).length, o), {}),
  by_area: {},
  results,
  context: ctx,
};
for (const area of [...new Set(results.map(r => r.area))]) {
  const rs = results.filter(r => r.area === area);
  summary.by_area[area] = {
    total: rs.length,
    pass: rs.filter(r => r.verdict === 'PASS').length,
    partial: rs.filter(r => r.verdict === 'PARTIAL').length,
    fail: rs.filter(r => r.verdict === 'FAIL').length,
    blocked: rs.filter(r => r.verdict === 'BLOCKED').length,
  };
}

// [AIQ-2032] Write into results/, which .gitignore already covers. These used to
// land at the repo root, so every campaign run left two untracked JSON files
// (the evidence file is ~350KB) sitting in `git status`.
const OUT_DIR = 'results';
fs.mkdirSync(OUT_DIR, { recursive: true });
fs.writeFileSync(`${OUT_DIR}/t18_results_${EPOCH}.json`, JSON.stringify(summary, null, 2));
fs.writeFileSync(`${OUT_DIR}/t18_evidence_${EPOCH}.json`, JSON.stringify(evidence, null, 2));

console.log(`\n${'='.repeat(100)}`);
console.log('  TOTALS:', JSON.stringify(summary.totals));
console.log('  BY AREA:', JSON.stringify(summary.by_area, null, 1));
console.log(`  Written: ${OUT_DIR}/t18_results_${EPOCH}.json / ${OUT_DIR}/t18_evidence_${EPOCH}.json`);
