// platform-s1p-profile.jsx — Rich Employee Profile (post-intake)
// 7 sections: Origin, Housing prefs, Spouse, Children, Pets, Temp housing, Financial.
// Reuses CountryCombo/Field/MultiChip/CommuteMap from platform-s1n-intake.jsx.
(function() {
const { useState, useMemo, useEffect, useRef } = React;
const I = window.PlatformIcon;

// ── Demo data: post-intake state for Marc Bouchard (family scenario) ──
const SEED_PROFILE = {
  // Origin details (A)
  origin_housing_status: 'Renting',
  lease_end_date: '2026-08-31',
  has_break_clause: 'Yes',
  is_selling: null, sale_date: null,
  household_volume: '3-bed',
  vehicles_to_ship: ['1 car'],
  important_docs: ['Diplomas & certificates', 'Birth certificates', 'Marriage certificate'],

  // Housing prefs (B)
  intent_rent_or_buy: 'Rent',
  housing_type: 'Apartment',
  bedrooms_needed: 3,
  must_haves: ['Parking', 'Pets allowed', 'Close to international school'],
  neighborhood_priorities: { commute: 5, intl_school: 5, parks: 3, expat: 4, nightlife: 2, safety: 5, transit: 4 },
  monthly_budget_min: 1500,
  monthly_budget_max: 3000,
  policy_cap: 3500,

  // Spouse (C)
  spouse_employment: 'Working',
  spouse_sector: 'Technology',
  spouse_contract: 'Permanent',
  spouse_resigning: 'Not sure',
  spouse_lang_level: 'Beginner',
  spouse_wants_lang: 'Yes',
  spouse_right_to_work: 'No',
  spouse_needs_dep_visa: 'Yes',
  spouse_needs_work_permit: 'Yes',
  spouse_credentials_ok: 'Not sure',
  spouse_wants_credential_support: 'Yes',

  // Children (D) — keyed per id
  children_extra: {
    c1: { school_pref: 'International', lang: 'English', special_needs: 'No', curriculum: 'IB' },
    c2: { school_pref: 'International', lang: 'English', special_needs: 'No', curriculum: 'French' },
  },

  // Pets (E) — keyed per id
  pets_extra: {},

  // Temp housing (F)
  temp_needed: 'Yes',
  temp_duration: '1–3 months',
  temp_type: 'Serviced apartment',

  // Financial (G)
  dual_tax: 'Yes',
  has_corporate_tax_support: 'Yes',
  need_bank_account: 'Yes',
  need_fx_transfer: 'Yes',
  fx_amount_range: '€50k–100k',
};

// Edge-case profile seeds
function seedForEdge(edge) {
  if (edge === 'solo') {
    return {
      origin_housing_status: 'Renting', lease_end_date: '2026-08-15', has_break_clause: 'Yes',
      household_volume: '1-bed', vehicles_to_ship: ['None'],
      important_docs: ['Diplomas & certificates'],
      intent_rent_or_buy: 'Rent', housing_type: 'Apartment', bedrooms_needed: 1,
      must_haves: ['Elevator', 'Close to transit'],
      neighborhood_priorities: { commute: 5, parks: 3, expat: 4, nightlife: 4, safety: 4, transit: 5 },
      monthly_budget_min: 1000, monthly_budget_max: 1800, policy_cap: 2500,
      temp_needed: 'Yes', temp_duration: '1–2 weeks', temp_type: 'Serviced apartment',
      dual_tax: 'No', has_corporate_tax_support: 'No', need_bank_account: 'Yes', need_fx_transfer: 'No',
    };
  }
  if (edge === 'uk_jp_pet') {
    return { ...SEED_PROFILE,
      origin_housing_status: 'Renting', lease_end_date: '2026-08-31', has_break_clause: 'Yes',
      household_volume: '2-bed', vehicles_to_ship: ['None'],
      important_docs: ['Diplomas & certificates', 'Medical records'],
      bedrooms_needed: 2,
      must_haves: ['Pets allowed', 'Garden / outdoor space'],
      monthly_budget_min: 2500, monthly_budget_max: 5000, policy_cap: 6000,
      pets_extra: {
        pet1: { name: 'Hugo', age: 4, vaccinations_uptodate: 'Yes', eu_pet_passport: 'have', origin_country: 'GB' },
      },
    };
  }
  return SEED_PROFILE;
}

// Member tracking — we read the household from the intake wizard's preset
function getMembersForEdge(edge) {
  const preset = window.intakePresetForEdge ? window.intakePresetForEdge(edge === 'solo' ? 'solo' : edge === 'uk_jp_pet' ? 'uk_jp_pet' : 'family') : null;
  return preset?.members || [{ id: 'self', kind: 'self' }];
}

function computeAge(dob) {
  if (!dob) return null;
  const d = new Date(dob);
  if (isNaN(d.getTime())) return null;
  return Math.floor((Date.now() - d.getTime()) / (1000*60*60*24*365.25));
}

// ── Section completion scoring ──────────────────────────────────
const SECTION_FIELDS = {
  AY: ['full_name', 'nationality', 'passport_country', 'passport_expiry'],
  WP: ['job_title', 'contract_type', 'contract_start', 'office_address', 'work_pattern', 'salary_band'],
  A: ['origin_housing_status', 'household_volume', 'vehicles_to_ship', 'important_docs'],
  B: ['intent_rent_or_buy', 'housing_type', 'bedrooms_needed', 'must_haves', 'neighborhood_priorities', 'monthly_budget_max'],
  C: ['spouse_employment', 'spouse_lang_level', 'spouse_right_to_work'],
  D: 'children',           // special handling
  E: 'pets',                // special handling
  F: ['temp_needed'],
  G: ['has_corporate_tax_support', 'need_bank_account'],
};

function sectionState(id, profile, members) {
  if (id === 'D') {
    const kids = members.filter(m => m.kind === 'child');
    if (!kids.length) return 'na';
    const all = kids.every(c => profile.children_extra?.[c.id]?.school_pref);
    const some = kids.some(c => profile.children_extra?.[c.id]?.school_pref);
    return all ? 'complete' : some ? 'partial' : 'empty';
  }
  if (id === 'E') {
    const pets = members.filter(m => m.kind === 'pet');
    if (!pets.length) return 'na';
    const all = pets.every(p => profile.pets_extra?.[p.id]?.vaccinations_uptodate);
    const some = pets.some(p => profile.pets_extra?.[p.id]?.vaccinations_uptodate);
    return all ? 'complete' : some ? 'partial' : 'empty';
  }
  if (id === 'C') {
    const hasPartner = members.some(m => m.kind === 'partner');
    if (!hasPartner) return 'na';
  }
  const fields = SECTION_FIELDS[id];
  const filled = fields.filter(f => {
    const v = profile[f];
    if (v == null || v === '') return false;
    if (Array.isArray(v)) return v.length > 0;
    if (typeof v === 'object') return Object.values(v).some(x => x > 0);
    return true;
  });
  if (filled.length === fields.length) return 'complete';
  if (filled.length > 0) return 'partial';
  return 'empty';
}

// ── Star rating ──────────────────────────────────────────────────
function StarRating({ value, onChange, max = 5 }) {
  return (
    <span className="iw-stars">
      {Array.from({ length: max }).map((_, i) => (
        <span key={i} className={`iw-star${i < value ? ' filled' : ''}`}
              onClick={() => onChange(i + 1)}>★</span>
      ))}
    </span>
  );
}

// ── Section wrapper ──────────────────────────────────────────────
function Section({ id, marker, t, sub, urgent, urgentReason, state, est, unlocks, expanded, onToggle, children, sectionRef }) {
  const stateLbl = state === 'complete' ? '✓ Complete' : state === 'partial' ? 'In progress' : state === 'na' ? 'Skipped' : 'Not started';
  const stateCls = state === 'complete' ? 'complete' : state === 'partial' ? 'partial' : '';
  return (
    <div className={`rp-section${expanded ? ' expanded' : ''}${urgent ? ' urgent' : ''}${state === 'complete' ? ' complete' : ''}`}
         id={`rp-${id}`} ref={sectionRef}>
      <div className="rp-section-hd" onClick={onToggle}>
        <div className="marker">{marker}</div>
        <div className="body">
          <div className="t">
            {t}
            {urgent && <span className="urgency"><I n="alert" s={9}/> {urgentReason}</span>}
          </div>
          <div className="s">{sub}</div>
          {!expanded && unlocks && (
            <div className="rp-unlock">
              <I n="sparkles" s={10}/>
              Unlocks: <strong>{unlocks}</strong>
            </div>
          )}
        </div>
        <div className="meta">
          {est && <span className="est">~{est} min</span>}
          <span className={`hh-status ${stateCls}`} style={{ fontSize: 10.5 }}>{stateLbl}</span>
          <I n="chevD" s={14} className="chev"/>
        </div>
      </div>
      {expanded && (
        <div className="rp-section-bd">
          {children}
        </div>
      )}
    </div>
  );
}

// Map of section feature key → minimum tier required
const SECTION_TIER = {
  AY: 'basic',    // About you — basic
  WP: 'basic',    // Work & place — basic
  A: 'premium',   // Origin details — premium
  B: 'standard',  // Housing prefs — standard+
  C: 'standard',  // Spouse — standard (full track is premium)
  D: 'standard',  // Children
  E: 'standard',  // Pets
  F: 'standard',  // Temp housing
  G: 'premium',   // Financial & tax — premium
};
const TIER_LBL = { basic: 'Basic', standard: 'Standard', premium: 'Premium' };
const TIER_RANK = { basic: 0, standard: 1, premium: 2 };
const tierMeets = (cur, req) => TIER_RANK[cur] >= TIER_RANK[req];

// Phase 0 summary (from quick intake)
function phase0Summary(edge) {
  if (edge === 'solo') return { from: '🇫🇷 France', to: '🇳🇴 Norway', purpose: 'Employment', household: 'Just me', start: 'Within 6 weeks' };
  if (edge === 'uk_jp_pet') return { from: '🇬🇧 United Kingdom', to: '🇯🇵 Japan', purpose: 'Employment', household: 'Solo + 1 pet', start: 'Within 3 months' };
  return { from: '🇫🇷 France', to: '🇳🇴 Norway', purpose: 'Employment', household: 'Partner + 2 children', start: 'Within 6 weeks' };
}

// About You + Work & Place baseline data (collected during the quick-intake wizard)
function aboutYouSeed(edge) {
  if (edge === 'solo' || edge === 'family' || edge === 'large') {
    return {
      full_name: 'Marc Bouchard', nationality: 'FR', passport_country: 'FR',
      passport_expiry: '2030-04-12', email: 'marc.bouchard@aurora-energy.com',
    };
  }
  if (edge === 'uk_jp_pet') {
    return {
      full_name: 'Sarah Kim', nationality: 'GB', passport_country: 'GB',
      passport_expiry: '2031-08-22', email: 'sarah.kim@atlas-mfg.jp',
    };
  }
  return { full_name: '', nationality: '', passport_country: '', passport_expiry: '', email: '' };
}
function workSeed(edge) {
  if (edge === 'uk_jp_pet') {
    return {
      job_title: 'Engineering Manager', contract_type: 'Permanent', contract_start: '2026-09-15',
      office_address: '3-2-1 Marunouchi, Chiyoda-ku, Tokyo', work_pattern: 'Hybrid',
      commute_mins: 35, commute_mode: ['public_transit'], salary_band: '150–200k€',
    };
  }
  return {
    job_title: 'Senior Engineer', contract_type: 'Permanent', contract_start: '2026-09-15',
    office_address: 'Forusparken 2, 4031 Stavanger, Norway', work_pattern: 'Hybrid',
    commute_mins: 30, commute_mode: ['public_transit', 'walking'], salary_band: '100–150k€',
  };
}

function TierGate({ tier, required, children, requiredLabel }) {
  const ok = tierMeets(tier, required);
  if (ok) return children;
  return (
    <div className="tier-gate">
      <div className="tier-gate-content">{children}</div>
      <div className="tier-gate-overlay">
        <div className="tier-gate-card">
          <div className="lock">🔒</div>
          <div className="t">
            Available on
            <span className={`tier-badge${required === 'premium' ? ' premium' : ''}`}>{TIER_LBL[required]}</span>
          </div>
          <div className="s">Ask your HR team to upgrade your ReloPass plan to unlock {requiredLabel || 'this section'}.</div>
          <button className="cta">✨ Request upgrade</button>
        </div>
      </div>
    </div>
  );
}

// ── Main screen ───────────────────────────────────────────────────
function ProfileScreen({ edge = 'family', showNotes = false, tier = 'standard' }) {
  const [profile, setProfile] = useState(() => ({ ...seedForEdge(edge), ...aboutYouSeed(edge), ...workSeed(edge) }));
  const [members, setMembers] = useState(() => getMembersForEdge(edge));
  useEffect(() => {
    setProfile({ ...seedForEdge(edge), ...aboutYouSeed(edge), ...workSeed(edge) });
    setMembers(getMembersForEdge(edge));
  }, [edge]);

  const [expanded, setExpanded] = useState({ B: true }); // Housing prefs expanded by default for the demo
  const sectionRefs = useRef({});

  const set = (k, v) => setProfile(p => ({ ...p, [k]: v }));
  const toggle = (id) => setExpanded(e => ({ ...e, [id]: !e[id] }));
  const focusSection = (id) => {
    setExpanded(e => ({ ...e, [id]: true }));
    setTimeout(() => {
      sectionRefs.current[id]?.scrollIntoView({ block: 'start' });
    }, 50);
  };

  const partner = members.find(m => m.kind === 'partner');
  const children = members.filter(m => m.kind === 'child');
  const pets = members.filter(m => m.kind === 'pet');
  const intl = true; // for the profile demo we assume an international move

  const sectionsConfig = [
    { id: 'A',  t: 'Origin details',         sub: 'Build the outbound leg — lease, household volume, vehicles.', est: 2, unlocks: 'Estate agent or lease-break milestones' },
    { id: 'B',  t: 'Destination housing',    sub: 'Pre-filter your housing recommendations.',                     est: 3, unlocks: 'Housing shortlist with commute + neighborhood scoring' },
    { id: 'C',  t: 'Spouse / partner',       sub: 'Build your partner\'s parallel track.',                         est: 3, unlocks: 'Partner immigration + career services',
      hidden: !partner },
    { id: 'D',  t: 'Children',               sub: 'School preferences, language, special needs.',                  est: 2, unlocks: 'School search + enrollment deadlines',
      hidden: !children.length, urgent: !!children.length && new Date('2026-09-01') - Date.now() < 90 * 86400000, urgentReason: 'school deadline' },
    { id: 'E',  t: 'Pet relocation',         sub: 'Vaccinations, microchips, quarantine prep.',                    est: 3, unlocks: 'Pet transport providers + health-cert milestones',
      hidden: !pets.length, urgent: !!pets.length },
    { id: 'F',  t: 'Temporary housing',      sub: 'Where you stay between arrival and your permanent home.',       est: 1, unlocks: 'Arrival sequence + temp housing providers' },
    { id: 'G',  t: 'Financial & tax',        sub: 'Tax equalization, banking, FX transfers.',                       est: 2, unlocks: 'Tax advisor + banking services' },
  ];

  const visibleSections = sectionsConfig.filter(s => !s.hidden);

  const totalCompletion = useMemo(() => {
    const scored = visibleSections.map(s => {
      const st = sectionState(s.id, profile, members);
      return st === 'complete' ? 1 : st === 'partial' ? 0.5 : 0;
    });
    return Math.round((scored.reduce((a, b) => a + b, 0) / scored.length) * 100);
  }, [profile, members, visibleSections]);

  // Completion ring math
  const r = 32, c = 2 * Math.PI * r;
  const off = c * (1 - totalCompletion / 100);

  return (
    <div className="page wide iw">
      <div className="page-hd">
        <div className="page-eyebrow">Employee · /case/profile</div>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12 }}>
          <h1 className="page-h">Your profile &amp; preferences</h1>
          <div style={{ flex: 1 }}/>
          <button className="btn"><I n="download" s={12}/> Export data</button>
        </div>
        <div className="page-sub">Refine the details that personalise your roadmap. None of this blocks your roadmap — but each completed section unlocks smarter recommendations and adds milestones.</div>
      </div>

      {showNotes && (
        <div className="iw-note">
          <span className="pin">📌</span>
          <div>
            <strong>UX model · rich profile, progressive:</strong> not a re-run of the wizard, but a persistent editor with section-level completion and contextual urgency. Sections that aren't relevant to your household (no partner → Section C, no kids → Section D, no pets → Section E) are hidden entirely.
          </div>
        </div>
      )}

      {edge !== 'family' && (
        <div className="iw-edge-banner">
          <I n="info" s={14}/>
          <div>
            <strong>Edge case · </strong>
            {edge === 'solo' && 'Solo move (no partner, no children, no pets). Sections C/D/E are hidden — only the relevant 4 sections appear.'}
            {edge === 'uk_jp_pet' && 'UK → Japan with a Rottweiler. Pet section is auto-flagged urgent: Japan requires pet quarantine (6+ months pre-arrival prep).'}
          </div>
        </div>
      )}

      {/* Phase 0 summary — quick-intake answers, collapsed */}
      {(() => { const p0 = phase0Summary(edge); return (
        <div className="rp-phase0">
          <div className="check">✓</div>
          <div className="body">
            <div className="ttl">Phase 0 · Quick setup<span className="complete">Complete</span></div>
            <div className="summary">
              <span>{p0.from} → {p0.to}</span>
              <span>{p0.purpose}</span>
              <span><strong>{p0.household}</strong></span>
              <span>Start: {p0.start}</span>
            </div>
          </div>
          <span className="edit">Edit →</span>
        </div>
      ); })()}

      {/* Overall 5-segment progress bar */}
      {(() => {
        const SEGS = [
          { id: 'p0',   t: 'Quick setup',    done: true,  pct: 100 },
          { id: 'p1',   t: 'About you',      done: true,  pct: 100 },
          { id: 'p2',   t: 'Your people',    done: false, pct: visibleSections.find(s => s.id === 'C' || s.id === 'D' || s.id === 'E') ? Math.round(visibleSections.filter(s => ['C','D','E'].includes(s.id)).map(s => sectionState(s.id, profile, members) === 'complete' ? 1 : sectionState(s.id, profile, members) === 'partial' ? 0.5 : 0).reduce((a,b) => a+b, 0) / Math.max(1, visibleSections.filter(s => ['C','D','E'].includes(s.id)).length) * 100) : 100 },
          { id: 'p3',   t: 'Work & Place',   done: true,  pct: 100 },
          { id: 'p4',   t: 'What you need', done: false, pct: visibleSections.filter(s => ['A','B','F','G'].includes(s.id)).map(s => sectionState(s.id, profile, members) === 'complete' ? 1 : sectionState(s.id, profile, members) === 'partial' ? 0.5 : 0).reduce((a,b) => a+b, 0) / Math.max(1, visibleSections.filter(s => ['A','B','F','G'].includes(s.id)).length) * 100 },
        ];
        const overall = Math.round(SEGS.reduce((a, s) => a + s.pct, 0) / SEGS.length);
        return (
          <div className="intake-progress-overall">
            <span className="lbl">Intake progress</span>
            <div className="intake-segments">
              {SEGS.map(s => (
                <div key={s.id} className={`intake-seg${s.pct >= 100 ? ' complete' : ''}`} title={`${s.t} — ${Math.round(s.pct)}%`}>
                  <span className="seg-lbl">{s.t}</span>
                  <div className="fill" style={{ width: Math.min(100, s.pct) + '%' }}/>
                </div>
              ))}
            </div>
            <span className="pct">{overall}%</span>
          </div>
        );
      })()}

      <div className="rp-shell">
        {/* Side: completion + ToC */}
        <div className="rp-side">
          <div className="rp-completion">
            <div className="ring">
              <svg width="80" height="80" viewBox="0 0 80 80">
                <circle className="bg" cx="40" cy="40" r={r} strokeWidth="6"/>
                <circle className="fg" cx="40" cy="40" r={r} strokeWidth="6"
                        strokeDasharray={c} strokeDashoffset={off}/>
              </svg>
              <div className="pct">{totalCompletion}%</div>
            </div>
            <div className="t">Profile completion</div>
            <div className="s">{visibleSections.filter(s => sectionState(s.id, profile, members) === 'complete').length} of {visibleSections.length} sections complete.</div>
          </div>

          <div className="rp-toc">
            {visibleSections.map(s => {
              const st = sectionState(s.id, profile, members);
              return (
                <div key={s.id} className={`rp-toc-item ${st === 'complete' ? 'complete' : st === 'partial' ? 'partial' : ''}${expanded[s.id] ? ' active' : ''}`}
                     onClick={() => focusSection(s.id)}>
                  <div className="marker"/>
                  <span className="lbl">{s.t}</span>
                  <span className="ct">{s.id}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Main */}
        <div className="rp-main">
          {/* A — Origin */}
          {visibleSections.find(s => s.id === 'A') && (
            <TierGate tier={tier} required={SECTION_TIER.A} requiredLabel="origin details">
            <Section id="A" marker="A" t="Origin details" sub="Help us build the outbound leg of your roadmap."
                     est={2} unlocks="Estate agent or lease-break milestones"
                     state={sectionState('A', profile, members)}
                     expanded={!!expanded.A} onToggle={() => toggle('A')}
                     sectionRef={(r) => sectionRefs.current.A = r}>
              <div className="iw-grid">
                <Field label="Housing situation at origin">
                  <select className="iw-select" value={profile.origin_housing_status || ''}
                          onChange={(e) => set('origin_housing_status', e.target.value)}>
                    <option value="">Select…</option>
                    <option>Renting</option><option>Own (mortgage)</option><option>Own (no mortgage)</option>
                    <option>Living with family / employer</option>
                  </select>
                </Field>
                {profile.origin_housing_status === 'Renting' && (
                  <>
                    <Field label="Lease end date">
                      <input className="iw-input" type="date" value={profile.lease_end_date || ''}
                             onChange={(e) => set('lease_end_date', e.target.value)}/>
                    </Field>
                    <Field label="Break clause in your lease?">
                      <select className="iw-select" value={profile.has_break_clause || ''}
                              onChange={(e) => set('has_break_clause', e.target.value)}>
                        <option value="">Select…</option><option>Yes</option><option>No</option><option>Not sure</option>
                      </select>
                    </Field>
                  </>
                )}
                {(profile.origin_housing_status || '').startsWith('Own') && (
                  <>
                    <Field label="Planning to sell?">
                      <select className="iw-select" value={profile.is_selling || ''}
                              onChange={(e) => set('is_selling', e.target.value)}>
                        <option value="">Select…</option><option>Yes</option><option>No</option>
                      </select>
                    </Field>
                    {profile.is_selling === 'Yes' && (
                      <Field label="Expected sale completion (optional)">
                        <input className="iw-input" type="date" value={profile.sale_date || ''}
                               onChange={(e) => set('sale_date', e.target.value)}/>
                      </Field>
                    )}
                  </>
                )}
                <Field label="Current household volume"
                       why="Movers use this for the volume estimate that drives shipping quotes.">
                  <select className="iw-select" value={profile.household_volume || ''}
                          onChange={(e) => set('household_volume', e.target.value)}>
                    <option value="">Select…</option>
                    <option>Studio</option><option>1-bed</option><option>2-bed</option>
                    <option>3-bed</option><option>4-bed+</option>
                  </select>
                </Field>
                <Field label="Vehicles to ship internationally" className="full">
                  <MultiChip value={profile.vehicles_to_ship || []}
                    onChange={(v) => set('vehicles_to_ship', v)}
                    options={['None', '1 car', '2+ cars', 'Motorbike', 'Other']}/>
                </Field>
                <Field label="Important documents to relocate" className="full">
                  <MultiChip value={profile.important_docs || []}
                    onChange={(v) => set('important_docs', v)}
                    options={['Diplomas & certificates','Medical records','Birth certificates','Marriage certificate','Other']}/>
                </Field>
              </div>
            </Section>
            </TierGate>
          )}

          {/* B — Housing prefs */}
          {visibleSections.find(s => s.id === 'B') && (
            <TierGate tier={tier} required={SECTION_TIER.B} requiredLabel="housing preferences">
            <Section id="B" marker="B" t="Destination housing preferences"
                     sub="The more you tell us here, the sharper your shortlist."
                     est={3} unlocks="Housing shortlist with commute + neighborhood scoring"
                     state={sectionState('B', profile, members)}
                     expanded={!!expanded.B} onToggle={() => toggle('B')}
                     sectionRef={(r) => sectionRefs.current.B = r}>
              <div className="iw-grid">
                <Field label="Rent or buy?">
                  <select className="iw-select" value={profile.intent_rent_or_buy || ''}
                          onChange={(e) => set('intent_rent_or_buy', e.target.value)}>
                    <option>Rent</option><option>Buy</option><option>Not sure yet</option>
                  </select>
                </Field>
                <Field label="Housing type">
                  <select className="iw-select" value={profile.housing_type || ''}
                          onChange={(e) => set('housing_type', e.target.value)}>
                    <option>Apartment</option><option>House</option><option>Either</option>
                  </select>
                </Field>
                <Field label="Bedrooms"
                       hint={`Auto-suggested ${children.length + 1} based on your household — adjust if needed.`}>
                  <input className="iw-input" type="number" min="1" max="8"
                         value={profile.bedrooms_needed} onChange={(e) => set('bedrooms_needed', Number(e.target.value))}/>
                </Field>
                <Field label="Monthly housing budget">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <input className="iw-input" type="number" placeholder="min"
                           value={profile.monthly_budget_min || ''}
                           onChange={(e) => set('monthly_budget_min', Number(e.target.value))}
                           style={{ flex: 1 }}/>
                    <span style={{ color: 'var(--text-3)' }}>—</span>
                    <input className="iw-input" type="number" placeholder="max"
                           value={profile.monthly_budget_max || ''}
                           onChange={(e) => set('monthly_budget_max', Number(e.target.value))}
                           style={{ flex: 1 }}/>
                    <span style={{ color: 'var(--text-3)', fontSize: 12 }}>€/mo</span>
                  </div>
                  {profile.policy_cap && (
                    <div className="help">
                      <I n="info" s={10} style={{ verticalAlign: -1, marginRight: 3, color: 'var(--accent)' }}/>
                      <strong>Your company covers up to €{profile.policy_cap.toLocaleString()}/month.</strong>
                    </div>
                  )}
                </Field>
                <Field label="Must-haves (pick up to 5)" className="full">
                  <MultiChip value={profile.must_haves || []}
                    onChange={(v) => v.length <= 5 && set('must_haves', v)}
                    options={['Garden / outdoor space', 'Elevator', 'Parking', 'Accessibility features',
                              'Pets allowed', 'Quiet neighborhood', 'Close to international school',
                              'Co-working space']}/>
                </Field>

                <div className="full">
                  <div className="iw-field">
                    <label>Neighborhood priorities <span className="opt">(rate by importance)</span></label>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 6 }}>
                      {[
                        { id: 'commute',     lbl: 'Short commute to work' },
                        { id: 'intl_school', lbl: 'International school proximity', hidden: !children.length },
                        { id: 'parks',       lbl: 'Nature & parks' },
                        { id: 'expat',       lbl: 'Expat community' },
                        { id: 'nightlife',   lbl: 'Nightlife & culture' },
                        { id: 'safety',      lbl: 'Safety' },
                        { id: 'transit',     lbl: 'Public transit quality' },
                      ].filter(p => !p.hidden).map(p => (
                        <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <span style={{ flex: 1, fontSize: 12.5, color: 'var(--text-2)' }}>{p.lbl}</span>
                          <StarRating value={profile.neighborhood_priorities?.[p.id] || 0}
                                      onChange={(v) => set('neighborhood_priorities', {
                                        ...profile.neighborhood_priorities, [p.id]: v
                                      })}/>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="full">
                  <Field label="Commute intelligence — live preview"
                         hint="The radius reflects the commute settings you saved in Quick Intake Step 4. Drag the slider below to test alternatives.">
                    {window.CommuteMap && (
                      <window.CommuteMap maxMins={profile._commute_slider || 30} mode={['public_transit']}/>
                    )}
                    <div className="iw-slider-row" style={{ marginTop: 10 }}>
                      <input className="iw-slider" type="range" min="15" max="75" step="5"
                             value={profile._commute_slider || 30}
                             onChange={(e) => set('_commute_slider', Number(e.target.value))}/>
                      <span className="val">{profile._commute_slider || 30}m</span>
                    </div>
                  </Field>
                </div>
              </div>
            </Section>
            </TierGate>
          )}

          {/* C — Spouse */}
          {visibleSections.find(s => s.id === 'C') && (
            <TierGate tier={tier} required={SECTION_TIER.C} requiredLabel="partner full profile">
            <Section id="C" marker="C" t="Spouse / partner full profile"
                     sub={`Building ${partner?.name || 'your partner'}'s parallel relocation track.`}
                     est={3} unlocks="Partner immigration milestones + career services"
                     state={sectionState('C', profile, members)}
                     expanded={!!expanded.C} onToggle={() => toggle('C')}
                     sectionRef={(r) => sectionRefs.current.C = r}>
              <div className="iw-grid">
                <Field label="Employment status">
                  <select className="iw-select" value={profile.spouse_employment || ''}
                          onChange={(e) => set('spouse_employment', e.target.value)}>
                    <option value="">Select…</option>
                    <option>Working</option><option>Self-employed</option>
                    <option>Student</option><option>Not working</option>
                  </select>
                </Field>
                {(profile.spouse_employment === 'Working' || profile.spouse_employment === 'Self-employed') && (
                  <>
                    <Field label="Industry / sector">
                      <select className="iw-select" value={profile.spouse_sector || ''}
                              onChange={(e) => set('spouse_sector', e.target.value)}>
                        <option value="">Select…</option>
                        <option>Technology</option><option>Finance</option><option>Legal</option>
                        <option>Healthcare</option><option>Education</option><option>Creative</option><option>Other</option>
                      </select>
                    </Field>
                    <Field label="Current contract">
                      <select className="iw-select" value={profile.spouse_contract || ''}
                              onChange={(e) => set('spouse_contract', e.target.value)}>
                        <option value="">Select…</option>
                        <option>Permanent</option><option>Fixed-term</option><option>Freelance</option>
                      </select>
                    </Field>
                    <Field label="Resigning to follow you?"
                           why="If their current job is contingent on the move, we surface job-search and career-coaching services earlier.">
                      <select className="iw-select" value={profile.spouse_resigning || ''}
                              onChange={(e) => set('spouse_resigning', e.target.value)}>
                        <option value="">Select…</option><option>Yes</option><option>No</option><option>Not sure</option>
                      </select>
                    </Field>
                  </>
                )}
                <Field label="Language level at destination">
                  <select className="iw-select" value={profile.spouse_lang_level || ''}
                          onChange={(e) => set('spouse_lang_level', e.target.value)}>
                    <option value="">Select…</option>
                    <option>Fluent</option><option>Conversational</option><option>Basic</option><option>None</option>
                  </select>
                </Field>
                {(profile.spouse_lang_level === 'Basic' || profile.spouse_lang_level === 'None') && (
                  <Field label="Would they like language training?">
                    <select className="iw-select" value={profile.spouse_wants_lang || ''}
                            onChange={(e) => set('spouse_wants_lang', e.target.value)}>
                      <option value="">Select…</option><option>Yes</option><option>No</option>
                    </select>
                  </Field>
                )}
                <Field label="Right to work at destination?">
                  <select className="iw-select" value={profile.spouse_right_to_work || ''}
                          onChange={(e) => set('spouse_right_to_work', e.target.value)}>
                    <option value="">Select…</option><option>Yes</option><option>No</option><option>Not sure</option>
                  </select>
                </Field>
                {profile.spouse_right_to_work !== 'Yes' && (
                  <Field label="Need a dependent visa?">
                    <select className="iw-select" value={profile.spouse_needs_dep_visa || ''}
                            onChange={(e) => set('spouse_needs_dep_visa', e.target.value)}>
                      <option value="">Select…</option><option>Yes</option><option>No</option><option>Not sure</option>
                    </select>
                  </Field>
                )}
                <Field label="Are their professional credentials recognized at destination?" className="full">
                  <select className="iw-select" value={profile.spouse_credentials_ok || ''}
                          onChange={(e) => set('spouse_credentials_ok', e.target.value)}>
                    <option value="">Select…</option>
                    <option>Yes</option><option>No</option><option>Not sure</option><option>Not applicable</option>
                  </select>
                </Field>
              </div>
            </Section>
            </TierGate>
          )}

          {/* D — Children */}
          {visibleSections.find(s => s.id === 'D') && (
            <TierGate tier={tier} required={SECTION_TIER.D} requiredLabel="children's school preferences">
            <Section id="D" marker="D" t="Children details"
                     sub="One card per child. We use this for school search and enrollment timing."
                     est={2} unlocks="School search + enrollment deadlines"
                     urgent={true} urgentReason="Sep 1 enrollment"
                     state={sectionState('D', profile, members)}
                     expanded={!!expanded.D} onToggle={() => toggle('D')}
                     sectionRef={(r) => sectionRefs.current.D = r}>
              {children.map((c, i) => {
                const extra = profile.children_extra?.[c.id] || {};
                const setExtra = (k, v) => set('children_extra', {
                  ...profile.children_extra, [c.id]: { ...extra, [k]: v }
                });
                const age = computeAge(c.dob);
                return (
                  <div key={c.id} className="hh-sub">
                    <div className="hh-sub-hd">
                      <div className="ico" style={{ width: 22, height: 22, borderRadius: 5, background: 'rgba(31,142,139,0.14)', display: 'grid', placeItems: 'center', fontSize: 12 }}>🧒</div>
                      Child {i + 1} · {c.name || `Child ${i + 1}`}
                      {age != null && <span style={{ marginLeft: 8, fontWeight: 500, color: 'var(--text-3)' }}>({age}y)</span>}
                    </div>
                    <div className="iw-grid">
                      <Field label="School type">
                        <select className="iw-select" value={extra.school_pref || ''}
                                onChange={(e) => setExtra('school_pref', e.target.value)}>
                          <option value="">Select…</option>
                          <option>Public</option><option>Private</option>
                          <option>International</option><option>Bilingual</option><option>Not sure yet</option>
                        </select>
                      </Field>
                      <Field label="Language of instruction">
                        <select className="iw-select" value={extra.lang || ''}
                                onChange={(e) => setExtra('lang', e.target.value)}>
                          <option value="">Select…</option>
                          <option>Destination country language</option>
                          <option>English</option><option>French</option><option>German</option><option>Spanish</option><option>Other</option>
                        </select>
                      </Field>
                      <Field label="Current curriculum">
                        <select className="iw-select" value={extra.curriculum || ''}
                                onChange={(e) => setExtra('curriculum', e.target.value)}>
                          <option value="">Select…</option>
                          <option>National</option><option>IB</option><option>British</option>
                          <option>American</option><option>French</option><option>German</option><option>Other</option>
                        </select>
                      </Field>
                      <Field label="Any special educational needs?">
                        <select className="iw-select" value={extra.special_needs || ''}
                                onChange={(e) => setExtra('special_needs', e.target.value)}>
                          <option value="">Select…</option><option>Yes — tell us more</option><option>No</option>
                        </select>
                      </Field>
                    </div>
                  </div>
                );
              })}
              <div className="iw-warn info">
                <I n="info" s={13} className="ico"/>
                <div>
                  <strong>Roadmap milestone added:</strong> for each child, a <code style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>school_enrollment_deadline</code> milestone is computed from your contract start date.
                </div>
              </div>
            </Section>
            </TierGate>
          )}

          {/* E — Pets */}
          {visibleSections.find(s => s.id === 'E') && (
            <TierGate tier={tier} required={SECTION_TIER.E} requiredLabel="pet relocation details">
            <Section id="E" marker="E" t="Pet relocation details"
                     sub={`Health certs, microchips, quarantine prep for ${pets.length} pet${pets.length > 1 ? 's' : ''}.`}
                     est={3} unlocks="Pet transport providers + health-cert milestones"
                     urgent={edge === 'uk_jp_pet'} urgentReason="quarantine prep"
                     state={sectionState('E', profile, members)}
                     expanded={!!expanded.E} onToggle={() => toggle('E')}
                     sectionRef={(r) => sectionRefs.current.E = r}>
              {pets.map((p, i) => {
                const extra = profile.pets_extra?.[p.id] || {};
                const setExtra = (k, v) => set('pets_extra', {
                  ...profile.pets_extra, [p.id]: { ...extra, [k]: v }
                });
                return (
                  <div key={p.id} className="hh-sub">
                    <div className="hh-sub-hd">
                      <div className="ico" style={{ width: 22, height: 22, borderRadius: 5, background: 'rgba(217,140,40,0.18)', display: 'grid', placeItems: 'center', fontSize: 12 }}>🐕</div>
                      Pet {i + 1} · {p.pet_type}{p.breed ? ` (${p.breed})` : ''}
                    </div>
                    <div className="iw-grid">
                      <Field label="Name (optional)">
                        <input className="iw-input" value={extra.name || ''}
                               onChange={(e) => setExtra('name', e.target.value)} placeholder="e.g. Hugo"/>
                      </Field>
                      <Field label="Age (years)">
                        <input className="iw-input" type="number" min="0" max="25"
                               value={extra.age || ''} onChange={(e) => setExtra('age', Number(e.target.value))}/>
                      </Field>
                      <Field label="Vaccinations up to date?">
                        <select className="iw-select" value={extra.vaccinations_uptodate || ''}
                                onChange={(e) => setExtra('vaccinations_uptodate', e.target.value)}>
                          <option value="">Select…</option><option>Yes</option><option>No</option>
                        </select>
                      </Field>
                      <Field label="EU pet passport / health certificate">
                        <select className="iw-select" value={extra.eu_pet_passport || ''}
                                onChange={(e) => setExtra('eu_pet_passport', e.target.value)}>
                          <option value="">Select…</option>
                          <option value="have">Has one</option>
                          <option value="need">Need to get one</option>
                          <option value="unknown">Don't know</option>
                        </select>
                      </Field>
                    </div>
                  </div>
                );
              })}
              {edge === 'uk_jp_pet' && (
                <div className="iw-warn">
                  <I n="alert" s={13} className="ico"/>
                  <div>
                    <strong>Japan quarantine track active.</strong> Your roadmap includes 6 milestones over 6 months: microchipping → blood test → rabies vax → waiting period → import permit → arrival inspection. Earliest start: <strong>March 1, 2026</strong>.
                  </div>
                </div>
              )}
              {edge === 'uk_jp_pet' && (
                <div className="iw-warn">
                  <I n="alert" s={13} className="ico"/>
                  <div>
                    <strong>Restricted breed (Rottweiler)</strong> may face housing restrictions across many Tokyo neighborhoods. We're filtering your housing options for landlords known to accept large/restricted breeds.
                  </div>
                </div>
              )}
            </Section>
            </TierGate>
          )}

          {/* F — Temp housing */}
          {visibleSections.find(s => s.id === 'F') && (
            <TierGate tier={tier} required={SECTION_TIER.F} requiredLabel="temporary housing planning">
            <Section id="F" marker="F" t="Temporary housing on arrival"
                     sub="Where you stay before your permanent home."
                     est={1} unlocks="Arrival sequence + temp housing providers"
                     state={sectionState('F', profile, members)}
                     expanded={!!expanded.F} onToggle={() => toggle('F')}
                     sectionRef={(r) => sectionRefs.current.F = r}>
              <div className="iw-grid">
                <Field label="Need temporary accommodation when you arrive?">
                  <select className="iw-select" value={profile.temp_needed || ''}
                          onChange={(e) => set('temp_needed', e.target.value)}>
                    <option value="">Select…</option>
                    <option>Yes</option><option>No</option><option>Company is arranging it</option>
                  </select>
                </Field>
                {profile.temp_needed === 'Yes' && (
                  <>
                    <Field label="How long?">
                      <select className="iw-select" value={profile.temp_duration || ''}
                              onChange={(e) => set('temp_duration', e.target.value)}>
                        <option value="">Select…</option>
                        <option>1–2 weeks</option><option>Up to 1 month</option>
                        <option>1–3 months</option><option>3+ months</option><option>Not sure</option>
                      </select>
                    </Field>
                    <Field label="Type preference">
                      <select className="iw-select" value={profile.temp_type || ''}
                              onChange={(e) => set('temp_type', e.target.value)}>
                        <option value="">Select…</option>
                        <option>Serviced apartment</option><option>Corporate housing</option>
                        <option>Hotel</option><option>Extended stay</option><option>No preference</option>
                      </select>
                    </Field>
                  </>
                )}
              </div>
            </Section>
            </TierGate>
          )}

          {/* G — Financial */}
          {visibleSections.find(s => s.id === 'G') && (
            <TierGate tier={tier} required={SECTION_TIER.G} requiredLabel="financial & tax planning">
            <Section id="G" marker="G" t="Financial &amp; tax context"
                     sub="Surface tax & banking services at the right time."
                     est={2} unlocks="Tax advisor + banking services"
                     state={sectionState('G', profile, members)}
                     expanded={!!expanded.G} onToggle={() => toggle('G')}
                     sectionRef={(r) => sectionRefs.current.G = r}>
              <div className="iw-grid">
                <Field label="Will you owe taxes in two countries this year?">
                  <select className="iw-select" value={profile.dual_tax || ''}
                          onChange={(e) => set('dual_tax', e.target.value)}>
                    <option value="">Select…</option>
                    <option>Yes</option><option>Possibly</option><option>No</option><option>Not sure</option>
                  </select>
                </Field>
                <Field label="Does your company offer tax equalization?"
                       why="Activates the tax-equalization milestone and brings in a tax advisor automatically.">
                  <select className="iw-select" value={profile.has_corporate_tax_support || ''}
                          onChange={(e) => set('has_corporate_tax_support', e.target.value)}>
                    <option value="">Select…</option>
                    <option>Yes</option><option>No</option><option>Not sure</option>
                  </select>
                </Field>
                <Field label="Need to open a destination bank account?">
                  <select className="iw-select" value={profile.need_bank_account || ''}
                          onChange={(e) => set('need_bank_account', e.target.value)}>
                    <option value="">Select…</option>
                    <option>Yes</option><option>No</option><option>Company is handling it</option>
                  </select>
                </Field>
                <Field label="Need to transfer funds internationally?">
                  <select className="iw-select" value={profile.need_fx_transfer || ''}
                          onChange={(e) => set('need_fx_transfer', e.target.value)}>
                    <option value="">Select…</option>
                    <option>Yes</option><option>No</option>
                  </select>
                </Field>
                {profile.need_fx_transfer === 'Yes' && (
                  <Field label="Estimated amount">
                    <select className="iw-select" value={profile.fx_amount_range || ''}
                            onChange={(e) => set('fx_amount_range', e.target.value)}>
                      <option value="">Select…</option>
                      <option>&lt;€10k</option><option>€10k–50k</option>
                      <option>€50k–100k</option><option>€100k+</option>
                    </select>
                  </Field>
                )}
              </div>
            </Section>
            </TierGate>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Field/MultiChip — minimal duplicates here so this file is standalone ──
function Field({ label, required, optional, hint, why, children, className }) {
  const [whyOpen, setWhyOpen] = useState(false);
  return (
    <div className={`iw-field${className ? ' ' + className : ''}`}>
      <label>
        {label}
        {required && <span className="req">*</span>}
        {optional && <span className="opt">(optional)</span>}
        {why && (
          <span className="iw-why" onClick={() => setWhyOpen(o => !o)}>
            <I n="info" s={11}/> Why?
          </span>
        )}
      </label>
      {children}
      {whyOpen && why && <div className="iw-why-popout">{why}</div>}
      {hint && <div className="help">{hint}</div>}
    </div>
  );
}
function MultiChip({ value, onChange, options }) {
  const toggle = (v) => {
    if (value.includes(v)) onChange(value.filter(x => x !== v));
    else onChange([...value, v]);
  };
  return (
    <div className="iw-multi">
      {options.map(o => (
        <div key={typeof o === 'string' ? o : o.value}
             className={`iw-multi-chip${value.includes(typeof o === 'string' ? o : o.value) ? ' active' : ''}`}
             onClick={() => toggle(typeof o === 'string' ? o : o.value)}>
          {typeof o === 'string' ? o : o.label}
        </div>
      ))}
    </div>
  );
}

window.ProfileRichScreen = ProfileScreen;
})();
