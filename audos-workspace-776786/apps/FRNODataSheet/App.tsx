// FR-NO Data Sheet Prototype — THROWAWAY UX PROTOTYPE
// Design-validation only: hardcoded mock data, zero API calls, no backend wiring.
// Validates the 'Personal Relocation Data Sheet' concept for the France→Norway EEA corridor.
import React, { useState } from 'react';
import { Pencil, Info, AlertTriangle, Printer } from 'lucide-react';

type Lang = 'en' | 'no';
type BadgeKind = 'intake' | 'ocr' | 'prior' | 'input' | 'consult';

interface FieldDef {
  id: string;
  label: { en: string; no: string };
  value?: string;
  badge: BadgeKind;
  note?: string;
}

interface SectionDef {
  id: string;
  title: string;
  subtitle: string;
  tooltip: string;
  infoTop?: string;
  infoBottom?: string;
  fields: FieldDef[];
}

const SECTIONS: SectionDef[] = [
  {
    id: 'dnumber',
    title: '1 · D-Number Application',
    subtitle: 'Skatteetaten · skatteetaten.no/en/forms/d-number',
    tooltip: 'Apply at least 4 weeks before first paycheck · skatteetaten.no',
    fields: [
      { id: 'd-name', label: { en: 'Full legal name', no: 'Fullt juridisk navn' }, value: 'Sophie Leblanc', badge: 'ocr' },
      { id: 'd-dob', label: { en: 'Date of birth', no: 'Fødselsdato' }, value: '22 July 1990', badge: 'ocr' },
      { id: 'd-nat', label: { en: 'Nationality', no: 'Statsborgerskap' }, value: 'French / Fransk', badge: 'intake' },
      { id: 'd-pass', label: { en: 'Passport number', no: 'Passnummer' }, value: '16AB98765', badge: 'ocr' },
      { id: 'd-passexp', label: { en: 'Passport expiry', no: 'Passutløpsdato' }, value: '3 March 2030', badge: 'ocr' },
      { id: 'd-employer', label: { en: 'Norwegian employer', no: 'Norsk arbeidsgiver' }, value: 'Cognite AS', badge: 'intake' },
      { id: 'd-org', label: { en: 'Org. number', no: 'Org.nummer' }, value: '913704777', badge: 'intake' },
      { id: 'd-firstday', label: { en: 'First work day', no: 'Første arbeidsdag' }, value: '1 October 2026', badge: 'intake' },
      { id: 'd-workaddr', label: { en: 'Norwegian work address', no: 'Norsk arbeidsadresse' }, badge: 'input' },
      { id: 'd-homeaddr', label: { en: 'Norwegian home address', no: 'Norsk bostedsadresse' }, badge: 'input' },
    ],
  },
  {
    id: 'eea',
    title: '2 · EEA Registration (Police / UDI)',
    subtitle: 'Two stages: (1) Online UDI application at udi.no before booking · (2) Police appointment — bring this sheet',
    tooltip: 'Complete UDI online application, then book police appointment · udi.no · Within first 3 months of arrival',
    infoBottom:
      'The registration certificate is issued BY the police at your appointment — it is not something you pre-fill. The fields above are what you will need when completing the UDI online application and presenting at the desk.',
    fields: [
      { id: 'e-name', label: { en: 'Full legal name', no: 'Fullt juridisk navn' }, value: 'Sophie Leblanc', badge: 'ocr' },
      { id: 'e-dob', label: { en: 'Date of birth', no: 'Fødselsdato' }, value: '22 July 1990', badge: 'ocr' },
      { id: 'e-nat', label: { en: 'Nationality', no: 'Statsborgerskap' }, value: 'French / Fransk', badge: 'intake' },
      { id: 'e-pass', label: { en: 'Passport number', no: 'Passnummer' }, value: '16AB98765', badge: 'ocr' },
      { id: 'e-homeaddr', label: { en: 'Home country address', no: 'Hjemstedsadresse' }, value: '8 Rue du Faubourg Saint-Antoine, Paris 75011', badge: 'intake' },
      { id: 'e-noaddr', label: { en: 'Norwegian address', no: 'Norsk adresse' }, badge: 'input' },
      { id: 'e-duration', label: { en: 'Intended duration', no: 'Planlagt varighet' }, value: '12+ months / 12+ måneder', badge: 'intake' },
      { id: 'e-purpose', label: { en: 'Purpose of stay', no: 'Oppholdsformål' }, value: 'Employment / Arbeid', badge: 'intake' },
      { id: 'e-letter', label: { en: 'Employer confirmation letter', no: 'Arbeidsgiverbekreftelse' }, badge: 'input', note: 'You must bring a signed letter from Cognite AS confirming your employment and salary' },
    ],
  },
  {
    id: 'skattekort',
    title: '3 · Tax Card (Skattekort)',
    subtitle: 'Skatteetaten portal · Must be in place before first paycheck',
    tooltip: 'Apply as soon as D-number is confirmed · skatteetaten.no · Must be active before first paycheck',
    fields: [
      { id: 's-name', label: { en: 'Full legal name', no: 'Fullt juridisk navn' }, value: 'Sophie Leblanc', badge: 'ocr' },
      { id: 's-dob', label: { en: 'Date of birth', no: 'Fødselsdato' }, value: '22 July 1990', badge: 'ocr' },
      { id: 's-employer', label: { en: 'Norwegian employer', no: 'Norsk arbeidsgiver' }, value: 'Cognite AS', badge: 'intake' },
      { id: 's-org', label: { en: 'Org. number', no: 'Org.nummer' }, value: '913704777', badge: 'intake' },
      { id: 's-salary', label: { en: 'Expected gross salary', no: 'Forventet bruttoinntekt' }, value: 'NOK 920,000 / year', badge: 'intake' },
      { id: 's-start', label: { en: 'Expected start date', no: 'Forventet startdato' }, value: '1 October 2026', badge: 'intake' },
      { id: 's-noaddr', label: { en: 'Norwegian address', no: 'Norsk adresse' }, badge: 'input' },
      { id: 's-previncome', label: { en: 'Previous Norwegian income?', no: 'Tidligere norsk inntekt?' }, badge: 'input' },
      { id: 's-residency', label: { en: 'Tax residency status', no: 'Skattemessig bosted' }, badge: 'consult', note: 'Whether you are Norwegian or French tax resident depends on where your permanent home and family are. A tax advisor must confirm this before your skattekort is issued.' },
    ],
  },
  {
    id: 'folkeregister',
    title: '4 · National Register (Folkeregister)',
    subtitle: 'Skatteetaten · Required if staying more than 6 months',
    tooltip: 'Register within 6 months of arrival if staying long-term · skatteetaten.no',
    fields: [
      { id: 'f-name', label: { en: 'Full legal name', no: 'Fullt juridisk navn' }, value: 'Sophie Leblanc', badge: 'ocr' },
      { id: 'f-dob', label: { en: 'Date of birth', no: 'Fødselsdato' }, value: '22 July 1990', badge: 'ocr' },
      { id: 'f-noaddr', label: { en: 'Norwegian address', no: 'Norsk adresse' }, badge: 'input' },
      { id: 'f-civil', label: { en: 'Civil status', no: 'Sivilstatus' }, value: 'Single / Ugift', badge: 'intake' },
      { id: 'f-children', label: { en: 'Dependent children following?', no: 'Medfølgende barn?' }, value: 'None / Ingen', badge: 'intake' },
      { id: 'f-stay', label: { en: 'Expected length of stay', no: 'Forventet oppholdslengde' }, value: '12+ months / 12+ måneder', badge: 'intake' },
    ],
  },
  {
    id: 'a1',
    title: '5 · A1 Certificate (Issued by French authorities)',
    subtitle: 'CPAM / URSSAF · Initiated by your French employer in France — NOT a Norwegian process',
    tooltip: 'French employer should apply via CPAM/Net-entreprises at least 4 weeks before posting starts',
    infoTop:
      'The A1 certificate proves that French social security continues to apply during your posting. It is requested by your French employer through CPAM or URSSAF — not by you, and not in Norway. ReloPass shows the information your employer will need, but cannot determine whether French or Norwegian social security applies in your case.',
    fields: [
      { id: 'a-name', label: { en: 'Employee name', no: 'Ansattnavn' }, value: 'Sophie Leblanc', badge: 'intake' },
      { id: 'a-fremployer', label: { en: 'French employer name', no: 'Fransk arbeidsgiver' }, badge: 'input', note: 'Enter the name of your French employer entity' },
      { id: 'a-host', label: { en: 'Norwegian host employer', no: 'Norsk vertsarbeidsgiver' }, value: 'Cognite AS', badge: 'intake' },
      { id: 'a-duration', label: { en: 'Expected posting duration', no: 'Forventet utstasjoneringsperiode' }, value: '12 months / 12 måneder', badge: 'intake' },
      { id: 'a-contract', label: { en: 'Contract type (secondment vs local hire)', no: 'Kontraktstype' }, badge: 'consult', note: 'Whether this is a posting (French contract) or a local hire (Norwegian contract) changes which social security system applies and must be confirmed by HR/legal before the A1 is requested.' },
      { id: 'a-socsec', label: { en: 'Social security determination', no: 'Trygdeavklaring' }, badge: 'consult', note: "Which country's social security applies (France or Norway) is a regulated determination under EU Regulation 883/2004. Route to a social security specialist." },
      { id: 'a-shadow', label: { en: 'Shadow payroll required?', no: 'Skyggelønnsoppgjør påkrevet?' }, badge: 'consult', note: 'If tax goes to Norway but social security stays French, a shadow payroll mechanism is required. Your HR advisor must confirm.' },
    ],
  },
];

const PROGRESS_LABELS: Record<string, string> = {
  dnumber: 'D-number',
  eea: 'EEA Registration',
  skattekort: 'Skattekort',
  folkeregister: 'Folkeregister',
  a1: 'A1',
};

const LEGEND: { badge: BadgeKind; text: string }[] = [
  { badge: 'intake', text: 'entered during case intake' },
  { badge: 'ocr', text: 'read from uploaded passport scan' },
  { badge: 'prior', text: 'carried from a previous case' },
  { badge: 'input', text: 'you must provide this value before your appointment' },
  { badge: 'consult', text: 'requires a regulated tax, legal, or social security advisor — ReloPass cannot determine this' },
];

function Badge({ kind }: { kind: BadgeKind }) {
  const base: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    fontSize: 11,
    fontWeight: 600,
    lineHeight: 1,
    padding: '4px 8px',
    borderRadius: 999,
    whiteSpace: 'nowrap',
  };
  switch (kind) {
    case 'intake':
      return <span style={{ ...base, background: '#DBEAFE', color: '#1E40AF' }}>intake</span>;
    case 'ocr':
      return <span style={{ ...base, background: '#EDE9FE', color: '#5B21B6' }}>passport-OCR</span>;
    case 'prior':
      return <span style={{ ...base, background: '#D1FAE5', color: '#065F46' }}>prior-form</span>;
    case 'input':
      return (
        <span style={{ ...base, background: '#FEF3C7', color: '#92400E', border: '1px solid #F59E0B' }}>
          <Pencil size={11} strokeWidth={2.5} /> NEEDS INPUT
        </span>
      );
    case 'consult':
      return (
        <span style={{ ...base, background: '#FEF3C7', color: '#92400E' }}>
          <AlertTriangle size={11} strokeWidth={2.5} color="#D97706" /> CONSULT PROFESSIONAL
        </span>
      );
  }
}

function InfoBox({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#1E3A5F', lineHeight: 1.5 }}>
      {children}
    </div>
  );
}

export default function FRNODataSheetPrototype() {
  const [lang, setLang] = useState<Lang>('en');
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [openTooltip, setOpenTooltip] = useState<string | null>(null);
  const [toast, setToast] = useState(false);

  const sectionComplete = (section: SectionDef) =>
    section.fields.filter((f) => f.badge === 'input').every((f) => (inputs[f.id] || '').trim().length > 0);

  const handlePrint = () => {
    setToast(true);
    window.setTimeout(() => setToast(false), 3500);
    window.setTimeout(() => window.print(), 350);
  };

  const renderValueCell = (f: FieldDef) => {
    if (f.badge === 'consult') {
      return (
        <div style={{ fontSize: 13, color: '#92400E', lineHeight: 1.5, fontStyle: 'italic' }}>{f.note}</div>
      );
    }
    if (f.badge === 'input') {
      const val = inputs[f.id] || '';
      const isEditing = editing === f.id;
      return (
        <div>
          {isEditing ? (
            <input
              autoFocus
              type="text"
              value={val}
              onChange={(e) => setInputs((prev) => ({ ...prev, [f.id]: e.target.value }))}
              onBlur={() => setEditing(null)}
              onKeyDown={(e) => { if (e.key === 'Enter') setEditing(null); }}
              placeholder={lang === 'en' ? 'Type here…' : 'Skriv her…'}
              style={{ width: '100%', fontSize: 14, padding: '6px 10px', border: '1px solid #F59E0B', borderRadius: 6, outline: 'none', background: '#FFFBEB', color: '#111827' }}
            />
          ) : (
            <button
              onClick={() => setEditing(f.id)}
              style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%', textAlign: 'left', fontSize: 14, padding: '6px 10px', border: '1px dashed ' + (val ? '#D1D5DB' : '#F59E0B'), borderRadius: 6, background: val ? '#FFFFFF' : '#FFFBEB', color: val ? '#111827' : '#B45309', cursor: 'text' }}
            >
              <Pencil size={13} style={{ flexShrink: 0, opacity: 0.6 }} />
              {val || (lang === 'en' ? 'Click to fill in' : 'Klikk for å fylle ut')}
            </button>
          )}
          {f.note && (
            <div style={{ marginTop: 4, fontSize: 12, color: '#92400E', lineHeight: 1.4 }}>{f.note}</div>
          )}
        </div>
      );
    }
    return <div style={{ fontSize: 14, color: '#111827' }}>{f.value}</div>;
  };

  return (
    <div style={{ position: 'relative', height: '100%', background: '#FFFFFF', overflow: 'auto', fontFamily: "'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif", color: '#111827' }} className="frno-sheet-root">
      <style>{`
        @media print {
          .frno-no-print { display: none !important; }
          .frno-tooltip { display: none !important; }
          .frno-sheet-root { overflow: visible !important; height: auto !important; }
        }
      `}</style>

      <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 20px 96px' }}>
        {/* ── Header ─────────────────────────────────────────── */}
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12, paddingBottom: 16, borderBottom: '2px solid #111827' }}>
          <div style={{ minWidth: 220 }}>
            <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.02em' }}>ReloPass</div>
            <div style={{ fontSize: 13, color: '#6B7280' }}>Personal Relocation Data Sheet</div>
          </div>
          <div style={{ fontSize: 12, color: '#6B7280', textAlign: 'center', flex: '1 1 auto' }}>
            Case FR-NO-2026-0081 · France → Norway · Generated 29 Jul 2026
          </div>
          <div className="frno-no-print" style={{ display: 'flex', gap: 0, border: '1px solid #E5E7EB', borderRadius: 8, overflow: 'hidden' }}>
            {(['en', 'no'] as Lang[]).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                style={{
                  padding: '6px 14px',
                  fontSize: 13,
                  fontWeight: 700,
                  border: 'none',
                  cursor: 'pointer',
                  background: lang === l ? '#111827' : '#FFFFFF',
                  color: lang === l ? '#FFFFFF' : '#6B7280',
                }}
              >
                {l.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* ── Regulatory banner ──────────────────────────────── */}
        <div style={{ marginTop: 16, background: '#FEF3C7', border: '1px solid #F59E0B', borderRadius: 8, padding: '12px 16px', fontSize: 13, color: '#92400E', lineHeight: 1.5, display: 'flex', gap: 10 }}>
          <AlertTriangle size={18} color="#D97706" style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            Fields marked <strong>Consult professional</strong> contain tax, social security, or legal determinations that ReloPass cannot make. A regulated advisor must confirm these before payroll or registration is finalised.
          </span>
        </div>

        {/* ── Progress indicator ─────────────────────────────── */}
        <div style={{ marginTop: 14, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px 18px', fontSize: 12, color: '#6B7280' }}>
          {SECTIONS.map((s) => {
            const done = sectionComplete(s);
            return (
              <span key={s.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 10, height: 10, borderRadius: 999, background: done ? '#10B981' : '#D1D5DB', transition: 'background 0.2s' }} />
                <span style={{ fontWeight: done ? 600 : 400, color: done ? '#065F46' : '#6B7280' }}>{PROGRESS_LABELS[s.id]}</span>
              </span>
            );
          })}
        </div>

        {/* ── Sections ───────────────────────────────────────── */}
        {SECTIONS.map((section) => (
          <div key={section.id} style={{ marginTop: 20, background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: 8, padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, position: 'relative' }}>
                  <h2 style={{ margin: 0, fontSize: 15, fontWeight: 700 }}>{section.title}</h2>
                  <span
                    className="frno-no-print"
                    style={{ position: 'relative', display: 'inline-flex' }}
                    onMouseEnter={() => setOpenTooltip(section.id)}
                    onMouseLeave={() => setOpenTooltip((cur) => (cur === section.id ? null : cur))}
                  >
                    <button
                      onClick={() => setOpenTooltip((cur) => (cur === section.id ? null : section.id))}
                      aria-label="Section info"
                      style={{ border: 'none', background: 'transparent', padding: 2, cursor: 'pointer', color: '#6B7280', display: 'inline-flex' }}
                    >
                      <Info size={14} />
                    </button>
                    {openTooltip === section.id && (
                      <div className="frno-tooltip" style={{ position: 'absolute', top: '100%', left: 0, zIndex: 20, width: 260, background: '#111827', color: '#F9FAFB', fontSize: 12, lineHeight: 1.5, padding: '8px 12px', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.25)', fontWeight: 400 }}>
                        {section.tooltip}
                      </div>
                    )}
                  </span>
                </div>
                <div style={{ marginTop: 2, fontSize: 12, color: '#6B7280' }}>{section.subtitle}</div>
              </div>
            </div>

            {section.infoTop && (
              <div style={{ marginTop: 12 }}>
                <InfoBox>{section.infoTop}</InfoBox>
              </div>
            )}

            {/* Field table */}
            <div style={{ marginTop: 12, background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 8, overflow: 'hidden' }}>
              {section.fields.map((f, i) => (
                <div
                  key={f.id}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'minmax(140px, 4fr) minmax(160px, 6fr) minmax(90px, auto)',
                    gap: 12,
                    alignItems: 'center',
                    padding: '9px 14px',
                    borderTop: i === 0 ? 'none' : '1px solid #F3F4F6',
                  }}
                >
                  <div style={{ fontSize: 13, color: '#6B7280', fontWeight: 500 }}>{f.label[lang]}</div>
                  <div>{renderValueCell(f)}</div>
                  <div style={{ textAlign: 'right' }}>
                    <Badge kind={f.badge} />
                  </div>
                </div>
              ))}
            </div>

            {section.infoBottom && (
              <div style={{ marginTop: 12 }}>
                <InfoBox>{section.infoBottom}</InfoBox>
              </div>
            )}
          </div>
        ))}

        {/* ── Footer legend ──────────────────────────────────── */}
        <div style={{ marginTop: 24, borderTop: '1px solid #E5E7EB', paddingTop: 14 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#6B7280', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
            Badge legend
          </div>
          <div style={{ display: 'grid', gap: 6 }}>
            {LEGEND.map((item) => (
              <div key={item.badge} style={{ display: 'grid', gridTemplateColumns: '180px 1fr', gap: 12, alignItems: 'center', fontSize: 12, color: '#6B7280' }}>
                <div><Badge kind={item.badge} /></div>
                <div>= {item.text}</div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 16, fontSize: 11, color: '#9CA3AF' }}>
            Prototype for design validation only — all data is fictional. Not legal, tax, or immigration advice.
          </div>
        </div>
      </div>

      {/* ── Floating print button ────────────────────────────── */}
      <button
        className="frno-no-print"
        onClick={handlePrint}
        style={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          zIndex: 30,
          display: 'inline-flex',
          alignItems: 'center',
          gap: 8,
          padding: '12px 18px',
          background: '#111827',
          color: '#FFFFFF',
          fontSize: 14,
          fontWeight: 600,
          border: 'none',
          borderRadius: 999,
          cursor: 'pointer',
          boxShadow: '0 4px 14px rgba(0,0,0,0.25)',
        }}
      >
        <Printer size={16} /> Print / Export
      </button>

      {/* ── Toast ────────────────────────────────────────────── */}
      {toast && (
        <div
          className="frno-no-print"
          style={{
            position: 'fixed',
            bottom: 84,
            right: 24,
            zIndex: 40,
            background: '#111827',
            color: '#F9FAFB',
            fontSize: 13,
            padding: '10px 16px',
            borderRadius: 8,
            boxShadow: '0 4px 14px rgba(0,0,0,0.3)',
          }}
        >
          PDF export will be available in the production build.
        </div>
      )}
    </div>
  );
}
