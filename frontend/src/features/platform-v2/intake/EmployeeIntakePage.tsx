import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../../../components/AppShell';
import { Button } from '../../../components/antigravity/Button';
import { Input } from '../../../components/antigravity/Input';
import { patchCase } from '../../../api/cases';
import { apiGet, apiPost, employeeAPI } from '../../../api/client';
import { ROUTE_DEFS } from '../../../navigation/routes';
import { useEmployeeAssignment } from '../../../contexts/EmployeeAssignmentContext';
import { getAuthItem } from '../../../utils/demo';
import { MultiChip } from './MultiChip';
import { PrivacyNotice } from '../../privacy/PrivacyNotice';
import { PRIVACY_NOTICE_VERSION } from '../../privacy/privacyNoticeContent';

// ─── Types ────────────────────────────────────────────────────────────────────

type MemberKind = 'self' | 'partner' | 'child' | 'pet' | 'adult';

interface Member {
  id: string;
  kind: MemberKind;
  // partner
  name?: string;
  employment?: string;
  needs_work_permit?: string;
  lang_level?: string;
  // child
  dob?: string;
  school?: string;
  // pet
  pet_type?: string;        // maps to species in backend
  breed?: string;
  count?: number;
  rabies?: string;
  microchipped?: string;
  notes?: string;
  // pet — extended fields (AIQ-160-C)
  microchip_number?: string;
  date_of_birth?: string;
  passport_number?: string;
  health_cert_expiry?: string;
  vaccinations_json?: string;   // JSON stringified: [{vax_name, vax_date, vax_expiry}]
  vet_name?: string;
  vet_phone?: string;
  vet_country?: string;
  // adult
  full_name?: string;
  relationship?: string;
  care_level?: string;
}

interface HousingPrefs {
  intent?: string;
  bedrooms?: number | '';
  budget?: number | '';
  school_type?: string;
  special_needs?: string;
  school_start?: string;
}

interface IntakeData {
  origin_country: string;
  origin_city: string;
  dest_country: string;
  dest_city: string;
  target_date: string;
  purpose: string;
  full_name: string;
  email: string;
  nationality: string;
  passport_country: string;
  passport_expiry: string;
  members: Member[];
  job_title: string;
  contract_type: string;
  contract_start: string;
  salary_band: string;
  office_address: string;
  work_pattern: string;
  commute_mins: number;
  commute_mode: string[];
  services: string[];
  service_notes: Record<string, string>;
  housing_prefs: HousingPrefs;
  consent: boolean;
}

// ─── Static data ──────────────────────────────────────────────────────────────

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
  { code: 'IN', name: 'India',          flag: '🇮🇳' },
  { code: 'SG', name: 'Singapore',      flag: '🇸🇬' },
  { code: 'AE', name: 'United Arab Emirates', flag: '🇦🇪' },
  { code: 'AU', name: 'Australia',      flag: '🇦🇺' },
  { code: 'BR', name: 'Brazil',         flag: '🇧🇷' },
];

const CITIES_BY_COUNTRY: Record<string, string[]> = {
  FR: ['Paris', 'Lyon', 'Marseille', 'Toulouse', 'Nice', 'Bordeaux'],
  DE: ['Berlin', 'Munich', 'Hamburg', 'Frankfurt', 'Cologne'],
  GB: ['London', 'Manchester', 'Birmingham', 'Edinburgh'],
  NO: ['Oslo', 'Bergen', 'Stavanger', 'Trondheim'],
  US: ['New York', 'San Francisco', 'Los Angeles', 'Chicago', 'Austin'],
  CA: ['Toronto', 'Vancouver', 'Montreal'],
  JP: ['Tokyo', 'Osaka', 'Kyoto'],
  IN: ['Mumbai', 'Bangalore', 'Delhi'],
  SG: ['Singapore'],
  AE: ['Dubai', 'Abu Dhabi'],
  NL: ['Amsterdam', 'Rotterdam', 'The Hague'],
  CH: ['Zurich', 'Geneva', 'Basel'],
  AU: ['Sydney', 'Melbourne', 'Brisbane'],
};

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

// Empty defaults. The wizard previously shipped a hardcoded demo persona
// (Marc Bouchard, France → Norway, fake family + address). That diverged
// from the case row on the hub (which reads `relocation_cases.host_country`
// — e.g. "Germany"), and rendered every field with a misleading
// "🔒 HR pre-filled" badge. Real values now come from three places, in
// priority order: the user's persisted draft (if any), the case row's
// destination + origin via `linkedSummaries`, and the user's login email.
const INITIAL_DATA: IntakeData = {
  origin_country: '',
  origin_city: '',
  dest_country: '',
  dest_city: '',
  target_date: '',
  purpose: 'Employment',
  full_name: '',
  email: '',
  nationality: '',
  passport_country: '',
  passport_expiry: '',
  // The employee themselves is always in the household — partner / kids /
  // pets are added via the "Add member" controls on step 3.
  members: [{ id: 'self', kind: 'self' }],
  job_title: '',
  contract_type: '',
  contract_start: '',
  salary_band: '',
  office_address: '',
  work_pattern: '',
  commute_mins: 30,
  commute_mode: [],
  services: [],
  service_notes: {},
  housing_prefs: {},
  consent: false,
};

// Normalise a country reference from the case row (which may be stored as
// "Germany" or "DE" depending on the HR input path) to the 2-letter code
// the wizard's CountryCombo expects. Falls back to the input as-is when
// no match — better to surface an unknown value than silently swallow it.
function countryNameToCode(input: string | null | undefined): string {
  if (!input) return '';
  const s = input.trim();
  if (s.length === 2) return s.toUpperCase();
  const lower = s.toLowerCase();
  const match = COUNTRIES.find((c) => c.name.toLowerCase() === lower);
  return match ? match.code : s;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function computeAge(dob?: string): number | null {
  if (!dob) return null;
  const d = new Date(dob);
  if (isNaN(d.getTime())) return null;
  return Math.floor((Date.now() - d.getTime()) / (1000 * 60 * 60 * 24 * 365.25));
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function FieldWrap({
  label,
  required,
  optional,
  hint,
  prefill,
  onUnlock,
  why,
  className = '',
  children,
}: {
  label: string;
  required?: boolean;
  optional?: boolean;
  hint?: string;
  prefill?: boolean;
  onUnlock?: () => void;
  why?: string;
  className?: string;
  children: React.ReactNode;
}) {
  const [whyOpen, setWhyOpen] = useState(false);
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-700 flex-wrap">
        {label}
        {required && <span className="text-red-500" title="Required">*</span>}
        {optional && <span className="text-gray-400 font-normal">(optional)</span>}
        {prefill && (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-accent-100 text-accent-700 text-[10px] font-medium">
            🔒 HR pre-filled
            {onUnlock && (
              <Button unstyled type="button" onClick={onUnlock} className="underline text-accent-500 hover:text-accent-700 ml-0.5">
                Edit
              </Button>
            )}
          </span>
        )}
        {why && (
          <Button unstyled type="button" onClick={() => setWhyOpen((o) => !o)} className="text-accent-500 text-[10px] font-medium hover:text-accent-700">
            Why?
          </Button>
        )}
      </label>
      {children}
      {whyOpen && why && (
        <div className="text-xs text-gray-500 bg-accent-50 border border-accent-100 rounded-lg px-3 py-2">{why}</div>
      )}
      {hint && <div className="text-xs text-gray-400">{hint}</div>}
    </div>
  );
}

const inputCls = (locked?: boolean) =>
  `w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300 ${
    locked ? 'bg-gray-50 text-gray-400 border-gray-100 cursor-not-allowed' : 'border-gray-200 bg-white'
  }`;

const selectCls = (locked?: boolean) =>
  `w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300 ${
    locked ? 'bg-gray-50 text-gray-400 border-gray-100 cursor-not-allowed' : 'border-gray-200 bg-white'
  }`;

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">{children}</div>;
}

function CountryCombo({ value, onChange, placeholder = 'Select a country', disabled }: {
  value: string; onChange: (v: string) => void; placeholder?: string; disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const selected = COUNTRIES.find((c) => c.code === value);
  const filtered = query
    ? COUNTRIES.filter((c) => c.name.toLowerCase().includes(query.toLowerCase()) || c.code.toLowerCase().includes(query.toLowerCase()))
    : COUNTRIES;

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <div className={`flex items-center border rounded-lg overflow-hidden ${disabled ? 'bg-gray-50 border-gray-100' : 'border-gray-200 bg-white'}`}>
        <span className="px-3 text-base">{selected ? selected.flag : '🔍'}</span>
        <Input unstyled
          type="text"
          className="flex-1 py-2 pr-3 text-sm focus:outline-none bg-transparent"
          value={open ? query : selected ? selected.name : ''}
          placeholder={placeholder}
          disabled={disabled}
          onChange={(v) => { setQuery(v); setOpen(true); }}
          onFocus={() => { if (!disabled) { setQuery(''); setOpen(true); } }}
          autoComplete="off"
        />
        <span className="px-2 text-gray-400 text-xs">▾</span>
      </div>
      {open && !disabled && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-white border border-gray-200 rounded-xl shadow-lg">
          {filtered.length === 0
            ? <div className="px-4 py-3 text-xs text-gray-400">No match</div>
            : filtered.map((c) => (
              <div key={c.code} onClick={() => { onChange(c.code); setOpen(false); setQuery(''); }}
                className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer text-sm hover:bg-gray-50 ${value === c.code ? 'bg-accent-50 text-accent-700' : ''}`}>
                <span className="text-base">{c.flag}</span>
                <span className="flex-1">{c.name}</span>
                <span className="text-xs text-gray-400">{c.code}</span>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

function CityCombo({ country, value, onChange }: { country: string; value: string; onChange: (v: string) => void }) {
  const opts = CITIES_BY_COUNTRY[country] ?? [];
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);
  return (
    <div ref={ref} className="relative">
      <div className="flex items-center border border-gray-200 rounded-lg bg-white overflow-hidden">
        <span className="px-3 text-gray-400 text-sm">📍</span>
        <Input unstyled type="text" value={value} placeholder="Select or type a city" autoComplete="off"
          className="flex-1 py-2 pr-3 text-sm focus:outline-none bg-transparent"
          onChange={(v) => onChange(v)}
          onFocus={() => setOpen(true)} />
        <span className="px-2 text-gray-400 text-xs">▾</span>
      </div>
      {open && opts.length > 0 && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 max-h-40 overflow-y-auto bg-white border border-gray-200 rounded-xl shadow-lg">
          {opts.map((c) => (
            <div key={c} onClick={() => { onChange(c); setOpen(false); }}
              className="px-4 py-2.5 cursor-pointer text-sm hover:bg-gray-50">{c}</div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Commute map (SVG) ────────────────────────────────────────────────────────

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

function CommuteMap({ maxMins, mode }: { maxMins: number; mode: string[] }) {
  const radius = Math.min(50, (maxMins / 60) * 50 + 5);
  const cx = 50, cy = 48;
  const inCount = NEIGHBORHOODS.filter((n) => n.t_min <= maxMins).length;
  return (
    <div className="relative rounded-xl overflow-hidden border border-gray-100 bg-gray-950">
      <span className="absolute top-2 right-2 z-10 flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent-600 text-white text-[10px] font-medium">
        <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse inline-block" /> live
      </span>
      <svg viewBox="0 0 100 100" className="w-full h-48" preserveAspectRatio="xMidYMid meet" aria-hidden>
        {[20, 40, 60, 80].map((v) => (
          <g key={`g${v}`}>
            <line x1={v} y1={0} x2={v} y2={100} stroke="#1f2937" strokeWidth="0.3" />
            <line x1={0} y1={v} x2={100} y2={v} stroke="#1f2937" strokeWidth="0.3" />
          </g>
        ))}
        <circle cx={cx} cy={cy} r={radius} fill="rgba(31, 142, 139,0.12)" stroke="rgba(31, 142, 139,0.4)" strokeWidth="0.6" />
        {NEIGHBORHOODS.map((n) => {
          const inside = n.t_min <= maxMins;
          return (
            <g key={n.id}>
              <circle cx={n.x} cy={n.y} r="3.5" fill={inside ? '#1f8e8b' : '#374151'} />
              <text x={n.x} y={n.y + 7} textAnchor="middle" fontSize="3.5"
                fill={inside ? '#6ec0bd' : '#6b7280'}>{n.name}</text>
            </g>
          );
        })}
        <circle cx={cx} cy={cy} r="8" fill="rgba(31, 142, 139,0.2)" stroke="#1f8e8b" strokeWidth="1" />
        <circle cx={cx} cy={cy} r="2.5" fill="#1f8e8b" />
        <text x={cx} y={cy - 5} textAnchor="middle" fontSize="3" fill="#6ec0bd">Office</text>
      </svg>
      <div className="absolute bottom-2 left-0 right-0 text-center text-[10px] text-gray-400">
        <strong className="text-accent-400">{inCount} neighborhoods</strong> within {maxMins}min
        {mode.length > 0 ? ` by ${mode.slice(0, 2).map((m) => m === 'public_transit' ? 'transit' : m).join('/')}` : ''}
      </div>
    </div>
  );
}

// ─── Household member cards ───────────────────────────────────────────────────

function CardShell({ ico, title, sub, status, expanded, onToggle, onRemove, urgent, children }: {
  ico: string; title: string; sub: string;
  status: 'complete' | 'partial' | 'empty';
  expanded: boolean; onToggle: () => void; onRemove?: () => void;
  urgent?: boolean; children: React.ReactNode;
}) {
  const statusCls = { complete: 'text-green-600 bg-green-50', partial: 'text-amber-600 bg-amber-50', empty: 'text-gray-400 bg-gray-50' };
  const statusLbl = { complete: '✓ Complete', partial: 'In progress', empty: 'Not started' };
  return (
    <div className={`border rounded-xl overflow-hidden ${urgent ? 'border-amber-200' : 'border-gray-100'} bg-white`}>
      <Button unstyled type="button" onClick={onToggle} className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition-colors text-left">
        <span className="text-xl flex-shrink-0">{ico}</span>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-gray-900 truncate">{title}</div>
          <div className="text-xs text-gray-400 truncate">{sub}</div>
        </div>
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${statusCls[status]}`}>{statusLbl[status]}</span>
        <span className={`text-gray-400 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}>▾</span>
        {onRemove && (
          <Button unstyled type="button" onClick={(e) => { e.stopPropagation(); onRemove(); }}
            className="ml-1 text-gray-300 hover:text-red-400 transition-colors text-sm font-bold">✕</Button>
        )}
      </Button>
      {expanded && <div className="px-4 pb-4 border-t border-gray-100">{children}</div>}
    </div>
  );
}

function PartnerCard({ m, onChange, onRemove, international, expanded, onToggle }: {
  m: Member; onChange: (m: Member) => void; onRemove: () => void;
  international: boolean; expanded: boolean; onToggle: () => void;
}) {
  const status: 'complete' | 'partial' | 'empty' = m.name && m.employment ? 'complete' : m.name || m.employment ? 'partial' : 'empty';
  return (
    <CardShell ico="👤" title={`Partner / Spouse${m.name ? ` · ${m.name}` : ''}`}
      sub={m.employment || 'Tell us about your partner'} status={status}
      expanded={expanded} onToggle={onToggle} onRemove={onRemove}>
      <Grid>
        <FieldWrap label="Full name" required>
          <Input unstyled className={inputCls()} value={m.name ?? ''} placeholder="e.g. Camille Bouchard"
            onChange={(v) => onChange({ ...m, name: v })} />
        </FieldWrap>
        <FieldWrap label="Employment status">
          <select className={selectCls()} value={m.employment ?? ''} onChange={(e) => onChange({ ...m, employment: e.target.value })}>
            <option value="">Select…</option>
            <option>Working</option><option>Not working</option><option>Student</option>
          </select>
        </FieldWrap>
        {international && m.employment === 'Working' && (
          <FieldWrap label="Need a work permit at destination?" why="If yes, we'll add the dependent work-permit track and surface partner career services.">
            <select className={selectCls()} value={m.needs_work_permit ?? ''} onChange={(e) => onChange({ ...m, needs_work_permit: e.target.value })}>
              <option value="">Select…</option><option>Yes</option><option>No</option><option>Not sure</option>
            </select>
          </FieldWrap>
        )}
        <FieldWrap label="Language level at destination">
          <select className={selectCls()} value={m.lang_level ?? ''} onChange={(e) => onChange({ ...m, lang_level: e.target.value })}>
            <option value="">Select…</option>
            <option>Fluent</option><option>Conversational</option><option>Beginner</option><option>None</option>
          </select>
        </FieldWrap>
      </Grid>
    </CardShell>
  );
}

function ChildCard({ m, onChange, onRemove, index, expanded, onToggle }: {
  m: Member; onChange: (m: Member) => void; onRemove: () => void;
  index: number; expanded: boolean; onToggle: () => void;
}) {
  const age = computeAge(m.dob);
  const schoolLvl = age == null ? '' : age < 6 ? 'pre-school' : age < 11 ? 'primary' : age < 15 ? 'middle' : 'secondary';
  const status: 'complete' | 'partial' | 'empty' = m.name && m.dob && m.school ? 'complete' : m.name || m.dob ? 'partial' : 'empty';
  return (
    <CardShell ico="🧒"
      title={`Child ${index + 1}${m.name ? ` · ${m.name}` : ''}${age != null ? ` · ${age}y` : ''}`}
      sub={m.school ? `${m.school} school` : 'Date of birth + school preference'}
      status={status} expanded={expanded} onToggle={onToggle} onRemove={onRemove}>
      <Grid>
        <FieldWrap label="First name" required>
          <Input unstyled className={inputCls()} value={m.name ?? ''} placeholder="e.g. Léo"
            onChange={(v) => onChange({ ...m, name: v })} />
        </FieldWrap>
        <FieldWrap label="Date of birth" required why="We compute age automatically for school search and enrollment timing.">
          <Input unstyled type="date" className={inputCls()} value={m.dob ?? ''}
            onChange={(v) => onChange({ ...m, dob: v })} />
          {age != null && (
            <div className="text-[10px] text-accent-600 mt-0.5">✦ {age} years old · {schoolLvl}</div>
          )}
        </FieldWrap>
        <FieldWrap label="School type preference" className="sm:col-span-2">
          <MultiChip value={m.school ? [m.school] : []} onChange={([v]) => onChange({ ...m, school: v })}
            options={['Public', 'Private', 'International', 'Bilingual', 'Not sure yet']} />
        </FieldWrap>
      </Grid>
    </CardShell>
  );
}


// ─── Pet card ─────────────────────────────────────────────────────────────────

type VaxEntry = { vax_name: string; vax_date: string; vax_expiry: string };

function PetCard({ m, onChange, onRemove, index, expanded, onToggle }: {
  m: Member; onChange: (m: Member) => void; onRemove: () => void;
  index: number; expanded: boolean; onToggle: () => void;
}) {
  const vaccinations: VaxEntry[] = (() => {
    try { return JSON.parse(m.vaccinations_json || '[]'); } catch { return []; }
  })();

  const setVax = (next: VaxEntry[]) => onChange({ ...m, vaccinations_json: JSON.stringify(next) });
  const addVax = () => setVax([...vaccinations, { vax_name: '', vax_date: '', vax_expiry: '' }]);
  const updateVax = (i: number, field: keyof VaxEntry, value: string) =>
    setVax(vaccinations.map((v, idx) => idx === i ? { ...v, [field]: value } : v));
  const removeVax = (i: number) => setVax(vaccinations.filter((_, idx) => idx !== i));

  const status: 'complete' | 'partial' | 'empty' =
    m.name && m.pet_type ? 'complete' : m.name || m.pet_type ? 'partial' : 'empty';

  return (
    <CardShell ico="🐾"
      title={`Pet ${index + 1}${m.name ? ` · ${m.name}` : ''}${m.pet_type ? ` (${m.pet_type})` : ''}`}
      sub={m.breed ? m.breed : m.pet_type ? m.pet_type : 'Name + species required'}
      status={status} expanded={expanded} onToggle={onToggle} onRemove={onRemove}>

      <Grid>
        <FieldWrap label="Pet name">
          <Input unstyled className={inputCls()} value={m.name ?? ''} placeholder="e.g. Luna"
            onChange={(v) => onChange({ ...m, name: v })} />
        </FieldWrap>
        <FieldWrap label="Species" required>
          <select className={selectCls()} value={m.pet_type ?? ''}
            onChange={(e) => onChange({ ...m, pet_type: e.target.value })}>
            <option value="">Select…</option>
            <option value="dog">Dog</option>
            <option value="cat">Cat</option>
            <option value="bird">Bird</option>
            <option value="rabbit">Rabbit</option>
            <option value="other">Other</option>
          </select>
        </FieldWrap>
        <FieldWrap label="Breed">
          <Input unstyled className={inputCls()} value={m.breed ?? ''} placeholder="e.g. Labrador"
            onChange={(v) => onChange({ ...m, breed: v })} />
        </FieldWrap>
        <FieldWrap label="Microchip number" why="Required by most countries — usually a 15-digit ISO chip.">
          <Input unstyled className={inputCls()} value={m.microchip_number ?? ''} placeholder="e.g. 985112345678901"
            onChange={(v) => onChange({ ...m, microchip_number: v })} />
        </FieldWrap>
        <FieldWrap label="Date of birth">
          <Input unstyled type="date" className={inputCls()} value={m.date_of_birth ?? ''}
            onChange={(v) => onChange({ ...m, date_of_birth: v })} />
        </FieldWrap>
        <FieldWrap label="Passport / pet book number">
          <Input unstyled className={inputCls()} value={m.passport_number ?? ''} placeholder="e.g. 900123456"
            onChange={(v) => onChange({ ...m, passport_number: v })} />
        </FieldWrap>
        <FieldWrap label="Health cert expiry" why="Many countries require a cert issued within 10 days of travel.">
          <Input unstyled type="date" className={inputCls()} value={m.health_cert_expiry ?? ''}
            onChange={(v) => onChange({ ...m, health_cert_expiry: v })} />
        </FieldWrap>
      </Grid>

      {/* Vaccinations */}
      <div className="mt-4">
        <div className="text-xs font-semibold text-gray-600 mb-2">Vaccinations</div>
        {vaccinations.length > 0 && (
          <div className="space-y-2 mb-2">
            {vaccinations.map((vax, i) => (
              <div key={i} className="flex gap-2 items-center">
                <Input unstyled className={`${inputCls()} flex-1`} value={vax.vax_name} placeholder="Vaccine name"
                  onChange={(v) => updateVax(i, 'vax_name', v)} />
                <Input unstyled type="date" className={`${inputCls()} flex-1`} value={vax.vax_date}
                  title="Date given"
                  onChange={(v) => updateVax(i, 'vax_date', v)} />
                <Input unstyled type="date" className={`${inputCls()} flex-1`} value={vax.vax_expiry}
                  title="Expiry date"
                  onChange={(v) => updateVax(i, 'vax_expiry', v)} />
                <Button unstyled type="button" onClick={() => removeVax(i)}
                  className="text-gray-300 hover:text-red-400 text-sm font-bold flex-shrink-0">✕</Button>
              </div>
            ))}
          </div>
        )}
        <Button unstyled type="button" onClick={addVax}
          className="text-xs text-accent-600 hover:text-accent-800 font-semibold">
          + Add vaccination
        </Button>
      </div>

      {/* Vet information */}
      <div className="mt-4">
        <div className="text-xs font-semibold text-gray-600 mb-2">Vet information</div>
        <Grid>
          <FieldWrap label="Vet name">
            <Input unstyled className={inputCls()} value={m.vet_name ?? ''} placeholder="e.g. Dr. Smith"
              onChange={(v) => onChange({ ...m, vet_name: v })} />
          </FieldWrap>
          <FieldWrap label="Vet phone">
            <Input unstyled className={inputCls()} value={m.vet_phone ?? ''} placeholder="+33 6 12 34 56 78"
              onChange={(v) => onChange({ ...m, vet_phone: v })} />
          </FieldWrap>
          <FieldWrap label="Vet country">
            <select className={selectCls()} value={m.vet_country ?? ''}
              onChange={(e) => onChange({ ...m, vet_country: e.target.value })}>
              <option value="">Select…</option>
              {COUNTRIES.map((c) => (
                <option key={c.code} value={c.code}>{c.flag} {c.name}</option>
              ))}
            </select>
          </FieldWrap>
        </Grid>
      </div>
    </CardShell>
  );
}

// ─── Step components ──────────────────────────────────────────────────────────

function StepHd({ title, sub, required }: { title: string; sub: string; required?: boolean }) {
  return (
    <div className="mb-5">
      <div className="text-base font-bold text-gray-900">{title}</div>
      <div className="text-sm text-gray-500 mt-0.5">{sub}</div>
      {required && <div className="text-xs text-gray-400 mt-1"><span className="text-red-400">*</span> required field</div>}
    </div>
  );
}

// ─── Quote request panel (WZ4) ────────────────────────────────────────────────

function QuoteRequestPanel({ caseId, services }: { caseId: string; services: string[] }) {
  const [notes, setNotes] = useState('');
  const [budgetRange, setBudgetRange] = useState('');
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSend = async () => {
    if (sending || sent) return;
    setSending(true);
    setError(null);
    try {
      await apiPost(`/api/cases/${caseId}/quote-request`, {
        services,
        notes: notes || undefined,
        budget_range: budgetRange || undefined,
      });
      setSent(true);
    } catch (e) {
      setError((e as Error).message ?? 'Failed to send request');
    } finally {
      setSending(false);
    }
  };

  if (sent) {
    return (
      <div className="mt-3 flex items-start gap-2 p-3 bg-green-50 border border-green-100 rounded-xl text-xs text-green-700">
        ✅ <span>Quote request sent — your HR team will be in touch.</span>
      </div>
    );
  }

  return (
    <div className="mt-3 border border-gray-100 rounded-xl p-4 bg-white">
      <div className="text-xs font-bold text-gray-700 mb-3">📋 Request vendor quotes</div>
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-semibold text-gray-600">Notes <span className="text-gray-400 font-normal">(optional)</span></label>
          <textarea rows={2} className="w-full rounded-lg border border-gray-200 px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-accent-300 resize-none"
            placeholder="Any specific requirements or context for the vendor…"
            value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-semibold text-gray-600">Budget range <span className="text-gray-400 font-normal">(optional)</span></label>
          <Input unstyled type="text" className="w-full rounded-lg border border-gray-200 px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-accent-300"
            placeholder="e.g. 5 000–10 000 €"
            value={budgetRange} onChange={(v) => setBudgetRange(v)} />
        </div>
        {error && <p className="text-xs text-red-500">{error}</p>}
        <Button unstyled type="button" onClick={handleSend} disabled={sending}
          className="self-start px-4 py-2 text-xs font-semibold rounded-lg bg-navy-800 text-white hover:bg-navy-900 disabled:bg-gray-200 disabled:text-gray-400 transition-colors">
          {sending ? 'Sending…' : 'Send quote request'}
        </Button>
      </div>
    </div>
  );
}

// ─── Case messages thread (WZ5) ───────────────────────────────────────────────

interface CaseMessage {
  id: string;
  case_id: string;
  sender_id: string;
  sender_role: string;
  content: string;
  created_at: string;
}

function CaseMessagesPanel({ caseId }: { caseId: string }) {
  const [messages, setMessages] = useState<CaseMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadMessages = useCallback(async () => {
    try {
      const res = await apiGet<CaseMessage[]>(`/api/cases/${caseId}/messages`);
      setMessages(res);
    } catch {
      // silently fail — thread may be empty or case not yet persisted
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => { loadMessages(); }, [loadMessages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setSending(true);
    setError(null);
    try {
      const msg = await apiPost<CaseMessage>(`/api/cases/${caseId}/messages`, { content: text });
      setMessages((prev) => [...prev, msg]);
      setInput('');
    } catch (e) {
      setError((e as Error).message ?? 'Failed to send message');
    } finally {
      setSending(false);
    }
  };

  const roleLabel = (role: string) =>
    role === 'hr' ? 'HR' : role === 'admin' ? 'Admin' : 'You';

  const roleColor = (role: string) =>
    role === 'employee' ? 'bg-accent-100 text-accent-800' : 'bg-blue-100 text-blue-800';

  return (
    <div className="mt-4 border border-gray-100 rounded-xl bg-white overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
        <span className="text-xs font-bold text-gray-700">💬 Messages</span>
        <span className="text-xs text-gray-400">between you and your HR team</span>
      </div>
      <div className="px-4 py-3 max-h-48 overflow-y-auto flex flex-col gap-2">
        {loading && <p className="text-xs text-gray-400">Loading messages…</p>}
        {!loading && messages.length === 0 && (
          <p className="text-xs text-gray-400">No messages yet — send one below to start the conversation.</p>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`flex flex-col gap-0.5 ${msg.sender_role === 'employee' ? 'items-end' : 'items-start'}`}>
            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${roleColor(msg.sender_role)}`}>
              {roleLabel(msg.sender_role)}
            </span>
            <div className={`max-w-[80%] rounded-xl px-3 py-2 text-xs ${
              msg.sender_role === 'employee'
                ? 'bg-accent-600 text-white rounded-br-none'
                : 'bg-gray-100 text-gray-800 rounded-bl-none'
            }`}>
              {msg.content}
            </div>
            <span className="text-[9px] text-gray-400">
              {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="px-4 py-3 border-t border-gray-100 flex gap-2">
        <Input unstyled
          type="text"
          className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-accent-300"
          placeholder="Write a message…"
          value={input}
          onChange={(v) => setInput(v)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
          disabled={sending}
        />
        <Button unstyled type="button" onClick={handleSend} disabled={!input.trim() || sending}
          className="px-3 py-2 text-xs font-semibold rounded-lg bg-navy-800 text-white hover:bg-navy-900 disabled:bg-gray-200 disabled:text-gray-400 transition-colors">
          {sending ? '…' : 'Send'}
        </Button>
      </div>
      {error && <p className="px-4 pb-3 text-xs text-red-500">{error}</p>}
    </div>
  );
}

// ─── Budget summary panel (WZ3) ───────────────────────────────────────────────

interface BudgetCategory {
  name: string;
  cap_amount: number | null;
  cap_currency: string;
  status: string;
}

function BudgetSummaryPanel({ caseId, services }: { caseId: string; services: string[] }) {
  const [categories, setCategories] = useState<BudgetCategory[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!caseId) return;
    setLoading(true);
    apiGet<{ case_id: string; categories: BudgetCategory[] }>(`/api/cases/${caseId}/budget-summary`)
      .then((res) => setCategories(res.categories))
      .catch(() => setCategories(null))
      .finally(() => setLoading(false));
  }, [caseId]);

  const displayCats: BudgetCategory[] = categories && categories.length > 0
    ? categories
    : services.map((s) => ({ name: s, cap_amount: null, cap_currency: 'EUR', status: 'no_cap' }));

  return (
    <div className="mt-4 border border-accent-100 rounded-xl p-4 bg-accent-50">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-bold text-accent-700 uppercase tracking-wide">Budget caps</span>
        <span className="text-xs text-accent-400">(from your HR policy)</span>
      </div>
      {loading ? (
        <p className="text-xs text-accent-400">Loading budget information…</p>
      ) : (
        <div className="flex flex-col gap-1.5">
          {displayCats.map((cat) => (
            <div key={cat.name} className="flex items-center justify-between text-xs">
              <span className="text-gray-600 capitalize">{cat.name.replace(/_/g, ' ')}</span>
              <span className={`font-semibold ${cat.cap_amount != null ? 'text-gray-800' : 'text-gray-400'}`}>
                {cat.cap_amount != null
                  ? `${cat.cap_amount.toLocaleString()} ${cat.cap_currency}`
                  : 'No cap set'}
              </span>
            </div>
          ))}
          {displayCats.length === 0 && (
            <p className="text-xs text-accent-400">No services selected.</p>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Review summary ───────────────────────────────────────────────────────────

function ReviewSummary({ data, goTo }: { data: IntakeData; goTo: (s: number) => void }) {
  const partner = data.members.find((m) => m.kind === 'partner');
  const children = data.members.filter((m) => m.kind === 'child');
  const oC = COUNTRIES.find((c) => c.code === data.origin_country);
  const dC = COUNTRIES.find((c) => c.code === data.dest_country);

  const Card = ({ label, step, rows }: { label: string; step: number; rows: [string, React.ReactNode][] }) => (
    <div className="border border-gray-100 rounded-xl p-4 bg-white">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-bold text-gray-700 uppercase tracking-wide">{label}</span>
        <Button unstyled type="button" onClick={() => goTo(step)} className="text-xs text-accent-600 font-medium hover:text-accent-800">Edit →</Button>
      </div>
      <div className="flex flex-col gap-1.5">
        {rows.map(([k, v]) => (
          <div key={k} className="flex gap-3 text-xs">
            <span className="text-gray-400 w-24 flex-shrink-0">{k}</span>
            <span className="text-gray-700 font-medium">{v}</span>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
      <Card label="Move" step={1} rows={[
        ['Route', `${oC?.flag ?? ''} ${data.origin_city} → ${dC?.flag ?? ''} ${data.dest_city}`],
        ['Target date', data.target_date || '—'],
        ['Purpose', data.purpose],
      ]} />
      <Card label="About you" step={2} rows={[
        ['Name', data.full_name || <em className="text-red-400">missing</em>],
        ['Passport', `${data.passport_country || '—'} · expires ${data.passport_expiry || '—'}`],
        ['Email', data.email || '—'],
      ]} />
      <Card label={`Household (${data.members.length})`} step={3} rows={[
        ['Self', data.full_name || 'You'],
        ...(partner ? [['Partner', `${partner.name ?? '—'} · ${partner.employment ?? '—'}`] as [string, React.ReactNode]] : []),
        ...(children.length ? [['Children', children.map((c) => `${c.name ?? '?'} (${computeAge(c.dob) ?? '?'}y)`).join(', ')] as [string, React.ReactNode]] : []),
      ]} />
      <Card label="Work & commute" step={4} rows={[
        ['Job', `${data.job_title || '—'} · ${data.contract_type}`],
        ['Office', data.office_address || <em className="text-red-400">missing</em>],
        ['Pattern', `${data.work_pattern}${data.work_pattern !== 'Fully remote' ? ` · ≤${data.commute_mins}min` : ''}`],
        ['Salary', data.salary_band || '—'],
      ]} />
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function EmployeeIntakePage() {
  const navigate = useNavigate();
  const [data, setData] = useState<IntakeData>(INITIAL_DATA);
  const [step, setStep] = useState(1);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  // Locks default to false. A field is only badged "🔒 HR pre-filled" once
  // the hydration effect below has actually populated it from the case
  // row. Previously every lock started true, falsely claiming the wizard's
  // hardcoded demo values were HR-controlled.
  const [locks, setLocks] = useState({ dest: false, destCity: false, email: false, job: false, contractType: false, contractStart: false, salary: false, office: false });
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [savedAt, setSavedAt] = useState(Date.now());
  // Stable case ID for the duration of this intake session.
  const caseIdRef = useRef<string>(crypto.randomUUID());
  // Latest assignment id captured in a ref so the debounced autosave
  // (set up inside `setField`'s closure) always posts to the *current*
  // linked assignment, even if it resolves after the wizard mounts.
  // We can't depend on `assignmentId` directly because setField is
  // stable and its closure would otherwise capture the initial null.
  const assignmentIdRef = useRef<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const setField = useCallback(<K extends keyof IntakeData>(k: K, v: IntakeData[K]) => {
    setData((d) => {
      const next = { ...d, [k]: v };
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(() => {
        setSavedAt(Date.now());
        const aid = assignmentIdRef.current;
        if (aid) {
          void employeeAPI
            .updateIntakeDraft(aid, next as unknown as Record<string, unknown>)
            .catch(() => {
              /* swallow — next edit will retry, wizard stays usable */
            });
        }
      }, 700);
      return next;
    });
  }, []);

  const unlock = (key: keyof typeof locks) => setLocks((l) => ({ ...l, [key]: false }));

  const international = !!(data.origin_country && data.dest_country && data.origin_country !== data.dest_country);

  const partner = data.members.find((m) => m.kind === 'partner');
  const children = data.members.filter((m) => m.kind === 'child');
  const pets = data.members.filter((m) => m.kind === 'pet');

  const addMember = (kind: MemberKind, extra?: Partial<Member>) => {
    const id = kind + Date.now();
    setField('members', [...data.members, { id, kind, count: 1, ...extra }]);
    setExpanded((e) => ({ ...e, [id]: true }));
  };
  const updateMember = (id: string, next: Member) => setField('members', data.members.map((m) => m.id === id ? next : m));
  const removeMember = (id: string) => setField('members', data.members.filter((m) => m.id !== id));
  const toggleMember = (id: string) => setExpanded((e) => ({ ...e, [id]: !e[id] }));

  // Auto-select services on household change.
  // AIQ-289: pets entry is on hold (separate tab) — the Pet relocation
  // service stays available in step "My Needs" so the employee can still
  // request it manually, but we no longer auto-add based on members.
  useEffect(() => {
    const auto = new Set(data.services);
    auto.add('housing'); auto.add('immigration');
    if (children.length) auto.add('schools');
    if (partner) auto.add('spouse');
    const next = [...auto];
    if (next.length !== data.services.length || next.some((s) => !data.services.includes(s))) {
      setField('services', next);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.members.length]);

  const stepValid = (s: number) => {
    if (s === 1) return !!(data.origin_country && data.origin_city && data.dest_country && data.dest_city && data.target_date && data.purpose);
    if (s === 2) return !!(data.full_name && data.nationality && data.passport_country && data.passport_expiry);
    if (s === 3) return data.members.length >= 1;
    // AIQ-289: step 4 is the Pets tab — on hold, always advance-able.
    if (s === 4) return true;
    if (s === 5) return !!(data.job_title && data.contract_start && data.contract_type && data.office_address && data.work_pattern && data.salary_band);
    if (s === 6) return data.services.length >= 1;
    return true;
  };

  const goTo = (s: number) => {
    setStep(s);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // AIQ-289: insert a dimmed "Pets" tab between My People and Work & Place.
  // The tab is visible but on-hold — index 3 of STEP_ON_HOLD marks it.
  const STEP_LABELS = ['Journey', 'About You', 'My People', 'Pets', 'Work & Place', 'My Needs', 'Review'];
  const STEP_ICONS  = ['🛫', '👤', '👪', '🐾', '🗺️', '✅', '📋'];
  const STEP_ON_HOLD: Record<number, boolean> = {};  // AIQ-160-C: step 4 (Pets) is now active
  const TOTAL_STEPS = STEP_LABELS.length;

  // ── Per-assignment hydration ──────────────────────────────────────────
  // The wizard is tied to the user's linked assignment_id. Three things
  // get pulled from the linked overview row on first render:
  //   1. The step counter (intake_step) — to put the user back where they
  //      left off; persisted independently below on every step change.
  //   2. dest_country + origin_country from the case's host_country /
  //      home_country — these are HR-entered values and the field gets
  //      badged "🔒 HR pre-filled" so the user knows where they came from.
  //   3. The user's login email — pre-filled into `email` if missing, but
  //      NOT locked (it's the user's data, not HR's).
  // Form data itself (other fields) is still ephemeral and lives in
  // component state until final submit — the step counter is the only
  // value persisted server-side today.
  const { assignmentId, linkedSummaries } = useEmployeeAssignment();
  const hydratedStepRef = useRef(false);
  const lastPersistedStepRef = useRef<number | null>(null);

  useEffect(() => {
    if (hydratedStepRef.current || !assignmentId) return;
    const row = linkedSummaries.find((r) => r.assignment_id === assignmentId);

    // Destination + origin from the case row. host_country may be a name
    // ("Germany") or a code ("DE") — countryNameToCode normalises both.
    const destCode = countryNameToCode(row?.destination?.host_country);
    const originCode = countryNameToCode(row?.destination?.home_country);
    // host_city / home_city are free-text strings stored as-typed by HR.
    const destCity = (row?.destination?.host_city || '').trim();
    const originCity = (row?.destination?.home_city || '').trim();
    const userEmail = (getAuthItem('relopass_email') || '').trim();
    if (destCode || originCode || destCity || originCity || userEmail) {
      setData((d) => {
        const next = { ...d };
        // Only fill if empty — user-entered data is never overwritten.
        if (!next.dest_country && destCode) next.dest_country = destCode;
        if (!next.origin_country && originCode) next.origin_country = originCode;
        if (!next.dest_city && destCity) next.dest_city = destCity;
        if (!next.origin_city && originCity) next.origin_city = originCity;
        if (!next.email && userEmail) next.email = userEmail;
        return next;
      });
    }
    if (destCity) {
      setLocks((l) => ({ ...l, destCity: true }));
    }
    // Lock destination only if we actually pre-filled it from the case
    // row — that's the "🔒 HR pre-filled" signal users see.
    if (destCode) {
      setLocks((l) => ({ ...l, dest: true }));
    }

    const saved = row?.intake_step;
    if (typeof saved === 'number' && saved > 0) {
      const clamped = Math.min(Math.max(saved, 1), TOTAL_STEPS);
      setStep(clamped);
      lastPersistedStepRef.current = clamped;
    } else if (typeof saved === 'number') {
      // saved === 0: never opened. Mark as hydrated so we don't keep checking.
      lastPersistedStepRef.current = 0;
    }
    hydratedStepRef.current = true;
  }, [assignmentId, linkedSummaries, TOTAL_STEPS]);

  // Keep the autosave closure pointing at the current assignment id.
  useEffect(() => {
    assignmentIdRef.current = assignmentId;
  }, [assignmentId]);

  // ── Form-draft hydration ──────────────────────────────────────
  // One-shot fetch of the saved draft from
  // GET /api/employee/assignments/{id}/intake. Merges into local
  // state only over empty fields so a user typing during the
  // load doesn't get their work overwritten. Failure is soft —
  // the wizard still runs against the in-memory defaults.
  const draftHydratedRef = useRef(false);
  useEffect(() => {
    if (draftHydratedRef.current || !assignmentId) return;
    let cancelled = false;
    void employeeAPI
      .getIntake(assignmentId)
      .then((res) => {
        if (cancelled) return;
        if (res.intakeDraft && typeof res.intakeDraft === 'object') {
          setData((d) => {
            const merged = { ...d };
            for (const [k, v] of Object.entries(res.intakeDraft as Record<string, unknown>)) {
              const key = k as keyof IntakeData;
              // Only fill if current value is empty/falsy — user-
              // entered changes during the load take priority.
              const cur = merged[key] as unknown;
              const isEmpty = cur === '' || cur === null || cur === undefined
                || (Array.isArray(cur) && cur.length === 0);
              if (isEmpty) (merged as Record<string, unknown>)[key as string] = v;
            }
            return merged;
          });
        }
      })
      .catch(() => {
        /* fall through to in-memory defaults */
      })
      .finally(() => {
        if (!cancelled) draftHydratedRef.current = true;
      });
    return () => {
      cancelled = true;
    };
  }, [assignmentId]);

  // Persist step on every change once hydrated. Fire-and-forget — failures
  // shouldn't block navigation in the wizard.
  useEffect(() => {
    if (!hydratedStepRef.current || !assignmentId) return;
    if (lastPersistedStepRef.current === step) return;
    lastPersistedStepRef.current = step;
    void employeeAPI.updateIntakeProgress(assignmentId, step, TOTAL_STEPS).catch(() => {
      // Allow a retry on the next step change by clearing the last-persisted ref.
      lastPersistedStepRef.current = null;
    });
  }, [step, assignmentId, TOTAL_STEPS]);

  const elapsedSecs = Math.floor((Date.now() - savedAt) / 1000);
  const savedLabel = elapsedSecs < 60 ? 'just now' : 'a moment ago';

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <div className="text-xs font-semibold text-accent-600 uppercase tracking-widest mb-1">Employee · Intake Wizard</div>
          <h1 className="text-2xl font-bold text-gray-900">Detailed intake</h1>
          <p className="mt-1 text-sm text-gray-500">
            This is where most of your relocation information lives. Work through the steps below — your answers help us build your personalised case, match the right services, and flag what needs attention before your move.
          </p>
        </div>

        {/* Pre-fill banner */}
        <div className="flex items-start gap-3 p-3 mb-5 bg-blue-50 border border-blue-100 rounded-xl text-xs text-blue-700">
          <span className="flex-shrink-0">ℹ</span>
          <div><strong>Some fields are pre-filled by your HR team</strong> (destination, office address, contract details, salary band). Click "Edit" on any pre-filled field if anything looks wrong.</div>
        </div>

        {/* Wizard frame */}
        <div className="bg-white border border-gray-100 rounded-2xl shadow-sm overflow-hidden">

          {/* Progress stepper */}
          <div className="border-b border-gray-100 px-5 pt-4 pb-3">
            <div className="flex items-center justify-between mb-2 text-xs text-gray-400">
              <span className="font-semibold text-gray-600">Detailed Intake</span>
              <span>Auto-saved {savedLabel}</span>
              <span>Step {step} / {TOTAL_STEPS}</span>
            </div>
            {/* Stepper: all 7 steps must be visible without horizontal scroll
                at the wizard's max-w-4xl width. flex-wrap is a safety net for
                narrow viewports — preferred over overflow-x-auto because
                scrolling steps offscreen hides the user's progress map. */}
            <div className="flex flex-wrap items-center gap-1">
              {STEP_LABELS.map((lbl, i) => {
                const n = i + 1;
                const onHold = !!STEP_ON_HOLD[n];
                const isDone = !onHold && stepValid(n) && n < step;
                const isActive = n === step;
                return (
                  <Button unstyled key={lbl} type="button"
                    onClick={() => n < step && goTo(n)}
                    disabled={n > step}
                    title={onHold ? 'On hold — coming soon' : undefined}
                    className={`flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-[10px] font-semibold flex-shrink-0 transition-colors ${
                      onHold && !isActive ? 'text-gray-400 opacity-60' :
                      isActive ? 'bg-accent-100 text-accent-700' :
                      isDone ? 'text-green-600 cursor-pointer hover:bg-green-50' :
                      'text-gray-300'
                    }`}>
                    <span className={`w-4 h-4 rounded-full text-[9px] flex items-center justify-center flex-shrink-0 ${
                      onHold && !isActive ? 'bg-gray-100 text-gray-400' :
                      isActive ? 'bg-accent-600 text-white' : isDone ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-400'
                    }`}>{isDone ? '✓' : n}</span>
                    <span className="hidden sm:inline">{STEP_ICONS[i]} {lbl}</span>
                    {onHold && (
                      <span className="hidden sm:inline ml-1 px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[9px] font-bold">
                        On hold
                      </span>
                    )}
                  </Button>
                );
              })}
            </div>
          </div>

          {/* Step body */}
          <div className="p-5">

            {/* ── Step 1 — Journey ── */}
            {step === 1 && (
              <>
                <StepHd title="Where are you moving from and to?" sub="Just the basics — we'll use this to start drafting your roadmap." required />
                <Grid>
                  <FieldWrap label="Origin country" required>
                    <CountryCombo value={data.origin_country} onChange={(v) => setField('origin_country', v)} />
                  </FieldWrap>
                  <FieldWrap label="Origin city" required>
                    <CityCombo country={data.origin_country} value={data.origin_city} onChange={(v) => setField('origin_city', v)} />
                  </FieldWrap>
                  <FieldWrap label="Destination country" required prefill={locks.dest} onUnlock={() => unlock('dest')}>
                    <CountryCombo value={data.dest_country} onChange={(v) => setField('dest_country', v)} disabled={locks.dest} />
                  </FieldWrap>
                  <FieldWrap label="Destination city" required prefill={locks.destCity} onUnlock={() => unlock('destCity')}>
                    <CityCombo country={data.dest_country} value={data.dest_city} onChange={(v) => setField('dest_city', v)} />
                  </FieldWrap>
                  <FieldWrap label="Target move date" required>
                    <Input unstyled type="date" className={inputCls()} value={data.target_date}
                      onChange={(v) => setField('target_date', v)} />
                  </FieldWrap>
                  <FieldWrap label="Purpose of relocation" required>
                    <select className={selectCls()} value={data.purpose} onChange={(e) => setField('purpose', e.target.value)}>
                      <option>Employment</option><option>Study</option><option>Family</option><option>Other</option>
                    </select>
                  </FieldWrap>
                </Grid>
                {international && (
                  <div className="flex items-start gap-2 mt-4 p-3 bg-blue-50 border border-blue-100 rounded-xl text-xs text-blue-700">
                    🌍 <span><strong>International move detected.</strong> We'll automatically include visa, customs, international movers, and pet import (if relevant) in your roadmap.</span>
                  </div>
                )}
              </>
            )}

            {/* ── Step 2 — About You ── */}
            {step === 2 && (
              <>
                <StepHd title="A bit about you" sub="Your passport details kick off the immigration track." />
                <Grid>
                  <FieldWrap label="Full name" required>
                    <Input unstyled className={inputCls()} value={data.full_name} placeholder="As shown on your passport"
                      onChange={(v) => setField('full_name', v)} />
                  </FieldWrap>
                  <FieldWrap label="Email" required prefill={locks.email} onUnlock={() => unlock('email')}>
                    <Input unstyled type="email" className={inputCls(locks.email)} value={data.email} disabled={locks.email}
                      onChange={(v) => setField('email', v)} />
                  </FieldWrap>
                  <FieldWrap label="Nationality" required>
                    <CountryCombo value={data.nationality} onChange={(v) => setField('nationality', v)} />
                  </FieldWrap>
                  <FieldWrap label="Passport country" required>
                    <CountryCombo value={data.passport_country} onChange={(v) => setField('passport_country', v)} />
                  </FieldWrap>
                  <FieldWrap label="Passport expiry" required>
                    <Input unstyled type="date" className={inputCls()} value={data.passport_expiry}
                      onChange={(v) => setField('passport_expiry', v)} />
                  </FieldWrap>
                  <FieldWrap label="Passport upload" optional hint="Drop a PDF or photo — we'll OCR name, country, and expiry." className="sm:col-span-2">
                    <div className="flex items-center justify-center border-2 border-dashed border-gray-200 rounded-xl p-5 text-sm text-gray-400 cursor-pointer hover:border-accent-300 hover:text-accent-500 transition-colors">
                      ↑ Drop your passport or click to browse
                    </div>
                  </FieldWrap>
                </Grid>
              </>
            )}

            {/* ── Step 3 — My People ── */}
            {step === 3 && (
              <>
                <StepHd title="Who's relocating with you?" sub="Add anyone joining the move. Cards expand for details and scale gracefully." />
                <div className="flex flex-col gap-2 mb-3">
                  {/* Self (immutable) */}
                  <div className="flex items-center gap-3 px-4 py-3 border border-green-100 bg-green-50/50 rounded-xl">
                    <span className="text-xl">🙋</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-semibold text-gray-900">{data.full_name || 'You'}</div>
                      <div className="text-xs text-gray-400">Primary relocator</div>
                    </div>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold text-green-600 bg-green-100">✓ From Step 2</span>
                  </div>

                  {partner && (
                    <PartnerCard m={partner} onChange={(n) => updateMember(partner.id, n)} onRemove={() => removeMember(partner.id)}
                      international={international} expanded={!!expanded[partner.id]} onToggle={() => toggleMember(partner.id)} />
                  )}
                  {children.map((c, i) => (
                    <ChildCard key={c.id} m={c} index={i} onChange={(n) => updateMember(c.id, n)} onRemove={() => removeMember(c.id)}
                      expanded={!!expanded[c.id]} onToggle={() => toggleMember(c.id)} />
                  ))}
                  {/* AIQ-289: pets moved out of Family / My People into the dedicated Pets tab (on hold). */}
                </div>
                {/* Add buttons */}
                <div className="flex flex-wrap gap-2 mb-3">
                  {!partner && <Button unstyled type="button" onClick={() => addMember('partner')} className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-gray-200 hover:bg-gray-50 transition-colors">+ Add partner</Button>}
                  <Button unstyled type="button" onClick={() => addMember('child')} className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-gray-200 hover:bg-gray-50 transition-colors">+ Add a child</Button>
                </div>
                {data.members.length === 1 && (
                  <div className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-100 rounded-xl text-xs text-blue-700">
                    ℹ <span><strong>Moving solo?</strong> That's fine — just continue. You can add household members later from your profile.</span>
                  </div>
                )}
              </>
            )}

            {/* ── Step 4 — Pets ── AIQ-160-C */}
            {step === 4 && (
              <>
                <StepHd title="Pets" sub="Tell us about the pets joining your move — we'll track microchip, vaccination, and destination import requirements." />

                <div className="space-y-3">
                  {pets.length === 0 && (
                    <div className="flex flex-col items-center justify-center gap-3 py-10 px-6 border border-dashed border-gray-200 bg-gray-50/40 rounded-2xl text-center">
                      <span className="text-3xl">🐾</span>
                      <div className="text-sm font-semibold text-gray-600">No pets added yet</div>
                      <div className="text-xs text-gray-400 max-w-sm leading-relaxed">
                        Add your pets below — we'll surface microchip, vaccination, and import requirements for your destination country.
                      </div>
                    </div>
                  )}

                  {pets.map((pet, i) => (
                    <PetCard
                      key={pet.id}
                      m={pet}
                      index={i}
                      expanded={!!expanded[pet.id]}
                      onToggle={() => toggleMember(pet.id)}
                      onChange={(next) => updateMember(pet.id, next)}
                      onRemove={() => {
                        if (window.confirm(`Remove ${pet.name || `Pet ${i + 1}`}?`)) {
                          removeMember(pet.id);
                        }
                      }}
                    />
                  ))}
                </div>

                <Button unstyled type="button"
                  onClick={() => addMember('pet', { pet_type: '' })}
                  className="mt-3 w-full py-3 text-sm font-semibold text-accent-600 border-2 border-dashed border-accent-200 rounded-xl hover:bg-accent-50 transition-colors">
                  🐾 Add a pet
                </Button>

                <div className="flex items-start gap-2 mt-4 p-3 bg-blue-50 border border-blue-100 rounded-xl text-xs text-blue-700">
                  ℹ <span><strong>No pets travelling with you?</strong> Skip this step — click Continue.</span>
                </div>
              </>
            )}

            {/* ── Step 5 — Work & Place ── */}
            {step === 5 && (
              <>
                <StepHd title="Your work & commute" sub="Most of this is pre-filled by your HR team — confirm or update. Commute settings drive your housing pre-filter." required />
                <Grid>
                  <FieldWrap label="Job title" required prefill={locks.job} onUnlock={() => unlock('job')}>
                    <Input unstyled className={inputCls(locks.job)} value={data.job_title} disabled={locks.job} placeholder="e.g. Senior Engineer"
                      onChange={(v) => setField('job_title', v)} />
                  </FieldWrap>
                  <FieldWrap label="Contract type" required prefill={locks.contractType} onUnlock={() => unlock('contractType')}>
                    <select className={selectCls(locks.contractType)} value={data.contract_type} disabled={locks.contractType}
                      onChange={(e) => setField('contract_type', e.target.value)}>
                      <option>Permanent</option><option>Fixed-term</option><option>Secondment</option>
                    </select>
                  </FieldWrap>
                  <FieldWrap label="Contract start date" required prefill={locks.contractStart} onUnlock={() => unlock('contractStart')}>
                    <Input unstyled type="date" className={inputCls(locks.contractStart)} value={data.contract_start} disabled={locks.contractStart}
                      onChange={(v) => setField('contract_start', v)} />
                  </FieldWrap>
                  <FieldWrap label="Salary band" required prefill={locks.salary} onUnlock={() => unlock('salary')} hint="Used to confirm visa salary thresholds.">
                    <select className={selectCls(locks.salary)} value={data.salary_band} disabled={locks.salary}
                      onChange={(e) => setField('salary_band', e.target.value)}>
                      <option value="">Select…</option>
                      <option>50–100k€</option><option>100–150k€</option><option>150–200k€</option><option>200–300k€</option><option>300k€+</option>
                    </select>
                  </FieldWrap>
                  <FieldWrap label="Office address at destination" required className="sm:col-span-2" prefill={locks.office} onUnlock={() => unlock('office')}
                    why="Anchors commute analysis. We'll show neighborhoods within your time radius.">
                    <Input unstyled className={inputCls(locks.office)} value={data.office_address} disabled={locks.office}
                      placeholder="Start typing…" onChange={(v) => setField('office_address', v)} />
                    {data.office_address && (
                      <div className="flex items-center gap-2 mt-1 px-2.5 py-1.5 bg-gray-50 rounded-lg text-xs text-gray-500">
                        📍 <span className="flex-1">{data.office_address}</span>
                        <span className="text-green-600 font-medium">Verified</span>
                      </div>
                    )}
                  </FieldWrap>
                  <FieldWrap label="Work pattern" required className="sm:col-span-2">
                    <MultiChip value={data.work_pattern ? [data.work_pattern] : []} onChange={(v) => setField('work_pattern', v[v.length - 1] || '')}
                      options={['Full in-office', 'Hybrid', 'Fully remote']} />
                  </FieldWrap>
                </Grid>

                {data.work_pattern !== 'Fully remote' && (
                  <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-5">
                    <div className="flex flex-col gap-4">
                      <FieldWrap label="Maximum commute you'd accept">
                        <div className="flex items-center gap-3">
                          <Input unstyled type="range" min={15} max={75} step={5} value={data.commute_mins}
                            onChange={(v) => setField('commute_mins', Number(v))}
                            className="flex-1 accent-accent-600" />
                          <span className="text-sm font-bold text-accent-700 w-12 text-right">{data.commute_mins}min</span>
                        </div>
                        <div className="text-xs text-gray-400">Shorter = fewer neighborhoods but better matches.</div>
                      </FieldWrap>
                      <FieldWrap label="Preferred way to commute">
                        <MultiChip value={data.commute_mode} onChange={(v) => setField('commute_mode', v)}
                          options={[
                            { value: 'car', label: '🚗 Car' },
                            { value: 'public_transit', label: '🚇 Transit' },
                            { value: 'bike', label: '🚴 Bike' },
                            { value: 'walking', label: '🚶 Walking' },
                            { value: 'no_pref', label: 'No preference' },
                          ]} />
                      </FieldWrap>
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-gray-700 mb-1.5">Commute map · live preview</div>
                      <CommuteMap maxMins={data.commute_mins} mode={data.commute_mode} />
                    </div>
                  </div>
                )}
                {data.work_pattern === 'Fully remote' && (
                  <div className="flex items-start gap-2 mt-4 p-3 bg-blue-50 border border-blue-100 rounded-xl text-xs text-blue-700">
                    ℹ <span><strong>Working fully remote.</strong> We'll skip commute filtering and lead housing search with neighborhood quality and lifestyle priorities instead.</span>
                  </div>
                )}
              </>
            )}

            {/* ── Step 6 — My Needs ── */}
            {step === 6 && (
              <>
                <StepHd title="What do you need help with?" sub="We've pre-selected services most relevant to your household. Adjust freely." />
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-5">
                  {SERVICES.map((svc) => (
                    <Button unstyled key={svc.id} type="button" disabled={svc.soon}
                      onClick={() => !svc.soon && setField('services', data.services.includes(svc.id)
                        ? data.services.filter((s) => s !== svc.id)
                        : [...data.services, svc.id])}
                      className={`flex flex-col gap-1 p-3 rounded-xl border text-left transition-all ${
                        svc.soon ? 'opacity-40 cursor-not-allowed border-gray-100 bg-gray-50' :
                        data.services.includes(svc.id) ? 'border-accent-300 bg-accent-50 ring-1 ring-accent-300' :
                        'border-gray-100 bg-white hover:border-gray-200 hover:bg-gray-50'
                      }`}>
                      <span className="text-lg">{svc.ico}</span>
                      <span className="text-xs font-semibold text-gray-900">{svc.t}{svc.soon && <span className="ml-1 text-[9px] text-gray-400">soon</span>}</span>
                      <span className="text-[10px] text-gray-400 leading-tight">{svc.s}</span>
                      {data.services.includes(svc.id) && <span className="text-[9px] font-bold text-accent-600 mt-0.5">✓ Selected</span>}
                    </Button>
                  ))}
                </div>
                {data.services.length === 0 && (
                  <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-100 rounded-xl text-xs text-amber-700">
                    ⚠ <span>Select at least one service to continue. You can always add more later.</span>
                  </div>
                )}
                {data.services.includes('housing') && (
                  <div className="border border-gray-100 rounded-xl p-4 mb-3 bg-white">
                    <div className="text-xs font-bold text-gray-700 mb-3">🏠 Housing preferences</div>
                    <Grid>
                      <FieldWrap label="Rent or buy?">
                        <select className={selectCls()} value={data.housing_prefs.intent ?? ''}
                          onChange={(e) => setField('housing_prefs', { ...data.housing_prefs, intent: e.target.value })}>
                          <option value="">Select…</option><option>Rent</option><option>Buy</option><option>Not sure yet</option>
                        </select>
                      </FieldWrap>
                      <FieldWrap label="Bedrooms needed">
                        <Input unstyled type="number" min={1} max={6} className={inputCls()} placeholder="e.g. 2"
                          value={data.housing_prefs.bedrooms ?? ''}
                          onChange={(v) => setField('housing_prefs', { ...data.housing_prefs, bedrooms: v === '' ? '' : Number(v) })} />
                      </FieldWrap>
                      <FieldWrap label="Monthly budget (€)" className="sm:col-span-2">
                        <Input unstyled type="number" className={inputCls()} placeholder="e.g. 2500"
                          value={data.housing_prefs.budget ?? ''}
                          onChange={(v) => setField('housing_prefs', { ...data.housing_prefs, budget: v === '' ? '' : Number(v) })} />
                      </FieldWrap>
                    </Grid>
                  </div>
                )}
                {data.services.includes('schools') && children.length > 0 && (
                  <div className="border border-gray-100 rounded-xl p-4 mb-3 bg-white">
                    <div className="text-xs font-bold text-gray-700 mb-3">🏫 Schools · {children.length} child{children.length > 1 ? 'ren' : ''}</div>
                    <Grid>
                      <FieldWrap label="School type">
                        <select className={selectCls()} value={data.housing_prefs.school_type ?? ''}
                          onChange={(e) => setField('housing_prefs', { ...data.housing_prefs, school_type: e.target.value })}>
                          <option value="">Select…</option>
                          <option>International</option><option>Public</option><option>Private</option><option>Bilingual</option>
                        </select>
                      </FieldWrap>
                      <FieldWrap label="Any special needs support?">
                        <select className={selectCls()} value={data.housing_prefs.special_needs ?? ''}
                          onChange={(e) => setField('housing_prefs', { ...data.housing_prefs, special_needs: e.target.value })}>
                          <option value="">Select…</option><option>Yes</option><option>No</option>
                        </select>
                      </FieldWrap>
                      <FieldWrap label="Expected school start date" className="sm:col-span-2" hint="Defaults to your move date; adjust if kids start later.">
                        <Input unstyled type="date" className={inputCls()} value={data.housing_prefs.school_start ?? data.target_date}
                          onChange={(v) => setField('housing_prefs', { ...data.housing_prefs, school_start: v })} />
                      </FieldWrap>
                    </Grid>
                  </div>
                )}
                {data.services.length > 0 && (
                  <QuoteRequestPanel caseId={caseIdRef.current} services={data.services} />
                )}
              </>
            )}

            {/* ── Step 7 — Review ── */}
            {step === 7 && (
              <>
                <StepHd title="Review & submit" sub="A quick check before we generate your roadmap. You can edit any section later." />
                <ReviewSummary data={data} goTo={goTo} />
                {data.services.length > 0 && (
                  <BudgetSummaryPanel caseId={caseIdRef.current} services={data.services} />
                )}
                <CaseMessagesPanel caseId={caseIdRef.current} />
                {/* PRIV-005 / AIQ-473 — Art. 13 notice at the point of collection.
                    Acknowledging records a privacy_consents row and unblocks submit. */}
                <div className="mt-5">
                  <PrivacyNotice
                    noticeVersion={PRIVACY_NOTICE_VERSION}
                    context="onboarding"
                    checked={data.consent}
                    onChange={(v) => setField('consent', v)}
                  />
                </div>
              </>
            )}
          </div>

          {/* Footer nav */}
          <div className="flex items-center justify-between border-t border-gray-100 px-5 py-4">
            {step > 1 ? (
              <Button unstyled type="button" onClick={() => goTo(step - 1)}
                className="px-4 py-2 text-sm font-semibold border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                ← Back
              </Button>
            ) : <div />}
            <div className="flex items-center gap-1.5 text-xs text-gray-400">
              🔒 Encrypted · only you and your HR team see this
            </div>
            {step < TOTAL_STEPS ? (
              <Button unstyled type="button" onClick={() => goTo(step + 1)} disabled={!stepValid(step)}
                className={`px-5 py-2 text-sm font-semibold rounded-lg transition-colors ${
                  stepValid(step) ? 'bg-navy-800 text-white hover:bg-navy-900' : 'bg-gray-100 text-gray-300 cursor-not-allowed'
                }`}>
                Continue →
              </Button>
            ) : (
              <>
                {submitError && (
                  <p className="text-xs text-red-500 mr-2">{submitError}</p>
                )}
                <Button unstyled type="button" disabled={!data.consent || submitting}
                  onClick={async () => {
                    setSubmitting(true);
                    setSubmitError(null);
                    try {
                      await patchCase(caseIdRef.current, { services: data.services });
                      // Mark intake as fully completed against the linked
                      // assignment so the hub row flips to "Submitted".
                      // Fire-and-forget — patchCase already succeeded.
                      if (assignmentId) {
                        void employeeAPI.updateIntakeProgress(
                          assignmentId,
                          TOTAL_STEPS,
                          TOTAL_STEPS,
                        ).catch(() => undefined);
                      }
                      navigate(ROUTE_DEFS.employeeDashboard.path);
                    } catch (e) {
                      setSubmitError((e as Error).message ?? 'Submission failed. Please try again.');
                      setSubmitting(false);
                    }
                  }}
                  className={`px-5 py-2 text-sm font-semibold rounded-lg transition-colors ${
                    data.consent && !submitting ? 'bg-navy-800 text-white hover:bg-navy-900' : 'bg-gray-100 text-gray-300 cursor-not-allowed'
                  }`}>
                  {submitting ? 'Submitting…' : '✦ Generate my roadmap'}
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
