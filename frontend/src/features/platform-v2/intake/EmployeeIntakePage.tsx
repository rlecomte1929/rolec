import { useState, useEffect, useRef, useCallback, lazy, Suspense } from 'react';
import type * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../../../components/AppShell';
import { Button } from '../../../components/antigravity/Button';
import { Input } from '../../../components/antigravity/Input';
import { SegmentedOptionCards } from '../../../components/antigravity/SegmentedOptionCards';
import { useGeocodedAddress } from '../../../components/geocode';
import { patchCase } from '../../../api/cases';
import { emitTestDriveStage, getTestDriveSession } from '../../../api/testDrive';
import { employeeAPI } from '../../../api/client';
import { track } from '../../../analytics';
import { trackWizardStepCompleted, trackWizardCompleted, type WizardStepName } from '../../../analyticsEvents';
import { ROUTE_DEFS, buildRoute } from '../../../navigation/routes';
import { useValidatedParams, caseParamsSchema } from '../../../hooks/useValidatedParams';
import { useEmployeeAssignment } from '../../../contexts/EmployeeAssignmentContext';
import { getAuthItem } from '../../../utils/demo';
import { PrivacyNotice } from '../../privacy/PrivacyNotice';
import { OutcomeSharingOptIn } from './OutcomeSharingOptIn';
import { PRIVACY_NOTICE_VERSION } from '../../privacy/privacyNoticeContent';
import { MultiChip } from './MultiChip';
import { INTAKE_STEP_LABELS } from './intakeSteps';
import { mergeIntakeDraft, clampIntakeStep } from './intakeHydration';
import { resolveIntakeIds } from './resolveIntakeIds';
import { intakeToCaseDraft } from './intakeToCaseDraft';
import { parseSubmitError } from './parseSubmitError';
import { matchCountry } from './countryMatch';
// Identity fields (nationality, passport) accept the full ISO list; the local
// COUNTRIES below stays scoped to the relocation origin/destination pickers,
// which also rely on CITIES_BY_COUNTRY (AIQ-1341).
import { COUNTRY_OPTIONS as ALL_COUNTRY_OPTIONS } from '../../policy-config/countryList';

// Leaflet is heavy — only load the real commute map once an address resolves.
const RichCommuteMap = lazy(() =>
  import('../../../components/RichCommuteMap').then((m) => ({ default: m.RichCommuteMap }))
);

// ─── Types ────────────────────────────────────────────────────────────────────

// Analytics: map the 1-indexed wizard step to a stable snake_case event name,
// aligned to INTAKE_STEP_LABELS (['Move details','About You','My People',
// 'Work & Place','Review']). Index 0 is unused (steps are 1-indexed).
const WIZARD_STEP_NAMES: readonly (WizardStepName | undefined)[] = [
  undefined,
  'move_details',
  'about_you',
  'my_people',
  'work_and_place',
  'review',
];

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

export interface IntakeData {
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
  /** AIQ-1349: STA (short-term) / LTA (long-term) / PERMANENT — shapes the
   *  duration-aware policy resolution + roadmap. Defaults to LTA (the prior
   *  implicit "full relocation" behaviour) so existing flows are unchanged. */
  assignment_type: string;
  /** AIQ-1349: optional expected assignment length in months. Feeds
   *  assignmentContext.expectedDurationMonths → duration_threshold policy rules. */
  expected_duration_months: number | null;
  commute_mins: number;
  // AIQ-1603: single-select preferred commute mode (persisted to cases.commute_preference).
  commute_preference: string;
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

// AIQ-1598: derive a flag emoji from an ISO-3166 alpha-2 code (regional-indicator
// pair). Identity fields (nationality, passport) use the full ISO list
// (COUNTRY_OPTIONS), whose entries carry no `flag`, so CountryCombo used to fall back
// to a 🌐 globe on the 'About You' step. Deriving from the code renders the SAME glyph
// the relocation COUNTRIES list hardcodes — so both steps look identical, no new dep.
// Returns '' for a non-two-letter code so the caller can fall back to the globe.
function flagEmoji(code?: string): string {
  const cc = (code ?? '').trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(cc)) return '';
  return String.fromCodePoint(...[...cc].map((ch) => 0x1f1e6 + ch.charCodeAt(0) - 65));
}

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
  purpose: 'employment', // must match the <select> option values, lowercase — see below
  full_name: '',
  email: '',
  nationality: '',
  passport_country: '',
  passport_expiry: '',
  // The employee themselves is always in the household — partner / kids /
  // pets are added via the "Add member" controls on step 3.
  members: [{ id: 'self', kind: 'self' }],
  job_title: '',
  // Default to the first option so the controlled <select> (which has no
  // empty placeholder, unlike salary_band) reflects committed state — otherwise
  // it displays "Permanent" while data.contract_type stays '' and stepValid(5)
  // silently blocks Continue. Mirrors `purpose: 'Employment'` above.
  contract_type: 'Permanent',
  contract_start: '',
  salary_band: '',
  office_address: '',
  work_pattern: '',
  // AIQ-1349: default LTA = the prior implicit "full relocation" behaviour, so
  // the new control never blocks Continue and existing cases are unaffected.
  assignment_type: 'LTA',
  // AIQ-1349: optional — left null so it drops from the draft JSON unless set.
  expected_duration_months: null,
  commute_mins: 30,
  commute_preference: 'no_preference',
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
      <label className="flex items-center gap-1.5 text-sm font-semibold text-gray-700 flex-wrap">
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
      {hint && <div className="text-sm text-gray-400">{hint}</div>}
    </div>
  );
}

const inputCls = (locked?: boolean) =>
  `w-full px-3 py-2 text-base border rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300 ${
    locked ? 'bg-gray-50 text-gray-400 border-gray-100 cursor-not-allowed' : 'border-gray-200 bg-white'
  }`;

const selectCls = (locked?: boolean) =>
  `w-full px-3 py-2 text-base border rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300 ${
    locked ? 'bg-gray-50 text-gray-400 border-gray-100 cursor-not-allowed' : 'border-gray-200 bg-white'
  }`;

// AIQ-1603: single-select commute preference. The persisted enum differs from the tokens
// RichCommuteMap understands, so translate when feeding the map.
const COMMUTE_OPTIONS = [
  { value: 'car', label: '🚗 Car' },
  { value: 'public_transport', label: '🚇 Public transport' },
  { value: 'bike', label: '🚴 Bike' },
  { value: 'walk', label: '🚶 Walk' },
  { value: 'no_preference', label: 'No preference' },
];
const COMMUTE_TO_MAP_TOKEN: Record<string, string> = {
  car: 'car', public_transport: 'public_transit', bike: 'bike',
  walk: 'walking', no_preference: 'no_pref',
};

// AIQ-1603: preset duration buttons (6/12/24/36 months) + an "Other" manual entry.
const DURATION_PRESETS = [6, 12, 24, 36];
function DurationPicker({ value, onChange }: { value: number | null; onChange: (v: number | null) => void }) {
  const isPreset = value != null && DURATION_PRESETS.includes(value);
  const [other, setOther] = useState(value != null && !isPreset);
  const presetCls = (active: boolean) =>
    `px-4 py-2 rounded-lg border text-base font-medium transition-colors ${
      active ? 'border-accent-500 bg-accent-50 text-accent-700' : 'border-gray-200 bg-white text-gray-700 hover:border-accent-300'
    }`;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        {DURATION_PRESETS.map((m) => (
          <Button key={m} unstyled type="button" onClick={() => { setOther(false); onChange(m); }}
            className={presetCls(!other && value === m)}>
            {m} months
          </Button>
        ))}
        <Button unstyled type="button" onClick={() => { setOther(true); onChange(null); }} className={presetCls(other)}>
          Other
        </Button>
      </div>
      {other && (
        <Input unstyled type="number" min={1} className={inputCls()}
          value={value != null ? String(value) : ''} placeholder="Enter months"
          onChange={(v) => onChange(v.trim() === '' ? null : Number(v))} />
      )}
    </div>
  );
}

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">{children}</div>;
}

function CountryCombo({ value, onChange, placeholder = 'Select a country', disabled, testId, options = COUNTRIES }: {
  value: string; onChange: (v: string) => void; placeholder?: string; disabled?: boolean; testId?: string;
  // Defaults to the relocation-destination list; identity fields pass the full ISO list (AIQ-1341).
  options?: ReadonlyArray<{ code: string; name: string; flag?: string }>;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const selected = options.find((c) => c.code === value);
  const filtered = query
    ? options.filter((c) => c.name.toLowerCase().includes(query.toLowerCase()) || c.code.toLowerCase().includes(query.toLowerCase()))
    : options;

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <div className={`flex items-center border rounded-lg overflow-hidden ${disabled ? 'bg-gray-50 border-gray-100' : 'border-gray-200 bg-white'}`}>
        <span className="px-3 text-base">{selected ? (selected.flag ?? (flagEmoji(selected.code) || '🌐')) : '🔍'}</span>
        <Input unstyled
          type="text"
          data-testid={testId}
          className="flex-1 py-2 pr-3 text-sm focus:outline-none bg-transparent"
          value={open ? query : selected ? selected.name : ''}
          placeholder={placeholder}
          disabled={disabled}
          onChange={(v) => {
            setQuery(v);
            setOpen(true);
            // Auto-commit when the typed text unambiguously identifies a country so
            // the user isn't left with an empty value (and a disabled Continue) after
            // typing the full name without clicking the dropdown. See matchCountry for
            // the name-prefix guard that keeps a code match from firing early.
            const exact = matchCountry(v, [...options]);
            if (exact) { onChange(exact.code); setOpen(false); setQuery(''); }
          }}
          onFocus={() => { if (!disabled) { setQuery(''); setOpen(true); } }}
          autoComplete="off"
        />
        <span className="px-2 text-gray-400 text-xs">▾</span>
      </div>
      {open && !disabled && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 max-h-48 overflow-y-auto bg-white border border-gray-200 rounded-xl shadow-lg">
          {query && filtered.length > 0 && (
            <div className="px-4 pt-2 pb-1 text-[11px] text-gray-400">Select your country from the list</div>
          )}
          {filtered.length === 0
            ? <div className="px-4 py-3 text-xs text-gray-400">No match</div>
            : filtered.map((c) => (
              <div key={c.code} onClick={() => { onChange(c.code); setOpen(false); setQuery(''); }}
                onKeyDown={(e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onChange(c.code); setOpen(false); setQuery(''); } }}
                role="option"
                aria-selected={value === c.code}
                tabIndex={0}
                className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer text-sm hover:bg-gray-50 ${value === c.code ? 'bg-accent-50 text-accent-700' : ''}`}>
                <span className="text-base">{c.flag ?? flagEmoji(c.code)}</span>
                <span className="flex-1">{c.name}</span>
                <span className="text-xs text-gray-400">{c.code}</span>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

function CityCombo({ country, value, onChange, testId, disabled }: { country: string; value: string; onChange: (v: string) => void; testId?: string; disabled?: boolean }) {
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
      <div className={`flex items-center border rounded-lg overflow-hidden ${disabled ? 'bg-gray-50 border-gray-100' : 'border-gray-200 bg-white'}`}>
        <span className="px-3 text-gray-400 text-sm">📍</span>
        <Input unstyled type="text" data-testid={testId} value={value} placeholder="Select or type a city" autoComplete="off"
          disabled={disabled}
          className={`flex-1 py-2 pr-3 text-sm focus:outline-none bg-transparent ${disabled ? 'text-gray-400 cursor-not-allowed' : ''}`}
          onChange={(v) => onChange(v)}
          onFocus={() => { if (!disabled) setOpen(true); }} />
        <span className="px-2 text-gray-400 text-xs">▾</span>
      </div>
      {open && !disabled && opts.length > 0 && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 max-h-40 overflow-y-auto bg-white border border-gray-200 rounded-xl shadow-lg">
          {opts.map((c) => (
            <div key={c} onClick={() => { onChange(c); setOpen(false); }}
              onKeyDown={(e: React.KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onChange(c); setOpen(false); } }}
              role="option"
              aria-selected={value === c}
              tabIndex={0}
              className="px-4 py-2.5 cursor-pointer text-sm hover:bg-gray-50">{c}</div>
          ))}
        </div>
      )}
    </div>
  );
}

// AIQ-1345: the hardcoded Oslo SVG CommuteMap was removed. The commute preview
// is now the real, geocoded <RichCommuteMap> (lazy-loaded), gated on a resolved
// office address — see the "Work & Place" step render below.

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
          <Input unstyled className={`${inputCls()} ph-no-capture`} value={m.name ?? ''} placeholder="e.g. Camille Bouchard"
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
          <Input unstyled className={`${inputCls()} ph-no-capture`} value={m.name ?? ''} placeholder="e.g. Léo"
            onChange={(v) => onChange({ ...m, name: v })} />
        </FieldWrap>
        <FieldWrap label="Date of birth" required why="We compute age automatically for school search and enrollment timing.">
          <Input unstyled type="date" className={`${inputCls()} ph-no-capture`} value={m.dob ?? ''}
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

function ReviewSummary({ data, goTo, loading = false }: { data: IntakeData; goTo: (s: number) => void; loading?: boolean }) {
  const partner = data.members.find((m) => m.kind === 'partner');
  const children = data.members.filter((m) => m.kind === 'child');
  const oC = COUNTRIES.find((c) => c.code === data.origin_country);
  const dC = COUNTRIES.find((c) => c.code === data.dest_country);

  // While the saved draft is still loading, show skeleton rows instead of the
  // "—"/"missing" fallbacks — populated fields would otherwise flash as lost.
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4" aria-busy="true" aria-label="Loading your saved answers">
        {['Move', 'About you', 'Household', 'Work & commute'].map((label) => (
          <div key={label} className="border border-gray-100 rounded-xl p-4 bg-white">
            <div className="mb-3"><span className="text-xs font-bold text-gray-700 uppercase tracking-wide">{label}</span></div>
            <div className="flex flex-col gap-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-3 rounded bg-gray-100 animate-pulse" style={{ width: `${70 - i * 12}%` }} />
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

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
  // TD-FIX-7 (AIQ-1510): origin/originCity join the lock set — a test-drive case is
  // pinned to its assigned corridor, so BOTH ends of the route are HR pre-filled, not
  // just the destination. For real users nothing else in the product writes
  // home_country today, so these stay unlocked exactly as before.
  const [locks, setLocks] = useState({ origin: false, originCity: false, dest: false, destCity: false, email: false, job: false, contractType: false, contractStart: false, salary: false, office: false });
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [savedAt, setSavedAt] = useState(Date.now());
  // Save indicator is bound to the ACTUAL server acknowledgement, not optimistic
  // local state: 'saving' while the PATCH is in flight, 'saved' only after a 2xx
  // (using the server's intakeUpdatedAt), 'error' (with a retry affordance) when
  // the write fails. Previously the indicator flipped to "Auto-saved" before the
  // request resolved and swallowed failures, so a dropped save showed a false
  // positive — the kernel of the "silently fails to persist" report.
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  // AIQ-976: case-scoped intake — when opened via /employee/case/:caseId/intake,
  // the clicked case drives the whole session (draft hydration, autosave, and the
  // services patch below). The bare /employee/intake route has no param, so it
  // falls back to a fresh session id / the primary linked case from context.
  // A brand-new case legitimately has no :caseId (a fresh session id is
  // generated below), so validate-only here — never redirect on a missing param.
  const routeCaseId = useValidatedParams(caseParamsSchema)?.caseId;
  // Stable case ID for the duration of this intake session.
  const caseIdRef = useRef<string>(routeCaseId ?? crypto.randomUUID());
  // Analytics timing: wizard start (for total duration) and per-step start (reset
  // on each forward advance) so wizard_step_completed carries an accurate duration.
  const wizardStartRef = useRef<number>(Date.now());
  const stepStartRef = useRef<number>(Date.now());
  // AIQ-1435: journey funnel — mark the intake step reached (once per mount).
  useEffect(() => {
    track('journey_step_started', { step: 'intake', case_id: caseIdRef.current, persona: 'employee' });
    // TD-FIX-4 (AIQ-1505): test-drive funnel — intake reached (no-op for real users).
    emitTestDriveStage('intake-start');
  }, []);
  // Latest assignment id captured in a ref so the debounced autosave
  // (set up inside `setField`'s closure) always posts to the *current*
  // linked assignment, even if it resolves after the wizard mounts.
  // We can't depend on `assignmentId` directly because setField is
  // stable and its closure would otherwise capture the initial null.
  const assignmentIdRef = useRef<string | null>(null);
  // True once the saved draft has been fetched (success or failure). The
  // autosave in setField is gated on this so a mount-time setField — e.g. the
  // auto-select-services effect, which runs before hydration — can't schedule a
  // save that captures the empty initial state. The draft store REPLACES (not
  // merges) on the backend, so such a save wiped the employee's saved answers
  // on every reload.
  const draftHydratedRef = useRef(false);
  // Render-visible mirror of draftHydratedRef (a ref can't drive a re-render).
  // Used to skeleton the Review summary and gate submit until the saved draft
  // has loaded, so a reload that restores straight to the Review step doesn't
  // paint populated fields as "missing"/"—" before the fetch resolves.
  const [draftHydrated, setDraftHydrated] = useState(false);
  // Set when the draft load FAILED (e.g. the request was blocked/errored). While
  // true we keep autosave disarmed (draftHydratedRef stays false) — saving the
  // empty defaults would overwrite the server draft — and surface a retry instead
  // of a silent blank form. Bumping hydrateAttempt re-runs the hydration effect.
  const [hydrateError, setHydrateError] = useState(false);
  const [hydrateAttempt, setHydrateAttempt] = useState(0);
  const retryHydrate = useCallback(() => setHydrateAttempt((n) => n + 1), []);
  // Tracks the latest unsaved data so the unmount-flush effect can access it
  // without a stale closure. Set in setField on every edit; cleared after
  // each successful debounced save so we don't re-send data that's already
  // persisted.
  const pendingSaveDataRef = useRef<IntakeData | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Persist one draft snapshot and reflect the REAL outcome in the indicator.
  // Resolves true only on a confirmed 2xx. On failure the payload is kept
  // pending (so the next edit or an explicit retry re-sends it) and the
  // indicator shows an error instead of a false "Auto-saved".
  const runIntakeSave = useCallback(async (payload: IntakeData): Promise<boolean> => {
    const aid = assignmentIdRef.current;
    if (!aid) return false;
    setSaveStatus('saving');
    try {
      const res = await employeeAPI.updateIntakeDraft(aid, payload);
      const ts = res?.intakeUpdatedAt ? Date.parse(res.intakeUpdatedAt) : Date.now();
      setSavedAt(Number.isNaN(ts) ? Date.now() : ts);
      setSaveStatus('saved');
      // Persisted — clear it so unmount-flush / retry don't re-send a stale copy.
      // Guard on reference equality: a newer edit may have replaced it mid-flight.
      if (pendingSaveDataRef.current === payload) pendingSaveDataRef.current = null;
      return true;
    } catch {
      pendingSaveDataRef.current = payload;
      setSaveStatus('error');
      return false;
    }
  }, []);

  const retryIntakeSave = useCallback(() => {
    const pending = pendingSaveDataRef.current;
    if (pending) void runIntakeSave(pending);
  }, [runIntakeSave]);

  // Force-persist any pending debounced edit immediately and await the REAL
  // outcome. Resolves true on a confirmed 2xx (or when there's nothing pending),
  // false on a failed save (the indicator then shows "Couldn't save — retry").
  // Used by step navigation and field blur so an edit is never lost, and never
  // left merely "in flight", when the user moves on.
  const flushSave = useCallback(async (): Promise<boolean> => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    const pending = pendingSaveDataRef.current;
    if (!pending || !draftHydratedRef.current || !assignmentIdRef.current) return true;
    return runIntakeSave(pending);
  }, [runIntakeSave]);

  const setField = useCallback(<K extends keyof IntakeData>(k: K, v: IntakeData[K]) => {
    setData((d) => {
      const next = { ...d, [k]: v };
      // Gate on hydration: never schedule a save before the saved draft has
      // loaded, or a pre-hydration edit would persist the empty initial state
      // and clobber the server draft (which replaces, not merges).
      if (draftHydratedRef.current) {
        // Always track the latest unsaved payload so the unmount-flush can
        // pick it up even if the debounce timer hasn't fired yet. Cleared by
        // runIntakeSave only after a confirmed write.
        pendingSaveDataRef.current = next;
        if (saveTimer.current) clearTimeout(saveTimer.current);
        saveTimer.current = setTimeout(() => {
          void runIntakeSave(next);
        }, 700);
      }
      return next;
    });
  }, [runIntakeSave]);

  // Unmount flush: if the user navigates away before the 700ms debounce fires,
  // immediately persist any pending data so it's not lost.
  useEffect(() => {
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
      const pending = pendingSaveDataRef.current;
      const aid = assignmentIdRef.current;
      if (pending && aid && draftHydratedRef.current) {
        // fire-and-forget — component is unmounting, can't update state
        void employeeAPI
          .updateIntakeDraft(aid, pending)
          .catch(() => { /* best-effort */ });
      }
    };
  }, []);

  const unlock = (key: keyof typeof locks) => setLocks((l) => ({ ...l, [key]: false }));

  // TD-FIX-7 (AIQ-1510): on a test drive the route is not the tester's to change — the
  // case is pinned to the corridor their session was assigned, and the server overrides
  // it on write regardless. So withhold the "unlock" escape hatch on the route fields:
  // re-opening them would only let the tester enter a value the server then silently
  // discards. Everything else in intake stays fully editable.
  const isTestDrive = !!getTestDriveSession();
  const routeUnlock = (key: keyof typeof locks) => (isTestDrive ? undefined : () => unlock(key));

  const international = !!(data.origin_country && data.dest_country && data.origin_country !== data.dest_country);

  const partner = data.members.find((m) => m.kind === 'partner');
  const children = data.members.filter((m) => m.kind === 'child');

  // AIQ-1345: geocode the office address (debounced) so the "Verified" badge and
  // the commute preview reflect the real, resolved location — not a fake.
  const officeGeo = useGeocodedAddress(data.office_address);

  const addMember = (kind: MemberKind, extra?: Partial<Member>) => {
    const id = kind + Date.now();
    setField('members', [...data.members, { id, kind, count: 1, ...extra }]);
    setExpanded((e) => ({ ...e, [id]: true }));
  };
  const updateMember = (id: string, next: Member) => setField('members', data.members.map((m) => m.id === id ? next : m));
  const removeMember = (id: string) => setField('members', data.members.filter((m) => m.id !== id));
  const toggleMember = (id: string) => setExpanded((e) => ({ ...e, [id]: !e[id] }));

  const stepValid = (s: number) => {
    if (s === 1) return !!(data.origin_country && data.origin_city && data.dest_country && data.dest_city && data.target_date && data.purpose);
    if (s === 2) return !!(data.full_name && data.nationality && data.passport_country && data.passport_expiry);
    if (s === 3) return data.members.length >= 1;
    if (s === 4) return !!(data.job_title && data.contract_start && data.contract_type && data.office_address && data.work_pattern && data.salary_band);
    return true;
  };

  const goTo = async (s: number) => {
    // Force-persist any pending edit and wait for a real 2xx before moving on.
    // On failure, stay on the current step (the indicator shows "Couldn't save
    // — retry") so navigation never silently drops unsaved data.
    const ok = await flushSave();
    if (!ok) return;
    // Analytics: only count a step as "completed" when advancing forward past it.
    if (s > step) {
      const name = WIZARD_STEP_NAMES[step];
      if (name) {
        trackWizardStepCompleted({
          case_id: caseIdRef.current,
          step_number: step,
          step_name: name,
          duration_seconds: Math.max(0, Math.round((Date.now() - stepStartRef.current) / 1000)),
        });
      }
    }
    stepStartRef.current = Date.now();
    setStep(s);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Pets are a normal service category now (selected in service selection, HR-curated);
  // the intake wizard no longer asks a has_pets yes/no.
  // Canonical step list lives in ./intakeSteps so the dashboard derives the same total.
  const STEP_LABELS = INTAKE_STEP_LABELS;
  // EMP-3: decorative emoji step-icons removed (consumer-app register). The numbered
  // circle in the stepper below is the step indicator (✓ when stepValid && n < step).
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
  // AIQ-976: the clicked case (routeCaseId) drives the session; the bare
  // /employee/intake route falls back to the primary linked assignment.
  // The intake endpoints are ASSIGNMENT-scoped (/api/employee/assignments/{id}/…),
  // so `routeCaseId` (a case_id) must be resolved to its assignment_id via
  // linkedSummaries — passing the case_id 404s (broke autosave/hydration/prefill
  // and logged console 404s). Stay null until resolved so the guarded effects
  // below never fire a request with the wrong id.
  const { assignmentId: contextAssignmentId, linkedSummaries } = useEmployeeAssignment();
  // The :caseId route param can be EITHER a case_id (sidebar "Intake form") or an
  // assignment_id (dashboard "Continue intake"). Normalize to both so both entry
  // points run the identical hydration/autosave/submit path.
  const resolvedIds = resolveIntakeIds(routeCaseId, linkedSummaries);
  const assignmentId = routeCaseId ? resolvedIds.assignmentId : contextAssignmentId;
  // Keep caseIdRef (used by the submit's PATCH /api/cases/{caseId}) pointed at the
  // real case_id once linkedSummaries resolves — even when the param was an
  // assignment_id. Falls back to the param for HR deep-links carrying a case UUID.
  useEffect(() => {
    if (resolvedIds.caseId) caseIdRef.current = resolvedIds.caseId;
  }, [resolvedIds.caseId]);
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
    // TD-FIX-7 (AIQ-1510): lock the ORIGIN too — but only on a test drive, where the
    // corridor genuinely is fixed by us.
    //
    // Why the guard: relocation_cases.home_country/host_country are written back from the
    // EMPLOYEE's own intake answers (db/intake.py apply_wizard_patch_side_effects →
    // touch_relocation_case_route_from_wizard). So for a real user this effect re-reads
    // what they typed themselves — and locking it would badge their own answer
    // "🔒 HR pre-filled", which is simply untrue. Real users keep the origin editable.
    // (The destination has claimed this since before TD-FIX-7; fixing that needs real
    // route provenance — HR actually setting the route — and is tracked separately.)
    if (isTestDrive && originCity) {
      setLocks((l) => ({ ...l, originCity: true }));
    }
    if (isTestDrive && originCode) {
      setLocks((l) => ({ ...l, origin: true }));
    }

    const saved = row?.intake_step;
    if (typeof saved === 'number' && saved > 0) {
      const clamped = clampIntakeStep(saved, TOTAL_STEPS);
      setStep(clamped);
      lastPersistedStepRef.current = clamped;
    } else if (typeof saved === 'number') {
      // saved === 0: never opened. Mark as hydrated so we don't keep checking.
      lastPersistedStepRef.current = 0;
    }
    hydratedStepRef.current = true;
  }, [assignmentId, linkedSummaries, TOTAL_STEPS, isTestDrive]);

  // Keep the autosave closure pointing at the current assignment id.
  useEffect(() => {
    assignmentIdRef.current = assignmentId;
  }, [assignmentId]);

  // ── Form-draft hydration ──────────────────────────────────────
  // One-shot fetch of the saved draft from
  // GET /api/employee/assignments/{id}/intake. Merges into local
  // state only over empty fields so a user typing during the
  // load doesn't get their work overwritten. Failure is soft —
  // the wizard still runs against the in-memory defaults. draftHydratedRef is
  // declared above (it also gates the autosave); set true here in finally().
  useEffect(() => {
    if (draftHydratedRef.current || !assignmentId) return;
    let cancelled = false;
    setHydrateError(false);
    void employeeAPI
      .getIntake(assignmentId)
      .then((res) => {
        if (cancelled) return;
        if (res.intakeDraft && typeof res.intakeDraft === 'object') {
          // Apply the saved draft over each field unless the user actively typed
          // something during the brief hydration window (detected by comparing
          // against INITIAL_DATA: a field that still matches its default is
          // untouched and gets the saved value; genuinely empty fields always do
          // too). This restores fields with non-empty defaults (members, purpose,
          // contract_type) which the old isEmpty-only check never restored. The
          // merge is a pure function (intakeHydration.ts) so it's unit-tested.
          setData((d) => mergeIntakeDraft(d, res.intakeDraft as Record<string, unknown>, INITIAL_DATA));
        }
        // Success — a real draft OR a legitimately-empty one (200 with null draft).
        // Only now is it safe to arm autosave; saving before a confirmed load could
        // overwrite the server draft with empty defaults.
        draftHydratedRef.current = true;
        setDraftHydrated(true);
      })
      .catch(() => {
        // Load failed (e.g. blocked/errored request). Do NOT arm autosave — an
        // empty-default save would clobber the saved draft — and surface a retry
        // rather than silently showing a blank form.
        if (!cancelled) setHydrateError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [assignmentId, hydrateAttempt]);

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

  // Only "loading" when there's an assignment whose saved draft hasn't resolved
  // yet. With no assignment (bare /employee/intake) there's nothing to fetch, so
  // the fresh empty defaults are correct and we don't skeleton.
  const intakeLoading = !!assignmentId && !draftHydrated && !hydrateError;

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

        {/* Pre-fill banner — only when HR actually pre-filled at least one field
            (locks.* are set during hydration only when the case carried a value;
            e.g. an empty destination leaves locks.dest false). Hidden otherwise so
            we never claim "destination pre-filled" on a case with no destination. */}
        {Object.values(locks).some(Boolean) && (
          <div className="flex items-start gap-3 p-3 mb-5 bg-blue-50 border border-blue-100 rounded-xl text-xs text-blue-700">
            <span className="flex-shrink-0">ℹ</span>
            {/* TD-FIX-7 (AIQ-1510): on a test drive the only pre-filled fields are the four
                route fields, and they carry no "Edit" affordance (the corridor is fixed and
                the server overrides it anyway) — so the standard "Click Edit" instruction
                would send the tester looking for a button that isn't there. */}
            {isTestDrive ? (
              <div><strong>Your route is fixed for this test</strong> — origin and destination are set to your assigned corridor. Everything else is yours to fill in.</div>
            ) : (
              <div><strong>Some fields are pre-filled by your HR team</strong> (destination, office address, contract details, salary band). Click &quot;Edit&quot; on any pre-filled field if anything looks wrong.</div>
            )}
          </div>
        )}

        {/* Hydration-failure banner — the saved draft couldn't be loaded. We keep
            autosave disarmed so we never overwrite the server draft with blanks,
            and offer a retry instead of a silent blank form. */}
        {hydrateError && (
          <div className="flex items-start justify-between gap-3 p-3 mb-5 bg-red-50 border border-red-100 rounded-xl text-xs text-red-700">
            <div>
              <strong>Couldn&apos;t load your saved answers.</strong> To avoid overwriting what
              you&apos;ve already saved, editing is paused until this loads.
            </div>
            <button
              type="button"
              onClick={retryHydrate}
              className="flex-shrink-0 font-semibold text-red-700 underline hover:text-red-900"
            >
              Retry
            </button>
          </div>
        )}

        {/* Wizard frame */}
        <div className="bg-white border border-gray-100 rounded-2xl shadow-sm overflow-hidden">

          {/* Progress stepper */}
          <div className="border-b border-gray-100 px-5 pt-4 pb-3">
            <div className="flex items-center justify-between mb-2 text-xs text-gray-400">
              <span className="font-semibold text-gray-600">Detailed Intake</span>
              {saveStatus === 'saving' ? (
                <span className="text-gray-400">Saving…</span>
              ) : saveStatus === 'error' ? (
                <button
                  type="button"
                  onClick={retryIntakeSave}
                  className="font-medium text-red-600 hover:underline"
                >
                  Couldn&apos;t save — retry
                </button>
              ) : (
                <span>Auto-saved {savedLabel}</span>
              )}
              <span data-testid="intake-step-indicator">Step {step} / {TOTAL_STEPS}</span>
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
                    onClick={() => { if (n < step) void goTo(n); }}
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
                    <span className="hidden sm:inline">{lbl}</span>
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
          <div className="p-5" onBlur={() => { void flushSave(); }}>

            {/* ── Step 1 — Journey ── */}
            {step === 1 && (
              <>
                <StepHd title="Where are you moving from and to?" sub="Just the basics — we'll use this to start drafting your roadmap." required />
                <Grid>
                  <FieldWrap label="Origin country" required prefill={locks.origin} onUnlock={routeUnlock('origin')}>
                    <CountryCombo testId="intake-origin_country" value={data.origin_country} onChange={(v) => setField('origin_country', v)} disabled={locks.origin} />
                  </FieldWrap>
                  <FieldWrap label="Origin city" required prefill={locks.originCity} onUnlock={routeUnlock('originCity')}>
                    <CityCombo testId="intake-origin_city" country={data.origin_country} value={data.origin_city} onChange={(v) => setField('origin_city', v)} disabled={locks.originCity} />
                  </FieldWrap>
                  <FieldWrap label="Destination country" required prefill={locks.dest} onUnlock={routeUnlock('dest')}>
                    <CountryCombo testId="intake-dest_country" value={data.dest_country} onChange={(v) => setField('dest_country', v)} disabled={locks.dest} />
                  </FieldWrap>
                  {/* destCity: badged as pre-filled but left EDITABLE for real users — that
                      is the pre-TD-FIX-7 behaviour and the city is often the part HR gets
                      wrong. Disabled only on a test drive, where the corridor is fixed. */}
                  <FieldWrap label="Destination city" required prefill={locks.destCity} onUnlock={routeUnlock('destCity')}>
                    <CityCombo testId="intake-dest_city" country={data.dest_country} value={data.dest_city} onChange={(v) => setField('dest_city', v)} disabled={isTestDrive && locks.destCity} />
                  </FieldWrap>
                  <FieldWrap label="Target move date" required>
                    <Input unstyled type="date" data-testid="intake-target_date" aria-label="Target move date" className={inputCls()} value={data.target_date}
                      onChange={(v) => setField('target_date', v)} />
                  </FieldWrap>
                  <FieldWrap label="Purpose of relocation" required>
                    {/* The values MUST be lowercase. This <select> had no value=
                        attributes, so the option TEXT was the value and it emitted
                        Title-Case "Employment". requirement_items.purpose is seeded
                        lowercase and matched with `==`, so every one of those cases
                        missed the catalog and got an empty requirements list —
                        which on that screen reads as "nothing is required of you". */}
                    <select data-testid="intake-purpose" aria-label="Purpose of relocation" className={selectCls()} value={data.purpose} onChange={(e) => setField('purpose', e.target.value)}>
                      <option value="employment">Employment</option>
                      <option value="study">Study</option>
                      <option value="family">Family</option>
                      <option value="other">Other</option>
                    </select>
                  </FieldWrap>
                </Grid>
                {international && (
                  <div className="flex items-start gap-2 mt-4 p-3 bg-blue-50 border border-blue-100 rounded-xl text-xs text-blue-700">
                    🌍 <span><strong>International move detected.</strong> We&apos;ll automatically include visa, customs, international movers, and pet import (if relevant) in your roadmap.</span>
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
                    <Input unstyled data-testid="intake-full_name" className={`${inputCls()} ph-no-capture`} value={data.full_name} placeholder="As shown on your passport"
                      onChange={(v) => setField('full_name', v)} />
                  </FieldWrap>
                  <FieldWrap label="Email" required prefill={locks.email} onUnlock={() => unlock('email')}>
                    <Input unstyled type="email" data-testid="intake-email" className={`${inputCls(locks.email)} ph-no-capture`} value={data.email} disabled={locks.email}
                      onChange={(v) => setField('email', v)} />
                  </FieldWrap>
                  <FieldWrap label="Nationality" required>
                    <CountryCombo testId="intake-nationality" value={data.nationality} onChange={(v) => setField('nationality', v)} options={ALL_COUNTRY_OPTIONS} />
                  </FieldWrap>
                  <FieldWrap label="Passport country" required>
                    <CountryCombo testId="intake-passport_country" value={data.passport_country} onChange={(v) => setField('passport_country', v)} options={ALL_COUNTRY_OPTIONS} />
                  </FieldWrap>
                  <FieldWrap label="Passport expiry" required>
                    <Input unstyled type="date" data-testid="intake-passport_expiry" className={`${inputCls()} ph-no-capture`} value={data.passport_expiry}
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
                    ℹ <span><strong>Moving solo?</strong> That&apos;s fine — just continue. You can add household members later from your profile.</span>
                  </div>
                )}
              </>
            )}

            {/* ── Step 4 — Work & Place ── */}
            {step === 4 && (
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
                      <div className={`flex items-center gap-2 mt-1 px-2.5 py-1.5 rounded-lg text-xs ${
                        officeGeo.status === 'notfound' ? 'bg-amber-50 text-amber-700' : 'bg-gray-50 text-gray-500'
                      }`}>
                        📍 <span className="flex-1">{data.office_address}</span>
                        {officeGeo.status === 'loading' && <span className="text-gray-400">Locating…</span>}
                        {officeGeo.status === 'ok' && (
                          <span className="text-green-600 font-medium">Verified</span>
                        )}
                        {officeGeo.status === 'notfound' && (
                          <span className="font-medium">Couldn&apos;t find that address — check the spelling</span>
                        )}
                      </div>
                    )}
                  </FieldWrap>
                  <FieldWrap label="Work pattern" required className="sm:col-span-2">
                    <MultiChip value={data.work_pattern ? [data.work_pattern] : []} onChange={(v) => setField('work_pattern', v[v.length - 1] || '')}
                      options={['Full in-office', 'Hybrid', 'Fully remote']} />
                  </FieldWrap>
                  {/* AIQ-1349: assignment type drives the duration-aware policy +
                      roadmap. STA gets a lighter journey; LTA/PERMANENT the full one. */}
                  <FieldWrap label="Assignment type" required className="sm:col-span-2"
                    why="Short-term assignments get a lighter roadmap and different benefits than a permanent move.">
                    <MultiChip value={data.assignment_type ? [data.assignment_type] : []}
                      onChange={(v) => setField('assignment_type', v[v.length - 1] || '')}
                      options={[
                        { value: 'STA', label: 'Short-term (under 12 months)' },
                        { value: 'LTA', label: 'Long-term (1–5 years)' },
                        { value: 'PERMANENT', label: 'Permanent transfer' },
                      ]} />
                  </FieldWrap>
                  {/* AIQ-1349: optional expected length in months →
                      assignmentContext.expectedDurationMonths for duration_threshold rules. */}
                  <FieldWrap label="Expected duration (months)"
                    hint="Optional — helps tailor which requirements apply to your stay.">
                    <DurationPicker value={data.expected_duration_months}
                      onChange={(v) => setField('expected_duration_months', v)} />
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
                        <SegmentedOptionCards value={data.commute_preference}
                          onChange={(v) => setField('commute_preference', v)}
                          options={COMMUTE_OPTIONS} />
                      </FieldWrap>
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-gray-700 mb-1.5">Commute map · live preview</div>
                      {officeGeo.status === 'ok' ? (
                        <Suspense fallback={<div className="rounded-xl border border-gray-100 bg-gray-50 h-48 flex items-center justify-center text-xs text-gray-400">Loading commute map…</div>}>
                          <RichCommuteMap
                            officeAddress={data.office_address}
                            commuteMins={data.commute_mins}
                            commuteMode={[COMMUTE_TO_MAP_TOKEN[data.commute_preference] ?? 'no_pref']}
                            hasChildren={children.length > 0}
                          />
                        </Suspense>
                      ) : (
                        <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 h-48 flex items-center justify-center px-4 text-center text-xs text-gray-400">
                          {officeGeo.status === 'notfound'
                            ? 'We couldn’t locate that office address — fix it above to preview your commute area.'
                            : 'Enter your office address above to preview your commute area.'}
                        </div>
                      )}
                    </div>
                  </div>
                )}
                {data.work_pattern === 'Fully remote' && (
                  <div className="flex items-start gap-2 mt-4 p-3 bg-blue-50 border border-blue-100 rounded-xl text-xs text-blue-700">
                    ℹ <span><strong>Working fully remote.</strong> We&apos;ll skip commute filtering and lead housing search with neighborhood quality and lifestyle priorities instead.</span>
                  </div>
                )}
              </>
            )}

            {/* ── Step 5 — Review ── */}
            {step === 5 && (
              <>
                <StepHd title="Review & submit" sub="A quick check before we generate your roadmap. You can edit any section later." />
                <ReviewSummary data={data} goTo={goTo} loading={intakeLoading} />
                {/* H-07 (AIQ-1254): the messaging panel was removed from the Review
                    step — a chat UI at the moment of submission was cognitive overload.
                    Point the employee to the Inbox instead. */}
                <p className="mt-4 text-sm text-slate-600">
                  Questions? Message your HR team from your Inbox after submitting.
                </p>
                {/* PRIV-005 / AIQ-473 — Art. 13 notice at the point of collection.
                    Acknowledging records a privacy_consents row and unblocks submit. */}
                <div className="mt-5">
                  <PrivacyNotice
                    noticeVersion={PRIVACY_NOTICE_VERSION}
                    context="onboarding"
                    checked={data.consent}
                    onChange={(v) => setField('consent', v)}
                  />
                  {/* P1-07c / AIQ-686 — optional anonymized outcome-sharing opt-in.
                      Distinct from the mandatory Art.13 ack above; never gates submit. */}
                  <OutcomeSharingOptIn caseId={caseIdRef.current} />
                </div>
              </>
            )}
          </div>

          {/* Footer nav */}
          <div className="flex items-center justify-between border-t border-gray-100 px-5 py-4">
            {step > 1 ? (
              <Button unstyled type="button" data-testid="intake-back" onClick={() => void goTo(step - 1)}
                className="px-4 py-2 text-sm font-semibold border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                ← Back
              </Button>
            ) : <div />}
            <div className="flex items-center gap-1.5 text-xs text-gray-400">
              🔒 Encrypted · only you and your HR team see this
            </div>
            {step < TOTAL_STEPS ? (
              <Button unstyled type="button" data-testid="intake-continue" onClick={() => void goTo(step + 1)} disabled={!stepValid(step)}
                aria-describedby={!stepValid(step) ? 'intake-step-hint' : undefined}
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
                <Button unstyled type="button" disabled={!data.consent || submitting || intakeLoading || hydrateError}
                  onClick={async () => {
                    setSubmitting(true);
                    setSubmitError(null);
                    try {
                      // Confirm the latest intake-draft is persisted before we
                      // promote it and flip status. Block submit on a failed save.
                      const saved = await flushSave();
                      if (!saved) {
                        setSubmitError("Couldn't save your latest changes. Please retry.");
                        setSubmitting(false);
                        return;
                      }
                      // Persist the FULL intake onto the canonical case (not just
                      // services) so HR, the case record, and the plan/roadmap see
                      // everything the employee entered.
                      await patchCase(caseIdRef.current, intakeToCaseDraft(data));
                      if (assignmentId) {
                        // Flip the assignment to "submitted" so the case advances
                        // past intake (status surfaces + roadmap generation). The
                        // backend syncs the profile from the full draft written
                        // above, so this no longer 400s "complete all wizard steps".
                        // Awaited: a real precondition failure surfaces to the user.
                        await employeeAPI.submitAssignment(assignmentId);
                        // Also mark the wizard complete (status reads intake_step too).
                        void employeeAPI.updateIntakeProgress(
                          assignmentId,
                          TOTAL_STEPS,
                          TOTAL_STEPS,
                        ).catch(() => undefined);
                      }
                      // AIQ-1435: journey funnel — intake completed on successful submit.
                      track('journey_step_completed', { step: 'intake', case_id: caseIdRef.current, persona: 'employee' });
                      // Typed funnel event with PII-free household shape (no names).
                      {
                        const nonSelf = data.members.filter((m) => m.kind !== 'self' && m.kind !== 'pet');
                        const partner = data.members.find((m) => m.kind === 'partner');
                        trackWizardCompleted({
                          case_id: caseIdRef.current,
                          total_duration_seconds: Math.max(0, Math.round((Date.now() - wizardStartRef.current) / 1000)),
                          has_family: nonSelf.length > 0,
                          household_size: data.members.filter((m) => m.kind !== 'pet').length,
                          partner_needs_work_permit: partner?.needs_work_permit === 'yes',
                        });
                      }
                      // TD-FIX-4 (AIQ-1505): test-drive funnel — intake completed.
                      emitTestDriveStage('intake-completed');
                      // B5: land on the roadmap the submit just unlocked, not a
                      // dashboard that can momentarily read as "intake not started".
                      navigate(
                        caseIdRef.current
                          ? buildRoute('employeeCaseRoadmap', { caseId: caseIdRef.current })
                          : ROUTE_DEFS.employeeDashboard.path,
                      );
                    } catch (e) {
                      // AIQ-1311: surface the server's human message + route the
                      // user back to the step it pinpoints, instead of the raw
                      // "Request failed with status code 400".
                      const { message, suggestedStep } = parseSubmitError(e);
                      setSubmitError(message);
                      setSubmitting(false);
                      if (suggestedStep != null) setStep(suggestedStep);
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
          {step < TOTAL_STEPS && !stepValid(step) && (
            <p
              id="intake-step-hint"
              role="status"
              className="px-5 pb-4 -mt-2 text-right text-xs text-gray-500"
            >
              Complete the required fields above to continue.
            </p>
          )}
        </div>
      </div>
    </AppShell>
  );
}
