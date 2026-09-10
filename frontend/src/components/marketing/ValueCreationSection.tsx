import React, { useEffect, useRef, useState } from 'react';
import './ValueCreation.css';

/**
 * ValueCreationSection — "Both Sides of the Move"
 *
 * A self-contained, interactive marketing widget that shows a cross-border
 * relocation from the HR and employee sides, contrasting today's fragmented
 * process with ReloPass. Two lenses (Compare: today/ReloPass, Whose view:
 * both/HR/employee) drive a system diagram, a step-through journey and an
 * editable savings model.
 *
 * Styling is scoped under `.vc-root` in ./ValueCreation.css so it never
 * collides with the marketing token utilities. Copy describes what the
 * controls DO and never claims a regulatory status (see
 * scripts/check_compliance_claims.py / docs/compliance/AIQ-1487).
 */

type Mode = 'today' | 'relopass';
type Persona = 'both' | 'hr' | 'emp';
type Cur = '€' | '$' | '£';

interface Stage {
  n: string;
  nm: string;
  tm: string;
  hrT: string;
  hrR: string;
  empT: string;
  empR: string;
  bT: string;
  bR: string;
  spT: string;
  spR: string;
}

const STAGES: Stage[] = [
  {
    n: '01', nm: 'Offer & decision', tm: 'Day 0',
    hrT: 'Start from a blank page. Dig up the last move’s email thread and hope this route is similar.',
    hrR: 'Open a case for the corridor. ReloPass loads the playbook for that route instantly.',
    empT: 'Said yes — now what? Google, forums, and a rising sense of dread.',
    empR: 'Get a personal link. One home for the whole move, from day one.',
    bT: 'No shared record', bR: 'Case created → invited',
    spT: 'Offer lives in an inbox; the employee is on their own.',
    spR: 'HR opens the case and invites the employee into it.',
  },
  {
    n: '02', nm: 'Intake', tm: 'Week 1',
    hrT: 'Email a questionnaire. Chase the replies for two weeks. Re-ask what got missed.',
    hrR: 'The employee self-serves a guided intake; HR watches it fill in live.',
    empT: 'Fill a generic form. Send the same passport scan three times.',
    empR: 'Answer once — family, timing, route — in a guided flow.',
    bT: 'Weeks of chasing', bR: 'Answered once',
    spT: 'HR can’t plan until the employee replies; the employee waits to be told what’s needed.',
    spR: 'Intake feeds the plan the moment it’s submitted — both sides see it.',
  },
  {
    n: '03', nm: 'Policy & budget', tm: 'Week 1–2',
    hrT: 'Re-interpret the policy PDF case by case. Decisions drift; no two are alike.',
    hrR: 'Set the policy once. ReloPass resolves each person’s entitlements from it.',
    empT: 'Unclear what’s covered. Ask HR. Wait. Ask again.',
    empR: 'See exactly what’s covered — grounded in your company policy, cited.',
    bT: '“Is X covered?” loop', bR: 'Entitlements resolved',
    spT: 'Every “is this covered?” is a round-trip that stalls both sides.',
    spR: 'Policy and entitlements are one source both sides read — no round-trip.',
  },
  {
    n: '04', nm: 'Services & suppliers', tm: 'Week 2–4',
    hrT: 'Email five vendors per service. Line the quotes up in a spreadsheet by hand.',
    hrR: 'Take the employee’s shortlist, request quotes from vendors, and see every offer in one view.',
    empT: 'Find your own bank, mover and insurer — and hope they’re any good.',
    empR: 'Pick from matched, vetted providers, shortlist them, then compare the offers HR brings back.',
    bT: 'Forwarded vendor emails', bR: 'Shortlist → quotes',
    spT: 'HR forwards vendor threads; the employee picks blind from a forwarded list.',
    spR: 'Employee shortlists → HR requests the quotes → employee compares. Neither step works alone.',
  },
  {
    n: '05', nm: 'Immigration & documents', tm: 'Week 3–8',
    hrT: 'Track visa steps in a spreadsheet. Miss one dependency and the chain breaks.',
    hrR: 'Immigration requirements tracked for the route, each with a live status.',
    empT: 'Wrong form, missed appointment, start the queue over.',
    empR: 'The exact steps and documents for your route — in the right order.',
    bT: 'Deadlines slip', bR: 'Requirements tracked',
    spT: 'A document only HR knows about blocks a step only the employee can take.',
    spR: 'Requirements and milestones are shared, so nothing waits on a hidden inbox.',
  },
  {
    n: '06', nm: 'Move & arrival', tm: 'Move month',
    hrT: 'Radio silence. You hear about the problem after it has already happened.',
    hrR: 'Live case progress; risks flag early enough to act on.',
    empT: 'Juggle movers, flights and keys alone, in a country you don’t know yet.',
    empR: 'A roadmap of milestones — you always know what’s next.',
    bT: 'Status by chasing', bR: 'Shared roadmap',
    spT: 'HR chases for status; the employee doesn’t know who to tell when it goes wrong.',
    spR: 'One roadmap shows both sides the same real-time status.',
  },
  {
    n: '07', nm: 'Settle in & productive', tm: 'Month 1–3',
    hrT: 'No idea if they’ve landed. Nothing captured for the next move.',
    hrR: 'The case closes into a record you reuse for the next person on this route.',
    empT: 'Still sorting tax and registration months later.',
    empR: 'Local setup steps guide you to productive, faster.',
    bT: 'Nothing captured', bR: 'Logged & reusable',
    spT: 'The knowledge leaves with the thread; the next move starts from zero.',
    spR: 'Every decision is logged — institutional memory both sides keep.',
  },
];

const DEFAULT_CALC = {
  relos: '25', hours: '40', rate: '60', emphours: '50', emprate: '50',
  vspend: '15000', failrate: '12', failcost: '25000',
  aCoord: '60', aEmp: '50', aVend: '8', aFail: '4',
};
type CalcState = typeof DEFAULT_CALC;

/* ---- small svg icon helpers (camelCase attrs for JSX) ---- */
const svgProps = {
  fill: 'none' as const, stroke: 'currentColor', strokeWidth: 2,
  strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, viewBox: '0 0 24 24',
};
const IcHR = () => (<svg {...svgProps}><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>);
const IcEmp = () => (<svg {...svgProps}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></svg>);
const IcHandoff = () => (<svg {...svgProps}><path d="M8 7h12l-3-3M16 17H4l3 3" /></svg>);
const IcResize = () => (<svg {...svgProps}><path d="M8 3H5a2 2 0 0 0-2 2v3m0 8v3a2 2 0 0 0 2 2h3m8-18h3a2 2 0 0 1 2 2v3m0 8v3a2 2 0 0 1-2 2h-3" /></svg>);
const IcPrev = () => (<svg {...svgProps}><path d="M19 12H5M11 18l-6-6 6-6" /></svg>);
const IcNext = () => (<svg {...svgProps}><path d="M5 12h14M13 6l6 6-6 6" /></svg>);
const IcInfo = () => (<svg {...svgProps}><circle cx="12" cy="12" r="9" /><path d="M12 8h.01M11 12h1v4h1" /></svg>);

/* ---- diagram geometry ---- */
const TODAY_LINKS: { d: string; c: string }[] = [
  { d: 'M190 90 C 340 70, 470 42, 596 47', c: 'vc-link vc-lk-hr' },
  { d: 'M190 90 C 300 62, 400 40, 470 35', c: 'vc-link vc-b vc-lk-hr' },
  { d: 'M190 90 C 360 100, 490 110, 612 113', c: 'vc-link vc-lk-hr' },
  { d: 'M190 90 C 350 150, 500 176, 628 179', c: 'vc-link vc-b vc-lk-hr' },
  { d: 'M190 90 C 340 180, 470 240, 596 245', c: 'vc-link vc-lk-hr' },
  { d: 'M190 90 C 320 220, 470 300, 600 309', c: 'vc-link vc-b vc-lk-hr' },
  { d: 'M190 90 C 250 190, 300 280, 346 300', c: 'vc-link vc-lk-hr' },
  { d: 'M190 250 C 350 240, 490 70, 596 47', c: 'vc-link vc-lk-emp' },
  { d: 'M190 250 C 360 240, 500 130, 612 113', c: 'vc-link vc-b vc-lk-emp' },
  { d: 'M190 250 C 340 235, 500 190, 628 179', c: 'vc-link vc-lk-emp' },
  { d: 'M190 250 C 360 250, 500 244, 596 245', c: 'vc-link vc-b vc-lk-emp' },
  { d: 'M190 250 C 340 300, 480 312, 600 309', c: 'vc-link vc-lk-emp' },
  { d: 'M190 250 C 250 280, 300 300, 346 300', c: 'vc-link vc-b vc-lk-emp' },
  { d: 'M190 250 C 320 240, 430 60, 470 35', c: 'vc-link vc-lk-emp' },
  { d: 'M190 90 C 235 140, 235 200, 190 250', c: 'vc-link vc-lk-both' },
  { d: 'M628 179 C 700 220, 680 285, 600 309', c: 'vc-link vc-b vc-lk-both' },
  { d: 'M596 47 C 690 70, 700 100, 612 113', c: 'vc-link vc-b vc-lk-both' },
];
const TODAY_BOXES = [
  { x: 596, y: 31, w: 118, h: 34, label: 'Immigration', ty: 53 },
  { x: 470, y: 18, w: 86, h: 34, label: 'Tax', ty: 40 },
  { x: 612, y: 96, w: 96, h: 34, label: 'Bank', ty: 118 },
  { x: 628, y: 162, w: 104, h: 34, label: 'Movers', ty: 184 },
  { x: 596, y: 228, w: 112, h: 34, label: 'Insurance', ty: 250 },
  { x: 600, y: 292, w: 118, h: 34, label: 'Housing', ty: 314 },
  { x: 300, y: 300, w: 92, h: 34, label: 'School', ty: 322 },
];
const RELO_OUT: string[] = [
  'M470 100 C 540 100, 545 40, 596 40',
  'M470 122 C 540 122, 548 86, 596 86',
  'M470 146 C 548 146, 552 132, 596 132',
  'M470 170 C 552 170, 552 178, 596 178',
  'M470 194 C 548 194, 548 224, 596 224',
  'M470 218 C 540 218, 540 270, 596 270',
  'M470 240 C 535 240, 535 316, 596 316',
];
const RELO_BOXES = [
  { x: 596, y: 24, w: 118, h: 32, label: 'Immigration', ty: 45 },
  { x: 596, y: 70, w: 118, h: 32, label: 'Bank', ty: 91 },
  { x: 596, y: 116, w: 118, h: 32, label: 'Movers', ty: 137 },
  { x: 596, y: 162, w: 118, h: 32, label: 'Housing', ty: 183 },
  { x: 596, y: 208, w: 118, h: 32, label: 'Insurance', ty: 229 },
  { x: 596, y: 254, w: 118, h: 32, label: 'School', ty: 275 },
  { x: 596, y: 300, w: 118, h: 32, label: 'Tax', ty: 321 },
];

const TRUST = [
  { icon: (<svg {...svgProps}><path d="M20 6 9 17l-5-5" /></svg>), title: 'A human reviews every recommendation', body: 'Nothing reaches an employee until a person has approved it. AI drafts; people decide.' },
  { icon: (<svg {...svgProps}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" /></svg>), title: 'Grounded in your policy, and cited', body: 'Answers come from your company’s own policy and curated corridor rules — with the source shown, not a guess.' },
  { icon: (<svg {...svgProps}><path d="M12 8v4l3 2" /><circle cx="12" cy="12" r="9" /></svg>), title: 'Every decision is logged', body: 'Each step is recorded with the information that informed it — an audit trail you can hand to any reviewer.' },
  { icon: (<svg {...svgProps}><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>), title: 'Personal data is masked', body: 'Names, passports, IBANs and the rest are stripped before any text is sent to an AI model.' },
  { icon: (<svg {...svgProps}><path d="M12 2 4 6v6c0 5 3.5 8 8 10 4.5-2 8-5 8-10V6Z" /></svg>), title: 'Requirements are served, not generated', body: 'What an employee must do comes from reviewed, cited data for their route — never written fresh at the moment they ask.' },
  { icon: (<svg {...svgProps}><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13A4 4 0 0 1 16 11" /></svg>), title: 'One record, reusable', body: 'Every move leaves institutional memory, so the next one in the same corridor starts miles ahead.' },
];

function readLS(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}

const SvgBox: React.FC<{ x: number; y: number; w: number; h: number; label: string; ty: number }> = ({ x, y, w, h, label, ty }) => (
  <g><rect className="vc-node" x={x} y={y} width={w} height={h} rx={8} /><text className="vc-node-lab" x={x + w / 2} y={ty} textAnchor="middle">{label}</text></g>
);

export const ValueCreationSection: React.FC = () => {
  const [mode, setMode] = useState<Mode>(() => {
    const v = readLS('rp-vc-mode');
    return v === 'today' || v === 'relopass' ? v : 'relopass';
  });
  const [persona, setPersona] = useState<Persona>(() => {
    const v = readLS('rp-vc-persona');
    return v === 'both' || v === 'hr' || v === 'emp' ? v : 'both';
  });
  const [stage, setStage] = useState<number>(() => {
    const v = readLS('rp-vc-stage');
    const i = v ? parseInt(v, 10) : 0;
    return !isNaN(i) ? Math.max(0, Math.min(STAGES.length - 1, i)) : 0;
  });
  const [cur, setCur] = useState<Cur>(() => {
    const v = readLS('rp-vc-cur');
    return v === '€' || v === '$' || v === '£' ? v : '€';
  });
  const [calc, setCalc] = useState<CalcState>(() => {
    const j = readLS('rp-vc-calc');
    if (j) { try { return { ...DEFAULT_CALC, ...(JSON.parse(j) as Partial<CalcState>) }; } catch { /* ignore */ } }
    return DEFAULT_CALC;
  });

  const railRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      localStorage.setItem('rp-vc-mode', mode);
      localStorage.setItem('rp-vc-persona', persona);
      localStorage.setItem('rp-vc-stage', String(stage));
      localStorage.setItem('rp-vc-cur', cur);
      localStorage.setItem('rp-vc-calc', JSON.stringify(calc));
    } catch { /* ignore */ }
  }, [mode, persona, stage, cur, calc]);

  const go = (i: number, focus = false) => {
    const ni = Math.max(0, Math.min(STAGES.length - 1, i));
    setStage(ni);
    if (focus) {
      requestAnimationFrame(() => {
        const btns = railRef.current?.querySelectorAll<HTMLButtonElement>('.vc-sstep');
        btns?.[ni]?.focus();
      });
    }
  };
  const onStepKey = (e: React.KeyboardEvent, i: number) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); go(i + 1, true); }
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); go(i - 1, true); }
  };

  const setField = (k: keyof CalcState, v: string) => setCalc((c) => ({ ...c, [k]: v }));

  /* ---- savings model ---- */
  const n = (s: string) => { const v = parseFloat(s); return isNaN(v) ? 0 : v; };
  const relos = n(calc.relos), hours = n(calc.hours), rate = n(calc.rate);
  const emphours = n(calc.emphours), emprate = n(calc.emprate);
  const vspend = n(calc.vspend), failrate = n(calc.failrate), failcost = n(calc.failcost);
  const coord = n(calc.aCoord), empRed = n(calc.aEmp), vend = n(calc.aVend), failTo = n(calc.aFail);

  const hoursSaved = relos * hours * (coord / 100);
  const hrCost = hoursSaved * rate;
  const empHoursSaved = relos * emphours * (empRed / 100);
  const empCost = empHoursSaved * emprate;
  const vendSaved = relos * vspend * (vend / 100);
  const riskToday = relos * (failrate / 100) * failcost;
  const riskAfter = relos * (Math.min(failTo, failrate) / 100) * failcost;
  const riskAvoid = Math.max(0, riskToday - riskAfter);
  const total = hrCost + empCost + vendSaved + riskAvoid;
  const perMove = relos > 0 ? total / relos : 0;

  const money = (v: number) => cur + Math.round(v).toLocaleString('en-US');
  const fmtInt = (v: number) => Math.round(v).toLocaleString('en-US');

  const p = STAGES[stage] ?? STAGES[0];
  if (!p) return null; // STAGES is non-empty; guard satisfies noUncheckedIndexedAccess

  const laneCard = (kind: 'hr' | 'emp') => {
    const isHr = kind === 'hr';
    return (
      <div className={`vc-lane-card ${isHr ? 'vc-hr' : 'vc-emp'}`}>
        <div className="vc-lane-top">
          <span className="vc-lane-ic">{isHr ? <IcHR /> : <IcEmp />}</span>
          {isHr ? 'HR' : 'Employee'} <small>{isHr ? 'company side' : 'the mover'}</small>
        </div>
        <div className="vc-swap-today">
          <span className="vc-badge vc-fr">⚠ {p.bT}</span>
          <p>{isHr ? p.hrT : p.empT}</p>
        </div>
        <div className="vc-swap-relo">
          <span className="vc-badge vc-fl">✓ {p.bR}</span>
          <p>{isHr ? p.hrR : p.empR}</p>
        </div>
      </div>
    );
  };

  return (
    <div className={`vc-root mode-${mode} persona-${persona}`}>
      <div className="vc-inner">

        {/* ---- controls ---- */}
        <div className="vc-controls">
          <div className="vc-ctrl-block">
            <span className="vc-ctrl-label">Compare</span>
            <div className="vc-seg" role="group" aria-label="Compare today with ReloPass">
              <button type="button" data-mode="today" aria-pressed={mode === 'today'} onClick={() => setMode('today')}><span className="vc-dot" />How it works today</button>
              <button type="button" data-mode="relopass" aria-pressed={mode === 'relopass'} onClick={() => setMode('relopass')}><span className="vc-dot" />With ReloPass</button>
            </div>
          </div>
          <div className="vc-ctrl-block">
            <span className="vc-ctrl-label">Whose view</span>
            <div className="vc-seg vc-persona" role="group" aria-label="Focus on one side or both">
              <button type="button" data-persona="both" aria-pressed={persona === 'both'} onClick={() => setPersona('both')}><span className="vc-twin"><span className="vc-dot" /><span className="vc-dot" /></span>Both</button>
              <button type="button" data-persona="hr" aria-pressed={persona === 'hr'} onClick={() => setPersona('hr')}><span className="vc-dot" />HR</button>
              <button type="button" data-persona="emp" aria-pressed={persona === 'emp'} onClick={() => setPersona('emp')}><span className="vc-dot" />Employee</button>
            </div>
          </div>
          <span className="vc-hint"><IcResize />Two lenses — compare today vs ReloPass, and focus on HR, the employee, or both.</span>
        </div>

        <div className="vc-legend">
          <span><i className="vc-chip vc-lg-hr" /> HR side</span>
          <span><i className="vc-chip vc-lg-emp" /> Employee side</span>
          <span><i className="vc-chip vc-lg-fr" /> Friction &amp; risk (today)</span>
          <span><i className="vc-chip vc-lg-fl" /> Handled &amp; flowing (ReloPass)</span>
        </div>

        {/* ---- diagram ---- */}
        <div className="vc-block">
          <div className="vc-sec-head">
            <span className="vc-eyebrow">The shape of the process</span>
            <h3>Today, everyone talks to everyone. With ReloPass, everyone talks to one place.</h3>
          </div>
          <div className="vc-diagram-card">
            <div className="vc-diagram-top">
              <p className="vc-t-today"><strong>Today —</strong> HR and the employee each chase the same movers, banks, lawyers and landlords separately. Status lives in inboxes, not in systems — nobody owns the whole picture, and things slip between them.</p>
              <p className="vc-t-relo"><strong>With ReloPass —</strong> HR sets the rules once; the employee follows one guided path; suppliers are orchestrated in order. Both sides read the same live case — the case does the coordination, so the team does the work.</p>
            </div>
            <div className="vc-diagram-stage">
              <div className="vc-stagewrap">
                {/* TODAY */}
                <svg className="vc-g-today" viewBox="0 0 800 340" role="img" aria-label="HR and the employee each separately connected to every supplier by many tangled, crossing lines">
                  <g>{TODAY_LINKS.map((l, i) => <path key={i} className={l.c} d={l.d} />)}</g>
                  <g className="vc-pnode vc-hrnode"><rect className="vc-node" x={70} y={66} width={120} height={48} rx={10} /><text className="vc-node-lab" x={130} y={88} textAnchor="middle">HR</text><text className="vc-node-sub" x={130} y={103} textAnchor="middle">company side</text></g>
                  <g className="vc-pnode vc-emp vc-empnode"><rect className="vc-node" x={70} y={226} width={120} height={48} rx={10} /><text className="vc-node-lab" x={130} y={248} textAnchor="middle">EMPLOYEE</text><text className="vc-node-sub" x={130} y={263} textAnchor="middle">the mover</text></g>
                  <g>{TODAY_BOXES.map((b) => <SvgBox key={b.label} {...b} />)}</g>
                </svg>
                {/* RELOPASS */}
                <svg className="vc-g-relopass" viewBox="0 0 800 340" role="img" aria-label="HR and the employee each connect with one line to a central ReloPass spine, which links to every supplier with a single clean line">
                  <path className="vc-rail-in vc-lk-hr" d="M190 96 C 265 96, 275 150, 330 150" />
                  <path className="vc-rail-in vc-lk-emp" d="M190 244 C 265 244, 275 190, 330 190" />
                  <g>{RELO_OUT.map((d, i) => <path key={i} className="vc-rail-out" d={d} />)}</g>
                  <g className="vc-pnode vc-hrnode"><rect className="vc-node" x={70} y={72} width={120} height={48} rx={10} /><text className="vc-node-lab" x={130} y={94} textAnchor="middle">HR</text><text className="vc-node-sub" x={130} y={109} textAnchor="middle">sets policy</text></g>
                  <g className="vc-pnode vc-emp vc-empnode"><rect className="vc-node" x={70} y={220} width={120} height={48} rx={10} /><text className="vc-node-lab" x={130} y={242} textAnchor="middle">EMPLOYEE</text><text className="vc-node-sub" x={130} y={257} textAnchor="middle">one clear path</text></g>
                  <rect className="vc-spine" x={330} y={72} width={140} height={196} rx={16} />
                  <text className="vc-spine-lab" x={400} y={164} textAnchor="middle">ReloPass</text>
                  <text className="vc-spine-sub" x={400} y={186} textAnchor="middle">ONE LIVE CASE</text>
                  <circle className="vc-flowdot" cx={330} cy={150} r={4} /><circle className="vc-flowdot" cx={330} cy={190} r={4} />
                  <g>{RELO_BOXES.map((b) => <SvgBox key={b.label} {...b} />)}</g>
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* ---- journey stepper ---- */}
        <div className="vc-block">
          <div className="vc-sec-head">
            <span className="vc-eyebrow">Relocation fails in the handoffs</span>
            <h3>Walk the move one step at a time — HR, the employee, and the handoff between them.</h3>
            <p>Seven stages, from the day the offer lands to the day they’re productive. Step through each one: at every stage, one side is waiting on the other — today in inboxes, on ReloPass in a single shared case.</p>
          </div>
          <div className="vc-stepper">
            <div className="vc-srail" ref={railRef} role="group" aria-label="Relocation stages">
              {STAGES.map((s, i) => (
                <button
                  key={s.n}
                  type="button"
                  className={`vc-sstep${i === stage ? ' vc-active' : ''}${i < stage ? ' vc-done' : ''}`}
                  aria-current={i === stage ? 'step' : undefined}
                  aria-label={`Step ${i + 1}: ${s.nm}`}
                  onClick={() => go(i)}
                  onKeyDown={(e) => onStepKey(e, i)}
                >
                  <span className="vc-snode">{i + 1}</span>
                  <span className="vc-slabel">{s.nm}<span className="vc-stime">{s.tm}</span></span>
                </button>
              ))}
            </div>
            <div className="vc-sdetail">
              <div className="vc-sdhead">
                <span className="vc-sd-num">{p.n} / 07</span>
                <span className="vc-sd-name">{p.nm}</span>
                <span className="vc-sd-time">{p.tm}</span>
              </div>
              <div className="vc-sd-lanes">
                {laneCard('hr')}
                {laneCard('emp')}
              </div>
              <div className="vc-handoff">
                <div className="vc-swap-today"><div className="vc-handoff-lab"><IcHandoff /> The handoff today · by inbox</div><p>{p.spT}</p></div>
                <div className="vc-swap-relo"><div className="vc-handoff-lab"><IcHandoff /> The handoff · one shared case</div><p>{p.spR}</p></div>
              </div>
            </div>
            <div className="vc-snav">
              <button type="button" onClick={() => go(stage - 1)} disabled={stage === 0}><IcPrev />Previous</button>
              <span className="vc-scount">Step {stage + 1} of {STAGES.length}</span>
              <button type="button" onClick={() => go(stage + 1)} disabled={stage === STAGES.length - 1}>Next<IcNext /></button>
            </div>
          </div>
        </div>

        {/* ---- savings ---- */}
        <div className="vc-block">
          <div className="vc-sec-head">
            <span className="vc-eyebrow">What the difference is worth</span>
            <h3>Put your own numbers in. The model does the rest.</h3>
            <p>A starting estimate of what one place — instead of everyone chasing everyone — saves a mobility team each year. Every figure is editable; the defaults are illustrative, not a quote.</p>
          </div>
          <div className="vc-calc">
            <div className="vc-panel">
              <h3>Your numbers</h3>
              <p className="vc-sub">Roughly, for your team as it runs today.</p>

              <div className="vc-field"><label htmlFor="vc-relos">Relocations per year</label>
                <input id="vc-relos" type="number" min={1} max={100000} step={1} value={calc.relos} onChange={(e) => setField('relos', e.target.value)} /></div>
              <div className="vc-field"><label htmlFor="vc-hours">HR hours spent coordinating one move</label>
                <input id="vc-hours" type="number" min={0} max={2000} step={1} value={calc.hours} onChange={(e) => setField('hours', e.target.value)} /></div>
              <div className="vc-field"><label htmlFor="vc-rate">Fully-loaded HR cost / hour <span className="vc-cur">{cur}</span></label>
                <input id="vc-rate" type="number" min={0} max={100000} step={1} value={calc.rate} onChange={(e) => setField('rate', e.target.value)} /></div>
              <div className="vc-field"><label htmlFor="vc-emphours">Employee hours lost to their own move</label>
                <input id="vc-emphours" type="number" min={0} max={4000} step={1} value={calc.emphours} onChange={(e) => setField('emphours', e.target.value)} /></div>
              <div className="vc-field"><label htmlFor="vc-emprate">Fully-loaded employee cost / hour <span className="vc-cur">{cur}</span></label>
                <input id="vc-emprate" type="number" min={0} max={100000} step={1} value={calc.emprate} onChange={(e) => setField('emprate', e.target.value)} /></div>
              <div className="vc-field"><label htmlFor="vc-vspend">Supplier spend per move <span className="vc-cur">{cur}</span></label>
                <input id="vc-vspend" type="number" min={0} max={100000000} step={100} value={calc.vspend} onChange={(e) => setField('vspend', e.target.value)} /></div>
              <div className="vc-field"><label htmlFor="vc-failrate">Moves that stall, slip or fail today <span className="vc-cur">%</span></label>
                <input id="vc-failrate" type="number" min={0} max={100} step={1} value={calc.failrate} onChange={(e) => setField('failrate', e.target.value)} /></div>
              <div className="vc-field"><label htmlFor="vc-failcost">Cost when a move goes wrong <span className="vc-cur">{cur}</span></label>
                <input id="vc-failcost" type="number" min={0} max={100000000} step={500} value={calc.failcost} onChange={(e) => setField('failcost', e.target.value)} /></div>

              <div className="vc-assump">
                <div className="vc-ah">ReloPass impact · adjustable assumptions</div>
                <div className="vc-field"><label htmlFor="vc-acoord">HR coordination time removed <span className="vc-cur vc-mono">{coord}%</span></label>
                  <div className="vc-row2"><input id="vc-acoord" type="range" min={0} max={90} step={5} value={calc.aCoord} onChange={(e) => setField('aCoord', e.target.value)} /></div></div>
                <div className="vc-field"><label htmlFor="vc-aemp">Employee’s own time removed <span className="vc-cur vc-mono">{empRed}%</span></label>
                  <div className="vc-row2"><input id="vc-aemp" type="range" min={0} max={90} step={5} value={calc.aEmp} onChange={(e) => setField('aEmp', e.target.value)} /></div></div>
                <div className="vc-field"><label htmlFor="vc-avend">Supplier spend saved via one RFQ <span className="vc-cur vc-mono">{vend}%</span></label>
                  <div className="vc-row2"><input id="vc-avend" type="range" min={0} max={30} step={1} value={calc.aVend} onChange={(e) => setField('aVend', e.target.value)} /></div></div>
                <div className="vc-field"><label htmlFor="vc-afail">Failure rate falls to <span className="vc-cur vc-mono">{failTo}%</span></label>
                  <div className="vc-row2"><input id="vc-afail" type="range" min={0} max={100} step={1} value={calc.aFail} onChange={(e) => setField('aFail', e.target.value)} /></div></div>
                <div className="vc-field" style={{ marginTop: 18 }}>
                  <span className="vc-cap">Currency</span>
                  <div className="vc-cur-select" role="group" aria-label="Currency">
                    {(['€', '$', '£'] as Cur[]).map((sym) => (
                      <button key={sym} type="button" aria-pressed={cur === sym} onClick={() => setCur(sym)}>{sym}</button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="vc-results">
              <div className="vc-headline">
                <div className="vc-lab">Estimated saving · per year</div>
                <div className="vc-big">{money(total)}</div>
                <div className="vc-per">About <b>{money(perMove)}</b> saved on every relocation.</div>
              </div>
              <div className="vc-tiles">
                <div className="vc-tile"><div className="vc-tl"><i className="vc-ic vc-ic-hrs" />HR hours freed / year</div><div className="vc-tv">{fmtInt(hoursSaved)}</div><div className="vc-tu">reclaimed from coordination</div></div>
                <div className="vc-tile"><div className="vc-tl"><i className="vc-ic vc-ic-hr" />HR cost saved</div><div className="vc-tv">{money(hrCost)}</div><div className="vc-tu">that coordination time, valued</div></div>
                <div className="vc-tile"><div className="vc-tl"><i className="vc-ic vc-ic-emp" />Employee time saved</div><div className="vc-tv">{money(empCost)}</div><div className="vc-tu">less time off work on paperwork</div></div>
                <div className="vc-tile"><div className="vc-tl"><i className="vc-ic vc-ic-vn" />Supplier spend saved</div><div className="vc-tv">{money(vendSaved)}</div><div className="vc-tu">competitive quotes in one view</div></div>
                <div className="vc-tile"><div className="vc-tl"><i className="vc-ic vc-ic-rk" />Risk cost avoided</div><div className="vc-tv">{money(riskAvoid)}</div><div className="vc-tu">fewer failed / stalled moves</div></div>
              </div>
              <p className="vc-disclaimer">
                <IcInfo />
                <span>An illustrative model to frame the conversation, not a commercial quote. It leaves out the things hardest to price and easiest to feel: an employee who arrives ready to work, and an HR team that can prove every decision was made to policy.</span>
              </p>
            </div>
          </div>
        </div>

        {/* ---- trust ---- */}
        <div className="vc-block">
          <div className="vc-trust">
            <div className="vc-sec-head">
              <span className="vc-eyebrow">Why not just paste it into ChatGPT?</span>
              <h3>Because a relocation is a compliance record, not a chat.</h3>
              <p>ReloPass uses AI to draft and speed the work — never to invent what an employee is told. These are the controls that make the difference, described by what they do.</p>
            </div>
            <div className="vc-ctrl-grid">
              {TRUST.map((t) => (
                <div className="vc-ctrl" key={t.title}>
                  <div className="vc-ci">{t.icon}</div>
                  <h4>{t.title}</h4>
                  <p>{t.body}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};
