// platform-s5b-policy-builder.jsx — HR Policy Builder (canvas + benefit matrix)
(function() {
const { useState, useEffect, useMemo, useRef } = React;
const I = window.PlatformIcon;

// ── Constants ─────────────────────────────────────────────────────
const CATEGORIES = [
  { id: 1, key: 'pre_assignment',     t: 'Pre-assignment support',       benefits: [
    { k: 'visa_work_permit_assistance', lbl: 'Visa & work permit assistance', tip: 'Application fees, legal support, document gathering.' },
    { k: 'medical_exam_reimbursement',  lbl: 'Medical exam reimbursement',     tip: 'Required by some destinations as part of visa.' },
    { k: 'pre_assignment_visit',        lbl: 'Pre-assignment visit',           tip: 'Scouting trip for housing, schools, neighborhoods.' },
    { k: 'cultural_training',           lbl: 'Cultural & intercultural training', tip: 'Briefings on workplace culture, customs, language norms.' },
    { k: 'language_training',           lbl: 'Language training',               tip: 'Lessons for the employee and/or family.' },
  ]},
  { id: 2, key: 'relocation',         t: 'Relocation assistance',         benefits: [
    { k: 'relocation_allowance_assignee_partner', lbl: 'Relocation allowance (assignee + partner)', tip: 'One-off lump sum for misc relocation costs.' },
    { k: 'relocation_allowance_dependent',         lbl: 'Relocation allowance (per dependent)',      tip: 'Per child/dependent additional allowance.' },
    { k: 'removal_expenses',                       lbl: 'Removal & shipping expenses',                tip: 'Movers, packing, customs.' },
    { k: 'shipment_of_goods',                      lbl: 'Shipment of personal goods',                 tip: 'Container or air-freight of household effects.' },
    { k: 'storage',                                lbl: 'Storage (temporary)',                        tip: 'Storage between origin departure and host arrival.' },
    { k: 'temporary_living',                       lbl: 'Temporary living accommodation',             tip: 'Serviced apartment / hotel while finding permanent.' },
    { k: 'settling_in_services',                   lbl: 'Settling-in services',                       tip: 'Local registration, utilities, bank, school admin.' },
  ]},
  { id: 3, key: 'compensation',       t: 'Compensation & allowances',     benefits: [
    { k: 'mobility_premium',         lbl: 'Mobility premium',               tip: 'Bonus for accepting the assignment.' },
    { k: 'location_allowance',       lbl: 'Location / hardship allowance',  tip: 'Extra pay for difficult or expensive destinations.' },
    { k: 'living_allowance',         lbl: 'Cost-of-living allowance',       tip: 'Compensates for cost-of-living differences.' },
    { k: 'cola',                     lbl: 'COLA (Cost of living adjustment)', tip: 'Index-linked recurring allowance.' },
    { k: 'host_housing_cap',         lbl: 'Host country housing cap',        tip: 'Monthly housing budget at destination.' },
    { k: 'host_transportation',      lbl: 'Host country transportation',     tip: 'Car lease, commute card, etc.' },
    { k: 'driving_test_reimbursement', lbl: 'Driving test reimbursement',    tip: 'If a local license is required.' },
    { k: 'dual_career_support',      lbl: 'Dual-career support',             tip: 'Partner job search, coaching, networking.' },
  ]},
  { id: 4, key: 'family',             t: 'Family support & education',     benefits: [
    { k: 'spouse_partner_assistance', lbl: 'Spouse / partner assistance',    tip: 'Career counseling, language, networking.' },
    { k: 'child_education_support',   lbl: 'Child education support',         tip: 'School fees, enrollment, tutoring.' },
  ]},
  { id: 5, key: 'leave',              t: 'Leave & repatriation',           benefits: [
    { k: 'home_leave_trips',                       lbl: 'Home leave trips',                          tip: 'Annual trips back to origin country.' },
    { k: 'extra_holiday_days',                     lbl: 'Extra holiday days',                         tip: 'Additional PTO for relocated employees.' },
    { k: 'repatriation_allowance_assignee_partner', lbl: 'Repatriation allowance (assignee + partner)', tip: 'End-of-assignment lump sum.' },
    { k: 'repatriation_allowance_dependent',        lbl: 'Repatriation allowance (per dependent)',     tip: 'Per dependent return.' },
    { k: 'return_shipment_travel',                  lbl: 'Return shipment & travel',                   tip: 'Shipping goods and travel back.' },
  ]},
  { id: 6, key: 'tax',                t: 'Tax & payroll',                  benefits: [
    { k: 'tax_equalisation',     lbl: 'Tax equalisation',         tip: 'Company covers any extra tax burden from the move.' },
    { k: 'payroll_structure',    lbl: 'Payroll structure',         tip: 'Split payroll, host country payment.' },
    { k: 'banking_assistance',   lbl: 'Banking setup assistance',  tip: 'Open a local bank account.' },
    { k: 'tax_return_preparation', lbl: 'Tax return preparation',  tip: 'Annual filing in one or both jurisdictions.' },
  ]},
];
const TIER_PALETTE = ['#2962ff', '#1f8e8b', '#7a4ea3', '#c2761a', '#16a34a'];
const CUR_SYM = { EUR: '€', USD: '$', GBP: '£', CHF: 'CHF' };

// ── Templates ─────────────────────────────────────────────────────
const TEMPLATES = [
  { id: 'standard',    ico: '🌐', t: 'Standard global mobility', s: 'Three tiers (Manager / Director / VP). Permanent transfers + long-term assignments. Most-used baseline.', tiers: ['Manager', 'Director', 'VP'] },
  { id: 'tech',        ico: '💻', t: 'Tech / startup',            s: 'Two flexible tiers (IC / Senior IC). Lean on lump-sum budgets. Generous remote.', tiers: ['Engineer', 'Senior Eng'] },
  { id: 'banking',     ico: '🏦', t: 'Banking & finance',         s: 'Four tiers including C-Suite. Hardship allowances + tax equalisation enabled by default.', tiers: ['Manager', 'Director', 'MD', 'C-Suite'] },
  { id: 'short_term',  ico: '✈️', t: 'Short-term focused',         s: 'Built around 3-12mo assignments. Generous temp living, limited household shipping.', tiers: ['Standard', 'Senior'] },
];

// ── Pre-built tier data per template ──────────────────────────────
function tiersForTemplate(tplId) {
  const tpls = {
    standard: [
      { name: 'Manager',  color: TIER_PALETTE[0], targeting: { level: ['manager'],          type: ['long_term','permanent'], family: ['single','married','accompanied_family'] }, mode: 'caps',     lump: 14000, emp: 8 },
      { name: 'Director', color: TIER_PALETTE[1], targeting: { level: ['director'],         type: ['long_term','permanent'], family: ['single','married','accompanied_family'] }, mode: 'caps',     lump: 28000, emp: 4 },
      { name: 'VP',       color: TIER_PALETTE[2], targeting: { level: ['vp'],               type: ['long_term','permanent'], family: ['single','married','accompanied_family'] }, mode: 'lump',     lump: 68000, emp: 2 },
    ],
    tech: [
      { name: 'Engineer',    color: TIER_PALETTE[0], targeting: { level: ['entry','manager'], type: ['long_term','permanent'], family: ['single','married','accompanied_family'] }, mode: 'lump', lump: 18000, emp: 12 },
      { name: 'Senior Eng',  color: TIER_PALETTE[1], targeting: { level: ['director'],        type: ['long_term','permanent'], family: ['single','married','accompanied_family'] }, mode: 'lump', lump: 38000, emp: 5 },
    ],
    banking: [
      { name: 'Manager',  color: TIER_PALETTE[0], targeting: { level: ['manager'],  type: ['long_term'],  family: ['single','married','accompanied_family'] }, mode: 'caps', lump: 18000, emp: 14 },
      { name: 'Director', color: TIER_PALETTE[1], targeting: { level: ['director'], type: ['long_term'],  family: ['single','married','accompanied_family'] }, mode: 'caps', lump: 38000, emp: 6 },
      { name: 'MD',       color: TIER_PALETTE[2], targeting: { level: ['vp'],       type: ['long_term'],  family: ['single','married','accompanied_family'] }, mode: 'caps', lump: 72000, emp: 3 },
      { name: 'C-Suite',  color: TIER_PALETTE[3], targeting: { level: ['c_suite'],  type: ['long_term','permanent'], family: ['single','married','accompanied_family'] }, mode: 'lump', lump: 120000, emp: 1 },
    ],
    short_term: [
      { name: 'Standard', color: TIER_PALETTE[0], targeting: { level: ['manager'],  type: ['short_term','extended_business_trip'], family: ['single','married'] }, mode: 'caps', lump: 12000, emp: 6 },
      { name: 'Senior',   color: TIER_PALETTE[1], targeting: { level: ['director'], type: ['short_term','extended_business_trip'], family: ['single','married'] }, mode: 'caps', lump: 22000, emp: 3 },
    ],
  };
  const arr = tpls[tplId] || tpls.standard;
  return arr.map((t, i) => ({ ...t, id: `t${i}-${Date.now()}`, benefits: buildDefaultBenefits(t.name, t.mode === 'lump') }));
}

function buildDefaultBenefits(tierName, lumpMode) {
  // For each benefit, set covered/value/freq based on tier seniority
  const isSr = /Director|VP|MD|C-Suite|Senior/.test(tierName);
  const isExec = /VP|MD|C-Suite/.test(tierName);
  const out = {};
  CATEGORIES.forEach(cat => {
    cat.benefits.forEach(b => {
      let covered = true;
      let value_type = 'currency';
      let amount = 0;
      let freq = 'one_time';
      // Defaults per benefit
      switch (b.k) {
        case 'visa_work_permit_assistance':       covered = true; value_type='none'; break;
        case 'medical_exam_reimbursement':         amount = 200; break;
        case 'pre_assignment_visit':               covered = isSr; amount = isSr ? 3000 : 0; break;
        case 'cultural_training':                  covered = true; amount = 800; break;
        case 'language_training':                  covered = true; amount = 1500; freq = 'yearly'; break;
        case 'relocation_allowance_assignee_partner': amount = isExec ? 12000 : isSr ? 8000 : 5000; break;
        case 'relocation_allowance_dependent':     amount = 2500; freq = 'per_dependent'; break;
        case 'removal_expenses':                   amount = isSr ? 10000 : 7000; break;
        case 'shipment_of_goods':                  amount = isExec ? 15000 : isSr ? 10000 : 6000; break;
        case 'storage':                            covered = isSr; amount = 2400; freq = 'monthly'; break;
        case 'temporary_living':                   amount = isExec ? 5000 : 2800; freq = 'monthly'; break;
        case 'settling_in_services':               covered = true; amount = 2400; break;
        case 'mobility_premium':                   covered = isSr; amount = isExec ? 25 : 15; value_type='percentage'; break;
        case 'location_allowance':                 covered = isSr; amount = isExec ? 15 : 8; value_type='percentage'; break;
        case 'living_allowance':                   covered = false; break;
        case 'cola':                               covered = isExec; amount = 10; value_type='percentage'; freq = 'monthly'; break;
        case 'host_housing_cap':                   amount = isExec ? 5500 : isSr ? 3800 : 2400; freq = 'monthly'; break;
        case 'host_transportation':                amount = isExec ? 1200 : isSr ? 800 : 0; covered = isSr; freq = 'monthly'; break;
        case 'driving_test_reimbursement':         amount = 300; break;
        case 'dual_career_support':                covered = isSr; amount = 3500; break;
        case 'spouse_partner_assistance':          covered = isSr; amount = 2000; break;
        case 'child_education_support':            covered = isSr; amount = isExec ? 18000 : 12000; freq = 'yearly'; break;
        case 'home_leave_trips':                   amount = isExec ? 4 : 2; value_type='text'; freq = 'yearly'; break;
        case 'extra_holiday_days':                 amount = isExec ? 10 : 5; value_type='text'; freq = 'yearly'; break;
        case 'repatriation_allowance_assignee_partner': amount = 5000; break;
        case 'repatriation_allowance_dependent':   amount = 2000; freq = 'per_dependent'; break;
        case 'return_shipment_travel':             amount = 8000; break;
        case 'tax_equalisation':                   covered = isSr; value_type='none'; break;
        case 'payroll_structure':                  covered = true; value_type='none'; break;
        case 'banking_assistance':                 covered = true; value_type='none'; break;
        case 'tax_return_preparation':             covered = isSr; value_type='none'; break;
        default: amount = 1000;
      }
      out[b.k] = { covered, value_type, amount, freq, lump_inc: lumpMode ? (covered ? 'included' : 'excluded') : null,
                   cap: ['host_housing_cap','child_education_support','temporary_living','storage'].includes(b.k),
                   conditions: b.k === 'relocation_allowance_dependent' || b.k === 'repatriation_allowance_dependent' };
    });
  });
  return out;
}

// ── Targeting label helpers ────────────────────────────────────────
const LEVEL_LBL = { entry: 'Entry', manager: 'Manager', director: 'Director', vp: 'VP', c_suite: 'C-Suite' };
const TYPE_LBL = { long_term: 'Long-term', short_term: 'Short-term', permanent: 'Permanent', commuter: 'Commuter', extended_business_trip: 'Ext. business trip' };
const FAMILY_LBL = { single: 'Single', married: 'Married', accompanied_family: 'With family' };

function targetingSummary(tg) {
  const parts = [];
  if (tg.level?.length) parts.push(tg.level.map(l => LEVEL_LBL[l]).join('/'));
  if (tg.type?.length)  parts.push(tg.type.map(t => TYPE_LBL[t]).join('/'));
  if (tg.family?.length === 3) parts.push('Any family');
  else if (tg.family?.length) parts.push(tg.family.map(f => FAMILY_LBL[f]).join('/'));
  return parts.join(' · ') || 'No rules set';
}

const FREQ_OPTS = [
  { v: 'one_time', l: 'ONE-TIME' },
  { v: 'monthly',  l: '/ MO' },
  { v: 'yearly',   l: '/ YR' },
  { v: 'per_trip', l: '/ TRIP' },
  { v: 'per_dependent', l: '/ DEP' },
];
const VAL_OPTS = [
  { v: 'currency',   l: '€' },
  { v: 'percentage', l: '%' },
  { v: 'text',       l: 'TXT' },
  { v: 'none',       l: '—' },
];

// ── Main screen ───────────────────────────────────────────────────
function PolicyBuilderScreen({ currency = 'EUR' }) {
  const [tiers, setTiers] = useState([]);
  const [mode, setMode] = useState('template');
  const [templateOpen, setTemplateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [collapsed, setCollapsed] = useState({});
  const [rulesDrawerFor, setRulesDrawerFor] = useState(null);
  const [savedAt, setSavedAt] = useState(null);
  const [version, setVersion] = useState(null);
  const [ctxOpen, setCtxOpen] = useState(false);
  const [focusedBenefit, setFocusedBenefit] = useState('host_housing_cap');
  const [focusedTierId, setFocusedTierId] = useState(null);

  const applyTemplate = (tpl) => {
    setTiers(tiersForTemplate(tpl.id));
    setTemplateOpen(false);
    setSavedAt(Date.now());
  };
  const addTier = () => {
    const id = `t-${Date.now()}`;
    const idx = tiers.length;
    const newTier = {
      id,
      name: `Tier ${idx + 1}`,
      color: TIER_PALETTE[idx % TIER_PALETTE.length],
      targeting: { level: [], type: [], family: [] },
      mode: 'caps',
      lump: 10000,
      emp: 0,
      benefits: buildDefaultBenefits(`Tier ${idx + 1}`, false),
    };
    setTiers([...tiers, newTier]);
  };
  const updateTier = (id, next) => setTiers(ts => ts.map(t => t.id === id ? { ...t, ...next } : t));
  const updateBenefit = (tierId, benefitKey, patch) =>
    setTiers(ts => ts.map(t => t.id === tierId
      ? { ...t, benefits: { ...t.benefits, [benefitKey]: { ...t.benefits[benefitKey], ...patch } } }
      : t));

  // Auto-save sim
  useEffect(() => {
    if (tiers.length === 0) return;
    const tm = setTimeout(() => setSavedAt(Date.now()), 1200);
    return () => clearTimeout(tm);
  }, [tiers]);

  const status = tiers.length === 0 ? 'no-policy' : version ? 'published' : 'draft';
  const statusLbl = status === 'no-policy' ? 'No policy' : status === 'draft' ? 'Draft' : 'Published';

  // Sticky header rendering
  return (
    <div className={`page wide pb-page${ctxOpen ? ' pb-with-ctx' : ''}`}>
      {window.ProfileSubNav && <window.ProfileSubNav active="builder"/>}

      <div className="pb-hd">
        <div className="title-block">
          <h1>Policy Builder</h1>
          <div className="status-line">
            <span className={`pb-status ${status}`}>{statusLbl}</span>
            {version && <span className="pb-version">{version}</span>}
            {savedAt && (
              <span className="pb-autosave"><span className="dot"/> Saved {timeAgo(savedAt)}</span>
            )}
          </div>
        </div>
        <div className="pb-mode">
          <span className={`pb-mode-tab${mode === 'template' ? ' active' : ''}`} onClick={() => setMode('template')}>
            Build from template
          </span>
          <span className={`pb-mode-tab${mode === 'document' ? ' active' : ''}`} onClick={() => setMode('document')}>
            Import from document
          </span>
        </div>
        <div className="pb-currency" title="Default currency — applies to all benefit amounts unless overridden">
          <span className="ico">{CUR_SYM[currency]}</span>
          <span className="lbl">Currency:</span>
          <select defaultValue={currency} onChange={() => {}}>
            <option value="EUR">EUR (€)</option>
            <option value="USD">USD ($)</option>
            <option value="GBP">GBP (£)</option>
            <option value="CHF">CHF</option>
          </select>
        </div>
        <div className="spc"/>
        <div className="actions">
          <button className={`pb-ctx-trigger${ctxOpen ? ' on' : ''}`} onClick={() => setCtxOpen(o => !o)}>
            <I n="pulse" s={12}/> {ctxOpen ? 'Context on' : 'Context'}
          </button>
          <button className="btn"><I n="clock" s={12}/></button>
          <button className="btn">Save draft</button>
          <button className="btn"><I n="eye" s={12}/> Preview</button>
          <button className="btn primary" disabled={tiers.length === 0}>
            <I n="check2" s={12}/> Publish
          </button>
        </div>
      </div>

      {/* Empty state */}
      {mode === 'template' && tiers.length === 0 && (
        <div className="pb-empty">
          <div className="glyph">
            <svg viewBox="0 0 96 96">
              <rect x="10" y="22" width="22" height="56" rx="4" fill="var(--accent-soft)" stroke="var(--accent)" strokeWidth="1.5"/>
              <rect x="37" y="14" width="22" height="64" rx="4" fill="var(--teal-soft)" stroke="var(--teal)" strokeWidth="1.5"/>
              <rect x="64" y="30" width="22" height="48" rx="4" fill="var(--warning-soft)" stroke="var(--warning)" strokeWidth="1.5"/>
            </svg>
          </div>
          <h2>No tiers configured yet</h2>
          <div className="s">Start from a template to be set up in minutes, or build your own tier structure from scratch.</div>
          <div className="ctas">
            <button className="btn primary" onClick={() => setTemplateOpen(true)}>
              <I n="sparkles" s={12}/> Start from a template
            </button>
            <button className="btn" onClick={addTier}><I n="plus" s={12}/> Add a tier</button>
          </div>
        </div>
      )}

      {/* Import-mode placeholder */}
      {mode === 'document' && tiers.length === 0 && (
        <div className="pb-empty">
          <div className="glyph">
            <svg viewBox="0 0 96 96">
              <path d="M20 14h40l20 20v48H20z" fill="var(--accent-soft)" stroke="var(--accent)" strokeWidth="1.5"/>
              <path d="M60 14v20h20" fill="none" stroke="var(--accent)" strokeWidth="1.5"/>
              <path d="M34 50h28M34 60h28M34 70h20" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </div>
          <h2>Upload your existing policy document</h2>
          <div className="s">PDF or Word. Our AI extracts benefits, caps, and conditions, then you review and apply to the canvas.</div>
          <div className="ctas">
            <button className="btn primary" onClick={() => setImportOpen(true)}><I n="upload" s={12}/> Choose file</button>
            <button className="btn" onClick={() => setMode('template')}>Use a template instead</button>
          </div>
        </div>
      )}

      {/* Canvas */}
      {tiers.length > 0 && (
        <div className="pb-canvas">
          {/* Left sidebar */}
          <div className="pb-cat-sidebar">
            {CATEGORIES.map(cat => {
              const isCol = collapsed[cat.id];
              return (
                <div key={cat.id} className={`pb-cat cat-${cat.id}${isCol ? ' collapsed' : ''}`}>
                  <div className="pb-cat-hd" onClick={() => setCollapsed(c => ({ ...c, [cat.id]: !c[cat.id] }))}>
                    <I n="chevD" s={12} className="chev"/>
                    <span style={{ flex: 1 }}>{cat.t}</span>
                    <span className="count">{cat.benefits.length}</span>
                  </div>
                  {!isCol && cat.benefits.map(b => (
                    <div key={b.k} className="pb-benefit-row">
                      <I n="info" s={11} className="info" title={b.tip}/>
                      <span className="lbl">{b.lbl}</span>
                    </div>
                  ))}
                  {!isCol && (
                    <div className="pb-add-custom">+ Add custom benefit</div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Tier columns */}
          <div className="pb-tiers">
            {tiers.map((tier, i) => (
              <TierColumn
                key={tier.id}
                tier={tier}
                categories={CATEGORIES}
                collapsed={collapsed}
                currency={currency}
                onRename={(name) => updateTier(tier.id, { name })}
                onModeChange={(m) => updateTier(tier.id, { mode: m })}
                onLumpChange={(v) => updateTier(tier.id, { lump: v })}
                onColorChange={(c) => updateTier(tier.id, { color: c })}
                onOpenRules={() => setRulesDrawerFor(tier.id)}
                onBenefitChange={(bKey, patch) => updateBenefit(tier.id, bKey, patch)}
                tierCount={tiers.length}
                maxTotal={Math.max(...tiers.map(t => t.lump || 0)) || 1}
              />
            ))}
            <div className="pb-tier add-tier" onClick={addTier}>
              <div style={{ textAlign: 'center' }}>
                <div className="plus">+</div>
                <div>Add tier</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {tiers.length > 0 && (
        <div className="pb-priority-hint">
          <strong>Tiers are evaluated left to right.</strong> The first matching tier wins.
          <span className="btn-lnk">Reorder tiers →</span>
        </div>
      )}

      {/* Tier rules drawer */}
      {rulesDrawerFor && (() => {
        const tier = tiers.find(t => t.id === rulesDrawerFor);
        return tier ? (
          <RulesDrawer
            tier={tier}
            allTiers={tiers}
            onChange={(targeting) => updateTier(tier.id, { targeting })}
            onClose={() => setRulesDrawerFor(null)}
          />
        ) : null;
      })()}

      {/* Import flow */}
      {importOpen && (
        <ImportFlow
          tiers={tiers.length > 0 ? tiers : tiersForTemplate('standard')}
          onClose={() => setImportOpen(false)}
          onApply={() => {
            if (tiers.length === 0) setTiers(tiersForTemplate('standard'));
            setImportOpen(false);
            setSavedAt(Date.now());
          }}
        />
      )}

      {/* Market context sidebar */}
      {ctxOpen && (
        <ContextSidebar
          focusedBenefit={focusedBenefit}
          focusedTier={focusedTierId ? tiers.find(t => t.id === focusedTierId) : (tiers[0] || null)}
          tiers={tiers}
          currency={currency}
          onClose={() => setCtxOpen(false)}
          onApplyMedian={(amount) => {
            const tId = focusedTierId || tiers[0]?.id;
            if (tId && focusedBenefit) updateBenefit(tId, focusedBenefit, { amount, covered: true, value_type: 'currency' });
          }}
        />
      )}

      {/* Template picker */}
      {templateOpen && (
        <div className="pb-modal-bd" onClick={() => setTemplateOpen(false)}>
          <div className="pb-modal" onClick={(e) => e.stopPropagation()}>
            <div className="pb-modal-hd">
              <I n="sparkles" s={16}/>
              <div className="t">Choose a template</div>
              <button className="x" onClick={() => setTemplateOpen(false)}><I n="x" s={14}/></button>
            </div>
            <div className="pb-modal-bd-content">
              <div style={{ fontSize: 13, color: 'var(--text-2)', marginBottom: 16 }}>
                Pick a starting point. You can fully customise every tier and benefit after applying.
              </div>
              <div className="pb-templates">
                {TEMPLATES.map(tpl => (
                  <button key={tpl.id} className="pb-template" onClick={() => applyTemplate(tpl)}>
                    <div className="ico">{tpl.ico}</div>
                    <div className="t">{tpl.t}</div>
                    <div className="s">{tpl.s}</div>
                    <div className="tier-chips">{tpl.tiers.map(t => <span key={t}>{t}</span>)}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Tier column ───────────────────────────────────────────────────
function TierColumn({ tier, categories, collapsed, currency, onRename, onModeChange, onLumpChange, onColorChange, onOpenRules, onBenefitChange, maxTotal }) {
  const isLump = tier.mode === 'lump';
  // Total: sum of currency benefits annualised, or lump
  const total = useMemo(() => {
    if (isLump) return tier.lump;
    let sum = 0;
    categories.forEach(cat => cat.benefits.forEach(b => {
      const v = tier.benefits[b.k];
      if (!v || !v.covered || v.value_type !== 'currency' || !v.amount) return;
      let annual = v.amount;
      if (v.freq === 'monthly') annual *= 12;
      sum += annual;
    }));
    return sum;
  }, [tier, categories, isLump]);

  const cur = CUR_SYM[currency];
  const fmt = (n) => cur + (n || 0).toLocaleString();
  const pct = Math.round((total / maxTotal) * 100);

  return (
    <div className="pb-tier" style={{ '--tier-color': tier.color }}>
      <div className="pb-tier-hd">
        <div className="name-row">
          <div className="swatch" title="Click to change tier color"/>
          <input className="name" value={tier.name} onChange={(e) => onRename(e.target.value)}/>
          <button className="menu" title="Tier actions">⋯</button>
        </div>
        <div className="emp-count">
          <I n="users" s={11}/>
          {tier.emp ? `${tier.emp} employee${tier.emp > 1 ? 's' : ''}` : '0 employees'}
        </div>
        <div className="targeting" onClick={onOpenRules} title="Click to edit targeting rules">
          <I n="filter" s={11} className="icon"/>
          <span className="lbl">{targetingSummary(tier.targeting)}</span>
          <I n="chevR" s={10}/>
        </div>
        <div className="pb-budget-toggle">
          <button className={tier.mode === 'lump' ? 'active' : ''} onClick={() => onModeChange('lump')}>Lump sum</button>
          <button className={tier.mode === 'caps' ? 'active' : ''} onClick={() => onModeChange('caps')}>Category caps</button>
        </div>
        {isLump && (
          <div className="pb-lump-input">
            <span className="lbl">Budget</span>
            <input type="number" value={tier.lump} onChange={(e) => onLumpChange(Number(e.target.value))}/>
            <span className="cur">{cur}/yr</span>
          </div>
        )}
      </div>

      {categories.map(cat => {
        if (collapsed[cat.id]) return <div key={cat.id} style={{ height: 41 }}/>;
        return (
          <React.Fragment key={cat.id}>
            <div style={{ background: 'var(--surface-2)', height: 41, borderTop: '1px solid var(--divider)' }}/>
            {cat.benefits.map(b => (
              <Cell key={b.k} bk={b.k} v={tier.benefits[b.k]} lump={isLump}
                    onChange={(patch) => onBenefitChange(b.k, patch)} cur={cur}/>
            ))}
            <div className="pb-add-custom" style={{ height: 36, opacity: 0 }}>·</div>
          </React.Fragment>
        );
      })}

      <div className="pb-tier-total">
        <div className="row">
          <span className="label">{isLump ? 'Lump-sum budget' : 'Est. annual cost'}</span>
          <span className="v">{fmt(total)}</span>
        </div>
        <div className="compare">
          vs other tiers
          <span className="bar"><div style={{ width: pct + '%' }}/></span>
          {pct}%
        </div>
      </div>
    </div>
  );
}

// ── Cell ──────────────────────────────────────────────────────────
function Cell({ bk, v, lump, onChange, cur }) {
  if (!v) return <div className="pb-cell"/>;
  if (lump) {
    const inc = v.lump_inc || (v.covered ? 'included' : 'excluded');
    const next = inc === 'included' ? 'optional' : inc === 'optional' ? 'excluded' : 'included';
    return (
      <div className="pb-cell lump-mode">
        <div className={`pb-lump-pill ${inc}`} onClick={() => onChange({ lump_inc: next })}>
          {inc === 'included' && <><I n="check" s={10}/> Included</>}
          {inc === 'optional' && <><I n="dot" s={10}/> Optional</>}
          {inc === 'excluded' && <><I n="x" s={10}/> Excluded</>}
        </div>
      </div>
    );
  }
  return (
    <div className={`pb-cell${v.covered ? '' : ' not-covered'}`}>
      <button
        className={`pb-cov ${v.covered ? 'on' : 'off'}`}
        onClick={() => onChange({ covered: !v.covered })}
        title={v.covered ? 'Covered — click to exclude' : 'Not covered — click to include'}
      >
        {v.covered ? '✓' : '—'}
      </button>
      {v.covered && (
        <>
          <select className="pb-value-type" value={v.value_type}
                  onChange={(e) => onChange({ value_type: e.target.value })}
                  onClick={(e) => e.stopPropagation()}>
            {VAL_OPTS.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
          </select>
          {v.value_type === 'currency' && (
            <>
              <div className="pb-amt">
                <input type="number" value={v.amount}
                       onChange={(e) => onChange({ amount: Number(e.target.value) })}/>
                <span className="cur">{cur}</span>
              </div>
              <select className="pb-freq" value={v.freq}
                      onChange={(e) => onChange({ freq: e.target.value })}>
                {FREQ_OPTS.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
              </select>
            </>
          )}
          {v.value_type === 'percentage' && (
            <div className="pb-amt">
              <input type="number" value={v.amount}
                     onChange={(e) => onChange({ amount: Number(e.target.value) })}/>
              <span className="pct">%</span>
            </div>
          )}
          {v.value_type === 'text' && (
            <div className="pb-amt">
              <input type="number" value={v.amount}
                     onChange={(e) => onChange({ amount: Number(e.target.value) })}/>
              <span className="cur">days/trips</span>
            </div>
          )}
          {v.value_type === 'none' && (
            <span style={{ flex: 1, fontSize: 11.5, color: 'var(--text-3)' }}>Service / no amount</span>
          )}
          {v.cap && <span className="pb-badge cap" title="A cap rule is attached to this benefit">CAP</span>}
          {v.conditions && <span className="pb-badge cond" title="Conditional on family status / type">IF</span>}
        </>
      )}
      <button className="edit-ico" title="Open full configuration"><I n="edit" s={11}/></button>
    </div>
  );
}

// ── Tier Rules Drawer ─────────────────────────────────────────────
function RulesDrawer({ tier, allTiers, onChange, onClose }) {
  const tg = tier.targeting;
  const [local, setLocal] = useState({
    level: tg.level || [], type: tg.type || [], family: tg.family || []
  });
  const toggle = (axis, v) => setLocal(L => ({
    ...L, [axis]: L[axis].includes(v) ? L[axis].filter(x => x !== v) : [...L[axis], v]
  }));

  // Conflict: any OTHER tier shares all 3 axes intersecting?
  const conflict = allTiers.find(t => t.id !== tier.id &&
    t.targeting.level.some(l => local.level.includes(l)) &&
    t.targeting.type.some(tp => local.type.includes(tp)) &&
    t.targeting.family.some(f => local.family.includes(f)));

  const LEVELS = Object.entries(LEVEL_LBL);
  const TYPES = [
    ['long_term', 'Long-term assignment (>12 months)'],
    ['short_term', 'Short-term assignment (3–12 months)'],
    ['permanent', 'Permanent transfer'],
    ['commuter', 'Cross-border commuter'],
    ['extended_business_trip', 'Extended business trip (<3 months)'],
  ];
  const FAMILY = [
    ['single', 'Single / No dependents'],
    ['married', 'Married / Partner (no dependents)'],
    ['accompanied_family', 'With accompanying dependents'],
  ];

  const save = () => { onChange(local); onClose(); };

  return (
    <>
      <div className="pb-drawer-bd" onClick={onClose}/>
      <aside className="pb-drawer">
        <div className="pb-drawer-hd">
          <div className="glyph"><I n="filter" s={16}/></div>
          <div style={{ flex: 1 }}>
            <div className="ttl">{tier.name} · targeting rules</div>
            <div className="sub">Define who lands in this tier. Multi-select across the three axes — an employee matching <strong>all three</strong> is assigned.</div>
          </div>
          <button className="x" onClick={onClose}><I n="x" s={14}/></button>
        </div>

        <div className="pb-drawer-body">
          <div className="pb-axis">
            <div className="axis-lbl">Employee level</div>
            <div className="pb-checks">
              {LEVELS.map(([v, l]) => (
                <label key={v} className={`pb-check${local.level.includes(v) ? ' on' : ''}`}
                       onClick={() => toggle('level', v)}>
                  <input type="checkbox" readOnly checked={local.level.includes(v)}/>
                  <span className="lbl">{l}{v === 'manager' ? ' / Senior IC' : v === 'vp' ? ' / Head of' : v === 'c_suite' ? ' / Executive' : ''}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="pb-axis">
            <div className="axis-lbl">Assignment type</div>
            <div className="pb-checks">
              {TYPES.map(([v, l]) => (
                <label key={v} className={`pb-check${local.type.includes(v) ? ' on' : ''}`}
                       onClick={() => toggle('type', v)}>
                  <input type="checkbox" readOnly checked={local.type.includes(v)}/>
                  <span className="lbl">{l}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="pb-axis">
            <div className="axis-lbl">Family status</div>
            <div className="pb-checks">
              {FAMILY.map(([v, l]) => (
                <label key={v} className={`pb-check${local.family.includes(v) ? ' on' : ''}`}
                       onClick={() => toggle('family', v)}>
                  <input type="checkbox" readOnly checked={local.family.includes(v)}/>
                  <span className="lbl">{l}</span>
                </label>
              ))}
            </div>
          </div>

          {conflict && (
            <div className="pb-conflict">
              <strong>⚠ Overlap detected with “{conflict.name}”.</strong> An employee matching these conditions would be assigned to the first matching tier (left-to-right priority). Drag to reorder tiers to set priority, or refine the rules to remove the overlap.
            </div>
          )}
        </div>

        <div className="pb-drawer-foot">
          <button onClick={onClose}>Cancel</button>
          <div className="spc"/>
          <button className="primary" onClick={save}>Save rules</button>
        </div>
      </aside>
    </>
  );
}

// ── time helper ────────────────────────────────────────────────
function timeAgo(ts) {
  if (!ts) return '—';
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 5) return 'just now';
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

// ── PDF Import Flow (Prompt 3) ─────────────────────────────────────
const STAGES = [
  { id: 'uploaded',       lbl: 'Uploading document…',     pct: 10 },
  { id: 'text_extracted', lbl: 'Reading document text…',  pct: 30 },
  { id: 'classified',     lbl: 'Identifying policy type…', pct: 50 },
  { id: 'normalized',     lbl: 'Extracting benefit rules…', pct: 75 },
  { id: 'review_required', lbl: 'Extraction complete — review needed', pct: 95 },
];
const MOCK_LOG = [
  '✓ Document classified as: Assignment Policy',
  '✓ Policy scope: Long-term assignment + Permanent transfer',
  '✓ Currency detected: EUR',
  '✓ Tiers identified: 3 (Manager / Director / VP)',
  '✓ 24 benefit rules extracted',
  '✓ 18 conditions parsed',
  '✓ 6 jurisdiction overrides found',
];
const MOCK_RULES = [
  { id: 'r1', category: 'compensation', cat_lbl: 'Compensation', confidence: 96, nm: 'Host country housing cap', val: '€2,500/mo (Tier: Manager)', cond: 'Long-term assignment only', assign_to: [0], decision: 'pending' },
  { id: 'r2', category: 'compensation', cat_lbl: 'Compensation', confidence: 94, nm: 'Host country housing cap', val: '€3,800/mo (Tier: Director)', cond: 'Long-term assignment only', assign_to: [1], decision: 'pending' },
  { id: 'r3', category: 'compensation', cat_lbl: 'Compensation', confidence: 91, nm: 'Mobility premium',         val: '15% of base salary',     cond: 'Director level and above', assign_to: [1, 2], decision: 'pending' },
  { id: 'r4', category: 'relocation',  cat_lbl: 'Relocation',   confidence: 88, nm: 'Relocation allowance',      val: '€8,000 one-time',         cond: 'Assignee + partner',       assign_to: [0, 1], decision: 'pending' },
  { id: 'r5', category: 'family',      cat_lbl: 'Family',       confidence: 87, nm: 'Child education support',   val: '€12,000/yr per child',    cond: 'With accompanying dependents only', assign_to: [0, 1, 2], decision: 'pending' },
  { id: 'r6', category: 'leave',       cat_lbl: 'Leave',         confidence: 72, nm: 'Home leave trips',          val: '2 trips/year',             cond: 'Long-term assignment',     assign_to: [0, 1], decision: 'pending', flag: true },
  { id: 'r7', category: 'tax',         cat_lbl: 'Tax',           confidence: 82, nm: 'Tax equalisation',          val: 'Provided',                 cond: 'Director and above',       assign_to: [1, 2], decision: 'pending' },
  { id: 'r8', category: 'relocation',  cat_lbl: 'Relocation',   confidence: 64, nm: 'Temporary living',           val: '€2,800/mo for up to 3 months', cond: 'On arrival',           assign_to: [0, 1, 2], decision: 'pending', flag: true },
];

function ImportFlow({ tiers, onClose, onApply }) {
  const [step, setStep] = useState(1);
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [stageIdx, setStageIdx] = useState(0);
  const [showLog, setShowLog] = useState(false);
  const [rules, setRules] = useState(MOCK_RULES);
  const [activeMark, setActiveMark] = useState(null);

  // Simulate processing
  useEffect(() => {
    if (step !== 2) return;
    setStageIdx(0);
    const ts = [];
    [1, 2, 3, 4].forEach((s, i) => {
      ts.push(setTimeout(() => setStageIdx(s), (i + 1) * 1100));
    });
    ts.push(setTimeout(() => setStep(3), 4800));
    return () => ts.forEach(clearTimeout);
  }, [step]);

  const stage = STAGES[stageIdx] || STAGES[0];
  const visibleLog = MOCK_LOG.slice(0, Math.min(MOCK_LOG.length, stageIdx + 2));

  const acceptedCount = rules.filter(r => r.decision === 'accepted').length;
  const rejectedCount = rules.filter(r => r.decision === 'rejected').length;
  const pendingCount = rules.length - acceptedCount - rejectedCount;
  const setDecision = (id, dec) => setRules(rs => rs.map(r => r.id === id ? { ...r, decision: dec } : r));
  const acceptAll = () => setRules(rs => rs.map(r => r.decision === 'pending' ? { ...r, decision: 'accepted' } : r));
  const acceptHighConf = () => setRules(rs => rs.map(r => r.decision === 'pending' && r.confidence >= 80 ? { ...r, decision: 'accepted' } : r));

  const toggleTier = (ruleId, tIdx) => setRules(rs => rs.map(r => {
    if (r.id !== ruleId) return r;
    const next = r.assign_to.includes(tIdx) ? r.assign_to.filter(x => x !== tIdx) : [...r.assign_to, tIdx];
    return { ...r, assign_to: next };
  }));

  const acceptedRules = rules.filter(r => r.decision === 'accepted');

  return (
    <div className="pb-import" onClick={(e) => { if (e.target.classList.contains('pb-import')) onClose(); }}>
      <div className="pb-import-shell">
        <div className="pb-import-hd">
          <I n="upload" s={16}/>
          <div className="t">Import policy from document</div>
          <button className="x" onClick={onClose}><I n="x" s={14}/></button>
        </div>

        <div className="pb-import-stepper">
          {['Upload', 'Processing', 'Review extraction', 'Map to policy'].map((lbl, i) => (
            <div key={lbl} className={`pb-import-step${step === i + 1 ? ' active' : ''}${step > i + 1 ? ' done' : ''}`}>
              <div className="num"><span>{i + 1}</span></div>
              {lbl}
            </div>
          ))}
        </div>

        <div className="pb-import-body">
          {step === 1 && (
            <div className="pb-import-step-body">
              {!file ? (
                <div className={`pb-dropzone${dragOver ? ' drag' : ''}`}
                     onClick={() => setFile({ nm: 'Aurora_Mobility_Policy_v2026.pdf', sz: '2.4 MB' })}
                     onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                     onDragLeave={() => setDragOver(false)}
                     onDrop={(e) => { e.preventDefault(); setDragOver(false); setFile({ nm: 'Aurora_Mobility_Policy_v2026.pdf', sz: '2.4 MB' }); }}>
                  <div className="ico"><I n="upload" s={22}/></div>
                  <div className="t">Drop your policy document here</div>
                  <div className="s">PDF or Word (.docx) · max 50 MB</div>
                  <div className="browse">Browse files</div>
                </div>
              ) : (
                <div className="pb-file-pill">
                  <div className="ico">PDF</div>
                  <div className="info">
                    <div className="nm">{file.nm}</div>
                    <div className="sz">{file.sz} · ready to extract</div>
                  </div>
                  <button className="rm" onClick={() => setFile(null)}><I n="x" s={14}/></button>
                </div>
              )}
              <div className="pb-hint-box">
                For best results, upload your full assignment policy document — not a summary sheet. The AI extracts benefit rules, caps, and conditions automatically.
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="pb-import-step-body">
              <div className="pb-processing">
                <div className="pb-processing-progress">
                  <div className="pb-processing-bar"><div style={{ width: stage.pct + '%' }}/></div>
                  <div className="pb-processing-stage">
                    <div className="spin"/>
                    {stage.lbl}
                  </div>
                </div>
                <div className="pb-processing-log-toggle" onClick={() => setShowLog(s => !s)}>
                  {showLog ? '▼ Hide details' : '▶ Show extraction details'}
                </div>
                {showLog && (
                  <div className="pb-processing-log">
                    {visibleLog.map((l, i) => <div key={i}>{l}</div>)}
                  </div>
                )}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="pb-review">
              <div className="pb-review-doc">
                <div className="doc-page-num">Page 4 of 12 · Source</div>
                <div className="doc-h">Section 3.2 — Host country housing</div>
                <p>
                  The Company shall provide a housing allowance for employees on long-term assignment. <mark className={activeMark === 'r1' ? 'active' : ''}>Tier 1 (Manager): up to €2,500 per month for furnished housing in the destination city.</mark> <mark className={activeMark === 'r2' ? 'active' : ''}>Tier 2 (Director): up to €3,800 per month, inclusive of utilities.</mark> Housing must be sourced from approved providers or independently with HR sign-off.
                </p>
                <div className="doc-h">Section 3.5 — Mobility incentive</div>
                <p>
                  <mark className={activeMark === 'r3' ? 'active' : ''}>Employees at Director level and above receive a mobility premium equal to 15% of base salary, paid quarterly for the duration of the assignment.</mark>
                </p>
                <div className="doc-h">Section 4 — Family support</div>
                <p>
                  <mark className={activeMark === 'r5' ? 'active' : ''}>Employees with accompanying dependents shall be eligible for child education support up to €12,000 per child per academic year</mark>, payable directly to the school or reimbursable on receipts.
                </p>
                <div className="doc-h">Section 5.1 — Leave</div>
                <p>
                  Long-term assignees are entitled to <mark className={activeMark === 'r6' ? 'active' : ''}>two return trips per calendar year</mark> to their origin country, in economy class.
                </p>
              </div>

              <div className="pb-review-rules">
                <div className="pb-review-stickytop">
                  <span className="stats"><strong>{rules.length}</strong> rules extracted · <strong>{acceptedCount}</strong> accepted · <strong>{rejectedCount}</strong> rejected · <strong>{pendingCount}</strong> pending</span>
                  <div className="spc"/>
                  <button onClick={acceptHighConf}>Accept high-confidence</button>
                  <button onClick={acceptAll}>Accept all</button>
                </div>
                {rules.map(r => {
                  const conf = r.confidence >= 90 ? 'high' : r.confidence >= 75 ? 'medium' : 'low';
                  return (
                    <div key={r.id}
                         className={`pb-rule-card ${r.decision}`}
                         onMouseEnter={() => setActiveMark(r.id)}
                         onMouseLeave={() => setActiveMark(null)}>
                      <div className="top">
                        <span className="cat-badge">{r.cat_lbl}</span>
                        <span className={`confidence ${conf}`}>{r.confidence}% confidence</span>
                        {r.flag && <span className="review-flag">⚠ Review</span>}
                      </div>
                      <div className="nm">{r.nm}</div>
                      <div className="val">{r.val}</div>
                      <div className="cond">{r.cond}</div>
                      <div className="actions">
                        <button className={`accept${r.decision === 'accepted' ? ' on' : ''}`} onClick={() => setDecision(r.id, r.decision === 'accepted' ? 'pending' : 'accepted')}>✓ Accept</button>
                        <button className={`reject${r.decision === 'rejected' ? ' on' : ''}`} onClick={() => setDecision(r.id, r.decision === 'rejected' ? 'pending' : 'rejected')}>✗ Reject</button>
                        <button>✎ Edit</button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="pb-import-step-body">
              <div className="pb-map">
                <div style={{ fontSize: 13, color: 'var(--text-2)', marginBottom: 14, lineHeight: 1.55 }}>
                  Assign each accepted rule to one or more tiers. Smart defaults applied based on extracted conditions — adjust freely.
                </div>
                {acceptedRules.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-3)', fontSize: 13 }}>
                    No accepted rules yet. Go back to Step 3 and accept at least one rule.
                  </div>
                ) : acceptedRules.map(r => (
                  <div key={r.id} className="pb-map-rule">
                    <div className="top">
                      <span className="cat-badge" style={{ background: 'var(--surface-3)', color: 'var(--text-2)', fontSize: 9.5, fontWeight: 700, textTransform: 'uppercase', padding: '2px 7px', borderRadius: 3, letterSpacing: '0.04em' }}>{r.cat_lbl}</span>
                    </div>
                    <div className="nm">{r.nm}</div>
                    <div className="meta">{r.val} · {r.cond}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 9, marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Assign to tier(s)</div>
                    <div className="pb-map-tiers">
                      {tiers.map((t, idx) => (
                        <button key={t.id} className={`pb-map-tier${r.assign_to.includes(idx) ? ' on' : ''}`}
                                onClick={() => toggleTier(r.id, idx)}>
                          {t.name}
                        </button>
                      ))}
                    </div>
                    {r.assign_to.length === 0 && (
                      <div className="conflict">No tier selected — this rule won't be applied. Pick at least one tier.</div>
                    )}
                  </div>
                ))}

                {acceptedRules.length > 0 && (
                  <div className="pb-map-summary">
                    About to apply <strong>{acceptedRules.filter(r => r.assign_to.length > 0).length}</strong> rule{acceptedRules.filter(r => r.assign_to.length > 0).length === 1 ? '' : 's'} across <strong>{new Set(acceptedRules.flatMap(r => r.assign_to)).size}</strong> tier{new Set(acceptedRules.flatMap(r => r.assign_to)).size === 1 ? '' : 's'}.
                    Where a benefit already has a value in the tier, the imported rule will overwrite it.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="pb-import-foot">
          {step > 1 && step < 4 && <button onClick={() => setStep(s => Math.max(1, s - 1))}>← Back</button>}
          {step === 1 && <span className="pb-import-foot-link" onClick={onClose}>Cancel</span>}
          <div className="spc"/>
          {step === 1 && (
            <button className="primary" disabled={!file} onClick={() => setStep(2)}>
              Start extraction →
            </button>
          )}
          {step === 2 && (
            <span className="pb-import-foot-link">Processing…</span>
          )}
          {step === 3 && (
            <>
              <span className="pb-import-foot-link" onClick={() => { acceptAll(); setStep(4); }}>Skip review — apply all</span>
              <button className="primary" disabled={acceptedCount === 0} onClick={() => setStep(4)}>
                Continue to mapping →
              </button>
            </>
          )}
          {step === 4 && (
            <button className="primary"
                    disabled={acceptedRules.filter(r => r.assign_to.length > 0).length === 0}
                    onClick={() => onApply(acceptedRules.filter(r => r.assign_to.length > 0))}>
              Apply to canvas →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

window.ImportFlow = ImportFlow;

// ── Market Context Sidebar (Prompt 4) ─────────────────────────────
const BENCH_COUNTRIES = [
  { code: 'DE', name: 'Germany',     flag: '🇩🇪' },
  { code: 'FR', name: 'France',      flag: '🇫🇷' },
  { code: 'GB', name: 'United Kingdom', flag: '🇬🇧' },
  { code: 'NO', name: 'Norway',      flag: '🇳🇴' },
  { code: 'US', name: 'United States', flag: '🇺🇸' },
  { code: 'CH', name: 'Switzerland', flag: '🇨🇭' },
  { code: 'SG', name: 'Singapore',   flag: '🇸🇬' },
  { code: 'JP', name: 'Japan',       flag: '🇯🇵' },
];

// Mock benchmark data per (benefit, country) - the values are illustrative
const BENCH_DATA = {
  host_housing_cap: {
    DE: { range: [1200, 3800], avg: 2100, providers: 7 },
    FR: { range: [1400, 4200], avg: 2400, providers: 9 },
    GB: { range: [1800, 5500], avg: 3000, providers: 12 },
    NO: { range: [1500, 4000], avg: 2300, providers: 5 },
    US: { range: [2000, 6000], avg: 3200, providers: 14 },
    CH: { range: [2400, 6500], avg: 3800, providers: 6 },
    SG: { range: [2200, 5800], avg: 3400, providers: 8 },
    JP: { range: [1800, 4800], avg: 2700, providers: 7 },
  },
  child_education_support: {
    DE: { range: [8000, 22000], avg: 13500, providers: 5 },
    FR: { range: [6000, 18000], avg: 11000, providers: 4 },
    GB: { range: [12000, 28000], avg: 18000, providers: 6 },
    NO: { range: [4000, 14000], avg: 8000, providers: 3 },
  },
  temporary_living: {
    DE: { range: [1400, 4500], avg: 2400, providers: 11 },
    FR: { range: [1600, 5000], avg: 2700, providers: 8 },
  },
};

const PROVIDERS_BY_COUNTRY = {
  DE: [
    { name: 'NestPick Berlin', verified: true, preferred: true,  rating: 4.7, reviews: 142, price: '€1,800–€3,200', tags: ['Furnished', 'Corporate', 'EN-speaking'] },
    { name: 'HousingAnywhere DE', verified: true, preferred: false, rating: 4.5, reviews: 89,  price: '€1,400–€2,800', tags: ['Online platform', 'EN-speaking'] },
    { name: 'Munich Relocation Hub', verified: true, preferred: false, rating: 4.6, reviews: 56,  price: '€1,900–€3,500', tags: ['Local agent', 'Family-focused'] },
    { name: 'Hamburg Living Co', verified: false, preferred: false, rating: 4.2, reviews: 24,  price: '€1,500–€2,400', tags: ['Hamburg only'] },
  ],
  FR: [
    { name: 'Paris Attitude',       verified: true, preferred: true,  rating: 4.8, reviews: 218, price: '€2,000–€4,000', tags: ['Furnished', 'Concierge'] },
    { name: 'Lodgis',                verified: true, preferred: false, rating: 4.6, reviews: 174, price: '€1,800–€3,800', tags: ['Long-term', 'Multilingual'] },
    { name: 'My Paris Agency',       verified: true, preferred: false, rating: 4.5, reviews: 67,  price: '€2,200–€4,500', tags: ['White-glove'] },
  ],
  NO: [
    { name: 'Stavanger Relocation Co.', verified: true, preferred: true, rating: 4.7, reviews: 87,  price: '€1,500–€3,400', tags: ['Local agent'] },
    { name: 'Bolig Direkte',         verified: true, preferred: false, rating: 4.4, reviews: 42,  price: '€1,200–€2,800', tags: ['Direct rentals'] },
  ],
};

const BENEFIT_LABELS = {
  host_housing_cap: 'Host country housing',
  child_education_support: 'Child education support',
  temporary_living: 'Temporary living',
  language_training: 'Language training',
};

function ContextSidebar({ focusedBenefit, focusedTier, tiers, currency, onClose, onApplyMedian }) {
  const [country, setCountry] = useState('DE');
  const [tab, setTab] = useState('bench');
  const cur = CUR_SYM[currency];
  const lbl = focusedBenefit ? BENEFIT_LABELS[focusedBenefit] || focusedBenefit : 'All benefits';
  const data = focusedBenefit ? (BENCH_DATA[focusedBenefit] || {})[country] : null;
  const providers = PROVIDERS_BY_COUNTRY[country] || [];

  const yourCap = useMemo(() => {
    if (!focusedTier || !focusedBenefit) return null;
    const v = focusedTier.benefits[focusedBenefit];
    return v && v.covered && v.value_type === 'currency' ? v.amount : null;
  }, [focusedTier, focusedBenefit]);

  // % bar widths for benchmark chart
  const widths = useMemo(() => {
    if (!data) return null;
    const max = Math.max(data.range[1], yourCap || 0) * 1.1;
    return {
      rangeStart: (data.range[0] / max) * 100,
      rangeEnd:   (data.range[1] / max) * 100,
      avg:        (data.avg / max) * 100,
      your:       yourCap ? (yourCap / max) * 100 : null,
    };
  }, [data, yourCap]);

  const verdict = useMemo(() => {
    if (!data || !yourCap) return null;
    if (yourCap > data.range[1]) return { tone: 'good',  txt: <>Your cap is <strong>above the market median</strong> — generous relative to the network.</> };
    if (yourCap < data.range[0]) return { tone: 'warn',  txt: <>Your cap is <strong>below the market floor</strong> — employees may struggle to find suitable housing within this budget.</> };
    if (yourCap < data.avg)      return { tone: '',      txt: <>Your cap is in range but <strong>below the platform average</strong> of {cur}{data.avg.toLocaleString()}.</> };
    return { tone: 'good', txt: <>Your cap is <strong>within typical range</strong>, slightly above the platform average. Comfortable.</> };
  }, [data, yourCap, cur]);

  return (
    <aside className="pb-ctx">
      <div className="pb-ctx-hd">
        <div className="t">Market context</div>
        <div className="s">{lbl}{focusedTier ? ` · ${focusedTier.name}` : ''}</div>
        <select value={country} onChange={(e) => setCountry(e.target.value)}>
          {BENCH_COUNTRIES.map(c => (
            <option key={c.code} value={c.code}>{c.flag} {c.name}</option>
          ))}
        </select>
      </div>

      <div className="pb-ctx-tabs">
        <button className={`pb-ctx-tab${tab === 'bench' ? ' active' : ''}`} onClick={() => setTab('bench')}>
          Benchmarks
        </button>
        <button className={`pb-ctx-tab${tab === 'providers' ? ' active' : ''}`} onClick={() => setTab('providers')}>
          Providers <span className="ct">{providers.length}</span>
        </button>
        <button className={`pb-ctx-tab${tab === 'historical' ? ' active' : ''}`} onClick={() => setTab('historical')}>
          History
        </button>
      </div>

      <div className="pb-ctx-body">
        {!focusedBenefit && (
          <div className="empty">
            <div className="glyph">👈</div>
            Hover over a benefit cell to see live market context for that line.
          </div>
        )}

        {focusedBenefit && tab === 'bench' && (
          data ? (
            <>
              <div className="pb-bench">
                <div className="nm">{lbl} — {BENCH_COUNTRIES.find(c => c.code === country)?.name}</div>
                <div className="row">
                  <span className="k">Market range</span>
                  <div className="bar">
                    <div className="fill range" style={{ left: widths.rangeStart + '%', width: (widths.rangeEnd - widths.rangeStart) + '%' }}/>
                  </div>
                  <span className="v">{cur}{data.range[0].toLocaleString()}–{data.range[1].toLocaleString()}</span>
                </div>
                <div className="row">
                  <span className="k">Avg on platform</span>
                  <div className="bar">
                    <div className="fill avg" style={{ left: widths.avg + '%', width: 0 }}/>
                  </div>
                  <span className="v">{cur}{data.avg.toLocaleString()}</span>
                </div>
                {yourCap != null && (
                  <div className="row">
                    <span className="k">Your cap</span>
                    <div className="bar">
                      <div className="fill your" style={{ left: widths.your + '%', width: 0 }}/>
                    </div>
                    <span className="v" style={{ color: 'var(--success)' }}>{cur}{yourCap.toLocaleString()}</span>
                  </div>
                )}
                {verdict && <div className={`verdict ${verdict.tone}`}>{verdict.txt}</div>}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--text-3)', lineHeight: 1.5, padding: '4px 2px' }}>
                Based on {data.providers} active suppliers + historical assignments in {BENCH_COUNTRIES.find(c => c.code === country)?.name}.
              </div>
            </>
          ) : (
            <div className="empty">
              <div className="glyph">📊</div>
              No benchmark data for <strong>{lbl}</strong> in {BENCH_COUNTRIES.find(c => c.code === country)?.name} yet. Showing platform averages where available.
            </div>
          )
        )}

        {focusedBenefit && tab === 'providers' && (
          providers.length === 0 ? (
            <div className="empty">
              <div className="glyph">🏢</div>
              No active providers found for this service in {BENCH_COUNTRIES.find(c => c.code === country)?.name}. Consider expanding coverage or adjusting the policy.
            </div>
          ) : providers.map(p => (
            <div key={p.name} className="pb-provider">
              <div className="top">
                <span className="nm">{p.name}</span>
                {p.verified && <span className="verified">VERIFIED</span>}
                {p.preferred && <span className="preferred">PREFERRED</span>}
              </div>
              <div className="meta">
                <span className="stars">{'★'.repeat(Math.round(p.rating))}</span>
                <span>{p.rating} ({p.reviews})</span>
                <span>·</span>
                <span className="price">{p.price}</span>
              </div>
              <div className="tags">
                {p.tags.map(t => <span key={t}>{t}</span>)}
              </div>
            </div>
          ))
        )}

        {focusedBenefit && tab === 'historical' && (
          <>
            <div className="pb-hist-sub">Selection rate</div>
            <div style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.55 }}>
              Of <strong>12 employees</strong> who had this benefit available in {BENCH_COUNTRIES.find(c => c.code === country)?.name}, <strong>9 (75%)</strong> used it.
            </div>
            <div className="pb-hist-sub">Actual spend distribution</div>
            <div className="pb-hist-row"><span className="k">Min</span> <span className="v">{cur}1,400/mo</span></div>
            <div className="pb-hist-row"><span className="k">Median</span> <span className="v">{cur}2,200/mo</span></div>
            <div className="pb-hist-row"><span className="k">Max</span> <span className="v">{cur}3,600/mo</span></div>
            {yourCap != null && (
              <div className="pb-hist-row"><span className="k">Your cap</span> <span className="v your">{cur}{yourCap.toLocaleString()} · covers ≈{Math.min(99, Math.round((yourCap / 3000) * 70))}% of cases</span></div>
            )}
            <div className="pb-hist-sub">Last 5 selections (anonymised)</div>
            {[
              { ref: 'Employee A', dest: 'Berlin',  type: 'Long-term', sel: '€2,100/mo' },
              { ref: 'Employee B', dest: 'Munich',  type: 'Long-term', sel: '€2,800/mo' },
              { ref: 'Employee C', dest: 'Hamburg', type: 'Permanent', sel: '€1,700/mo' },
              { ref: 'Employee D', dest: 'Berlin',  type: 'Long-term', sel: '€2,400/mo' },
              { ref: 'Employee E', dest: 'Frankfurt', type: 'Long-term', sel: '€2,200/mo' },
            ].map(s => (
              <div key={s.ref} style={{ fontSize: 11.5, color: 'var(--text-2)', padding: '5px 0', borderBottom: '1px solid var(--divider)' }}>
                <strong style={{ color: 'var(--text)' }}>{s.ref}</strong> · {s.dest} · {s.type} · <span style={{ fontFamily: 'var(--mono)', color: 'var(--text)' }}>{s.sel}</span>
              </div>
            ))}
          </>
        )}
      </div>

      {focusedBenefit && data && yourCap != null && (
        <div className="pb-ctx-foot">
          <button onClick={() => onApplyMedian(data.avg)}>
            Apply median ({cur}{data.avg.toLocaleString()}) to this tier
          </button>
          <div className="disclaimer">Benchmarks are indicative, sourced from the ReloPass network. Not legal or tax advice.</div>
        </div>
      )}
    </aside>
  );
}

window.ContextSidebar = ContextSidebar;

window.PolicyBuilderScreen = PolicyBuilderScreen;
})();
