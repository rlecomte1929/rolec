// platform-s1n-intake.jsx — Redesigned Employee Intake Wizard (5 steps)
// Quick-intake pass: ≤5 min, unblocks the roadmap. Household-builder pattern,
// commute map widget, HR pre-fill chips, mobile-responsive.
(function() {
const { useState, useEffect, useMemo, useRef } = React;
const I = window.PlatformIcon;

// ── Static option lists ────────────────────────────────────────────
const COUNTRIES = [
  { code: 'FR', name: 'France',         flag: '🇫🇷' },
  { code: 'DE', name: 'Germany',        flag: '🇩🇪' },
  { code: 'GB', name: 'United Kingdom', flag: '🇬🇧' },
  { code: 'NO', name: 'Norway',         flag: '🇳🇴' },
  { code: 'SE', name: 'Sweden',         flag: '🇸🇪' },
  { code: 'NL', name: 'Netherlands',    flag: '🇳🇱' },
  { code: 'BE', name: 'Belgium',        flag: '🇧🇪' },
  { code: 'IE', name: 'Ireland',        flag: '🇮🇪' },
  { code: 'CH', name: 'Switzerland',    flag: '🇨🇭' },
  { code: 'IT', name: 'Italy',          flag: '🇮🇹' },
  { code: 'ES', name: 'Spain',          flag: '🇪🇸' },
  { code: 'PT', name: 'Portugal',       flag: '🇵🇹' },
  { code: 'US', name: 'United States',  flag: '🇺🇸' },
  { code: 'CA', name: 'Canada',         flag: '🇨🇦' },
  { code: 'JP', name: 'Japan',          flag: '🇯🇵' },
  { code: 'KR', name: 'South Korea',    flag: '🇰🇷' },
  { code: 'CN', name: 'China',          flag: '🇨🇳' },
  { code: 'IN', name: 'India',          flag: '🇮🇳' },
  { code: 'SG', name: 'Singapore',      flag: '🇸🇬' },
  { code: 'AE', name: 'United Arab Emirates', flag: '🇦🇪' },
  { code: 'AU', name: 'Australia',      flag: '🇦🇺' },
  { code: 'BR', name: 'Brazil',         flag: '🇧🇷' },
  { code: 'MX', name: 'Mexico',         flag: '🇲🇽' },
];

const CITIES_BY_COUNTRY = {
  FR: ['Paris', 'Lyon', 'Marseille', 'Toulouse', 'Nice', 'Bordeaux'],
  DE: ['Berlin', 'Munich', 'Hamburg', 'Frankfurt', 'Cologne', 'Stuttgart'],
  GB: ['London', 'Manchester', 'Birmingham', 'Edinburgh', 'Glasgow'],
  NO: ['Oslo', 'Bergen', 'Stavanger', 'Trondheim'],
  US: ['New York', 'San Francisco', 'Los Angeles', 'Chicago', 'Boston', 'Austin'],
  CA: ['Toronto', 'Vancouver', 'Montreal', 'Calgary'],
  JP: ['Tokyo', 'Osaka', 'Kyoto', 'Yokohama', 'Nagoya'],
  IN: ['Mumbai', 'Bangalore', 'Delhi', 'Hyderabad', 'Pune'],
  SG: ['Singapore'],
  AE: ['Dubai', 'Abu Dhabi'],
  NL: ['Amsterdam', 'Rotterdam', 'The Hague', 'Utrecht', 'Eindhoven'],
  CH: ['Zurich', 'Geneva', 'Basel', 'Bern', 'Lausanne'],
  AU: ['Sydney', 'Melbourne', 'Brisbane', 'Perth'],
};

// Quarantine countries that auto-show pet quarantine info
const QUARANTINE_COUNTRIES = ['GB','AU','JP','NZ','SG','TW'];

// Restricted dog breeds (illustrative subset)
const RESTRICTED_BREEDS = ['Pit Bull', 'Pitbull', 'American Staffordshire', 'Amstaff', 'Rottweiler', 'Doberman', 'Dogo Argentino', 'Tosa Inu', 'Bull Terrier', 'Staffordshire Bull Terrier'];

// ── Searchable country combobox ───────────────────────────────────
function CountryCombo({ value, onChange, placeholder = 'Select a country', disabled }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [open]);
  const selected = COUNTRIES.find(c => c.code === value);
  const filtered = query
    ? COUNTRIES.filter(c => c.name.toLowerCase().includes(query.toLowerCase()) || c.code.toLowerCase().includes(query.toLowerCase()))
    : COUNTRIES;
  return (
    <div className="iw-combo" ref={ref}>
      <span className="left-g">{selected ? selected.flag : <I n="search" s={14}/>}</span>
      <input
        type="text"
        className="iw-combo-input"
        value={open ? query : (selected ? selected.name : '')}
        placeholder={placeholder}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => { if (!disabled) { setQuery(''); setOpen(true); } }}
        disabled={disabled}
        autoComplete="off"
      />
      <span className="right-g"><I n="chevD" s={11}/></span>
      {open && !disabled && (
        <div className="iw-combo-list">
          {filtered.length === 0
            ? <div style={{ padding: 10, color: 'var(--text-3)', fontSize: 12 }}>No match</div>
            : filtered.map(c => (
                <div key={c.code} className={`iw-combo-item${value === c.code ? ' hover' : ''}`}
                     onClick={() => { onChange(c.code); setOpen(false); setQuery(''); }}>
                  <span className="flag">{c.flag}</span>
                  <span>{c.name}</span>
                  <span className="code">{c.code}</span>
                </div>
              ))}
        </div>
      )}
    </div>
  );
}

// ── City combo (depends on country) ───────────────────────────────
function CityCombo({ country, value, onChange, placeholder = 'Select or type a city' }) {
  const opts = (country && CITIES_BY_COUNTRY[country]) || [];
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [open]);
  return (
    <div className="iw-combo" ref={ref}>
      <span className="left-g"><I n="pin" s={14}/></span>
      <input
        type="text"
        className="iw-combo-input"
        value={value || ''}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setOpen(true)}
      />
      <span className="right-g"><I n="chevD" s={11}/></span>
      {open && opts.length > 0 && (
        <div className="iw-combo-list">
          {opts.map(c => (
            <div key={c} className="iw-combo-item" onClick={() => { onChange(c); setOpen(false); }}>
              <span>{c}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── HR pre-fill chip + inline edit toggle ─────────────────────────
function PrefillChip({ locked, onUnlock }) {
  return (
    <span className={`iw-prefill ${locked ? 'locked' : ''}`} title="Set by your HR team">
      <I n="lock" s={9} className="ic"/>
      {locked ? 'HR pre-filled' : 'Editable'}
      {locked && (
        <span className="iw-prefill-toggle" onClick={(e) => { e.preventDefault(); onUnlock(); }}>
          Edit
        </span>
      )}
    </span>
  );
}

// ── Field helpers ────────────────────────────────────────────
function Field({ label, required, optional, hint, prefill, prefillLocked, onUnlock, children, why }) {
  const [whyOpen, setWhyOpen] = useState(false);
  return (
    <div className="iw-field">
      <label>
        {label}
        {required && <span className="req" title="Required field — you need to fill this before continuing.">*</span>}
        {optional && <span className="opt">(optional)</span>}
        {prefill && <PrefillChip locked={prefillLocked} onUnlock={onUnlock}/>}
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

// ── Choice card ────────────────────────────────────────────
function Choice({ ico, t, s, active, onClick }) {
  return (
    <button type="button" className={`iw-choice${active ? ' active' : ''}`} onClick={onClick}>
      {ico && <div className="ico">{ico}</div>}
      <div className="t">{t}</div>
      {s && <div className="s">{s}</div>}
      <div className="check"/>
    </button>
  );
}

// ── Multi-chip ────────────────────────────────────────────
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

// ── Compute age from DOB ──────────────────────────────────
function computeAge(dob) {
  if (!dob) return null;
  const d = new Date(dob);
  if (isNaN(d.getTime())) return null;
  const diff = Date.now() - d.getTime();
  const age = Math.floor(diff / (1000 * 60 * 60 * 24 * 365.25));
  return age >= 0 && age < 130 ? age : null;
}

// ── COMMUTE MAP (interactive SVG) ──────────────────────────────────
// Office at center. Neighborhoods scattered around with distance values.
// Radius circle grows with the slider value.
const NEIGHBORHOODS = [
  { id: 'n1', x: 50, y: 28, t_min: 8,  name: 'Vika' },
  { id: 'n2', x: 28, y: 35, t_min: 14, name: 'Frogner' },
  { id: 'n3', x: 70, y: 38, t_min: 16, name: 'Grünerløkka' },
  { id: 'n4', x: 38, y: 56, t_min: 22, name: 'Bygdøy' },
  { id: 'n5', x: 64, y: 60, t_min: 26, name: 'Tøyen' },
  { id: 'n6', x: 22, y: 70, t_min: 34, name: 'Bærum' },
  { id: 'n7', x: 78, y: 73, t_min: 42, name: 'Furuset' },
  { id: 'n8', x: 50, y: 82, t_min: 52, name: 'Sandvika' },
];

function CommuteMap({ maxMins, mode }) {
  // Visual radius is a function of the time radius (max 60min → 50% of viewport)
  const radius = Math.min(50, (maxMins / 60) * 50 + 5);
  const cx = 50, cy = 48; // office pin
  return (
    <div className="iw-map">
      <span className="iw-map-tag">
        <I n="pulse" s={9}/> live
      </span>
      <svg viewBox="0 0 100 100" className="iw-map-svg" preserveAspectRatio="xMidYMid meet" aria-hidden>
        {/* faint background grid */}
        {[20, 40, 60, 80].map(v => (
          <React.Fragment key={`g${v}`}>
            <line x1={v} y1={0} x2={v} y2={100} className="grid-line"/>
            <line x1={0} y1={v} x2={100} y2={v} className="grid-line"/>
          </React.Fragment>
        ))}

        {/* Neighborhoods */}
        {NEIGHBORHOODS.map(n => {
          const inside = n.t_min <= maxMins;
          return (
            <g key={n.id}>
              <circle cx={n.x} cy={n.y} r="4.2"
                      className={`neighborhood ${inside ? 'in' : 'out'}`}/>
              <text x={n.x} y={n.y + 9} className={`n-label ${inside ? 'in' : ''}`}>{n.name}</text>
            </g>
          );
        })}

        {/* Commute radius */}
        <circle cx={cx} cy={cy} r={radius} className="radius-ring"/>

        {/* Office pin */}
        <circle cx={cx} cy={cy} r="9" className="office-pin-ring"/>
        <circle cx={cx} cy={cy} r="3" className="office-pin"/>
        <text x={cx} y={cy - 5} className="office-label">Office</text>
      </svg>
      <div className="iw-map-cap">
        <strong>{NEIGHBORHOODS.filter(n => n.t_min <= maxMins).length} neighborhoods</strong> within {maxMins}m
        {mode && mode.length > 0 ? ` by ${mode.slice(0, 2).join('/')}` : ''}
      </div>
    </div>
  );
}

// ── Edge-case presets ────────────────────────────────────────────
function presetForEdge(edge) {
  const base = {
    origin_country: '', origin_city: '',
    dest_country: 'NO', dest_city: 'Oslo',                  // HR pre-filled by default
    target_date: '2026-09-01',
    purpose: 'Employment',
    full_name: '', nationality: '', passport_country: '', passport_expiry: '',
    email: 'marc.bouchard@aurora-energy.com',                 // HR pre-filled
    members: [{ id: 'self', kind: 'self' }],
    job_title: '', contract_start: '2026-09-15', contract_type: 'Permanent',
    office_address: '', work_pattern: 'Hybrid',
    commute_mins: 30, commute_mode: ['public_transit', 'walking'],
    salary_band: '',
    consent: false,
  };
  if (edge === 'solo') {
    return { ...base,
      origin_country: 'FR', origin_city: 'Paris',
      full_name: 'Marc Bouchard', nationality: 'FR', passport_country: 'FR',
      passport_expiry: '2030-04-12', job_title: 'Senior Engineer',
      office_address: 'Forusparken 2, 4031 Stavanger, Norway',
      dest_country: 'NO', dest_city: 'Stavanger',
      members: [{ id: 'self', kind: 'self' }],
    };
  }
  if (edge === 'family') {
    return { ...base,
      origin_country: 'FR', origin_city: 'Paris',
      full_name: 'Marc Bouchard', nationality: 'FR', passport_country: 'FR',
      passport_expiry: '2030-04-12', job_title: 'Senior Engineer',
      office_address: 'Forusparken 2, 4031 Stavanger, Norway',
      dest_country: 'NO', dest_city: 'Stavanger',
      members: [
        { id: 'self', kind: 'self' },
        { id: 'p1', kind: 'partner', name: 'Camille Bouchard', employment: 'Working',
          needs_work_permit: 'Yes', lang_level: 'Beginner' },
        { id: 'c1', kind: 'child', name: 'Léo', dob: '2017-04-12', school: 'International' },
        { id: 'c2', kind: 'child', name: 'Élise', dob: '2019-09-30', school: 'International' },
      ],
    };
  }
  if (edge === 'large') {
    return { ...base,
      origin_country: 'FR', origin_city: 'Paris',
      full_name: 'Marc Bouchard', nationality: 'FR', passport_country: 'FR',
      passport_expiry: '2030-04-12',
      members: [
        { id: 'self', kind: 'self' },
        { id: 'p1', kind: 'partner', name: 'Camille', employment: 'Working' },
        { id: 'c1', kind: 'child', name: 'Léo', dob: '2014-04-12', school: 'International' },
        { id: 'c2', kind: 'child', name: 'Élise', dob: '2016-09-30', school: 'International' },
        { id: 'c3', kind: 'child', name: 'Théo', dob: '2018-03-15', school: 'International' },
        { id: 'c4', kind: 'child', name: 'Lucie', dob: '2020-11-08', school: 'Public' },
        { id: 'pet1', kind: 'pet', pet_type: 'Dog', breed: 'Labrador', count: 1, rabies: 'Yes', microchipped: 'Yes' },
        { id: 'pet2', kind: 'pet', pet_type: 'Dog', breed: 'Pit Bull', count: 1, rabies: 'Yes', microchipped: 'Yes' },
      ],
    };
  }
  if (edge === 'uk_jp_pet') {
    return { ...base,
      origin_country: 'GB', origin_city: 'London',
      dest_country: 'JP', dest_city: 'Tokyo',
      full_name: 'Sarah Kim', nationality: 'GB', passport_country: 'GB',
      passport_expiry: '2031-08-22', job_title: 'Engineering Manager',
      office_address: '3-2-1 Marunouchi, Chiyoda-ku, Tokyo',
      email: 'sarah.kim@atlas-mfg.jp',
      members: [
        { id: 'self', kind: 'self' },
        { id: 'pet1', kind: 'pet', pet_type: 'Dog', breed: 'Rottweiler', count: 1,
          rabies: 'Yes', microchipped: 'Yes', age: 4 },
      ],
    };
  }
  return base;
}

// ── Member card components ─────────────────────────────────────────
function PartnerCard({ m, onChange, onRemove, international, expanded, onToggle }) {
  const complete = m.name && m.employment;
  const partial  = m.name || m.employment;
  return (
    <div className={`hh-card partner${expanded ? ' expanded' : ''}`}>
      <div className="hh-card-hd" onClick={onToggle}>
        <div className="ico">👤</div>
        <div className="body">
          <div className="t">Partner / Spouse{m.name ? ` · ${m.name}` : ''}</div>
          <div className="s">{m.employment || 'Tell us about your partner'}</div>
        </div>
        <div className="right">
          <span className={`hh-status${complete ? ' complete' : (partial ? ' partial' : '')}`}>
            {complete ? '✓ Complete' : partial ? 'In progress' : 'Not started'}
          </span>
          <I n="chevD" s={13} className="chev"/>
          <span className="rm" onClick={(e) => { e.stopPropagation(); onRemove(); }}><I n="x" s={13}/></span>
        </div>
      </div>
      {expanded && (
        <div className="hh-card-bd">
          <div className="iw-grid">
            <Field label="Full name" required>
              <input className="iw-input" value={m.name || ''}
                     onChange={(e) => onChange({ ...m, name: e.target.value })}
                     placeholder="e.g. Camille Bouchard"/>
            </Field>
            <Field label="Employment status">
              <select className="iw-select" value={m.employment || ''}
                      onChange={(e) => onChange({ ...m, employment: e.target.value })}>
                <option value="">Select…</option>
                <option>Working</option>
                <option>Not working</option>
                <option>Student</option>
              </select>
            </Field>
            {international && m.employment === 'Working' && (
              <Field label="Need a work permit at destination?"
                     why="If yes, we'll add the dependent work-permit track to your roadmap and surface partner-career services.">
                <select className="iw-select" value={m.needs_work_permit || ''}
                        onChange={(e) => onChange({ ...m, needs_work_permit: e.target.value })}>
                  <option value="">Select…</option>
                  <option>Yes</option>
                  <option>No</option>
                  <option>Not sure</option>
                </select>
              </Field>
            )}
            <Field label="Language level at destination">
              <select className="iw-select" value={m.lang_level || ''}
                      onChange={(e) => onChange({ ...m, lang_level: e.target.value })}>
                <option value="">Select…</option>
                <option>Fluent</option>
                <option>Conversational</option>
                <option>Beginner</option>
                <option>None</option>
              </select>
            </Field>
          </div>
        </div>
      )}
    </div>
  );
}

function ChildCard({ m, onChange, onRemove, expanded, onToggle, index }) {
  const age = computeAge(m.dob);
  const complete = m.name && m.dob && m.school;
  const partial  = m.name || m.dob || m.school;
  return (
    <div className={`hh-card child${expanded ? ' expanded' : ''}`}>
      <div className="hh-card-hd" onClick={onToggle}>
        <div className="ico">🧒</div>
        <div className="body">
          <div className="t">Child {index + 1}{m.name ? ` · ${m.name}` : ''}{age != null ? ` · ${age}y` : ''}</div>
          <div className="s">{m.school ? `${m.school} school` : 'Date of birth + school preference'}</div>
        </div>
        <div className="right">
          <span className={`hh-status${complete ? ' complete' : (partial ? ' partial' : '')}`}>
            {complete ? '✓ Complete' : partial ? 'In progress' : 'Not started'}
          </span>
          <I n="chevD" s={13} className="chev"/>
          <span className="rm" onClick={(e) => { e.stopPropagation(); onRemove(); }}><I n="x" s={13}/></span>
        </div>
      </div>
      {expanded && (
        <div className="hh-card-bd">
          <div className="iw-grid">
            <Field label="First name" required>
              <input className="iw-input" value={m.name || ''}
                     onChange={(e) => onChange({ ...m, name: e.target.value })}
                     placeholder="e.g. Léo"/>
            </Field>
            <Field label="Date of birth" required
                   why="We compute your child's age automatically and use it to find appropriate schools and plan enrollment timing.">
              <input className="iw-input" type="date" value={m.dob || ''}
                     onChange={(e) => onChange({ ...m, dob: e.target.value })}/>
              {age != null && (
                <div className="iw-derived">
                  <I n="sparkles" s={10}/> {age} years old · {age < 6 ? 'pre-school' : age < 11 ? 'primary' : age < 15 ? 'middle school' : 'secondary'}
                </div>
              )}
            </Field>
            <Field label="School type preference" className="full">
              <div className="iw-multi">
                {['Public', 'Private', 'International', 'Bilingual', 'Not sure yet'].map(s => (
                  <div key={s} className={`iw-multi-chip${m.school === s ? ' active' : ''}`}
                       onClick={() => onChange({ ...m, school: s })}>{s}</div>
                ))}
              </div>
            </Field>
          </div>
        </div>
      )}
    </div>
  );
}

function PetCard({ m, onChange, onRemove, international, destCountry, expanded, onToggle, index }) {
  const complete = m.pet_type && m.count;
  const partial  = m.pet_type || m.breed || m.notes;
  const restrictedBreed = m.breed && RESTRICTED_BREEDS.some(b => m.breed.toLowerCase().includes(b.toLowerCase()));
  const quarantineRequired = QUARANTINE_COUNTRIES.includes(destCountry);
  return (
    <div className={`hh-card pet${expanded ? ' expanded' : ''}`}>
      <div className="hh-card-hd" onClick={onToggle}>
        <div className="ico">{m.pet_type === 'Cat' ? '🐱' : m.pet_type === 'Bird' ? '🐦' : '🐕'}</div>
        <div className="body">
          <div className="t">
            {(m.pet_type || 'Pet')}{m.breed ? ` · ${m.breed}` : ''}{m.count > 1 ? ` × ${m.count}` : ''}
            {restrictedBreed && <span className="iw-prefill" style={{ background: 'var(--warning-soft)', color: 'var(--warning)', marginLeft: 8 }}>⚠ Breed flagged</span>}
          </div>
          <div className="s">{international ? 'Vaccination, microchip, breed' : 'Type & count'}</div>
        </div>
        <div className="right">
          <span className={`hh-status${complete ? ' complete' : (partial ? ' partial' : '')}`}>
            {complete ? '✓ Complete' : partial ? 'In progress' : 'Not started'}
          </span>
          <I n="chevD" s={13} className="chev"/>
          <span className="rm" onClick={(e) => { e.stopPropagation(); onRemove(); }}><I n="x" s={13}/></span>
        </div>
      </div>
      {expanded && (
        <div className="hh-card-bd">
          <div className="iw-grid">
            <Field label="Type" required>
              <select className="iw-select" value={m.pet_type || ''}
                      onChange={(e) => onChange({ ...m, pet_type: e.target.value })}>
                <option value="">Select…</option>
                <option>Dog</option><option>Cat</option><option>Bird</option><option>Exotic</option><option>Other</option>
              </select>
            </Field>
            <Field label="Count" required>
              <input className="iw-input" type="number" min="1" max="10" value={m.count || 1}
                     onChange={(e) => onChange({ ...m, count: Number(e.target.value) })}/>
            </Field>
            {(m.pet_type === 'Dog' || m.pet_type === 'Cat') && (
              <Field label="Breed" required={m.pet_type === 'Dog'} className="full"
                     why="Some breeds face housing restrictions or import limits at the destination. Telling us now means we can flag this early.">
                <input className="iw-input" value={m.breed || ''}
                       onChange={(e) => onChange({ ...m, breed: e.target.value })}
                       placeholder={m.pet_type === 'Dog' ? 'e.g. Labrador, Pit Bull' : 'e.g. Maine Coon'}/>
                {restrictedBreed && (
                  <div className="iw-warn">
                    <I n="alert" s={13} className="ico"/>
                    <div>
                      <strong>This breed may face housing restrictions</strong> at many apartment buildings in {COUNTRIES.find(c => c.code === destCountry)?.name || 'the destination'}. We'll automatically flag this on housing options and add an alert to your roadmap.
                    </div>
                  </div>
                )}
              </Field>
            )}
            {international && (
              <>
                <Field label="Rabies vaccination">
                  <select className="iw-select" value={m.rabies || ''}
                          onChange={(e) => onChange({ ...m, rabies: e.target.value })}>
                    <option value="">Select…</option><option>Yes</option><option>No</option>
                  </select>
                </Field>
                <Field label="Microchipped">
                  <select className="iw-select" value={m.microchipped || ''}
                          onChange={(e) => onChange({ ...m, microchipped: e.target.value })}>
                    <option value="">Select…</option><option>Yes</option><option>No</option>
                  </select>
                </Field>
              </>
            )}
            <Field label="Notes for relocation" className="full" optional
                   hint="e.g. vaccination details, special handling, size, behaviour… anything the pet transport provider should know.">
              <textarea className="iw-textarea" rows="2"
                        value={m.notes || ''}
                        onChange={(e) => onChange({ ...m, notes: e.target.value })}
                        placeholder="e.g. up to date on bordetella, needs sedation for flights…"/>
            </Field>
            {international && quarantineRequired && (
              <div className="full">
                <div className="iw-warn info">
                  <I n="info" s={13} className="ico"/>
                  <div>
                    <strong>{COUNTRIES.find(c => c.code === destCountry)?.name} requires pet quarantine.</strong>
                    Your roadmap will include a dedicated pet quarantine track with milestones for import permits, health certificates, and arrival inspection. Typical timeline: 6–12 months pre-arrival.
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function AdultCard({ m, onChange, onRemove, expanded, onToggle }) {
  const complete = m.count > 0 && m.relationship && m.care_level;
  const partial  = m.count > 0 || m.relationship || m.care_level;
  const RELATIONSHIPS = ['parent', 'parent_in_law', 'sibling', 'elder', 'other'];
  const RELATIONSHIP_LBL = { parent: 'Parent', parent_in_law: 'Parent-in-law', sibling: 'Sibling', elder: 'Other elder', other: 'Other' };
  const CARE_LEVELS = [
    { id: 'basic',    t: 'Basic',    s: 'Independent, just needs help settling' },
    { id: 'assisted', t: 'Assisted', s: 'Needs regular daily support' },
    { id: 'medical',  t: 'Medical',  s: 'Requires medical or nursing care' },
  ];
  return (
    <div className={`hh-card adult${expanded ? ' expanded' : ''}`}>
      <div className="hh-card-hd" onClick={onToggle}>
        <div className="ico">🧓</div>
        <div className="body">
          <div className="t">Dependent adult{m.count > 1 ? `s × ${m.count}` : ''}{m.relationship ? ` · ${RELATIONSHIP_LBL[m.relationship]}` : ''}</div>
          <div className="s">{m.care_level ? `${CARE_LEVELS.find(c => c.id === m.care_level)?.t} care` : 'Relationship & care level'}</div>
        </div>
        <div className="right">
          <span className={`hh-status${complete ? ' complete' : (partial ? ' partial' : '')}`}>
            {complete ? '✓ Complete' : partial ? 'In progress' : 'Not started'}
          </span>
          <I n="chevD" s={13} className="chev"/>
          <span className="rm" onClick={(e) => { e.stopPropagation(); onRemove(); }}><I n="x" s={13}/></span>
        </div>
      </div>
      {expanded && (
        <div className="hh-card-bd">
          <div className="iw-grid">
            <Field label="Full name" optional>
              <input className="iw-input" value={m.full_name || ''}
                     onChange={(e) => onChange({ ...m, full_name: e.target.value })}
                     placeholder="e.g. Marie Bouchard"/>
            </Field>
            <Field label="How many?" required>
              <input className="iw-input" type="number" min="1" max="6" value={m.count || 1}
                     onChange={(e) => onChange({ ...m, count: Number(e.target.value) })}/>
            </Field>
            <Field label="Relationship" required className="full">
              <div className="iw-multi">
                {RELATIONSHIPS.map(rel => (
                  <div key={rel} className={`iw-multi-chip${m.relationship === rel ? ' active' : ''}`}
                       onClick={() => onChange({ ...m, relationship: rel })}>
                    {RELATIONSHIP_LBL[rel]}
                  </div>
                ))}
              </div>
            </Field>
            <Field label="Care level" required className="full"
                   why="Drives the kind of housing (accessibility), medical services, and in-home support we surface.">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {CARE_LEVELS.map(lvl => (
                  <label key={lvl.id} style={{
                    display: 'flex', alignItems: 'flex-start', gap: 9,
                    padding: '9px 11px',
                    border: `1.5px solid ${m.care_level === lvl.id ? 'var(--accent)' : 'var(--border)'}`,
                    background: m.care_level === lvl.id ? 'var(--accent-soft)' : 'var(--surface)',
                    borderRadius: 8,
                    cursor: 'pointer',
                    transition: 'all 100ms ease'
                  }}>
                    <input type="radio" name={`care-${m.id}`}
                           checked={m.care_level === lvl.id}
                           onChange={() => onChange({ ...m, care_level: lvl.id })}
                           style={{ marginTop: 3, accentColor: 'var(--accent)' }}/>
                    <span style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: m.care_level === lvl.id ? 'var(--accent)' : 'var(--text)', letterSpacing: '-0.005em' }}>{lvl.t}</div>
                      <div style={{ fontSize: 11.5, color: 'var(--text-3)', marginTop: 2 }}>{lvl.s}</div>
                    </span>
                  </label>
                ))}
              </div>
            </Field>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main wizard ──────────────────────────────────────────────────
function QuickIntakeScreen({ edge = 'family', step: stepProp = 1, showNotes = false, onAdvance, onComplete }) {
  const [data, setData] = useState(() => presetForEdge(edge));
  useEffect(() => setData(presetForEdge(edge)), [edge]);

  const [step, setStep] = useState(stepProp);
  useEffect(() => setStep(stepProp), [stepProp]);

  const [destLocked, setDestLocked] = useState(true);
  const [destCityLocked, setDestCityLocked] = useState(true);
  const [emailLocked, setEmailLocked] = useState(true);
  const [jobLocked, setJobLocked] = useState(true);
  const [contractTypeLocked, setContractTypeLocked] = useState(true);
  const [contractStartLocked, setContractStartLocked] = useState(true);
  const [salaryLocked, setSalaryLocked] = useState(true);
  const [officeLocked, setOfficeLocked] = useState(true);
  const [expanded, setExpanded] = useState({}); // map id → bool
  const [savedAt, setSavedAt] = useState(Date.now());
  const saveTimer = useRef(null);

  const setField = (k, v) => {
    setData(d => ({ ...d, [k]: v }));
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => setSavedAt(Date.now()), 700);
  };

  const international = data.origin_country && data.dest_country && data.origin_country !== data.dest_country;
  const STEP_LBL = ['Journey', 'About You', 'My People', 'Work & Place', 'My Needs', 'Review'];
  const STEP_ICO = ['🛫', '👤', '👪', '🗺️', '✅', '📋'];

  const goTo = (s) => {
    setStep(s);
    onAdvance?.(s);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // ── Step-level validation ─────────────────────────────
  const stepValid = (s) => {
    if (s === 1) return data.origin_country && data.origin_city && data.dest_country && data.dest_city && data.target_date && data.purpose;
    if (s === 2) return data.full_name && data.nationality && data.passport_country && data.passport_expiry;
    if (s === 3) return data.members.length >= 1; // at least 'self'
    if (s === 4) return data.job_title && data.contract_start && data.contract_type && data.office_address && data.work_pattern && data.salary_band;
    if (s === 5) return (data.services || []).length >= 1;
    return true;
  };

  // ── Household members operations ─────────────────────
  const partner = data.members.find(m => m.kind === 'partner');
  const children = data.members.filter(m => m.kind === 'child');
  const pets = data.members.filter(m => m.kind === 'pet');
  const adults = data.members.filter(m => m.kind === 'adult');

  const addPartner = () => {
    if (partner) return;
    const id = 'p' + Date.now();
    setField('members', [...data.members, { id, kind: 'partner' }]);
    setExpanded(e => ({ ...e, [id]: true }));
  };
  const addChild = () => {
    const id = 'c' + Date.now();
    setField('members', [...data.members, { id, kind: 'child' }]);
    setExpanded(e => ({ ...e, [id]: true }));
  };
  const addPet = () => {
    const id = 'pet' + Date.now();
    setField('members', [...data.members, { id, kind: 'pet', count: 1 }]);
    setExpanded(e => ({ ...e, [id]: true }));
  };
  const addAdult = () => {
    if (adults.length) return;
    const id = 'adult' + Date.now();
    setField('members', [...data.members, { id, kind: 'adult', count: 1 }]);
    setExpanded(e => ({ ...e, [id]: true }));
  };
  const updateMember = (id, next) => setField('members', data.members.map(m => m.id === id ? next : m));
  const removeMember = (id) => setField('members', data.members.filter(m => m.id !== id));

  return (
    <div className="page iw">
      <div className="page-hd">
        <div className="page-eyebrow">Employee · /case/wizard/{step}</div>
        <h1 className="page-h">Detailed Intake</h1>
        <div className="page-sub">Tell us about your relocation so we can prepare the right recommendations for you. Each tab takes a couple of minutes — you can refine details later in your profile.</div>
      </div>

      {showNotes && (
        <div className="iw-note">
          <span className="pin">📌</span>
          <div>
            <strong>UX model · hybrid intake:</strong> 5 essential steps now → editable rich profile afterwards. Country detection is silent; HR pre-fills are visually distinct. Each step ≤ 4 visible fields. The household builder replaces marital-status + spouse fields with cards that scale from "just me" to a family of 6 with pets.
          </div>
        </div>
      )}

      {edge !== 'family' && (
        <div className="iw-edge-banner">
          <I n="info" s={14}/>
          <div>
            <strong>Edge case demo · </strong>
            {edge === 'solo' && 'Solo move (just me) — household builder shows the fast path.'}
            {edge === 'large' && 'Large family — 4 children, 2 dogs (one restricted breed).'}
            {edge === 'uk_jp_pet' && 'UK → Japan with a restricted-breed dog — quarantine + housing warnings active.'}
          </div>
        </div>
      )}

      {/* Pre-fill banner at the very top */}
      <div className="iw-warn info" style={{ marginBottom: 14 }}>
        <I n="info" s={13} className="ico"/>
        <div>
          <strong>Some fields are pre-filled by your HR team</strong> (destination, office address, contract details, salary band). They're locked by default — click “Edit” on any pre-filled field if anything looks wrong.
        </div>
      </div>

      <div className="iw-frame">
        {/* Progress */}
        <div className="iw-progress">
          <div className="iw-progress-top">
            <span className="ttl">Detailed Intake</span>
            <span className="save">Auto-saved {Math.floor((Date.now() - savedAt) / 1000) < 60 ? 'just now' : 'a moment ago'}</span>
            <span className="step-of">Step {step} / 6</span>
          </div>
          <div className="iw-stepper">
            {STEP_LBL.map((lbl, i) => {
              const isDone = stepValid(i + 1) && i + 1 < step;
              return (
                <div key={lbl} className={`iw-step${i + 1 === step ? ' active' : (isDone ? ' done' : '')}`}
                     onClick={() => { if (i + 1 < step) goTo(i + 1); }}>
                  <div className="num"><span>{i + 1}</span></div>
                  <div className="lbl">{STEP_ICO[i]} {lbl}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Body */}
        <div className="iw-body fade-in" key={step}>
          {step === 1 && (
            <>
              <div className="iw-step-hd">
                <div className="t">Where are you moving from and to?</div>
                <div className="s">Just the basics — we'll use this to start drafting your roadmap and detect whether your case is international.</div>
                <span className="legend"><span className="star">*</span> required field</span>
              </div>
              <div className="iw-grid">
                <Field label="Origin country" required>
                  <CountryCombo value={data.origin_country} onChange={(v) => setField('origin_country', v)}/>
                </Field>
                <Field label="Origin city" required>
                  <CityCombo country={data.origin_country} value={data.origin_city}
                             onChange={(v) => setField('origin_city', v)}/>
                </Field>
                <Field label="Destination country" required prefill prefillLocked={destLocked}
                       onUnlock={() => setDestLocked(false)}>
                  <CountryCombo value={data.dest_country} onChange={(v) => setField('dest_country', v)} disabled={destLocked}/>
                </Field>
                <Field label="Destination city" required prefill prefillLocked={destCityLocked}
                       onUnlock={() => setDestCityLocked(false)}>
                  <CityCombo country={data.dest_country} value={data.dest_city}
                             onChange={(v) => setField('dest_city', v)}/>
                </Field>
                <Field label="Target move date" required>
                  <input className="iw-input" type="date" value={data.target_date}
                         onChange={(e) => setField('target_date', e.target.value)}/>
                </Field>
                <Field label="Purpose of relocation" required>
                  <select className="iw-select" value={data.purpose}
                          onChange={(e) => setField('purpose', e.target.value)}>
                    <option>Employment</option><option>Study</option><option>Family</option><option>Other</option>
                  </select>
                </Field>
              </div>
              {international && (
                <div className="iw-warn info" style={{ marginTop: 18 }}>
                  <I n="globe" s={14} className="ico"/>
                  <div>
                    <strong>International move detected.</strong> We'll automatically include visa, customs, international movers, and (if relevant) pet import as part of your roadmap.
                  </div>
                </div>
              )}
            </>
          )}

          {step === 2 && (
            <>
              <div className="iw-step-hd">
                <div className="t">A bit about you</div>
                <div className="s">Your passport details kick off the immigration track. Upload your passport to auto-fill these in seconds.</div>
              </div>
              <div className="iw-grid">
                <Field label="Full name" required>
                  <input className="iw-input" value={data.full_name}
                         onChange={(e) => setField('full_name', e.target.value)}
                         placeholder="As shown on your passport"/>
                </Field>
                <Field label="Email" required prefill prefillLocked={emailLocked}
                       onUnlock={() => setEmailLocked(false)}>
                  <input className={`iw-input${emailLocked ? ' locked' : ''}`} type="email"
                         value={data.email} disabled={emailLocked}
                         onChange={(e) => setField('email', e.target.value)}/>
                </Field>
                <Field label="Nationality" required>
                  <CountryCombo value={data.nationality} onChange={(v) => setField('nationality', v)}/>
                </Field>
                <Field label="Passport country" required>
                  <CountryCombo value={data.passport_country} onChange={(v) => setField('passport_country', v)}/>
                </Field>
                <Field label="Passport expiry" required>
                  <input className="iw-input" type="date" value={data.passport_expiry}
                         onChange={(e) => setField('passport_expiry', e.target.value)}/>
                </Field>
                <Field label="Passport upload" optional className="full"
                       hint="Drag-and-drop a PDF or photo — we'll OCR your name, country and expiry date.">
                  <div style={{ padding: 14, border: '1.5px dashed var(--border-2)', borderRadius: 8, textAlign: 'center', color: 'var(--text-3)', cursor: 'pointer' }}>
                    <I n="upload" s={16}/> &nbsp;Drop your passport or click to browse
                  </div>
                </Field>
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <div className="iw-step-hd">
                <div className="t">Who's relocating with you?</div>
                <div className="s">Add anyone joining the move — partner, kids, pets, or dependent adults. Cards expand for details and scale gracefully.</div>
              </div>
              <div className="hh-list">
                {/* Self card (always present, minimal) */}
                <div className="hh-card self">
                  <div className="hh-card-hd" style={{ cursor: 'default' }}>
                    <div className="ico">🙋</div>
                    <div className="body">
                      <div className="t">{data.full_name || 'You'}</div>
                      <div className="s">Primary relocator</div>
                    </div>
                    <span className="hh-status complete">✓ From Step 2</span>
                  </div>
                </div>
                {partner && (
                  <PartnerCard m={partner}
                    onChange={(next) => updateMember(partner.id, next)}
                    onRemove={() => removeMember(partner.id)}
                    international={international}
                    expanded={expanded[partner.id] || false}
                    onToggle={() => setExpanded(e => ({ ...e, [partner.id]: !e[partner.id] }))}/>
                )}
                {children.map((c, i) => (
                  <ChildCard key={c.id} m={c} index={i}
                    onChange={(next) => updateMember(c.id, next)}
                    onRemove={() => removeMember(c.id)}
                    expanded={expanded[c.id] || false}
                    onToggle={() => setExpanded(e => ({ ...e, [c.id]: !e[c.id] }))}/>
                ))}
                {pets.map((p, i) => (
                  <PetCard key={p.id} m={p} index={i}
                    international={international}
                    destCountry={data.dest_country}
                    onChange={(next) => updateMember(p.id, next)}
                    onRemove={() => removeMember(p.id)}
                    expanded={expanded[p.id] || false}
                    onToggle={() => setExpanded(e => ({ ...e, [p.id]: !e[p.id] }))}/>
                ))}
                {adults.map((a) => (
                  <AdultCard key={a.id} m={a}
                    onChange={(next) => updateMember(a.id, next)}
                    onRemove={() => removeMember(a.id)}
                    expanded={expanded[a.id] || false}
                    onToggle={() => setExpanded(e => ({ ...e, [a.id]: !e[a.id] }))}/>
                ))}

                <div className="hh-add">
                  {!partner && <button type="button" className="hh-add-btn" onClick={addPartner}><I n="plus" s={11}/> Add partner</button>}
                  <button type="button" className="hh-add-btn" onClick={addChild}><I n="plus" s={11}/> Add a child</button>
                  <button type="button" className="hh-add-btn" onClick={addPet}><I n="plus" s={11}/> Add a pet</button>
                  {!adults.length && <button type="button" className="hh-add-btn" onClick={addAdult}><I n="plus" s={11}/> Add dependent adult</button>}
                </div>
                {data.members.length === 1 && (
                  <div className="iw-warn info">
                    <I n="info" s={13} className="ico"/>
                    <div>
                      <strong>Moving solo?</strong> That's totally fine — just continue. You can always add household members later from your profile.
                    </div>
                  </div>
                )}
              </div>
            </>
          )}

          {step === 4 && (
            <>
              <div className="iw-step-hd">
                <div className="t">Your work &amp; commute</div>
                <div className="s">Most of this is pre-filled by your HR team — confirm or update. The commute settings drive your housing pre-filter.</div>
                <span className="legend"><span className="star">*</span> required field</span>
              </div>
              <div className="iw-grid">
                <Field label="Job title" required prefill prefillLocked={jobLocked}
                       onUnlock={() => setJobLocked(false)}>
                  <input className={`iw-input${jobLocked ? ' locked' : ''}`} value={data.job_title} disabled={jobLocked}
                         onChange={(e) => setField('job_title', e.target.value)}
                         placeholder="e.g. Senior Engineer"/>
                </Field>
                <Field label="Contract type" required prefill prefillLocked={contractTypeLocked}
                       onUnlock={() => setContractTypeLocked(false)}>
                  <select className={`iw-select${contractTypeLocked ? ' locked' : ''}`} value={data.contract_type}
                          disabled={contractTypeLocked}
                          onChange={(e) => setField('contract_type', e.target.value)}>
                    <option>Permanent</option><option>Fixed-term</option><option>Secondment</option>
                  </select>
                </Field>
                <Field label="Contract start date" required prefill prefillLocked={contractStartLocked}
                       onUnlock={() => setContractStartLocked(false)}>
                  <input className={`iw-input${contractStartLocked ? ' locked' : ''}`} type="date" value={data.contract_start}
                         disabled={contractStartLocked}
                         onChange={(e) => setField('contract_start', e.target.value)}/>
                </Field>
                <Field label="Salary band" required prefill prefillLocked={salaryLocked}
                       onUnlock={() => setSalaryLocked(false)}
                       hint="Used to confirm visa salary thresholds.">
                  <select className={`iw-select${salaryLocked ? ' locked' : ''}`} value={data.salary_band}
                          disabled={salaryLocked}
                          onChange={(e) => setField('salary_band', e.target.value)}>
                    <option value="">Select…</option>
                    <option>50–100k€</option>
                    <option>100–150k€</option>
                    <option>150–200k€</option>
                    <option>200–300k€</option>
                    <option>300k€+</option>
                  </select>
                </Field>
                <Field label="Office address at destination" required className="full"
                       prefill prefillLocked={officeLocked}
                       onUnlock={() => setOfficeLocked(false)}
                       why="Anchors the commute analysis. We'll show neighborhoods within your time radius for housing.">
                  <input className={`iw-input${officeLocked ? ' locked' : ''}`} value={data.office_address}
                         disabled={officeLocked}
                         onChange={(e) => setField('office_address', e.target.value)}
                         placeholder="Start typing — we'll autocomplete from Google Places"/>
                  {data.office_address && (
                    <div className="iw-address">
                      <div className="pin"><I n="pin" s={12}/></div>
                      <div className="body">
                        <div className="addr">{data.office_address}</div>
                        <div className="sub">Verified · used for commute filtering</div>
                      </div>
                      {!officeLocked && (
                        <span className="clear" onClick={() => setField('office_address', '')}><I n="x" s={12}/></span>
                      )}
                    </div>
                  )}
                </Field>
                <Field label="Work pattern" required className="full">
                  <div className="iw-multi">
                    {['Full in-office', 'Hybrid', 'Fully remote'].map(p => (
                      <div key={p} className={`iw-multi-chip${data.work_pattern === p ? ' active' : ''}`}
                           onClick={() => setField('work_pattern', p)}>{p}</div>
                    ))}
                  </div>
                </Field>
              </div>

              {data.work_pattern !== 'Fully remote' && (
                <div className="iw-commute-row">
                  <div className="iw-slider-wrap">
                    <Field label="Maximum commute you'd accept">
                      <div className="iw-slider-row">
                        <input className="iw-slider" type="range" min="15" max="75" step="5"
                               value={data.commute_mins}
                               onChange={(e) => setField('commute_mins', Number(e.target.value))}/>
                        <span className="val">{data.commute_mins}m</span>
                      </div>
                      <div className="help">Tip: shorter commute = fewer neighborhoods shown but higher quality matches.</div>
                    </Field>
                    <Field label="Preferred way to commute">
                      <MultiChip value={data.commute_mode}
                        onChange={(v) => setField('commute_mode', v)}
                        options={[
                          { value: 'car', label: '🚗 Car' },
                          { value: 'public_transit', label: '🚇 Public transit' },
                          { value: 'bike', label: '🚴 Bike' },
                          { value: 'walking', label: '🚶 Walking' },
                          { value: 'no_pref', label: 'No preference' },
                        ]}/>
                    </Field>
                  </div>
                  <div>
                    <Field label="Commute map · live preview"
                           hint="The radius updates as you change the slider. This drives your housing neighborhood shortlist.">
                      <CommuteMap maxMins={data.commute_mins} mode={data.commute_mode}/>
                    </Field>
                  </div>
                </div>
              )}

              {data.work_pattern === 'Fully remote' && (
                <div className="iw-warn info" style={{ marginTop: 14 }}>
                  <I n="info" s={13} className="ico"/>
                  <div>
                    <strong>Working fully remote.</strong> We'll skip commute filtering and lead your housing search with neighborhood quality, expat community, and lifestyle priorities instead.
                  </div>
                </div>
              )}
            </>
          )}

          {step === 5 && <MyNeedsStep data={data} setField={setField} members={data.members}/>}

          {step === 6 && (
            <>
              <div className="iw-step-hd">
                <div className="t">Review &amp; submit</div>
                <div className="s">A quick check before we generate your roadmap. You can edit any section later from your profile.</div>
              </div>
              <ReviewSummary data={data} goTo={goTo}/>
              <div className="iw-consent">
                <input type="checkbox" checked={data.consent}
                       onChange={(e) => setField('consent', e.target.checked)}/>
                <div>
                  <div className="t">I agree to ReloPass storing this information to generate my relocation roadmap.</div>
                  <div className="s">
                    Your personal data is processed in accordance with the <a>Privacy policy</a> and <a>Terms of service</a> · GDPR v2026.4. You can request export or deletion any time from your profile.
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Foot */}
        <div className="iw-foot">
          {step > 1 && (
            <button className="iw-btn ghost" onClick={() => goTo(step - 1)}>
              <I n="arrowL" s={12}/> Back
            </button>
          )}
          <span className="meta">
            <I n="lock" s={11}/> Encrypted · only you and your HR team see this
          </span>
          <span className="spc"/>
          {step < 6 && (
            <button className="iw-btn primary" onClick={() => goTo(step + 1)} disabled={!stepValid(step)}>
              Continue <I n="arrowR" s={12}/>
            </button>
          )}
          {step === 6 && (
            <button className="iw-btn primary"
                    disabled={!data.consent}
                    onClick={() => onComplete?.(data)}>
              <I n="sparkles" s={12}/> Generate my roadmap
            </button>
          )}
        </div>
      </div>

      {showNotes && (
        <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="iw-note">
            <span className="pin">📌</span>
            <div>
              <strong>Tradeoff · all-on-one-page vs stepped:</strong> we kept the stepped pattern (5 steps) because the validation gates produce a calmer cognitive load and let HR pre-fills be obvious. Tradeoff: ~5 button clicks vs one long scroll. The household builder card pattern in Step 3 reduces page count significantly vs the original 9-screen wizard.
            </div>
          </div>
          <div className="iw-note">
            <span className="pin">📌</span>
            <div>
              <strong>Tradeoff · commute map vs slider alone:</strong> the live SVG map adds visual proof that commute data is captured correctly — without it, users frequently misjudge whether 30 minutes is enough. Tradeoff: extra dev complexity and another loading state. We mitigate by using a stylised abstract map (no Google Maps SDK).
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ReviewSummary({ data, goTo }) {
  const partner = data.members.find(m => m.kind === 'partner');
  const children = data.members.filter(m => m.kind === 'child');
  const pets = data.members.filter(m => m.kind === 'pet');
  const adults = data.members.filter(m => m.kind === 'adult');
  const oC = COUNTRIES.find(c => c.code === data.origin_country);
  const dC = COUNTRIES.find(c => c.code === data.dest_country);
  return (
    <div className="iw-review-grid">
      <div className="iw-review-card">
        <div className="lbl">Move <span className="edit" onClick={() => goTo(1)}>Edit</span></div>
        <div className="iw-review-row"><span className="k">Route</span><span className="v">{oC?.flag} {data.origin_city} → {dC?.flag} {data.dest_city}</span></div>
        <div className="iw-review-row"><span className="k">Target date</span><span className="v">{data.target_date || '—'}</span></div>
        <div className="iw-review-row"><span className="k">Purpose</span><span className="v">{data.purpose}</span></div>
      </div>
      <div className="iw-review-card">
        <div className="lbl">About you <span className="edit" onClick={() => goTo(2)}>Edit</span></div>
        <div className="iw-review-row"><span className="k">Name</span><span className="v">{data.full_name || <em className="v muted">missing</em>}</span></div>
        <div className="iw-review-row"><span className="k">Passport</span><span className="v">{data.passport_country || '—'} · expires {data.passport_expiry || '—'}</span></div>
      </div>
      <div className="iw-review-card full">
        <div className="lbl">Household ({data.members.length} total) <span className="edit" onClick={() => goTo(3)}>Edit</span></div>
        <div className="iw-review-row"><span className="k">Self</span><span className="v">{data.full_name || 'You'}</span></div>
        {partner && <div className="iw-review-row"><span className="k">Partner</span><span className="v">{partner.name || '—'} · {partner.employment || '—'}{partner.needs_work_permit ? ` · work permit: ${partner.needs_work_permit}` : ''}</span></div>}
        {children.length > 0 && <div className="iw-review-row"><span className="k">Children</span><span className="v">{children.map(c => `${c.name || 'unnamed'} (${computeAge(c.dob) ?? '?'}y, ${c.school || '?'})`).join(' · ')}</span></div>}
        {pets.length > 0 && <div className="iw-review-row"><span className="k">Pets</span><span className="v">{pets.map(p => `${p.pet_type || '?'}${p.breed ? ' (' + p.breed + ')' : ''}${p.count > 1 ? ' × ' + p.count : ''}`).join(' · ')}</span></div>}
        {adults.length > 0 && <div className="iw-review-row"><span className="k">Dependent adults</span><span className="v">{adults[0].count} {adults[0].accessibility === 'Yes' ? ` · accessibility needs noted` : ''}</span></div>}
      </div>
      <div className="iw-review-card full">
        <div className="lbl">Work &amp; commute <span className="edit" onClick={() => goTo(4)}>Edit</span></div>
        <div className="iw-review-row"><span className="k">Job</span><span className="v">{data.job_title || '—'} · {data.contract_type}</span></div>
        <div className="iw-review-row"><span className="k">Office</span><span className="v">{data.office_address || <em className="v muted">missing</em>}</span></div>
        <div className="iw-review-row"><span className="k">Work pattern</span><span className="v">{data.work_pattern}{data.work_pattern !== 'Fully remote' ? ` · ≤ ${data.commute_mins} min by ${data.commute_mode.slice(0, 2).join('/')}` : ''}</span></div>
        <div className="iw-review-row"><span className="k">Salary band</span><span className="v">{data.salary_band || '—'}</span></div>
      </div>
    </div>
  );
}

// ── Flow diagram screen (separate annotated view) ──────────────
function IntakeFlowDiagram() {
  const STEPS = [
    { n: 1, t: 'Move context', s: 'Origin/dest country + city, target date, purpose.', b: ['Silent international detection (origin ≠ dest)', '→ Activates visa, customs, intl movers downstream'] },
    { n: 2, t: 'About you', s: 'Name, nationality, passport, email.', b: ['Passport OCR auto-fills 4 fields', 'Email pre-filled by HR (lockable)'] },
    { n: 3, t: 'Household', s: 'Anchor: who is moving with you? Card-based builder.', b: ['Partner card → needs work permit branch', 'Child card → DOB auto-computes age', 'Pet card → breed restriction check', 'Dependent adult → accessibility'] },
    { n: 4, t: 'Work & commute', s: 'Job title, office address, work pattern, commute.', b: ['Office address anchors commute map', '"Fully remote" collapses commute fields', 'Maps to worksRemote, commuteMins, commuteMode'] },
    { n: 5, t: 'Review & submit', s: 'Read-only summary, section-edit links, consent gate.', b: ['Generates first draft roadmap on submit', 'Routes employee to Rich Profile for refinement'] },
  ];
  return (
    <div className="iw-flow">
      <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>Quick-intake flow · branching logic</div>
      <div style={{ fontSize: 12.5, color: 'var(--text-2)', marginBottom: 16, lineHeight: 1.55 }}>
        Read left-to-right. Branches and downstream system effects are listed below each step. After Step 5, the employee is routed to the persistent <strong>Rich Profile</strong> page to enrich progressively.
      </div>
      <div className="iw-flow-row">
        {STEPS.map(s => (
          <div key={s.n} className="iw-flow-step">
            <div className="n">{s.n}</div>
            <div className="t">{s.t}</div>
            <div className="s">{s.s}</div>
            <div className="branches">
              {s.b.map((bb, i) => (
                <div key={i}>{bb.includes('→')
                  ? <><strong>{bb.split('→')[0].trim()}</strong> → {bb.split('→')[1]}</>
                  : bb}</div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── My Needs (services selection) — Step 5 ───────────────────────
const SERVICES = [
  { id: 'housing',     ico: '🏠', t: 'Housing search',       s: 'Apartment or house search at destination' },
  { id: 'immigration', ico: '🛂', t: 'Immigration',          s: 'Visas, permits, residence registration' },
  { id: 'schools',     ico: '🏫', t: 'Schools',              s: 'School search and enrollment for kids' },
  { id: 'movers',      ico: '📦', t: 'International movers', s: 'Household goods shipping' },
  { id: 'banking',     ico: '🏦', t: 'Banking',              s: 'Local bank account, FX transfer' },
  { id: 'tax',         ico: '🧾', t: 'Tax advisor',          s: 'Cross-border tax, equalization' },
  { id: 'language',    ico: '🗣️', t: 'Language tuition',     s: 'Lessons for you or your family' },
  { id: 'pets',        ico: '🐾', t: 'Pet relocation',       s: 'Quarantine, health certs, transport' },
  { id: 'temp',        ico: '🏨', t: 'Temporary housing',    s: 'Where you stay on arrival' },
  { id: 'spouse',      ico: '💼', t: 'Spouse career',        s: 'Job search, coaching, credentials' },
  { id: 'healthcare',  ico: '🏥', t: 'Healthcare',           s: 'Insurance, doctor finding', soon: true },
  { id: 'culture',     ico: '🎭', t: 'Culture & community',  s: 'Expat groups, orientation', soon: true },
];

function MyNeedsStep({ data, setField, members }) {
  const services = data.services || [];
  const ref = useRef(false);
  // Auto-select based on household composition (first mount only)
  useEffect(() => {
    if (ref.current) return;
    ref.current = true;
    const auto = new Set(services);
    if (members.find(m => m.kind === 'child')) auto.add('schools');
    if (members.find(m => m.kind === 'pet'))   auto.add('pets');
    if (members.find(m => m.kind === 'partner')) auto.add('spouse');
    auto.add('housing');
    auto.add('immigration');
    if (auto.size !== services.length) setField('services', [...auto]);
    // eslint-disable-next-line
  }, []);

  const toggle = (id) => {
    if (services.includes(id)) setField('services', services.filter(s => s !== id));
    else setField('services', [...services, id]);
  };

  const setNote = (id, v) => setField('service_notes', { ...(data.service_notes || {}), [id]: v });
  const setHousingPref = (k, v) => setField('housing_prefs', { ...(data.housing_prefs || {}), [k]: v });
  const housingPrefs = data.housing_prefs || {};

  return (
    <>
      <div className="iw-step-hd">
        <div className="t">What do you need help with?</div>
        <div className="s">Pick the services we should prepare for you. Based on your household, we've pre-selected the ones most teams in your situation need — adjust freely.</div>
      </div>

      <div className="iw-choice-grid" style={{ marginBottom: 22 }}>
        {SERVICES.map(svc => (
          <button key={svc.id}
                  type="button"
                  className={`iw-choice${services.includes(svc.id) ? ' active' : ''}`}
                  disabled={svc.soon}
                  style={svc.soon ? { opacity: 0.5, cursor: 'not-allowed' } : null}
                  onClick={() => !svc.soon && toggle(svc.id)}>
            <div className="ico">{svc.ico}</div>
            <div className="t">{svc.t}{svc.soon && <span className="iw-prefill" style={{ marginLeft: 6 }}>Coming soon</span>}</div>
            <div className="s">{svc.s}</div>
            <div className="check"/>
          </button>
        ))}
      </div>

      {services.length === 0 && (
        <div className="iw-warn info">
          <I n="info" s={13} className="ico"/>
          <div><strong>Select at least one service</strong> to continue. You can always add more later.</div>
        </div>
      )}

      {services.length > 0 && (
        <>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-3)', margin: '10px 0 12px' }}>
            Preferences ({services.length} service{services.length > 1 ? 's' : ''})
          </div>

          {services.includes('housing') && (
            <div className="hh-sub">
              <div className="hh-sub-hd">🏠 Housing search</div>
              <div className="iw-grid">
                <Field label="Rent or buy?">
                  <select className="iw-select" value={housingPrefs.intent || ''}
                          onChange={(e) => setHousingPref('intent', e.target.value)}>
                    <option value="">Select…</option><option>Rent</option><option>Buy</option><option>Not sure yet</option>
                  </select>
                </Field>
                <Field label="Bedrooms needed">
                  <input className="iw-input" type="number" min="1" max="6"
                         value={housingPrefs.bedrooms || ''}
                         onChange={(e) => setHousingPref('bedrooms', Number(e.target.value))}
                         placeholder="e.g. 2"/>
                </Field>
                <Field label="Monthly budget (€)" className="full">
                  <input className="iw-input" type="number"
                         value={housingPrefs.budget || ''}
                         onChange={(e) => setHousingPref('budget', Number(e.target.value))}
                         placeholder="e.g. 2500"/>
                </Field>
              </div>
              <Field label="Anything else about housing?" className="full" optional>
                <textarea className="iw-textarea" rows="2"
                          value={(data.service_notes || {}).housing || ''}
                          onChange={(e) => setNote('housing', e.target.value)}
                          placeholder="e.g. need a quiet area, dog-friendly building, etc."/>
              </Field>
            </div>
          )}

          {services.includes('schools') && (
            <div className="hh-sub">
              <div className="hh-sub-hd">🏫 Schools{members.filter(m => m.kind === 'child').length > 0 ? ` · ${members.filter(m => m.kind === 'child').length} child${members.filter(m => m.kind === 'child').length > 1 ? 'ren' : ''}` : ''}</div>
              <div className="iw-grid">
                <Field label="School type">
                  <select className="iw-select" value={housingPrefs.school_type || ''}
                          onChange={(e) => setHousingPref('school_type', e.target.value)}>
                    <option value="">Select…</option>
                    <option>International</option><option>Public</option><option>Private</option><option>Bilingual</option>
                  </select>
                </Field>
                <Field label="Any special needs support?">
                  <select className="iw-select" value={housingPrefs.special_needs || ''}
                          onChange={(e) => setHousingPref('special_needs', e.target.value)}>
                    <option value="">Select…</option><option>Yes</option><option>No</option>
                  </select>
                </Field>
                <Field label="Expected school start date" className="full">
                  <input className="iw-input" type="date" value={housingPrefs.school_start || data.target_date}
                         onChange={(e) => setHousingPref('school_start', e.target.value)}/>
                  <div className="help">Defaults to your move date; adjust if your kids will start later.</div>
                </Field>
              </div>
            </div>
          )}

          {/* Quick-add notes for the remaining services */}
          {services.filter(id => !['housing', 'schools'].includes(id)).map(id => {
            const svc = SERVICES.find(s => s.id === id);
            return (
              <div key={id} className="hh-sub">
                <div className="hh-sub-hd">{svc.ico} {svc.t}</div>
                <Field label={`Anything else we should know about ${svc.t.toLowerCase()}?`} optional>
                  <textarea className="iw-textarea" rows="2"
                            value={(data.service_notes || {})[id] || ''}
                            onChange={(e) => setNote(id, e.target.value)}
                            placeholder={`Any specific needs, preferences or constraints for ${svc.t.toLowerCase()}…`}/>
                </Field>
              </div>
            );
          })}
        </>
      )}
    </>
  );
}

window.QuickIntakeScreen = QuickIntakeScreen;
window.IntakeFlowDiagram = IntakeFlowDiagram;
window.INTAKE_COUNTRIES = COUNTRIES;
window.intakePresetForEdge = presetForEdge;
window.CommuteMap = CommuteMap;
})();
