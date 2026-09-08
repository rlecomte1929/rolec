// Corridor Data-Sheet Engine — THROWAWAY UX PROTOTYPE
// Design-validation only: hardcoded mock data, zero API calls, zero production wiring.
// Generalises the validated FR-NO data-sheet design into a corridor-agnostic component
// driven by a typed CorridorConfig object. FR-NO is the reference config.
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, ChevronDown, ChevronRight, Info, Pencil, Printer } from 'lucide-react';

// ────────────────────────────────────────────────────────────────────
// Core types
// ────────────────────────────────────────────────────────────────────
type MovementBasis = 'EEA_FREE_MOVEMENT' | 'THIRD_COUNTRY_PERMIT' | 'BILATERAL';
type FieldSource = 'intake' | 'passport-ocr' | 'prior-form' | 'needs-input' | 'consult-professional';
type Channel = 'online-portal' | 'in-person-appointment' | 'fillable-pdf' | 'automatic' | 'employer-owned';
type ResponsibleParty = 'employee' | 'employer' | 'both';

interface CorridorConfig {
  corridorId: string;
  destination: { name: string; countryCode: string; localLanguage: string; localLanguageName: string };
  origin: { name: string; countryCode: string };
  movement_basis: MovementBasis;
  regulatoryBanners: { type: 'moat-fact' | 'warning'; text: string }[];
  sections: Section[];
  consultProfessionalItems: ConsultProfessionalItem[];
}

interface Section {
  id: string;
  title: { en: string; local: string };
  authority?: { name: string; url: string };
  channels: Channel[];
  portalNote?: string;
  fields: Field[];
}

interface Field {
  id: string;
  label: { en: string; local: string };
  value?: string;
  source: FieldSource;
  sourceNote?: string;
  requiresOriginal?: boolean;
  responsibleParty?: ResponsibleParty;
  slaNote?: string;
  // Additive extension for the HR view annotation column (employer action note).
  employerActionNote?: string;
}

interface ConsultProfessionalItem {
  id: string;
  topic: { en: string; local: string };
  reason: string;
}

// ────────────────────────────────────────────────────────────────────
// FR-NO reference config (hardcoded mock — Sophie Leblanc)
// ────────────────────────────────────────────────────────────────────
const FR_NO_CONFIG: CorridorConfig = {
  corridorId: 'fr-no',
  destination: { name: 'Norway', countryCode: 'NO', localLanguage: 'no', localLanguageName: 'Norsk' },
  origin: { name: 'France', countryCode: 'FR' },
  movement_basis: 'EEA_FREE_MOVEMENT',
  regulatoryBanners: [
    { type: 'moat-fact', text: 'D-number and skattekort can be applied for in ONE Skatteetaten portal session — most guides treat them as two separate processes.' },
    { type: 'moat-fact', text: 'Complete the UDI online application BEFORE booking the police appointment — booking first is the most common FR→NO sequencing mistake.' },
    { type: 'warning', text: 'Skattekort must be issued before the first payroll run — without it, 50% emergency withholding applies.' },
    { type: 'moat-fact', text: 'The A1 certificate is a France-side process (CPAM/URSSAF, initiated by the French employer) — it cannot be obtained from any Norwegian authority.' },
  ],
  sections: [
    {
      id: 'personal-identity',
      title: { en: '1 · Personal identity', local: '1 · Personlig identitet' },
      channels: [],
      fields: [
        { id: 'pi-full-name', label: { en: 'Full legal name', local: 'Fullt juridisk navn' }, value: 'Sophie Leblanc', source: 'intake' },
        { id: 'pi-nationality', label: { en: 'Nationality', local: 'Statsborgerskap' }, value: 'French', source: 'intake' },
        { id: 'pi-passport-number', label: { en: 'Passport number', local: 'Passnummer' }, value: 'FR123456789', source: 'passport-ocr', requiresOriginal: true },
        { id: 'pi-dob', label: { en: 'Date of birth', local: 'Fødselsdato' }, value: '14 March 1989', source: 'passport-ocr' },
        { id: 'pi-pob', label: { en: 'Place of birth', local: 'Fødested' }, value: 'Paris, France', source: 'passport-ocr' },
        { id: 'pi-fr-address', label: { en: 'Current address – France', local: 'Nåværende adresse – Frankrike' }, value: '18 Rue de la Verrerie, 44100 Nantes, France', source: 'intake' },
        { id: 'pi-no-address', label: { en: 'Norwegian address', local: 'Norsk adresse' }, source: 'needs-input' },
        { id: 'pi-emergency', label: { en: 'Emergency contact', local: 'Nødkontakt' }, source: 'needs-input' },
      ],
    },
    {
      id: 'employment',
      title: { en: '2 · Employment', local: '2 · Arbeidsforhold' },
      channels: ['employer-owned'],
      fields: [
        { id: 'em-employer', label: { en: 'Employer name', local: 'Arbeidsgivers navn' }, value: 'Énergie Atlantique SAS', source: 'intake' },
        { id: 'em-orgnr', label: { en: 'Norwegian org-number', local: 'Norsk organisasjonsnummer' }, value: '923 456 789', source: 'intake' },
        { id: 'em-role', label: { en: 'Role / job title', local: 'Stilling' }, value: 'Senior Software Engineer', source: 'intake' },
        { id: 'em-start', label: { en: 'Contract start date', local: 'Kontraktens startdato' }, value: '1 October 2026', source: 'intake' },
        { id: 'em-salary', label: { en: 'Gross annual salary (NOK)', local: 'Brutto årslønn (NOK)' }, source: 'needs-input' },
        { id: 'em-contract-type', label: { en: 'Contract type', local: 'Kontraktstype' }, value: 'Permanent', source: 'intake' },
      ],
    },
    {
      id: 'eea-registration',
      title: { en: '3 · EEA registration (police)', local: '3 · EØS-registrering (politiet)' },
      authority: { name: 'UDI', url: 'udi.no/en/come-to-norway/eia' },
      channels: ['online-portal', 'in-person-appointment'],
      portalNote: 'Two stages: (1) complete the UDI online application at udi.no BEFORE booking the police appointment; (2) attend the police appointment with this sheet and your original documents.',
      fields: [
        { id: 'eea-udi-ref', label: { en: 'UDI application reference', local: 'UDI-søknadsreferanse' }, source: 'needs-input' },
        { id: 'eea-police-district', label: { en: 'Police district', local: 'Politidistrikt' }, source: 'needs-input' },
        { id: 'eea-appt-date', label: { en: 'Appointment date', local: 'Oppmøtedato' }, source: 'needs-input', slaNote: 'Within 3 months of arrival' },
        { id: 'eea-duration', label: { en: 'Duration of stay declared', local: 'Oppgitt oppholdsvarighet' }, value: 'More than 3 months', source: 'intake' },
      ],
    },
    {
      id: 'd-number',
      title: { en: '4 · D-number', local: '4 · D-nummer' },
      authority: { name: 'Skatteetaten', url: 'skatteetaten.no' },
      channels: ['online-portal'],
      portalNote: 'Can be applied for in the same Skatteetaten session as the skattekort (Section 5). Online portal — employer or self-service.',
      fields: [
        { id: 'dn-number', label: { en: 'D-number', local: 'D-nummer' }, source: 'needs-input' },
        { id: 'dn-app-date', label: { en: 'Application date', local: 'Søknadsdato' }, source: 'needs-input' },
        { id: 'dn-employer-init', label: { en: 'Employer-initiated', local: 'Initiert av arbeidsgiver' }, value: 'Yes', source: 'intake' },
      ],
    },
    {
      id: 'skattekort',
      title: { en: '5 · Skattekort (tax card)', local: '5 · Skattekort' },
      authority: { name: 'Skatteetaten', url: 'skatteetaten.no' },
      channels: ['online-portal'],
      portalNote: 'Apply in the same Skatteetaten session as the D-number. Must be issued BEFORE first payroll run — risk of 50% emergency withholding if absent.',
      fields: [
        {
          id: 'sk-issued',
          label: { en: 'Skattekort issued', local: 'Skattekort utstedt' },
          source: 'needs-input',
          responsibleParty: 'both',
          slaNote: 'Must be issued before first payroll. Employer registers org-number.',
          employerActionNote: 'Employer must register Skattekort before first payroll run',
        },
        { id: 'sk-org-registered', label: { en: 'Employer org-number registered', local: 'Arbeidsgivers org.nummer registrert' }, value: '923 456 789', source: 'intake', sourceNote: 'Provided by employer', responsibleParty: 'employer' },
        { id: 'sk-salary-entered', label: { en: 'Expected salary entered', local: 'Forventet lønn registrert' }, source: 'needs-input', responsibleParty: 'employee' },
      ],
    },
    {
      id: 'folkeregister',
      title: { en: '6 · Folkeregister', local: '6 · Folkeregisteret' },
      authority: { name: 'Skatteetaten', url: 'skatteetaten.no' },
      channels: ['online-portal', 'in-person-appointment'],
      fields: [
        { id: 'fr-reg-date', label: { en: 'Registration date', local: 'Registreringsdato' }, source: 'needs-input' },
        { id: 'fr-no-address', label: { en: 'Norwegian address confirmed', local: 'Norsk adresse bekreftet' }, source: 'needs-input' },
        { id: 'fr-civil-status', label: { en: 'Civil status declared', local: 'Oppgitt sivilstatus' }, value: 'Single', source: 'intake' },
      ],
    },
    {
      id: 'a1-certificate',
      title: { en: '7 · A1 certificate (France-side)', local: '7 · A1-attest (fransk side)' },
      authority: { name: 'Net-Entreprises / URSSAF', url: 'net-entreprises.fr' },
      channels: ['employer-owned'],
      portalNote: 'A1 is issued by France (CPAM/URSSAF), initiated by the French employer. This is not a Norwegian process.',
      fields: [
        {
          id: 'a1-submitted',
          label: { en: 'A1 application submitted', local: 'A1-søknad sendt' },
          value: 'No — NEEDS EMPLOYER ACTION',
          source: 'intake',
          sourceNote: 'Employer-owned — French employer initiates',
          responsibleParty: 'employer',
          slaNote: 'Before departure date',
          employerActionNote: 'French employer must file the A1 request via Net-Entreprises / URSSAF',
        },
        { id: 'a1-issue-date', label: { en: 'A1 issue date', local: 'A1 utstedelsesdato' }, source: 'needs-input', responsibleParty: 'employer', slaNote: 'Before departure date' },
        { id: 'a1-ref', label: { en: 'A1 reference number', local: 'A1-referansenummer' }, source: 'needs-input', responsibleParty: 'employer' },
      ],
    },
  ],
  consultProfessionalItems: [
    { id: 'cp-tax-residency', topic: { en: 'Tax residency status', local: 'Skattemessig bosted' }, reason: 'Determines which country has primary taxing rights. Depends on 183-day rule and habitual abode. Cannot be determined from data alone.' },
    { id: 'cp-a1-coordination', topic: { en: 'A1 / social security coordination', local: 'A1 / trygdekoordinering' }, reason: "Which country's social security applies depends on whether this is a posting or a local hire. Incorrect determination leads to double contributions or gaps." },
    { id: 'cp-contract-class', topic: { en: 'Contract classification', local: 'Kontraktsklassifisering' }, reason: 'Secondment vs local hire changes the tax and social security outcome. HR/legal must resolve before ReloPass outputs anything definitive.' },
    { id: 'cp-shadow-payroll', topic: { en: 'Shadow payroll requirement', local: 'Behov for skyggelønn' }, reason: 'If social security stays French but income tax becomes Norwegian, the employer may need a Norwegian shadow payroll.' },
    { id: 'cp-pe-risk', topic: { en: 'Permanent establishment risk', local: 'Risiko for fast driftssted' }, reason: 'If the French employer has no Norwegian entity, PE risk must be assessed before the employee starts work in Norway.' },
  ],
};

// Future corridors: add the config here — the shell picks it up automatically.
const CORRIDOR_CONFIGS: CorridorConfig[] = [FR_NO_CONFIG];

// Per-corridor presentation metadata (mock case header + sparse-mode keep list).
const CASE_META: Record<string, { caseRef: string; person: string; generated: string }> = {
  'fr-no': { caseRef: 'Case FR-NO-2026-0102', person: 'Sophie Leblanc', generated: 'Generated 3 Aug 2026' },
};
// Sparse mode: ONLY these fields stay prefilled; everything else becomes needs-input.
const SPARSE_KEEP_IDS: Record<string, string[]> = {
  'fr-no': ['pi-full-name', 'pi-passport-number'],
};

// ────────────────────────────────────────────────────────────────────
// Labels
// ────────────────────────────────────────────────────────────────────
const MOVEMENT_BASIS_LABEL: Record<MovementBasis, string> = {
  EEA_FREE_MOVEMENT: 'EEA free movement',
  THIRD_COUNTRY_PERMIT: 'Third-country permit',
  BILATERAL: 'Bilateral agreement',
};

const CHANNEL_LABEL: Record<Channel, string> = {
  'online-portal': 'Online portal',
  'in-person-appointment': 'In-person appointment',
  'fillable-pdf': 'Fillable PDF',
  automatic: 'Automatic',
  'employer-owned': 'Employer-owned',
};

const BADGE_LABEL: Record<FieldSource, string> = {
  intake: 'intake',
  'passport-ocr': 'passport-OCR',
  'prior-form': 'prior-form',
  'needs-input': 'NEEDS INPUT',
  'consult-professional': 'CONSULT PROFESSIONAL',
};

const RP_LABEL: Record<ResponsibleParty, string> = {
  employee: 'Employee',
  employer: 'Employer',
  both: 'Both',
};

const LEGEND: { source: FieldSource; text: string }[] = [
  { source: 'intake', text: 'entered during case intake' },
  { source: 'passport-ocr', text: 'read from uploaded passport scan' },
  { source: 'prior-form', text: 'carried from a previous form or case' },
  { source: 'needs-input', text: 'you must provide this value before your appointment' },
  { source: 'consult-professional', text: 'requires a regulated tax, legal, or social security advisor — ReloPass cannot determine this' },
];

type Lang = 'en' | 'local';
type DataMode = 'full' | 'sparse';
type ViewMode = 'employee' | 'hr';

// ────────────────────────────────────────────────────────────────────
// Small building blocks
// ────────────────────────────────────────────────────────────────────
function SourceBadge({ source }: { source: FieldSource }) {
  return (
    <span className={'cds-badge cds-badge-' + source}>
      {source === 'needs-input' && <Pencil size={11} strokeWidth={2.5} />}
      {source === 'consult-professional' && <AlertTriangle size={11} strokeWidth={2.5} />}
      {BADGE_LABEL[source]}
    </span>
  );
}

function RpChip({ rp }: { rp: ResponsibleParty }) {
  const styles: Record<ResponsibleParty, React.CSSProperties> = {
    employee: { background: '#F1F5F9', color: '#475569', border: '1px solid #CBD5E1' },
    employer: { background: '#E0E7FF', color: '#3730A3', border: '1px solid #C7D2FE' },
    both: { background: '#EDE9FE', color: '#5B21B6', border: '1px solid #DDD6FE' },
  };
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', fontSize: 10, fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', padding: '3px 8px', borderRadius: 999, whiteSpace: 'nowrap', ...styles[rp] }}>
      {RP_LABEL[rp]}
    </span>
  );
}

function HrAnnotation({ field }: { field: Field }) {
  const rp = field.responsibleParty || 'employee';
  return (
    <div style={{ display: 'grid', gap: 4, fontSize: 11.5, lineHeight: 1.45, color: '#4B5563' }}>
      <div><RpChip rp={rp} /></div>
      {field.slaNote && (
        <div><span style={{ fontWeight: 700, color: '#92400E' }}>SLA:</span> {field.slaNote}</div>
      )}
      {field.employerActionNote && (
        <div><span style={{ fontWeight: 700, color: '#3730A3' }}>Employer action:</span> {field.employerActionNote}</div>
      )}
    </div>
  );
}

function ToggleGroup<T extends string>({ options, value, onChange }: { options: { value: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div style={{ display: 'flex', border: '1px solid #E5E7EB', borderRadius: 8, overflow: 'hidden', flexShrink: 0 }}>
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          style={{
            padding: '6px 12px',
            fontSize: 12.5,
            fontWeight: 700,
            border: 'none',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            background: value === o.value ? '#111827' : '#FFFFFF',
            color: value === o.value ? '#FFFFFF' : '#6B7280',
          }}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// Main component
// ────────────────────────────────────────────────────────────────────
export default function CorridorDataSheetEngine() {
  const [corridorId, setCorridorId] = useState<string>(CORRIDOR_CONFIGS[0].corridorId);
  const [lang, setLang] = useState<Lang>('en');
  const [dataMode, setDataMode] = useState<DataMode>('full');
  const [viewMode, setViewMode] = useState<ViewMode>('employee');
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({});
  const [isMobile, setIsMobile] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  const config = CORRIDOR_CONFIGS.find((c) => c.corridorId === corridorId) || CORRIDOR_CONFIGS[0];
  const meta = CASE_META[config.corridorId];

  // Container-width detection so the mobile layout also triggers inside a narrow app window.
  useEffect(() => {
    const el = rootRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect?.width;
      if (typeof w === 'number') setIsMobile(w < 640);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Sparse mode: strip values and force needs-input on everything except the keep list.
  const sections = useMemo<Section[]>(() => {
    if (dataMode === 'full') return config.sections;
    const keep = new Set(SPARSE_KEEP_IDS[config.corridorId] || []);
    return config.sections.map((s) => ({
      ...s,
      fields: s.fields.map((f) =>
        keep.has(f.id)
          ? f
          : { ...f, value: undefined, source: 'needs-input' as FieldSource, sourceNote: undefined }
      ),
    }));
  }, [config, dataMode]);

  const fieldKey = (sectionId: string, fld: Field) => sectionId + ':' + fld.id;

  const sectionStats = (s: Section) => {
    const needs = s.fields.filter((f) => f.source === 'needs-input');
    const remaining = needs.filter((f) => !(inputs[fieldKey(s.id, f)] || '').trim()).length;
    return { total: needs.length, remaining, complete: remaining === 0 };
  };

  const overall = useMemo(() => {
    let total = 0;
    let remaining = 0;
    sections.forEach((s) => {
      const st = { needs: s.fields.filter((f) => f.source === 'needs-input') };
      total += st.needs.length;
      remaining += st.needs.filter((f) => !(inputs[fieldKey(s.id, f)] || '').trim()).length;
    });
    return { total, filled: total - remaining, remaining };
  }, [sections, inputs]);

  const resetCase = () => {
    setInputs({});
    setEditing(null);
  };

  const switchDataMode = (m: DataMode) => {
    setDataMode(m);
    resetCase();
  };

  const switchCorridor = (id: string) => {
    setCorridorId(id);
    setLang('en');
    resetCase();
  };

  const handlePrint = () => {
    window.setTimeout(() => window.print(), 150);
  };

  const localLabel = (pair: { en: string; local: string }) => (lang === 'en' ? pair.en : pair.local);

  // ── Field value cell ──
  const renderValue = (s: Section, f: Field) => {
    if (f.source === 'needs-input') {
      const key = fieldKey(s.id, f);
      const val = inputs[key] || '';
      const isEditing = editing === key;
      return (
        <div>
          <div className="cds-no-print">
            {isEditing ? (
              <input
                autoFocus
                type="text"
                value={val}
                onChange={(e) => setInputs((prev) => ({ ...prev, [key]: e.target.value }))}
                onBlur={() => setEditing(null)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') setEditing(null);
                }}
                placeholder={lang === 'en' ? 'Type here…' : 'Skriv her…'}
                style={{ width: '100%', fontSize: 14, padding: '6px 10px', border: '1px solid #9CA3AF', borderRadius: 6, outline: 'none', background: '#F9FAFB', color: '#111827', boxSizing: 'border-box' }}
              />
            ) : (
              <button
                onClick={() => setEditing(key)}
                style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%', textAlign: 'left', fontSize: 14, padding: '6px 10px', border: '1px dashed ' + (val ? '#D1D5DB' : '#9CA3AF'), borderRadius: 6, background: val ? '#FFFFFF' : '#F9FAFB', color: val ? '#111827' : '#6B7280', cursor: 'text', boxSizing: 'border-box' }}
              >
                <Pencil size={13} style={{ flexShrink: 0, opacity: 0.6 }} />
                {val || (lang === 'en' ? 'Click to fill in' : 'Klikk for å fylle ut')}
              </button>
            )}
          </div>
          <div className="cds-print-only" style={{ fontSize: 13, color: '#111827', borderBottom: '1px solid #9CA3AF', minHeight: 16 }}>
            {val || '\u00A0'}
          </div>
          {f.sourceNote && <div style={{ marginTop: 4, fontSize: 12, color: '#6B7280', lineHeight: 1.4 }}>{f.sourceNote}</div>}
        </div>
      );
    }
    return (
      <div>
        {/* Identifier values stay verbatim in both language modes. */}
        <div style={{ fontSize: 14, color: '#111827' }}>{f.value}</div>
        {f.sourceNote && <div style={{ marginTop: 2, fontSize: 11.5, color: '#6B7280', lineHeight: 1.4 }}>{f.sourceNote}</div>}
      </div>
    );
  };

  const renderFieldRow = (s: Section, f: Field, i: number) => {
    if (isMobile) {
      return (
        <div key={f.id} style={{ padding: '10px 12px', borderTop: i === 0 ? 'none' : '1px solid #F3F4F6' }}>
          <div style={{ fontSize: 13, color: '#374151', fontWeight: 600 }}>
            {localLabel(f.label)}
            {f.requiresOriginal && <span style={{ marginLeft: 6, fontSize: 10.5, fontWeight: 600, color: '#B45309' }}>original required</span>}
          </div>
          <div style={{ marginTop: 4 }}>
            <SourceBadge source={f.source} />
          </div>
          <div style={{ marginTop: 6 }}>{renderValue(s, f)}</div>
          {viewMode === 'hr' && (
            <div style={{ marginTop: 8, padding: '8px 10px', background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 6 }}>
              <HrAnnotation field={f} />
            </div>
          )}
        </div>
      );
    }
    const cols =
      viewMode === 'hr'
        ? 'minmax(130px, 3fr) minmax(150px, 5fr) minmax(105px, auto) minmax(170px, 4fr)'
        : 'minmax(140px, 4fr) minmax(170px, 6fr) minmax(105px, auto)';
    return (
      <div key={f.id} style={{ display: 'grid', gridTemplateColumns: cols, gap: 12, alignItems: 'start', padding: '9px 14px', borderTop: i === 0 ? 'none' : '1px solid #F3F4F6' }}>
        <div style={{ fontSize: 13, color: '#6B7280', fontWeight: 500, paddingTop: 4 }}>
          {localLabel(f.label)}
          {f.requiresOriginal && <div style={{ fontSize: 10.5, fontWeight: 600, color: '#B45309' }}>original required</div>}
        </div>
        <div>{renderValue(s, f)}</div>
        <div style={{ textAlign: 'right', paddingTop: 2 }}>
          <SourceBadge source={f.source} />
        </div>
        {viewMode === 'hr' && (
          <div className="cds-hr-col" style={{ borderLeft: '2px solid #E2E8F0', paddingLeft: 12 }}>
            <HrAnnotation field={f} />
          </div>
        )}
      </div>
    );
  };

  const renderSection = (s: Section) => {
    const stats = sectionStats(s);
    const isOpen = !isMobile || (openSections[s.id] ?? false);
    const wide = s.fields.length > 4;
    return (
      <div
        key={s.id}
        className={'cds-section' + (wide ? ' cds-section-wide' : '')}
        style={{
          marginTop: isMobile ? 12 : 20,
          background: stats.complete ? '#F0FDF4' : '#F9FAFB',
          border: '1px solid ' + (stats.complete ? '#86EFAC' : '#E5E7EB'),
          borderRadius: 8,
          padding: isMobile ? 12 : 16,
          transition: 'background 0.2s, border-color 0.2s',
        }}
      >
        {/* Header (tap-to-collapse on mobile) */}
        <div
          onClick={isMobile ? () => setOpenSections((prev) => ({ ...prev, [s.id]: !(prev[s.id] ?? false) })) : undefined}
          style={{ display: 'flex', alignItems: 'flex-start', gap: 8, cursor: isMobile ? 'pointer' : 'default' }}
        >
          {isMobile && (
            <span className="cds-no-print" style={{ marginTop: 2, color: '#6B7280', flexShrink: 0 }}>
              {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </span>
          )}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
              <h2 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: '#111827' }}>{localLabel(s.title)}</h2>
              {s.channels.map((ch) => (
                <span key={ch} style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', padding: '3px 8px', borderRadius: 999, background: '#E0F2FE', color: '#075985', border: '1px solid #BAE6FD', whiteSpace: 'nowrap' }}>
                  {CHANNEL_LABEL[ch]}
                </span>
              ))}
            </div>
            {s.authority && (
              <div style={{ marginTop: 2, fontSize: 12, color: '#6B7280' }}>
                {s.authority.name} · {s.authority.url}
              </div>
            )}
          </div>
          {/* Per-section progress chip */}
          <div className="cds-no-print" style={{ flexShrink: 0 }}>
            {stats.total === 0 || stats.complete ? (
              <span style={{ fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 999, background: '#DCFCE7', color: '#166534', whiteSpace: 'nowrap' }}>Complete</span>
            ) : (
              <span style={{ fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 999, background: '#FFFFFF', color: '#6B7280', border: '1px solid #9CA3AF', whiteSpace: 'nowrap' }}>
                {stats.remaining} needs input
              </span>
            )}
          </div>
        </div>

        {isOpen && (
          <div>
            {s.portalNote && (
              <div style={{ marginTop: 12, display: 'flex', gap: 10, background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#1E3A5F', lineHeight: 1.5 }}>
                <Info size={16} style={{ flexShrink: 0, marginTop: 2 }} />
                <span>{s.portalNote}</span>
              </div>
            )}
            {viewMode === 'hr' && !isMobile && (
              <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'minmax(130px, 3fr) minmax(150px, 5fr) minmax(105px, auto) minmax(170px, 4fr)', gap: 12, padding: '0 14px', fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#9CA3AF' }}>
                <div>Field</div>
                <div>Value</div>
                <div style={{ textAlign: 'right' }}>Source</div>
                <div style={{ paddingLeft: 14 }}>HR annotations</div>
              </div>
            )}
            <div style={{ marginTop: viewMode === 'hr' && !isMobile ? 6 : 12, background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, overflow: 'hidden' }}>
              {s.fields.map((f, i) => renderFieldRow(s, f, i))}
            </div>
            {s.authority && (
              <div className="cds-print-only cds-print-authority" style={{ marginTop: 8, fontSize: 10.5, color: '#6B7280' }}>
                Authority: {s.authority.name} — {s.authority.url}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div
      ref={rootRef}
      className="cds-root"
      style={{ position: 'relative', height: '100%', background: '#FFFFFF', overflow: 'auto', fontFamily: "'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif", color: '#111827' }}
    >
      <style>{`
        .cds-badge { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; font-weight: 600; line-height: 1; padding: 4px 8px; border-radius: 999px; white-space: nowrap; }
        .cds-badge-intake { background: #DBEAFE; color: #1E40AF; }
        .cds-badge-passport-ocr { background: #EDE9FE; color: #5B21B6; }
        .cds-badge-prior-form { background: #CCFBF1; color: #115E59; }
        .cds-badge-needs-input { background: #FFFFFF; color: #6B7280; border: 1px solid #9CA3AF; }
        .cds-badge-consult-professional { background: #F59E0B; color: #FFFFFF; }
        .cds-print-only { display: none; }
        @media print {
          .cds-no-print { display: none !important; }
          .cds-print-only { display: block !important; }
          .cds-root { overflow: visible !important; height: auto !important; }
          /* Source badges render as plain text labels */
          .cds-badge { background: none !important; border: none !important; color: #374151 !important; padding: 0 !important; border-radius: 0 !important; }
          .cds-badge::before { content: '['; }
          .cds-badge::after { content: ']'; }
          .cds-badge svg { display: none !important; }
          /* Two-column layout for compact sections (≤4 fields) */
          .cds-sections { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: start; }
          .cds-section { margin-top: 0 !important; break-inside: avoid; }
          .cds-section-wide { grid-column: 1 / -1; }
          /* Page break before CONSULT PROFESSIONAL */
          .cds-consult { break-before: page; page-break-before: always; }
        }
      `}</style>

      <div style={{ maxWidth: viewMode === 'hr' ? 1060 : 880, margin: '0 auto', padding: isMobile ? '16px 12px 96px' : '24px 20px 96px', transition: 'max-width 0.2s' }}>
        {/* ── Header ── */}
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12, paddingBottom: 14, borderBottom: '2px solid #111827' }}>
          <div style={{ minWidth: 200 }}>
            <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.02em' }}>ReloPass</div>
            <div style={{ fontSize: 13, color: '#6B7280' }}>Corridor Data-Sheet Engine</div>
          </div>
          <div style={{ fontSize: 12, color: '#6B7280' }}>
            {meta ? meta.caseRef + ' · ' + meta.person + ' · ' : ''}
            {config.origin.name} → {config.destination.name} · {MOVEMENT_BASIS_LABEL[config.movement_basis]}
            {meta ? ' · ' + meta.generated : ''}
          </div>
        </div>

        {/* ── Controls: corridor selector + toggles ── */}
        <div className="cds-no-print" style={{ marginTop: 14, display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 12.5, fontWeight: 600, color: '#374151' }}>
            Corridor
            <select
              value={corridorId}
              onChange={(e) => switchCorridor(e.target.value)}
              style={{ fontSize: 13, fontWeight: 600, padding: '6px 10px', border: '1px solid #E5E7EB', borderRadius: 8, background: '#FFFFFF', color: '#111827', cursor: 'pointer' }}
            >
              {CORRIDOR_CONFIGS.map((c) => (
                <option key={c.corridorId} value={c.corridorId}>
                  {c.origin.name} ({c.origin.countryCode}) → {c.destination.name} ({c.destination.countryCode})
                </option>
              ))}
            </select>
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
            <ToggleGroup<ViewMode>
              options={[{ value: 'employee', label: 'Employee view' }, { value: 'hr', label: 'HR view' }]}
              value={viewMode}
              onChange={setViewMode}
            />
            <ToggleGroup<DataMode>
              options={[{ value: 'full', label: 'Full data' }, { value: 'sparse', label: 'Sparse data' }]}
              value={dataMode}
              onChange={switchDataMode}
            />
            <ToggleGroup<Lang>
              options={[{ value: 'en', label: 'EN' }, { value: 'local', label: config.destination.localLanguage.toUpperCase() }]}
              value={lang}
              onChange={setLang}
            />
            <button
              onClick={handlePrint}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 14px', background: '#111827', color: '#FFFFFF', fontSize: 12.5, fontWeight: 700, border: 'none', borderRadius: 8, cursor: 'pointer' }}
            >
              <Printer size={14} /> Print
            </button>
          </div>
        </div>

        {/* ── Regulatory banners (moat facts + warnings) ── */}
        <div style={{ marginTop: 14, display: 'grid', gap: 8 }}>
          {config.regulatoryBanners.map((b, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                gap: 10,
                background: '#FEF3C7',
                border: b.type === 'warning' ? '2px solid #D97706' : '1px solid #F59E0B',
                borderRadius: 8,
                padding: '10px 14px',
                fontSize: 13,
                color: '#92400E',
                lineHeight: 1.5,
              }}
            >
              <AlertTriangle size={17} color="#D97706" style={{ flexShrink: 0, marginTop: 1 }} />
              <span>
                {b.type === 'warning' && <strong style={{ textTransform: 'uppercase', letterSpacing: '0.04em', marginRight: 6 }}>Warning:</strong>}
                {b.text}
              </span>
            </div>
          ))}
        </div>

        {/* ── Sparse mode explainer ── */}
        {dataMode === 'sparse' && (
          <div className="cds-no-print" style={{ marginTop: 12, background: '#F9FAFB', border: '1px dashed #D1D5DB', borderRadius: 8, padding: '10px 14px', fontSize: 12.5, color: '#6B7280', lineHeight: 1.5 }}>
            <strong style={{ color: '#374151' }}>Sparse data mode</strong> — simulating a case where intake and document OCR captured almost nothing. Only the full name and passport number are known; every other field shows its NEEDS INPUT empty state. Missing values are never guessed or prefilled.
          </div>
        )}

        {/* ── Progress ── */}
        {isMobile ? (
          <div className="cds-no-print" style={{ marginTop: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#6B7280', marginBottom: 4 }}>
              <span style={{ fontWeight: 600 }}>Progress</span>
              <span>
                {overall.filled} / {overall.total} filled
              </span>
            </div>
            <div style={{ height: 8, background: '#E5E7EB', borderRadius: 999, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: (overall.total ? Math.round((overall.filled / overall.total) * 100) : 100) + '%', background: '#10B981', borderRadius: 999, transition: 'width 0.25s' }} />
            </div>
          </div>
        ) : (
          <div className="cds-no-print" style={{ marginTop: 14, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px 18px', fontSize: 12, color: '#6B7280' }}>
            {sections.map((s) => {
              const st = sectionStats(s);
              return (
                <span key={s.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 10, height: 10, borderRadius: 999, background: st.complete ? '#10B981' : '#D1D5DB', transition: 'background 0.2s' }} />
                  <span style={{ fontWeight: st.complete ? 600 : 400, color: st.complete ? '#065F46' : '#6B7280' }}>
                    {s.title.en.replace(/^\d+ · /, '')}
                    {!st.complete && st.total > 0 ? ' (' + st.remaining + ')' : ''}
                  </span>
                </span>
              );
            })}
          </div>
        )}

        {/* ── Sections ── */}
        <div className="cds-sections" style={{ marginTop: isMobile ? 4 : 0 }}>
          {sections.map((s) => renderSection(s))}
        </div>

        {/* ── CONSULT PROFESSIONAL ── */}
        <div className="cds-consult" style={{ marginTop: isMobile ? 12 : 20, background: '#FFFBEB', border: '1px solid #F59E0B', borderRadius: 8, padding: isMobile ? 12 : 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertTriangle size={17} color="#D97706" style={{ flexShrink: 0 }} />
            <h2 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: '#92400E' }}>
              {lang === 'en' ? 'Consult professional' : 'Kontakt rådgiver'}
            </h2>
          </div>
          <div style={{ marginTop: 4, fontSize: 12, color: '#92400E' }}>
            {lang === 'en'
              ? 'Regulated determinations ReloPass cannot make. Route each item to a qualified advisor.'
              : 'Regulerte vurderinger ReloPass ikke kan gjøre. Hver sak må rutes til en kvalifisert rådgiver.'}
          </div>
          <div style={{ marginTop: 12, background: '#FFFFFF', border: '1px solid #FDE68A', borderRadius: 8, overflow: 'hidden' }}>
            {config.consultProfessionalItems.map((item, i) => (
              <div key={item.id} style={{ display: isMobile ? 'block' : 'grid', gridTemplateColumns: isMobile ? undefined : 'minmax(160px, 3fr) minmax(220px, 7fr) minmax(105px, auto)', gap: 12, alignItems: 'start', padding: '10px 14px', borderTop: i === 0 ? 'none' : '1px solid #FEF3C7', background: '#FFFBEB' }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#92400E' }}>{localLabel(item.topic)}</div>
                <div style={{ marginTop: isMobile ? 4 : 0, fontSize: 12.5, color: '#92400E', lineHeight: 1.5, fontStyle: 'italic' }}>{item.reason}</div>
                <div style={{ marginTop: isMobile ? 6 : 0, textAlign: isMobile ? 'left' : 'right' }}>
                  <SourceBadge source="consult-professional" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── UNVERIFIED footer ── */}
        <div style={{ marginTop: 16, fontSize: 11.5, color: '#9CA3AF', fontWeight: 600 }}>
          ⚠️ UNVERIFIED — REQUIRES ROMAIN SIGN-OFF
        </div>

        {/* ── Badge legend ── */}
        <div style={{ marginTop: 18, borderTop: '1px solid #E5E7EB', paddingTop: 14 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#6B7280', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>Badge legend</div>
          <div style={{ display: 'grid', gap: 6 }}>
            {LEGEND.map((item) => (
              <div key={item.source} style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '190px 1fr', gap: isMobile ? 2 : 12, alignItems: 'center', fontSize: 12, color: '#6B7280' }}>
                <div>
                  <SourceBadge source={item.source} />
                </div>
                <div>= {item.text}</div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 14, fontSize: 11, color: '#9CA3AF' }}>
            Throwaway UX prototype for design validation only — all data is fictional and hardcoded. Not legal, tax, or immigration advice.
          </div>
        </div>
      </div>
    </div>
  );
}
