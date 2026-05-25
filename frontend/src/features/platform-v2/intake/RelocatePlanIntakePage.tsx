/**
 * RelocatePlanIntakePage
 *
 * Simple 6-step card-grid intake wizard ("Build your relocation plan").
 * Matches the platform-v2 design mocks exactly:
 *   From → To → Purpose → Type → Start → Household
 *
 * Right-panel updates live as the user selects each option.
 * Saves each answer to the backend via PATCH /api/cases/:caseId (deep-merge).
 *
 * Case ID resolution order:
 *   1. URL path param  :caseId
 *   2. URL search param  ?caseId=xxx
 *   3. First linked assignment in EmployeeAssignmentContext
 *   4. Demo-mode (no backend save)
 */

import { useState, useCallback, useRef } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
// useNavigate is used in the completion screen CTA
import { AppShell } from '../../../components/AppShell';
import { logger } from '../../../lib/logger';
import { patchCase } from '../../../api/cases';
import { useEmployeeAssignment } from '../../../contexts/EmployeeAssignmentContext';
import { getAuthItem } from '../../../utils/demo';

// ─── Types ────────────────────────────────────────────────────────────────────

interface IntakeState {
  fromCode: string | null;    // ISO 3166-1 alpha-2
  toCode: string | null;
  purpose: string | null;     // 'employment' | 'intracompany' | 'study' | 'family'
  employmentType: string | null; // 'Permanent' | 'Fixed-term' | 'Secondment'
  startWindow: string | null; // 'within6w' | '1to3m' | '3to6m' | 'flexible'
  household: string | null;   // 'solo' | 'partner' | 'partner_children' | 'children'
}

interface Country {
  code: string;
  name: string;
  flag: string;
}

interface OptionCard {
  id: string;
  label: string;
  sub?: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const GRID_COUNTRIES: Country[] = [
  { code: 'FR', name: 'France',         flag: '🇫🇷' },
  { code: 'DE', name: 'Germany',        flag: '🇩🇪' },
  { code: 'GB', name: 'United Kingdom', flag: '🇬🇧' },
  { code: 'ES', name: 'Spain',          flag: '🇪🇸' },
  { code: 'NL', name: 'Netherlands',    flag: '🇳🇱' },
  { code: 'IT', name: 'Italy',          flag: '🇮🇹' },
  { code: 'IN', name: 'India',          flag: '🇮🇳' },
  { code: 'BR', name: 'Brazil',         flag: '🇧🇷' },
  { code: 'US', name: 'United States',  flag: '🇺🇸' },
  { code: 'CA', name: 'Canada',         flag: '🇨🇦' },
  { code: 'NO', name: 'Norway',         flag: '🇳🇴' },
  { code: 'SG', name: 'Singapore',      flag: '🇸🇬' },
];

const PURPOSE_OPTIONS: OptionCard[] = [
  { id: 'employment',     label: 'Employment',              sub: 'Long-term role with your company' },
  { id: 'intracompany',   label: 'Intra-company transfer',  sub: 'Move between company entities' },
  { id: 'study',          label: 'Study or research',       sub: 'Sponsored academic placement' },
  { id: 'family',         label: 'Family reunification',    sub: 'Joining an existing resident' },
];

const TYPE_OPTIONS: OptionCard[] = [
  { id: 'Permanent',   label: 'Permanent',   sub: 'Full-time, open-ended' },
  { id: 'Fixed-term',  label: 'Fixed-term',  sub: '6–36 months' },
  { id: 'Secondment',  label: 'Secondment',  sub: 'Inter-entity placement' },
];

const START_OPTIONS: OptionCard[] = [
  { id: 'within6w', label: 'Within 6 weeks', sub: 'Expedite track' },
  { id: '1to3m',    label: 'In 1–3 months',  sub: 'Standard track' },
  { id: '3to6m',    label: 'In 3–6 months',  sub: 'Planned track' },
  { id: 'flexible', label: 'Flexible',        sub: 'No fixed date yet' },
];

const HOUSEHOLD_OPTIONS: OptionCard[] = [
  { id: 'solo',             label: 'Just me',              sub: 'No dependents' },
  { id: 'partner',          label: 'Partner',              sub: 'Married or civil union' },
  { id: 'partner_children', label: 'Partner + children',   sub: 'School-age dependents' },
  { id: 'children',         label: 'Children only',        sub: 'Single-parent move' },
];

const STEPS = ['From', 'To', 'Purpose', 'Type', 'Start', 'Household'] as const;

// ─── AI Prediction Lookup ────────────────────────────────────────────────────

interface Prediction {
  route: string;
  weeks: string;
  cost: string;
  confidence: number;
}

const CORRIDOR_PREDICTIONS: Record<string, Prediction> = {
  'FR-NO-employment':   { route: 'Skilled Worker Permit (UDI)', weeks: '10–14 weeks', cost: '€680',   confidence: 95 },
  'DE-NO-employment':   { route: 'Skilled Worker Permit (UDI)', weeks: '8–12 weeks',  cost: '€680',   confidence: 92 },
  'GB-NO-employment':   { route: 'Skilled Worker Permit (UDI)', weeks: '10–14 weeks', cost: '€680',   confidence: 90 },
  'IN-NO-employment':   { route: 'Skilled Worker Permit (UDI)', weeks: '14–20 weeks', cost: '€750',   confidence: 78 },
  'US-NO-employment':   { route: 'Skilled Worker Permit (UDI)', weeks: '12–18 weeks', cost: '€750',   confidence: 80 },
  'FR-DE-employment':   { route: 'EU Blue Card',                weeks: '8–12 weeks',  cost: '€450',   confidence: 90 },
  'IN-DE-employment':   { route: 'Skilled Worker Visa (§18a)',   weeks: '12–18 weeks', cost: '€650',   confidence: 82 },
  'GB-DE-employment':   { route: 'Skilled Worker Visa (§18a)',   weeks: '10–16 weeks', cost: '€600',   confidence: 85 },
  'US-DE-employment':   { route: 'Skilled Worker Visa',          weeks: '10–14 weeks', cost: '€550',   confidence: 80 },
  'FR-NL-employment':   { route: 'Highly Skilled Migrant (HSM)', weeks: '4–8 weeks',   cost: '€350',   confidence: 93 },
  'IN-NL-employment':   { route: 'Highly Skilled Migrant (HSM)', weeks: '4–8 weeks',   cost: '€420',   confidence: 88 },
  'FR-GB-employment':   { route: 'Skilled Worker Visa',          weeks: '8–12 weeks',  cost: '£1,100', confidence: 88 },
  'IN-GB-employment':   { route: 'Skilled Worker Visa',          weeks: '8–12 weeks',  cost: '£1,300', confidence: 85 },
  'FR-SG-employment':   { route: 'Employment Pass (EP)',          weeks: '3–5 weeks',   cost: 'S$160',  confidence: 87 },
  'IN-SG-employment':   { route: 'S Pass / Employment Pass',      weeks: '3–6 weeks',   cost: 'S$200',  confidence: 80 },
  'FR-CA-employment':   { route: 'Work Permit (LMIA-exempt)',     weeks: '8–16 weeks',  cost: 'C$230',  confidence: 78 },
  'GB-CA-employment':   { route: 'Work Permit (IEC / LMIA)',      weeks: '8–16 weeks',  cost: 'C$230',  confidence: 78 },
  'FR-ES-employment':   { route: 'EU Free Movement',             weeks: '2–4 weeks',   cost: '€80',    confidence: 97 },
  'FR-IT-employment':   { route: 'EU Free Movement',             weeks: '2–4 weeks',   cost: '€80',    confidence: 97 },
  'FR-BE-employment':   { route: 'EU Free Movement',             weeks: '1–3 weeks',   cost: '€60',    confidence: 98 },
  'DE-FR-employment':   { route: 'EU Free Movement',             weeks: '1–3 weeks',   cost: '€60',    confidence: 98 },
  // Intracompany
  'FR-NO-intracompany': { route: 'ICT Permit (Norway)',          weeks: '12–16 weeks', cost: '€750',   confidence: 88 },
  'FR-DE-intracompany': { route: 'ICT Visa (§19a AufenthG)',     weeks: '8–12 weeks',  cost: '€500',   confidence: 88 },
  'IN-DE-intracompany': { route: 'ICT Visa (§19a AufenthG)',     weeks: '10–14 weeks', cost: '€600',   confidence: 85 },
  // Study
  'FR-NO-study':        { route: 'Student Residence Permit',     weeks: '4–8 weeks',   cost: '€400',   confidence: 85 },
  'IN-DE-study':        { route: 'Student Visa (§16b)',          weeks: '8–12 weeks',  cost: '€500',   confidence: 82 },
};

function getPrediction(fromCode: string | null, toCode: string | null, purpose: string | null): Prediction | null {
  if (!fromCode || !toCode || !purpose) return null;
  const purposeKey = purpose.replace('intracompany', 'intracompany');
  const key = `${fromCode}-${toCode}-${purposeKey}`;
  return CORRIDOR_PREDICTIONS[key] ?? null;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getCountry(code: string | null): Country | null {
  if (!code) return null;
  return GRID_COUNTRIES.find((c) => c.code === code) ?? null;
}

function startWindowToLabel(id: string | null): string {
  if (!id) return '—';
  return START_OPTIONS.find((o) => o.id === id)?.label ?? '—';
}

function householdToLabel(id: string | null): string {
  if (!id) return '—';
  return HOUSEHOLD_OPTIONS.find((o) => o.id === id)?.label ?? '—';
}

function purposeToLabel(id: string | null): string {
  if (!id) return '—';
  return PURPOSE_OPTIONS.find((o) => o.id === id)?.label ?? '—';
}

/** Compute targetMoveDate from startWindow choice */
function startWindowToDate(id: string): string | null {
  const today = new Date();
  const add = (days: number) => {
    const d = new Date(today);
    d.setDate(d.getDate() + days);
    return d.toISOString().slice(0, 10);
  };
  if (id === 'within6w') return add(42);
  if (id === '1to3m')    return add(60);
  if (id === '3to6m')    return add(120);
  return null; // flexible
}

/** Map household choice → draft shape */
function householdToDraft(id: string) {
  if (id === 'solo')             return { hasDependents: false,  maritalStatus: 'Single'  };
  if (id === 'partner')          return { hasDependents: true,   maritalStatus: 'Married' };
  if (id === 'partner_children') return { hasDependents: true,   maritalStatus: 'Married' };
  if (id === 'children')         return { hasDependents: true,   maritalStatus: 'Single'  };
  return {};
}

// Step-specific info tips
function getInfoTip(step: number, state: IntakeState): string | null {
  if (step === 1 && state.toCode === 'NO')
    return 'Most EU employees moving to Norway file civil documents from the origin country first — we\'ll pre-fill those.';
  if (step === 2)
    return 'ReloPass currently has corridor-grade requirements for 47 destinations.';
  if (step === 3 && state.fromCode && state.toCode)
    return `We\'ll tailor your document checklist to the exact ${getCountry(state.fromCode)?.name} → ${getCountry(state.toCode)?.name} corridor.`;
  return null;
}

// ─── Brand palette ────────────────────────────────────────────────────────────

const T    = '#197b78';   // teal accent
const TL   = '#e6f2f4';   // teal light bg
const NAVY = '#0c1929';   // primary navy

// ─── Extended country list (for "not listed" modal dropdown) ──────────────────

const MODAL_COUNTRIES = [
  { code: 'FR', name: 'France',               flag: '🇫🇷' },
  { code: 'DE', name: 'Germany',              flag: '🇩🇪' },
  { code: 'GB', name: 'United Kingdom',       flag: '🇬🇧' },
  { code: 'NO', name: 'Norway',               flag: '🇳🇴' },
  { code: 'SE', name: 'Sweden',               flag: '🇸🇪' },
  { code: 'NL', name: 'Netherlands',          flag: '🇳🇱' },
  { code: 'BE', name: 'Belgium',              flag: '🇧🇪' },
  { code: 'IE', name: 'Ireland',              flag: '🇮🇪' },
  { code: 'CH', name: 'Switzerland',          flag: '🇨🇭' },
  { code: 'IT', name: 'Italy',                flag: '🇮🇹' },
  { code: 'ES', name: 'Spain',                flag: '🇪🇸' },
  { code: 'PT', name: 'Portugal',             flag: '🇵🇹' },
  { code: 'US', name: 'United States',        flag: '🇺🇸' },
  { code: 'CA', name: 'Canada',               flag: '🇨🇦' },
  { code: 'JP', name: 'Japan',                flag: '🇯🇵' },
  { code: 'KR', name: 'South Korea',          flag: '🇰🇷' },
  { code: 'IN', name: 'India',                flag: '🇮🇳' },
  { code: 'SG', name: 'Singapore',            flag: '🇸🇬' },
  { code: 'AE', name: 'United Arab Emirates', flag: '🇦🇪' },
  { code: 'AU', name: 'Australia',            flag: '🇦🇺' },
  { code: 'BR', name: 'Brazil',               flag: '🇧🇷' },
  { code: 'PL', name: 'Poland',               flag: '🇵🇱' },
  { code: 'DK', name: 'Denmark',              flag: '🇩🇰' },
  { code: 'FI', name: 'Finland',              flag: '🇫🇮' },
  { code: 'MX', name: 'Mexico',               flag: '🇲🇽' },
  { code: 'ZA', name: 'South Africa',         flag: '🇿🇦' },
  { code: 'NZ', name: 'New Zealand',          flag: '🇳🇿' },
  { code: 'HK', name: 'Hong Kong',            flag: '🇭🇰' },
  { code: 'TH', name: 'Thailand',             flag: '🇹🇭' },
  { code: 'AR', name: 'Argentina',            flag: '🇦🇷' },
  { code: 'CL', name: 'Chile',                flag: '🇨🇱' },
  { code: 'CO', name: 'Colombia',             flag: '🇨🇴' },
  { code: 'AT', name: 'Austria',              flag: '🇦🇹' },
  { code: 'CZ', name: 'Czech Republic',       flag: '🇨🇿' },
  { code: 'HU', name: 'Hungary',              flag: '🇭🇺' },
  { code: 'RO', name: 'Romania',              flag: '🇷🇴' },
  { code: 'MA', name: 'Morocco',              flag: '🇲🇦' },
  { code: 'EG', name: 'Egypt',                flag: '🇪🇬' },
  { code: 'NG', name: 'Nigeria',              flag: '🇳🇬' },
  { code: 'KE', name: 'Kenya',                flag: '🇰🇪' },
  { code: 'IL', name: 'Israel',               flag: '🇮🇱' },
  { code: 'SA', name: 'Saudi Arabia',         flag: '🇸🇦' },
  { code: 'QA', name: 'Qatar',                flag: '🇶🇦' },
  { code: 'MY', name: 'Malaysia',             flag: '🇲🇾' },
  { code: 'PH', name: 'Philippines',          flag: '🇵🇭' },
  { code: 'ID', name: 'Indonesia',            flag: '🇮🇩' },
  { code: 'VN', name: 'Vietnam',              flag: '🇻🇳' },
  { code: 'CN', name: 'China',                flag: '🇨🇳' },
  { code: 'TW', name: 'Taiwan',               flag: '🇹🇼' },
  { code: 'PK', name: 'Pakistan',             flag: '🇵🇰' },
  { code: 'BD', name: 'Bangladesh',           flag: '🇧🇩' },
  { code: 'LK', name: 'Sri Lanka',            flag: '🇱🇰' },
  { code: 'GH', name: 'Ghana',                flag: '🇬🇭' },
  { code: 'ET', name: 'Ethiopia',             flag: '🇪🇹' },
  { code: 'CI', name: "Côte d'Ivoire",        flag: '🇨🇮' },
  { code: 'SN', name: 'Senegal',              flag: '🇸🇳' },
  { code: 'TN', name: 'Tunisia',              flag: '🇹🇳' },
  { code: 'DZ', name: 'Algeria',              flag: '🇩🇿' },
  { code: 'UA', name: 'Ukraine',              flag: '🇺🇦' },
  { code: 'RS', name: 'Serbia',               flag: '🇷🇸' },
  { code: 'HR', name: 'Croatia',              flag: '🇭🇷' },
  { code: 'SK', name: 'Slovakia',             flag: '🇸🇰' },
  { code: 'BG', name: 'Bulgaria',             flag: '🇧🇬' },
  { code: 'LT', name: 'Lithuania',            flag: '🇱🇹' },
  { code: 'LV', name: 'Latvia',               flag: '🇱🇻' },
  { code: 'EE', name: 'Estonia',              flag: '🇪🇪' },
  { code: 'IS', name: 'Iceland',              flag: '🇮🇸' },
  { code: 'LU', name: 'Luxembourg',           flag: '🇱🇺' },
  { code: 'MT', name: 'Malta',                flag: '🇲🇹' },
  { code: 'CY', name: 'Cyprus',               flag: '🇨🇾' },
  { code: 'GR', name: 'Greece',               flag: '🇬🇷' },
];

// ─── Country-request types & storage ─────────────────────────────────────────

type CountryRequestKind = 'origin' | 'destination';
type CountryRequestStatus = 'pending' | 'approved' | 'rejected';

interface CountryRequest {
  kind: CountryRequestKind;
  country: string;
  countryName: string;
  startDate: string;
  contractType: string;
  note: string;
  submittedAt: string;
  status: CountryRequestStatus;
}

const CR_KEY = 'relopass_country_request_plan';

function loadCountryRequests(): CountryRequest[] {
  try {
    const s = localStorage.getItem(CR_KEY);
    return s ? (JSON.parse(s) as CountryRequest[]) : [];
  } catch { return []; }
}

function saveCountryRequest(cr: CountryRequest) {
  try {
    const existing = loadCountryRequests().filter(
      (r) => r.kind !== cr.kind || r.country !== cr.country
    );
    localStorage.setItem(CR_KEY, JSON.stringify([...existing, cr]));
  } catch { /* non-critical */ }
}

// ─── Request Country Modal ────────────────────────────────────────────────────

function RequestCountryModal({
  kind,
  onSubmit,
  onClose,
}: {
  kind: CountryRequestKind;
  onSubmit: (req: CountryRequest) => void;
  onClose: () => void;
}) {
  const [country,      setCountry]      = useState('');
  const [startDate,    setStartDate]    = useState('');
  const [contractType, setContractType] = useState('');
  const [note,         setNote]         = useState('');
  const [submitting,   setSubmitting]   = useState(false);

  const isDestination = kind === 'destination';
  const countryLabel  = isDestination ? 'Destination country' : 'Origin country';
  const title         = isDestination ? 'Request a destination country' : 'Request an origin country';
  const description   = isDestination
    ? 'Your HR team will review the request and validate immigration, policy, and compliance details for that country. You can continue filling in your profile in the meantime.'
    : 'Your HR team will review the request and validate origin-side requirements, apostille routes, and departure compliance for that country.';

  const canSubmit = country !== '' && contractType !== '';

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    await new Promise((r) => setTimeout(r, 320));
    const countryObj = MODAL_COUNTRIES.find((c) => c.code === country)!;
    const req: CountryRequest = {
      kind,
      country,
      countryName: countryObj?.name ?? country,
      startDate,
      contractType,
      note,
      submittedAt: new Date().toISOString(),
      status: 'pending',
    };
    saveCountryRequest(req);
    onSubmit(req);
    setSubmitting(false);
  };

  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 70, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px 16px', background: 'rgba(12,25,41,.65)', backdropFilter: 'blur(3px)' }}
      onClick={onClose}
    >
      <div
        style={{ background: '#fff', borderRadius: 20, width: '100%', maxWidth: 520, overflow: 'hidden', display: 'flex', flexDirection: 'column', boxShadow: '0 32px 80px rgba(0,0,0,.28)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid #f1f5f9', display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: NAVY }}>{title}</div>
            <div style={{ fontSize: 12, color: '#64748b', marginTop: 3, lineHeight: 1.5 }}>{description}</div>
          </div>
          <button type="button" onClick={onClose} style={{ width: 28, height: 28, borderRadius: '50%', border: '1px solid #e5e7eb', background: '#f8fafc', cursor: 'pointer', fontSize: 16, color: '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>×</button>
        </div>

        {/* Body */}
        <div style={{ padding: '20px 24px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Country */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 700, color: NAVY, display: 'block', marginBottom: 6 }}>{countryLabel} <span style={{ color: '#ef4444' }}>*</span></label>
            <select
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              style={{ width: '100%', padding: '9px 12px', borderRadius: 10, border: `1.5px solid ${country ? T : '#e2e8f0'}`, fontSize: 13, color: '#1e293b', background: '#fff', outline: 'none', cursor: 'pointer' }}
            >
              <option value="">— select a country —</option>
              {MODAL_COUNTRIES.map((c) => (
                <option key={c.code} value={c.code}>{c.flag} {c.name}</option>
              ))}
            </select>
          </div>

          {/* Contract type */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 700, color: NAVY, display: 'block', marginBottom: 8 }}>Contract type <span style={{ color: '#ef4444' }}>*</span></label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {['Permanent hire', 'Secondment', 'Contractor', 'Intra-company transfer', 'Short-term assignment'].map((ct) => (
                <label key={ct} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 20, border: `1.5px solid ${contractType === ct ? T : '#e2e8f0'}`, background: contractType === ct ? TL : '#fff', cursor: 'pointer', fontSize: 12, fontWeight: 600, color: contractType === ct ? T : '#374151', transition: 'all .14s' }}>
                  <input type="radio" name="contractTypePlan" value={ct} checked={contractType === ct} onChange={() => setContractType(ct)} style={{ display: 'none' }} />
                  {ct}
                </label>
              ))}
            </div>
          </div>

          {/* Target start date */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 700, color: NAVY, display: 'block', marginBottom: 6 }}>Target start date <span style={{ fontSize: 11, fontWeight: 400, color: '#94a3b8' }}>(optional)</span></label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              style={{ width: '100%', padding: '9px 12px', borderRadius: 10, border: '1.5px solid #e2e8f0', fontSize: 13, color: '#1e293b', background: '#fff', outline: 'none', boxSizing: 'border-box' as const }}
            />
          </div>

          {/* Note for HR */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 700, color: NAVY, display: 'block', marginBottom: 6 }}>Note for HR <span style={{ fontSize: 11, fontWeight: 400, color: '#94a3b8' }}>(optional)</span></label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              placeholder="Any context that will help HR validate this request — visa type, family situation, urgency…"
              style={{ width: '100%', padding: '9px 12px', borderRadius: 10, border: '1.5px solid #e2e8f0', fontSize: 12, color: '#374151', background: '#fff', outline: 'none', resize: 'vertical' as const, fontFamily: 'inherit', boxSizing: 'border-box' as const, lineHeight: 1.5 }}
            />
          </div>

          {/* Info callout */}
          <div style={{ padding: '10px 14px', borderRadius: 10, background: TL, border: `1px solid ${T}40`, fontSize: 11, color: '#374151', lineHeight: 1.5 }}>
            <strong style={{ color: T }}>What happens next?</strong> Your HR team will receive a notification and validate the country's immigration requirements, company policy, and compliance obligations. You'll be notified by email once approved — usually within 1–2 business days.
          </div>
        </div>

        {/* Footer */}
        <div style={{ padding: '14px 24px', borderTop: '1px solid #f1f5f9', display: 'flex', gap: 10 }}>
          <button type="button" onClick={onClose} style={{ flex: 1, padding: '10px 0', borderRadius: 10, fontSize: 13, color: '#64748b', border: '1px solid #e5e7eb', background: '#fff', cursor: 'pointer' }}>Cancel</button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit || submitting}
            style={{ flex: 2, padding: '10px 0', borderRadius: 10, fontSize: 13, fontWeight: 700, border: 'none', cursor: canSubmit && !submitting ? 'pointer' : 'not-allowed', background: canSubmit ? T : '#e2e8f0', color: canSubmit ? '#fff' : '#9ca3af', transition: 'all .15s' }}
          >
            {submitting ? '⏳ Sending to HR…' : '✈️ Send request to HR'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

/** Top progress stepper — completed and active steps are clickable */
function ProgressStepper({
  currentStep,
  state,
  onStepClick,
}: {
  currentStep: number;
  state: IntakeState;
  onStepClick: (step: number) => void;
}) {
  const completedValues = [state.fromCode, state.toCode, state.purpose, state.employmentType, state.startWindow, state.household];
  return (
    <div className="flex items-start justify-between gap-1 mb-0">
      {STEPS.map((label, i) => {
        const stepNum = i + 1;
        const isCompleted = completedValues[i] !== null;
        const isActive = stepNum === currentStep;
        // A step is navigable if it's already completed or is the active step,
        // or if the previous step was completed (i.e. it's the next reachable step)
        const isNavigable = isCompleted || isActive || (i > 0 && completedValues[i - 1] !== null);
        return (
          <div key={label} className="flex flex-col items-center flex-1 relative">
            {/* Connecting line before */}
            {i > 0 && (
              <div className={`absolute top-[13px] right-1/2 w-full h-[2px] ${completedValues[i - 1] !== null ? 'bg-blue-500' : 'bg-gray-200'}`} />
            )}
            {/* Circle — clickable when navigable */}
            <button
              type="button"
              disabled={!isNavigable}
              onClick={() => isNavigable && onStepClick(stepNum)}
              title={isNavigable ? `Go to ${label}` : undefined}
              className={`relative z-10 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-all focus:outline-none ${
                isCompleted
                  ? 'bg-blue-600 border-blue-600 text-white hover:bg-blue-700 hover:border-blue-700 cursor-pointer'
                  : isActive
                    ? 'bg-white border-blue-500 text-blue-600 cursor-default'
                    : isNavigable
                      ? 'bg-white border-blue-300 text-blue-400 hover:border-blue-400 cursor-pointer'
                      : 'bg-white border-gray-300 text-gray-400 cursor-not-allowed'
              }`}
            >
              {isCompleted ? (
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              ) : isActive ? (
                <div className="w-2 h-2 rounded-full bg-blue-500" />
              ) : null}
            </button>
            {/* Label */}
            <span
              onClick={() => isNavigable && onStepClick(stepNum)}
              className={`mt-1.5 text-[10px] font-medium text-center leading-tight transition-colors ${
                isActive
                  ? 'text-gray-800'
                  : isCompleted
                    ? 'text-blue-600 hover:text-blue-800 cursor-pointer'
                    : isNavigable
                      ? 'text-blue-400 hover:text-blue-600 cursor-pointer'
                      : 'text-gray-400'
              }`}
            >
              {label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Blue info bubble */
function InfoBubble({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-2.5 px-4 py-3 mb-5 bg-blue-50 border border-blue-100 rounded-xl">
      <div className="w-2 h-2 mt-1 rounded-full bg-blue-500 flex-shrink-0" />
      <p className="text-xs text-blue-700 leading-relaxed">{text}</p>
    </div>
  );
}

/** 3-column country grid */
function CountryGrid({
  selected,
  onSelect,
  onNotListed,
}: {
  selected: string | null;
  onSelect: (code: string) => void;
  onNotListed?: () => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-3 gap-2.5">
        {GRID_COUNTRIES.map((c) => {
          const isSelected = selected === c.code;
          return (
            <button
              key={c.code}
              type="button"
              onClick={() => onSelect(c.code)}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl border-2 text-left transition-all duration-150 group ${
                isSelected
                  ? 'border-blue-500 bg-blue-50 shadow-sm'
                  : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/40'
              }`}
            >
              <span className="text-xl leading-none">{c.flag}</span>
              <span className={`flex-1 text-sm font-medium truncate ${isSelected ? 'text-blue-800' : 'text-gray-700'}`}>
                {c.name}
              </span>
              {isSelected && (
                <svg className="w-4 h-4 text-blue-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
              )}
            </button>
          );
        })}
      </div>

      {/* "My country isn't listed" link */}
      {onNotListed && (
        <div className="flex justify-center pt-1">
          <button
            type="button"
            onClick={onNotListed}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-teal-700 hover:text-teal-900 underline underline-offset-2 transition-colors"
          >
            <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            My country isn't listed — request it from HR
          </button>
        </div>
      )}
    </div>
  );
}

/** Generic option card grid (for purpose / type / start / household) */
function CardGrid({
  options,
  selected,
  onSelect,
  columns = 2,
}: {
  options: OptionCard[];
  selected: string | null;
  onSelect: (id: string) => void;
  columns?: 2 | 3 | 4;
}) {
  const colClass = columns === 3 ? 'grid-cols-3' : columns === 4 ? 'grid-cols-2 sm:grid-cols-4' : 'grid-cols-2';
  return (
    <div className={`grid ${colClass} gap-2.5`}>
      {options.map((opt) => {
        const isSelected = selected === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            onClick={() => onSelect(opt.id)}
            className={`flex flex-col gap-1 px-4 py-4 rounded-xl border-2 text-left transition-all duration-150 ${
              isSelected
                ? 'border-blue-500 bg-blue-50 shadow-sm'
                : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/40'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className={`text-sm font-semibold ${isSelected ? 'text-blue-800' : 'text-gray-800'}`}>
                {opt.label}
              </span>
              {isSelected && (
                <svg className="w-4 h-4 text-blue-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
              )}
            </div>
            {opt.sub && (
              <span className={`text-xs ${isSelected ? 'text-blue-600' : 'text-gray-500'}`}>{opt.sub}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/** Right panel — live relocation profile + AI prediction */
function LiveProfilePanel({
  state,
  employeeName,
}: {
  state: IntakeState;
  employeeName: string;
}) {
  const from = getCountry(state.fromCode);
  const to = getCountry(state.toCode);
  const prediction = getPrediction(state.fromCode, state.toCode, state.purpose);

  const Row = ({ label, value, flag }: { label: string; value: string; flag?: string }) => (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-[11px] font-semibold text-gray-400 tracking-wide uppercase">{label}</span>
      <span className="text-sm font-medium text-gray-900 flex items-center gap-1.5">
        {flag && <span className="text-base leading-none">{flag}</span>}
        {value}
      </span>
    </div>
  );

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden sticky top-6">
      {/* Header */}
      <div className="px-5 pt-4 pb-3 border-b border-gray-100">
        {from && to ? (
          <div className="flex items-center gap-2 text-sm font-bold text-gray-900">
            <span>{from.flag}</span>
            <span className="text-gray-600 font-medium">{from.code}</span>
            <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 8l4 4m0 0l-4 4m4-4H3" />
            </svg>
            <span>{to.flag}</span>
            <span className="text-gray-600 font-medium">{to.code}</span>
          </div>
        ) : (
          <div className="text-sm font-bold text-gray-400">Your relocation profile</div>
        )}
        <p className="text-xs text-gray-400 mt-0.5">
          Live relocation profile
          {employeeName ? ` · ${employeeName}` : ''}
        </p>
      </div>

      {/* Profile rows */}
      <div className="px-5 py-3 divide-y divide-gray-100">
        <Row label="FROM"      value={from?.name ?? '—'}             flag={from?.flag} />
        <Row label="TO"        value={to?.name ?? '—'}               flag={to?.flag} />
        <Row label="PURPOSE"   value={purposeToLabel(state.purpose)} />
        <Row label="TYPE"      value={state.employmentType ?? '—'} />
        <Row label="START"     value={startWindowToLabel(state.startWindow)} />
        <Row label="HOUSEHOLD" value={householdToLabel(state.household)} />
      </div>

      {/* AI Prediction — always visible; dims until steps 1-3 are done */}
      <div className="px-5 pt-3 pb-4 bg-gray-50 border-t border-gray-100">
        <div className={`text-[11px] font-bold uppercase tracking-wider mb-3 ${prediction ? 'text-gray-500' : 'text-gray-400'}`}>
          AI Prediction
        </div>
        {prediction ? (
          <div className="space-y-2">
            <div className="flex items-start justify-between gap-2">
              <span className="text-xs text-gray-500 flex-shrink-0">Likely visa route</span>
              <span className="text-xs font-semibold text-gray-900 text-right leading-tight">
                {prediction.route}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500">Estimated time</span>
              <span className="text-xs font-semibold text-gray-900">{prediction.weeks}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500">Est. processing cost</span>
              <span className="text-xs font-semibold text-gray-900">{prediction.cost}</span>
            </div>
            <div className="pt-1">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs text-gray-500">Confidence</span>
                <span className="text-xs font-semibold text-gray-900">{prediction.confidence}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-gray-200 overflow-hidden">
                <div
                  className="h-full rounded-full bg-blue-500 transition-all duration-700"
                  style={{ width: `${prediction.confidence}%` }}
                />
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-2 opacity-40">
            {['Likely visa route', 'Estimated time', 'Est. processing cost'].map((label) => (
              <div key={label} className="flex items-center justify-between">
                <span className="text-xs text-gray-500">{label}</span>
                <div className="h-3 w-24 bg-gray-300 rounded animate-pulse" />
              </div>
            ))}
            <div className="pt-1">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs text-gray-500">Confidence</span>
                <div className="h-3 w-8 bg-gray-300 rounded animate-pulse" />
              </div>
              <div className="h-1.5 rounded-full bg-gray-200" />
            </div>
            <p className="text-[10px] text-gray-400 pt-1">Select origin, destination &amp; purpose to unlock</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Step Content ─────────────────────────────────────────────────────────────

interface StepContentProps {
  step: number;
  state: IntakeState;
  onSelect: (value: string) => void;
  onNotListed?: (kind: CountryRequestKind) => void;
}

function StepContent({ step, state, onSelect, onNotListed }: StepContentProps) {
  const tip = getInfoTip(step, state);

  const stepConfig: Record<number, { title: string; subtitle: string; content: React.ReactNode }> = {
    1: {
      title: 'Where are you relocating from?',
      subtitle: 'Used to determine your origin-side documents and apostille route.',
      content: (
        <CountryGrid
          selected={state.fromCode}
          onSelect={onSelect}
          onNotListed={onNotListed ? () => onNotListed('origin') : undefined}
        />
      ),
    },
    2: {
      title: 'Where are you moving to?',
      subtitle: 'Determines the visa pathway and authority.',
      content: (
        <CountryGrid
          selected={state.toCode}
          onSelect={onSelect}
          onNotListed={onNotListed ? () => onNotListed('destination') : undefined}
        />
      ),
    },
    3: {
      title: 'What is the purpose of this relocation?',
      subtitle: 'Different routes follow different visa categories.',
      content: <CardGrid options={PURPOSE_OPTIONS} selected={state.purpose} onSelect={onSelect} columns={2} />,
    },
    4: {
      title: 'What type of employment are you on?',
      subtitle: 'Determines which salary thresholds and visa subcategories apply.',
      content: <CardGrid options={TYPE_OPTIONS} selected={state.employmentType} onSelect={onSelect} columns={3} />,
    },
    5: {
      title: 'When does your contract start?',
      subtitle: 'Determines processing urgency and prioritisation.',
      content: <CardGrid options={START_OPTIONS} selected={state.startWindow} onSelect={onSelect} columns={2} />,
    },
    6: {
      title: 'Who is relocating with you?',
      subtitle: 'Each dependent gets their own track and document set.',
      content: <CardGrid options={HOUSEHOLD_OPTIONS} selected={state.household} onSelect={onSelect} columns={2} />,
    },
  };

  // Step 7: completion screen
  if (step === 7) return null; // rendered separately in main page

  const config = stepConfig[step];
  if (!config) return null;

  return (
    <>
      <div className="mb-5">
        <h2 className="text-xl font-bold text-gray-900">{config.title}</h2>
        <p className="text-sm text-gray-500 mt-1">{config.subtitle}</p>
      </div>
      {tip && <InfoBubble text={tip} />}
      {config.content}
    </>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export function RelocatePlanIntakePage() {
  const { caseId: caseIdParam } = useParams<{ caseId?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { linkedSummaries } = useEmployeeAssignment();

  // Resolve case ID
  const caseId: string | null =
    caseIdParam ||
    searchParams.get('caseId') ||
    linkedSummaries[0]?.case_id ||
    null;

  // Employee name — from auth storage (same pattern as CaseWizardPage)
  const employeeName = getAuthItem('relopass_name') || '';

  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const advanceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [countryModalKind, setCountryModalKind] = useState<CountryRequestKind | null>(null);
  // Tracks submitted country requests — used to show confirmation banners in future iterations
  const [_countryRequests, setCountryRequests] = useState<CountryRequest[]>(() => loadCountryRequests());
  const [state, setState] = useState<IntakeState>({
    fromCode: null,
    toCode: null,
    purpose: null,
    employmentType: null,
    startWindow: null,
    household: null,
  });

  // Auto-advance delay after selection (ms)
  const ADVANCE_DELAY = 350;

  const saveToBackend = useCallback(async (patch: object) => {
    if (!caseId) return;
    setSaving(true);
    try {
      await patchCase(caseId, patch as any);
    } catch (err) {
      // Non-blocking — show in console only
      logger.warn('[RelocatePlanIntake] save failed', err);
    } finally {
      setSaving(false);
    }
  }, [caseId]);

  const handleSelect = useCallback((value: string) => {
    let nextState = { ...state };
    let patch: object = {};

    if (step === 1) {
      const country = GRID_COUNTRIES.find((c) => c.code === value);
      nextState.fromCode = value;
      patch = { relocationBasics: { originCountry: country?.name ?? value } };
    } else if (step === 2) {
      const country = GRID_COUNTRIES.find((c) => c.code === value);
      nextState.toCode = value;
      patch = { relocationBasics: { destCountry: country?.name ?? value } };
    } else if (step === 3) {
      nextState.purpose = value;
      patch = { relocationBasics: { purpose: value } };
    } else if (step === 4) {
      nextState.employmentType = value;
      patch = { assignmentContext: { contractType: value } };
    } else if (step === 5) {
      nextState.startWindow = value;
      const dateVal = startWindowToDate(value);
      patch = dateVal
        ? { relocationBasics: { targetMoveDate: dateVal } }
        : { relocationBasics: {} };
    } else if (step === 6) {
      nextState.household = value;
      const { hasDependents, maritalStatus } = householdToDraft(value);
      patch = {
        relocationBasics: { hasDependents },
        familyMembers: { maritalStatus },
      };
    }

    setState(nextState);
    void saveToBackend(patch);

    // Auto-advance to next step after brief delay
    // Step 7 = completion screen (stays within this page — no redirect)
    if (advanceTimer.current) clearTimeout(advanceTimer.current);
    advanceTimer.current = setTimeout(() => setStep((s) => Math.min(s + 1, 7)), ADVANCE_DELAY);
  }, [step, state, saveToBackend]);

  const handleBack = () => {
    if (advanceTimer.current) clearTimeout(advanceTimer.current);
    if (step > 1) setStep((s) => s - 1);
  };

  const handleStepClick = (target: number) => {
    if (advanceTimer.current) clearTimeout(advanceTimer.current);
    setStep(target);
  };

  return (
    <AppShell>
      <div className="max-w-6xl mx-auto px-4 py-6">

        {/* Page header */}
        <div className="mb-6">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-1">
            Employee Intake · ReloPass
          </p>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Build your relocation plan</h1>
              <p className="text-sm text-gray-500 mt-1">
                ReloPass adapts its questions to your situation. The plan on the right rebuilds as you answer.
              </p>
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-blue-50 border border-blue-100 text-xs text-blue-600 font-medium flex-shrink-0 ml-4">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              est. 90 seconds
            </div>
          </div>
        </div>

        {/* Main layout: wizard left, panel right */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr,320px] gap-6 items-start">

          {/* ── Wizard card ── */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">

            {/* Progress stepper — always visible */}
            <div className="px-6 pt-5 pb-4 border-b border-gray-100">
              <ProgressStepper currentStep={step} state={state} onStepClick={handleStepClick} />
            </div>

            {step === 7 ? (
              /* ── Completion screen ── */
              <div className="px-6 py-10 flex flex-col items-center text-center gap-4">
                <div className="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center">
                  <svg className="w-7 h-7 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-900">Your profile is built</h2>
                  <p className="text-sm text-gray-500 mt-1 max-w-sm">
                    ReloPass has enough to estimate your visa route and timeline. Continue to the detailed intake to complete your full dossier.
                  </p>
                </div>
                <div className="flex flex-col sm:flex-row gap-3 mt-2">
                  <button
                    type="button"
                    onClick={() => navigate('/employee/intake/detailed')}
                    className="px-5 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-xl hover:bg-blue-700 transition-colors"
                  >
                    Continue to detailed intake →
                  </button>
                  <button
                    type="button"
                    onClick={() => setStep(1)}
                    className="px-5 py-2.5 border border-gray-200 text-gray-600 text-sm font-medium rounded-xl hover:bg-gray-50 transition-colors"
                  >
                    Review my answers
                  </button>
                </div>
              </div>
            ) : (
              <>
                {/* Step content */}
                <div className="px-6 pt-6 pb-4">
                  <StepContent
                    step={step}
                    state={state}
                    onSelect={handleSelect}
                    onNotListed={(kind) => setCountryModalKind(kind)}
                  />
                </div>

                {/* Footer nav */}
                <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100">
                  <button
                    type="button"
                    onClick={handleBack}
                    disabled={step === 1}
                    className={`flex items-center gap-1.5 text-sm font-medium transition-colors ${
                      step === 1 ? 'text-transparent pointer-events-none' : 'text-gray-500 hover:text-gray-800'
                    }`}
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                    </svg>
                    Back
                  </button>

                  <div className="flex items-center gap-1.5 text-xs text-gray-400">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                    Encrypted · GDPR · SOC 2
                  </div>

                  {/* Saving indicator */}
                  <div className={`text-xs text-gray-400 transition-opacity ${saving ? 'opacity-100' : 'opacity-0'}`}>
                    Saving…
                  </div>
                </div>
              </>
            )}
          </div>

          {/* ── Right panel ── */}
          <LiveProfilePanel state={state} employeeName={employeeName} />
        </div>

        {/* Country request modal */}
        {countryModalKind && (
          <RequestCountryModal
            kind={countryModalKind}
            onSubmit={(req) => {
              setCountryRequests((prev) => [...prev.filter((r) => r.kind !== req.kind || r.country !== req.country), req]);
              setCountryModalKind(null);
            }}
            onClose={() => setCountryModalKind(null)}
          />
        )}

      </div>
    </AppShell>
  );
}
