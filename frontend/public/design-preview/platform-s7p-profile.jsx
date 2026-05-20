// platform-s7p-profile.jsx — HR Company Profile (sub-section of S7)
// Sections: Identity / Location & Contact / HR & Mobility Defaults / Branding.
// Variants: filled (canonical), empty welcome, 3-step wizard.
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
  { code: 'FI', name: 'Finland',        flag: '🇫🇮' },
  { code: 'DK', name: 'Denmark',        flag: '🇩🇰' },
  { code: 'NL', name: 'Netherlands',    flag: '🇳🇱' },
  { code: 'BE', name: 'Belgium',        flag: '🇧🇪' },
  { code: 'IE', name: 'Ireland',        flag: '🇮🇪' },
  { code: 'CH', name: 'Switzerland',    flag: '🇨🇭' },
  { code: 'IT', name: 'Italy',          flag: '🇮🇹' },
  { code: 'ES', name: 'Spain',          flag: '🇪🇸' },
  { code: 'PT', name: 'Portugal',       flag: '🇵🇹' },
  { code: 'AT', name: 'Austria',        flag: '🇦🇹' },
  { code: 'PL', name: 'Poland',         flag: '🇵🇱' },
  { code: 'US', name: 'United States',  flag: '🇺🇸' },
  { code: 'CA', name: 'Canada',         flag: '🇨🇦' },
  { code: 'MX', name: 'Mexico',         flag: '🇲🇽' },
  { code: 'BR', name: 'Brazil',         flag: '🇧🇷' },
  { code: 'AR', name: 'Argentina',      flag: '🇦🇷' },
  { code: 'JP', name: 'Japan',          flag: '🇯🇵' },
  { code: 'KR', name: 'South Korea',    flag: '🇰🇷' },
  { code: 'CN', name: 'China',          flag: '🇨🇳' },
  { code: 'IN', name: 'India',          flag: '🇮🇳' },
  { code: 'SG', name: 'Singapore',      flag: '🇸🇬' },
  { code: 'AE', name: 'United Arab Emirates', flag: '🇦🇪' },
  { code: 'AU', name: 'Australia',      flag: '🇦🇺' },
  { code: 'NZ', name: 'New Zealand',    flag: '🇳🇿' },
  { code: 'ZA', name: 'South Africa',   flag: '🇿🇦' },
];

const INDUSTRIES = [
  'Technology', 'Financial Services', 'Professional Services',
  'Healthcare', 'Pharma / Biotech', 'Manufacturing', 'Retail',
  'Energy', 'Media & Entertainment', 'Non-profit', 'Government',
  'Education', 'Logistics', 'Other',
];

const SIZE_BANDS = ['1–10', '11–50', '51–200', '201–500', '501–1000', '1001–5000', '5000+'];

const WORKING_LOCATIONS = ['Remote', 'Hybrid', 'On-site', 'Office-first', 'Distributed'];

const BRAND_COLORS = [
  '#0b2b43', // navy (default)
  '#2962ff', // electric blue
  '#1f8e8b', // teal
  '#16a34a', // forest green
  '#c2761a', // amber
  '#7a4ea3', // plum
  '#c0392b', // crimson
  '#475569', // slate
];

// Filled-state seed data
const SEED_FILLED = {
  name: 'Aurora Energy',
  legal_name: 'Aurora Energy AS',
  industry: 'Energy',
  size_band: '201–500',
  website: 'aurora-energy.com',
  country: 'FR',
  hq_city: 'Paris',
  address: '12 Avenue de Friedland, 75008 Paris, France',
  phone: '+33 1 4502 8821',
  hr_contact: 'helena.muller@aurora-energy.com',
  support_email: 'mobility@aurora-energy.com',
  default_destination_country: 'NO',
  default_working_location: 'Hybrid',
  brand_color: '#0b2b43',
  logo_uploaded: true,
};
const SEED_EMPTY = {
  name: '', legal_name: '', industry: '', size_band: '', website: '',
  country: '', hq_city: '', address: '', phone: '',
  hr_contact: '', support_email: '',
  default_destination_country: '', default_working_location: '',
  brand_color: '#2962ff',
  logo_uploaded: false,
};

// Section assignment for fields (used for grouping + completion scoring)
const SECTION_FIELDS = {
  A: ['name', 'legal_name', 'industry', 'size_band', 'website'],
  B: ['country', 'hq_city', 'address', 'phone'],
  C: ['hr_contact', 'support_email', 'default_destination_country', 'default_working_location'],
  D: ['logo_uploaded', 'brand_color'],
};
const FIELD_WEIGHTS = {
  name: 18,                          // required, baseline
  country: 14,                       // prefills cases
  default_destination_country: 12,
  logo_uploaded: 10,
  support_email: 9,
  legal_name: 6,
  industry: 6,
  size_band: 6,
  hq_city: 4,
  address: 4,
  hr_contact: 4,
  default_working_location: 4,
  website: 1,
  phone: 1,
  brand_color: 1,
};

// ── Searchable country combobox ───────────────────────────────────
function CountryCombo({ value, onChange, placeholder = 'Select a country' }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const selected = COUNTRIES.find(c => c.code === value);
  const filtered = query
    ? COUNTRIES.filter(c => c.name.toLowerCase().includes(query.toLowerCase()) || c.code.toLowerCase().includes(query.toLowerCase()))
    : COUNTRIES;

  return (
    <div className="hp-combo" ref={ref}>
      <span className="left-glyph">{selected ? selected.flag : <I n="search" s={14}/>}</span>
      <input
        type="text"
        className="hp-combo-input"
        value={open ? query : (selected ? selected.name : '')}
        placeholder={placeholder}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => { setQuery(''); setOpen(true); }}
        autoComplete="off"
      />
      <span className="right-glyph"><I n="chevD" s={12}/></span>
      {open && (
        <div className="hp-combo-list">
          {filtered.length === 0 && (
            <div style={{ padding: 12, color: 'var(--text-3)', fontSize: 12.5, textAlign: 'center' }}>
              No country matches “{query}”
            </div>
          )}
          {filtered.map(c => (
            <div key={c.code} className={`hp-combo-item${value === c.code ? ' hover' : ''}`}
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

// ── Working-location combo (text + suggestions) ───────────────────
function LocationCombo({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);
  return (
    <div className="hp-combo" ref={ref}>
      <span className="left-glyph"><I n="house" s={14}/></span>
      <input
        type="text"
        className="hp-combo-input"
        value={value || ''}
        placeholder="e.g. Hybrid, Remote, On-site"
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setOpen(true)}
      />
      <span className="right-glyph"><I n="chevD" s={12}/></span>
      {open && (
        <div className="hp-combo-list">
          {WORKING_LOCATIONS.map(l => (
            <div key={l} className={`hp-combo-item${value === l ? ' hover' : ''}`}
                 onClick={() => { onChange(l); setOpen(false); }}>
              <span>{l}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Logo dropzone ─────────────────────────────────────────────────
function LogoDropzone({ uploaded, uploading, error, dragHover, onRequestUpload, onRemove, onSetDrag, onSetUploaded }) {
  // Demo-only: clicking the empty zone simulates an upload.
  const handleClick = () => {
    if (uploaded || uploading) return;
    onRequestUpload?.();
  };
  return (
    <div className={[
      'hp-logo-zone',
      dragHover ? 'drag' : '',
      uploading ? 'uploading' : '',
      uploaded ? 'uploaded' : '',
    ].filter(Boolean).join(' ')}
      onClick={handleClick}
      onDragEnter={(e) => { e.preventDefault(); onSetDrag?.(true); }}
      onDragOver={(e) => { e.preventDefault(); }}
      onDragLeave={(e) => { e.preventDefault(); onSetDrag?.(false); }}
      onDrop={(e) => { e.preventDefault(); onSetDrag?.(false); onRequestUpload?.(); }}
    >
      {uploaded && !uploading && (
        <img src="assets/relopass-mark.png" alt="Company logo"/>
      )}
      {uploading && (
        <>
          <div className="spin"/>
          <div className="t">Uploading…</div>
          <div className="s">Securely transferring to your private space</div>
          <div className="progress-bar"><div style={{ width: '68%' }}/></div>
        </>
      )}
      {!uploading && !uploaded && (
        <>
          <div className="ico"><I n="upload" s={16}/></div>
          <div className="t">Drag &amp; drop or click to upload</div>
          <div className="s">PNG, JPG or SVG · max <strong>2 MB</strong> · 512×512 recommended</div>
        </>
      )}
    </div>
  );
}

// ── Brand color swatches ──────────────────────────────────────────
function ColorSwatches({ value, onChange }) {
  return (
    <div className="hp-colors">
      {BRAND_COLORS.map(c => (
        <div
          key={c}
          className={`hp-color${value === c ? ' active' : ''}`}
          style={{ background: c }}
          onClick={() => onChange(c)}
          title={c}
        />
      ))}
    </div>
  );
}

// ── Save-status pill (per-section) ────────────────────────────────
function SaveStatus({ status }) {
  if (status === 'saved')  return <span className="save-status saved">Saved</span>;
  if (status === 'saving') return <span className="save-status saving">Saving…</span>;
  if (status === 'dirty')  return <span className="save-status dirty">Unsaved</span>;
  return null;
}

// ── Completion ring (small chip) ──────────────────────────────────
function CompletionRing({ pct, large = false }) {
  const size = large ? 56 : 22;
  const stroke = large ? 5 : 3;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const off = c * (1 - Math.min(1, pct / 100));
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: 'rotate(-90deg)' }}>
      <circle className="bg" cx={size/2} cy={size/2} r={r} strokeWidth={stroke}/>
      <circle className="fg" cx={size/2} cy={size/2} r={r} strokeWidth={stroke}
              strokeDasharray={c} strokeDashoffset={off}/>
    </svg>
  );
}

// ── Section header ────────────────────────────────────────────────
function SectionHeader({ marker, title, sub, status, complete, zoom }) {
  return (
    <div className="hp-section-hd">
      <div className={`marker${complete ? ' complete' : ''}`}>{complete ? '✓' : marker}</div>
      <div className="body">
        <div className="t">{title}</div>
        <div className="s">{sub}</div>
      </div>
      <SaveStatus status={status}/>
    </div>
  );
}

// ── Main screen ───────────────────────────────────────────────────
function CompanyProfileScreen({ initialMode = 'filled', initialZoom = null, initialLogoState = null }) {
  // mode: 'filled' | 'empty' | 'wizard'
  const [mode, setMode] = useState(initialMode);
  useEffect(() => setMode(initialMode), [initialMode]);

  // Form state
  const seed = initialMode === 'filled' ? SEED_FILLED : SEED_EMPTY;
  const [data, setData] = useState(seed);
  useEffect(() => { setData(initialMode === 'filled' ? SEED_FILLED : SEED_EMPTY); }, [initialMode]);
  const update = (k, v) => setData(d => ({ ...d, [k]: v }));

  // Per-section saved/dirty state (demo: auto-save on tab-out simulated by debounce)
  const [secStatus, setSecStatus] = useState({ A: 'saved', B: 'saved', C: 'saved', D: 'saved' });
  const markDirty = (sec) => setSecStatus(s => ({ ...s, [sec]: 'dirty' }));
  const fieldSection = (k) => {
    for (const sec of Object.keys(SECTION_FIELDS)) if (SECTION_FIELDS[sec].includes(k)) return sec;
    return null;
  };
  const onFieldChange = (k, v) => {
    update(k, v);
    const sec = fieldSection(k);
    if (sec) {
      markDirty(sec);
      // Auto-save simulation
      clearTimeout(saveTimers.current[sec]);
      saveTimers.current[sec] = setTimeout(() => {
        setSecStatus(s => ({ ...s, [sec]: 'saving' }));
        setTimeout(() => setSecStatus(s => ({ ...s, [sec]: 'saved' })), 600);
      }, 900);
    }
  };
  const saveTimers = useRef({});

  // Logo state — separate from form for upload UI
  const [logoState, setLogoState] = useState(initialLogoState || (seed.logo_uploaded ? 'uploaded' : 'empty'));
  const [dragHover, setDragHover] = useState(false);
  const [logoError, setLogoError] = useState(null);
  useEffect(() => {
    if (initialLogoState) setLogoState(initialLogoState);
    else setLogoState(data.logo_uploaded ? 'uploaded' : 'empty');
  }, [initialLogoState, data.logo_uploaded]);

  const simulateUpload = () => {
    setLogoError(null);
    setLogoState('uploading');
    setTimeout(() => {
      setLogoState('uploaded');
      update('logo_uploaded', true);
      markDirty('D');
      setTimeout(() => setSecStatus(s => ({ ...s, D: 'saved' })), 700);
    }, 1600);
  };
  const removeLogo = () => {
    setLogoState('empty');
    update('logo_uploaded', false);
    markDirty('D');
    setTimeout(() => setSecStatus(s => ({ ...s, D: 'saved' })), 500);
  };

  // Completion score
  const completion = useMemo(() => {
    let score = 0;
    let total = 0;
    for (const [field, weight] of Object.entries(FIELD_WEIGHTS)) {
      total += weight;
      const v = data[field];
      const has = field === 'logo_uploaded' ? !!v : (v != null && v !== '');
      if (has) score += weight;
    }
    return Math.round((score / total) * 100);
  }, [data]);

  // Per-section completion (for marker checkmark)
  const sectionComplete = (sec) => {
    const fields = SECTION_FIELDS[sec];
    return fields.every(f => {
      if (f === 'logo_uploaded') return !!data[f];
      return data[f] != null && data[f] !== '';
    });
  };

  const checklist = [
    { id: 'basics',   t: 'Add company name + country',     done: !!data.name && !!data.country },
    { id: 'logo',     t: 'Upload your logo',                done: !!data.logo_uploaded },
    { id: 'defaults', t: 'Set a default destination country', done: !!data.default_destination_country },
  ];

  // ── Welcome / empty state ────────────────────────────────────
  if (mode === 'empty') {
    return (
      <div className="page wide">
        <ProfileSubNav active="profile"/>
        <PageHeader data={data} completion={completion} mode={mode}/>

        <div className="hp-welcome">
          <div className="eyebrow"><I n="sparkles" s={11}/> Set up in 3 minutes</div>
          <h1>Welcome to ReloPass. Let's set up your workspace.</h1>
          <p>This information powers every relocation case, drives policy recommendations, and shows up wherever your employees interact with us.</p>
          <div className="steps">
            <div className="step"><div className="n">1</div><div><div className="t">Tell us about your company</div><div className="s">Name, country, industry, size.</div></div></div>
            <div className="step"><div className="n">2</div><div><div className="t">Set your mobility defaults</div><div className="s">Where most of your relocations go.</div></div></div>
            <div className="step"><div className="n">3</div><div><div className="t">Add your brand</div><div className="s">Logo + colour appear platform-wide.</div></div></div>
          </div>
          <button className="hp-welcome-cta" onClick={() => setMode('wizard')}>
            <I n="sparkles" s={13}/>
            Start guided setup
            <I n="arrowR" s={13}/>
          </button>
          <button className="hp-welcome-secondary" onClick={() => setMode('filled')}>
            Skip the wizard
          </button>
        </div>

        <div className="hp-banner">
          <div style={{ position: 'relative' }} className="ring-lg">
            <CompletionRing pct={completion} large/>
            <div className="pct" style={{ position:'absolute', top:'50%', left:'50%', transform:'translate(-50%,-50%) rotate(0)' }}>{completion}%</div>
          </div>
          <div className="body">
            <div className="t">Profile {completion}% complete</div>
            <div className="s">A complete profile unlocks smarter case defaults, faster onboarding, and personalised supplier recommendations.</div>
            <div className="checklist">
              {checklist.map(c => (
                <span key={c.id} className={`hp-check${c.done ? ' done' : ''}`}>
                  <span className="box"/>
                  {c.t}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Wizard ───────────────────────────────────────────────────
  if (mode === 'wizard') {
    return <Wizard data={data} onChange={onFieldChange} onUpdate={update}
                   onCancel={() => setMode('empty')}
                   onComplete={() => setMode('filled')}
                   logoState={logoState} simulateUpload={simulateUpload} removeLogo={removeLogo}
                   dragHover={dragHover} setDragHover={setDragHover}/>;
  }

  // ── Canonical filled view ────────────────────────────────────
  return (
    <div className="page wide">
      <ProfileSubNav active="profile"/>
      <PageHeader data={data} completion={completion} mode={mode}/>

      {/* Top completion banner */}
      <div className="hp-banner">
        <div style={{ position: 'relative' }} className="ring-lg">
          <CompletionRing pct={completion} large/>
          <div className="pct" style={{ position:'absolute', top:'50%', left:'50%', transform:'translate(-50%,-50%)' }}>{completion}%</div>
        </div>
        <div className="body">
          <div className="t">
            {completion === 100 ? 'Profile complete — everything is wired up.' :
             completion >= 80 ? `Profile ${completion}% complete — a few details left.` :
             `Profile ${completion}% complete — add the items below to unlock smarter case defaults.`}
          </div>
          <div className="s">Aurora Energy · last updated 2 days ago</div>
          <div className="checklist">
            {checklist.map(c => (
              <span key={c.id} className={`hp-check${c.done ? ' done' : ''}`}>
                <span className="box"/>
                {c.t}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Sections in a compact 2x2 grid */}
      <div className="hp-sections">
      {/* Section A — Identity */}
      <div className={`hp-section${initialZoom === 'A' ? ' zoom' : ''}`}>
        <SectionHeader marker="A" title="Company identity"
          sub="How your company is identified across ReloPass."
          status={secStatus.A} complete={sectionComplete('A')}/>
        <div className="hp-section-bd">
          <div className="hp-grid">
            <FieldText label="Company name"
              hint="Pre-fills as the employer name in every new relocation case."
              value={data.name} onChange={(v) => onFieldChange('name', v)}
              placeholder="Aurora Energy"/>
            <FieldText label="Legal name" optional
              hint="Used on official case documents and contracts."
              value={data.legal_name} onChange={(v) => onFieldChange('legal_name', v)}
              placeholder="Aurora Energy AS"/>
            <FieldSelect label="Industry" optional value={data.industry}
              onChange={(v) => onFieldChange('industry', v)}
              options={['', ...INDUSTRIES]} labels={['Select an industry', ...INDUSTRIES]}/>
            <FieldSelect label="Company size band" optional value={data.size_band}
              onChange={(v) => onFieldChange('size_band', v)}
              options={['', ...SIZE_BANDS]} labels={['Select a size', ...SIZE_BANDS]}
              hint="Used for filtering &amp; may affect policy tier eligibility."/>
            <FieldUrl label="Website" optional value={data.website}
              onChange={(v) => onFieldChange('website', v)} placeholder="company.com"/>
          </div>
        </div>
      </div>

      {/* Section B — Location & Contact */}
      <div className={`hp-section${initialZoom === 'B' ? ' zoom' : ''}`}>
        <SectionHeader marker="B" title="Location &amp; contact"
          sub="Where your company is based and how to reach you."
          status={secStatus.B} complete={sectionComplete('B')}/>
        <div className="hp-section-bd">
          <div className="hp-grid">
            <div className="hp-field">
              <label>Country of incorporation</label>
              <CountryCombo value={data.country} onChange={(v) => onFieldChange('country', v)}/>
              <div className="help">Pre-filled as employer country in every new relocation case.</div>
            </div>
            <FieldText label="HQ city" optional value={data.hq_city}
              onChange={(v) => onFieldChange('hq_city', v)} placeholder="Paris"/>
            <FieldText label="Address" optional fullWidth value={data.address}
              onChange={(v) => onFieldChange('address', v)}
              placeholder="Street, postal code, city"/>
            <FieldText label="Phone" optional value={data.phone}
              onChange={(v) => onFieldChange('phone', v)}
              placeholder="+33 1 45 02 88 21" hint="International format with country code."/>
          </div>
        </div>
      </div>

      {/* Section C — HR & Mobility Defaults */}
      <div className={`hp-section${initialZoom === 'C' ? ' zoom' : ''}`}>
        <SectionHeader marker="C" title="HR &amp; mobility defaults"
          sub="These defaults power your relocation cases and policy engine."
          status={secStatus.C} complete={sectionComplete('C')}/>
        <div className="hp-section-bd">
          <div className="hp-grid">
            <FieldText label="HR contact" optional value={data.hr_contact}
              onChange={(v) => onFieldChange('hr_contact', v)}
              placeholder="Name or email"
              hint={<><strong>Internal</strong> — used in audit logs and admin views.</>}/>
            <FieldEmail label="Support email" optional value={data.support_email}
              onChange={(v) => onFieldChange('support_email', v)}
              placeholder="mobility@yourco.com"
              hint={<span className="help flow"><I n="info" s={13} className="ico"/><span><strong>Employees see this</strong> as their HR contact in the relocation portal.</span></span>}/>
            <div className="hp-field">
              <label>Default destination country</label>
              <CountryCombo value={data.default_destination_country}
                onChange={(v) => onFieldChange('default_destination_country', v)}
                placeholder="Most common destination"/>
              <div className="help flow"><I n="info" s={13} className="ico"/><span>Seeds the destination picker in <strong>every new case</strong> and drives supplier &amp; resource recommendations.</span></div>
            </div>
            <div className="hp-field">
              <label>Default working location</label>
              <LocationCombo value={data.default_working_location}
                onChange={(v) => onFieldChange('default_working_location', v)}/>
              <div className="help flow"><I n="info" s={13} className="ico"/><span>Injected into the <strong>policy evaluation engine</strong> — affects which policies are triggered for each case.</span></div>
            </div>
          </div>
        </div>
      </div>

      {/* Section D — Branding */}
      <div className={`hp-section${initialZoom === 'D' ? ' zoom' : ''}`}>
        <SectionHeader marker="D" title="Branding"
          sub="Your logo and colours appear across the entire platform."
          status={secStatus.D} complete={sectionComplete('D')}/>
        <div className="hp-section-bd">
          <div className="hp-logo">
            <LogoDropzone
              uploaded={logoState === 'uploaded'}
              uploading={logoState === 'uploading'}
              error={logoError}
              dragHover={dragHover}
              onRequestUpload={simulateUpload}
              onSetDrag={setDragHover}
            />
            <div className="hp-logo-side">
              <div className="t">Company logo</div>
              <div className="s">PNG, JPG or SVG · max 2 MB · square 512×512 recommended for best quality.</div>
              {logoState === 'uploaded' && (
                <div className="hp-logo-actions">
                  <button onClick={simulateUpload}><I n="upload" s={12}/> Replace</button>
                  <button className="danger" onClick={removeLogo}><I n="x" s={12}/> Remove</button>
                </div>
              )}
              {logoError && <div className="hp-logo-err"><I n="alert" s={13}/> {logoError}</div>}
              <div className="hp-logo-hint">
                <I n="info" s={13} className="ico"/>
                <span><strong>Your logo appears in the header</strong> on every page of the platform, visible to both HR managers and employees.</span>
              </div>
            </div>
          </div>

          <div style={{ marginTop: 22 }}>
            <div className="hp-field" style={{ maxWidth: 480 }}>
              <label>Brand colour</label>
              <ColorSwatches value={data.brand_color}
                onChange={(v) => onFieldChange('brand_color', v)}/>
              <div className="help">Used as the accent colour in highlight states and case headers.</div>
            </div>
          </div>
        </div>
      </div>
      </div>
      {/* Sticky save bar */}
      <div className="hp-saver">
        <span className="status">
          {Object.values(secStatus).every(s => s === 'saved')
            ? <><span className="badge saved"><I n="check2" s={10}/> All changes saved</span> <span>Auto-saved 3 seconds ago</span></>
            : Object.values(secStatus).some(s => s === 'saving')
              ? <><span className="badge">Saving…</span> <span>Auto-saving as you go</span></>
              : <><span className="badge">Unsaved changes</span> <span>Auto-save in a moment</span></>}
        </span>
        <button className="btn"><I n="arrowL" s={12}/> Back to mobility control</button>
        <button className="btn primary"><I n="check" s={12}/> Save profile</button>
      </div>
    </div>
  );
}

// ── Page header ───────────────────────────────────────────────────
function PageHeader({ data, completion, mode }) {
  return (
    <div className="page-hd">
      <div className="page-eyebrow">HR · /hr/company-profile</div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12 }}>
        <h1 className="page-h">Company profile</h1>
        <div style={{ flex: 1 }}/>
        <span className="hp-complete-chip">
          <span className="ring">
            <CompletionRing pct={completion}/>
          </span>
          {completion}% complete
        </span>
      </div>
      <div className="hp-meta">
        <span className="hp-readonly active">Active</span>
        <span className="hp-readonly medium"><span className="lbl">Plan</span> Medium</span>
        <span className="hp-readonly"><span className="lbl">Tenant ID</span> <code style={{ fontFamily:'var(--mono)', fontSize:10.5 }}>co_aurora</code></span>
      </div>
      <div className="page-sub">
        Identity, defaults and branding for your workspace. Saved fields automatically flow into every relocation case and the policy engine.
      </div>
    </div>
  );
}

// ── Sub-nav strip at top of HR area ──────────────────────────────
function ProfileSubNav({ active }) {
  const setRoute = (r) => window.dispatchEvent(new CustomEvent('platform-set-route', { detail: r }));
  const pendingExc = (window.PLATFORM_EXCEPTIONS || []).filter(e => e.status === 'pending').length;
  return (
    <div className="hr-subnav">
      <div className={`hr-subnav-tab${active === 'control' ? ' active' : ''}`}
           onClick={() => setRoute('s7')}>
        <I n="globe" s={13}/>
        Mobility control
        <span className="ct">12</span>
      </div>
      <div className={`hr-subnav-tab${active === 'exceptions' ? ' active' : ''}`}
           onClick={() => setRoute('s7e')}>
        <I n="alert" s={13}/>
        Exceptions
        {pendingExc > 0 && <span className="ct" style={{ background: 'var(--warning-soft)', color: 'var(--warning)' }}>{pendingExc}</span>}
      </div>
      <div className={`hr-subnav-tab${active === 'profile' ? ' active' : ''}`}
           onClick={() => setRoute('s7p')}>
        <I n="briefcase" s={13}/>
        Company profile
      </div>
      <div className={`hr-subnav-tab${active === 'policy' ? ' active' : ''}`}
           onClick={() => setRoute('s5')}>
        <I n="shield" s={13}/>
        Policy &amp; benefits
      </div>
    </div>
  );
}

// ── Field primitives ─────────────────────────────────────────────
function FieldText({ label, value, onChange, placeholder, hint, required, optional, fullWidth }) {
  return (
    <div className={`hp-field${fullWidth ? ' full' : ''}`}>
      <label>{label}</label>
      <input className="hp-input" type="text" value={value || ''} placeholder={placeholder}
             onChange={(e) => onChange(e.target.value)}/>
      {hint && (typeof hint === 'string' ? <div className="help">{hint}</div> : <div className="help">{hint}</div>)}
    </div>
  );
}
function FieldEmail({ label, value, onChange, placeholder, hint, required, optional }) {
  return (
    <div className="hp-field">
      <label>{label}</label>
      <input className="hp-input" type="email" value={value || ''} placeholder={placeholder}
             onChange={(e) => onChange(e.target.value)}/>
      {hint && <div>{typeof hint === 'string' ? <div className="help">{hint}</div> : hint}</div>}
    </div>
  );
}
function FieldUrl({ label, value, onChange, placeholder, hint, required, optional }) {
  return (
    <div className="hp-field">
      <label>{label}</label>
      <div className="hp-input-prefix">
        <span className="prefix">https://</span>
        <input className="hp-input with-prefix" type="text" value={value || ''} placeholder={placeholder}
               onChange={(e) => onChange(e.target.value)}/>
      </div>
      {hint && <div className="help">{hint}</div>}
    </div>
  );
}
function FieldSelect({ label, value, onChange, options, labels, hint, required, optional }) {
  return (
    <div className="hp-field">
      <label>{label}</label>
      <select className="hp-select" value={value || ''} onChange={(e) => onChange(e.target.value)}>
        {options.map((o, i) => (
          <option key={o || `__${i}`} value={o}>{labels?.[i] || o || 'Select…'}</option>
        ))}
      </select>
      {hint && <div className="help" dangerouslySetInnerHTML={typeof hint === 'string' ? { __html: hint } : undefined}>{typeof hint !== 'string' ? hint : null}</div>}
    </div>
  );
}

// ── 3-step Wizard ────────────────────────────────────────────────
function Wizard({ data, onChange, onUpdate, onCancel, onComplete, logoState, simulateUpload, removeLogo, dragHover, setDragHover }) {
  const [step, setStep] = useState(0);
  const STEPS = [
    { id: 0, lbl: 'Identity',     sub: 'Name &amp; basics' },
    { id: 1, lbl: 'Location',     sub: 'Where you are' },
    { id: 2, lbl: 'Defaults &amp; brand', sub: 'Mobility + logo' },
  ];

  return (
    <div className="page wide">
      <ProfileSubNav active="profile"/>
      <div className="page-hd">
        <div className="page-eyebrow">HR · setup wizard</div>
        <h1 className="page-h">Set up your company profile</h1>
        <div className="page-sub">A few quick questions. You can edit anything later.</div>
      </div>

      <div className="hp-wizard">
        <div className="hp-wizard-hd">
          <div>
            <div className="t">{STEPS[step].lbl}</div>
            <div className="s" dangerouslySetInnerHTML={{ __html: STEPS[step].sub }}/>
          </div>
          <div className="step-of">{step + 1} / {STEPS.length}</div>
        </div>

        <div className="hp-stepper">
          {STEPS.map((s, i) => (
            <div key={s.id} className={`hp-step${i === step ? ' active' : i < step ? ' done' : ''}`}>
              <div className="num"><span>{i + 1}</span></div>
              <div className="lbl">
                {s.lbl.replace(/&amp;/g, '&')}
                <div className="sub" dangerouslySetInnerHTML={{ __html: s.sub }}/>
              </div>
            </div>
          ))}
        </div>

        <div className="hp-wizard-body">
          {step === 0 && (
            <div className="hp-grid">
              <FieldText label="Company name" required value={data.name}
                onChange={(v) => onChange('name', v)} placeholder="e.g. Aurora Energy"/>
              <FieldText label="Legal name" optional value={data.legal_name}
                onChange={(v) => onChange('legal_name', v)} placeholder="e.g. Aurora Energy AS"/>
              <FieldSelect label="Industry" optional value={data.industry}
                onChange={(v) => onChange('industry', v)}
                options={['', ...INDUSTRIES]} labels={['Select…', ...INDUSTRIES]}/>
              <FieldSelect label="Company size band" optional value={data.size_band}
                onChange={(v) => onChange('size_band', v)}
                options={['', ...SIZE_BANDS]} labels={['Select…', ...SIZE_BANDS]}/>
              <FieldUrl label="Website" optional fullWidth value={data.website}
                onChange={(v) => onChange('website', v)} placeholder="aurora-energy.com"/>
            </div>
          )}
          {step === 1 && (
            <div className="hp-grid">
              <div className="hp-field">
                <label>Country of incorporation</label>
                <CountryCombo value={data.country} onChange={(v) => onChange('country', v)}/>
                <div className="help">Pre-fills as employer country in every new relocation case.</div>
              </div>
              <FieldText label="HQ city" optional value={data.hq_city}
                onChange={(v) => onChange('hq_city', v)} placeholder="Paris"/>
              <FieldText label="Address" optional fullWidth value={data.address}
                onChange={(v) => onChange('address', v)} placeholder="Street, city, postal code"/>
              <FieldText label="Phone" optional value={data.phone}
                onChange={(v) => onChange('phone', v)} placeholder="+33 …"/>
            </div>
          )}
          {step === 2 && (
            <>
              <div className="hp-grid" style={{ marginBottom: 22 }}>
                <FieldText label="HR contact" optional value={data.hr_contact}
                  onChange={(v) => onChange('hr_contact', v)} placeholder="Name or email"/>
                <FieldEmail label="Support email" optional value={data.support_email}
                  onChange={(v) => onChange('support_email', v)} placeholder="mobility@yourco.com"
                  hint="Employees see this in their portal."/>
                <div className="hp-field">
                  <label>Default destination country</label>
                  <CountryCombo value={data.default_destination_country}
                    onChange={(v) => onChange('default_destination_country', v)}
                    placeholder="Most common destination"/>
                  <div className="help">Seeds new cases &amp; drives supplier matching.</div>
                </div>
                <div className="hp-field">
                  <label>Default working location</label>
                  <LocationCombo value={data.default_working_location}
                    onChange={(v) => onChange('default_working_location', v)}/>
                  <div className="help">Used by the policy engine.</div>
                </div>
              </div>
              <div className="hp-logo" style={{ marginBottom: 20 }}>
                <LogoDropzone
                  uploaded={logoState === 'uploaded'}
                  uploading={logoState === 'uploading'}
                  dragHover={dragHover}
                  onRequestUpload={simulateUpload}
                  onSetDrag={setDragHover}
                />
                <div className="hp-logo-side">
                  <div className="t">Upload your logo</div>
                  <div className="s">PNG, JPG or SVG · max 2 MB · square 512×512 recommended.</div>
                  {logoState === 'uploaded' && (
                    <div className="hp-logo-actions">
                      <button onClick={simulateUpload}><I n="upload" s={12}/> Replace</button>
                      <button className="danger" onClick={removeLogo}><I n="x" s={12}/> Remove</button>
                    </div>
                  )}
                </div>
              </div>
              <div className="hp-field" style={{ maxWidth: 420 }}>
                <label>Brand colour</label>
                <ColorSwatches value={data.brand_color}
                  onChange={(v) => onChange('brand_color', v)}/>
              </div>
            </>
          )}
        </div>

        <div className="hp-wizard-foot">
          <button className="hp-wizard-btn ghost" onClick={onCancel}>Cancel</button>
          <div className="spc"/>
          {step > 0 && <button className="hp-wizard-btn" onClick={() => setStep(s => s - 1)}>← Back</button>}
          {step < STEPS.length - 1 && (
            <button className="hp-wizard-btn primary" onClick={() => setStep(s => s + 1)}>
              Continue →
            </button>
          )}
          {step === STEPS.length - 1 && (
            <button className="hp-wizard-btn primary" onClick={onComplete}>
              Finish setup
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

window.CompanyProfileScreen = CompanyProfileScreen;
window.ProfileSubNav = ProfileSubNav;
})();
