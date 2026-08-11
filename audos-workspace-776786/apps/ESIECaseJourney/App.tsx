// ES_IE Case Journey Prototype — THROWAWAY UX PROTOTYPE
// Design-validation only: hardcoded mock data, zero API calls, zero DB reads/writes,
// no production wiring. Persona 'Ana García' is fictitious — no PII.
// The real build lands in the rolec repo via Claude Code, not here.
import React, { useState } from 'react';
import { AlertTriangle, Info } from 'lucide-react';

type TabId = 'timeline' | 'compliance' | 'dublin';
type OwnerKind = 'employer' | 'hr' | 'employee' | 'employeeHr' | 'spouse';

// ── Hardcoded case dates ────────────────────────────────────────────
// CONTRACT_SIGNED = 2026-08-01, TARGET_START_DATE = 2027-02-01 → 26 weeks (safe)
const WEEKS_TO_TARGET = 26;

const FONT = "'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";

// ── Shared building blocks ──────────────────────────────────────────

function OwnerBadge({ kind }: { kind: OwnerKind }) {
  const base: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    fontSize: 11,
    fontWeight: 700,
    lineHeight: 1.2,
    padding: '4px 10px',
    borderRadius: 999,
    whiteSpace: 'nowrap',
  };
  // Employer-side obligations: blue fill — visually distinct from employee-step badges (grey).
  const employer: React.CSSProperties = { ...base, background: '#DBEAFE', color: '#1E40AF', border: '1px solid #93C5FD' };
  const employee: React.CSSProperties = { ...base, background: '#F3F4F6', color: '#374151', border: '1px solid #E5E7EB' };
  switch (kind) {
    case 'employer':
      return <span style={employer}>🏢 EMPLOYER FILES — HR obligation</span>;
    case 'hr':
      return <span style={employer}>🏢 HR obligation</span>;
    case 'employee':
      return <span style={employee}>👤 Employee</span>;
    case 'employeeHr':
      return <span style={employee}>👤 Employee + HR support</span>;
    case 'spouse':
      return <span style={employee}>👤 Spouse + HR support</span>;
  }
}

function ConsultBadge() {
  // Amber-FILLED pill (#F59E0B family) — intentionally distinct from the moat-fact callouts (left-border style).
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        fontSize: 11,
        fontWeight: 700,
        lineHeight: 1.2,
        padding: '5px 10px',
        borderRadius: 999,
        whiteSpace: 'nowrap',
        background: '#F59E0B',
        color: '#451A03',
      }}
    >
      <AlertTriangle size={12} strokeWidth={2.5} /> CONSULT PROFESSIONAL
    </span>
  );
}

// Moat-fact callout: amber LEFT BORDER + light amber fill — a filled callout block,
// visually distinct from the amber CONSULT PROFESSIONAL pill badge.
function MoatCallout({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        background: '#FFFBEB',
        borderLeft: '4px solid #F59E0B',
        borderTop: '1px solid #FDE68A',
        borderRight: '1px solid #FDE68A',
        borderBottom: '1px solid #FDE68A',
        borderRadius: 8,
        padding: '12px 16px',
        fontSize: 13,
        color: '#78350F',
        lineHeight: 1.55,
      }}
    >
      {children}
    </div>
  );
}

function AmberNote({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ background: '#FFFBEB', border: '1px solid #FDE68A', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#92400E', lineHeight: 1.5 }}>
      {children}
    </div>
  );
}

function RedNote({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: '#991B1B', lineHeight: 1.5 }}>
      {children}
    </div>
  );
}

// ── TAB 1 · Timeline & SLA ──────────────────────────────────────────

interface TimelineStep {
  id: string;
  week: string;
  label: string;
  owner: OwnerKind;
  authority?: string;
  cost?: string;
  leadTime?: string;
  leadTimeWarning?: string; // amber
  note?: string;
  noteAmber?: string; // amber callout note
  warningRed?: string; // red warning
  parallelBranch?: {
    label: string;
    owner: OwnerKind;
    note: string;
  };
}

const TIMELINE_STEPS: TimelineStep[] = [
  {
    id: 'csep',
    week: 'WEEK 0',
    label: 'CSEP Application lodged',
    owner: 'employer',
    authority: 'DETE (Dept. Enterprise, Trade & Employment)',
    leadTime: '12–16 weeks processing after lodgement',
    note: 'The employer is the applicant for the Critical Skills Employment Permit. The employee does not file this. HR must lodge via EPOS (Employment Permits Online System).',
  },
  {
    id: 'dvisa',
    week: 'WEEKS 12–16 (CSEP issued)',
    label: 'Long-stay D Employment Visa',
    owner: 'employee',
    authority: 'Irish Embassy / Consulate, Madrid',
    leadTime: '4–8 weeks after CSEP issued',
    note: 'Apply for a long-stay D Employment Visa at the Irish Embassy in Madrid. Bring: CSEP, passport, employer letter, proof of accommodation. Visa is issued by an Irish authority at the Spanish location.',
  },
  {
    id: 'travel',
    week: 'WEEKS 20–26 (visa issued)',
    label: 'Travel to Ireland',
    owner: 'employee',
    note: 'Travel only after the D Employment Visa is stamped in your passport.',
  },
  {
    id: 'irp',
    week: 'WITHIN 90 DAYS OF ARRIVAL',
    label: 'IRP Registration (Stamp 1)',
    owner: 'employee',
    authority: 'Immigration Registration Office — Burgh Quay, Dublin 2',
    cost: '€300',
    leadTimeWarning: '⚠️ IRP appointments at Burgh Quay are in high demand — typical booking lead time is 6–8 weeks. Book your appointment as soon as you arrive. Do not wait.',
    note: 'This is your immigration permission. Without Stamp 1, you are not legally authorised to reside in Ireland, regardless of your CSEP.',
    parallelBranch: {
      label: 'Spouse — Stamp 1G (if applicable)',
      owner: 'spouse',
      note: 'Stamp 1G conditions (work authorisation or work-prohibited) depend on current INIS policy. Confirm with your relocation agent.',
    },
  },
  {
    id: 'ppsn',
    week: 'AFTER IRP',
    label: 'PPSN',
    owner: 'employeeHr',
    authority: 'Dept. Social Protection (Intreo)',
    note: 'PPSN appointment at your local Intreo office. Bring: passport, IRP registration certificate, proof of address, employer letter.',
  },
  {
    id: 'rpn',
    week: 'AFTER PPSN',
    label: 'Register with Revenue (RPN)',
    owner: 'hr',
    note: 'Register with Irish Revenue and receive a Revenue Payroll Notification (RPN) before first paycheck.',
    warningRed: '⛔ If first paycheck issues before RPN is registered, emergency tax applies — typically >50% deduction. This must be resolved before payroll runs.',
  },
  {
    id: 'bank',
    week: 'AFTER ARRIVAL',
    label: 'Bank account',
    owner: 'employee',
    noteAmber:
      'Catch-22: Irish banks require proof of address; landlords want proof of a bank account. Bridge with Revolut or N26 (no proof-of-address required) for the first 4–6 weeks, then open an AIB/BOI/PTSB account once you have utility bills or a lease.',
  },
  {
    id: 'stamp4',
    week: '21 MONTHS POST-ARRIVAL',
    label: 'Stamp 4 eligibility',
    owner: 'employeeHr',
    note: 'CSEP holders become eligible for Stamp 4 (unrestricted work authorisation) after 21 months of employment on the permit. This removes the need to renew the CSEP and allows employment with any employer.',
  },
];

const MOAT_FACTS: string[] = [
  'Your Spanish TIE does not give you the right to live in Ireland. Ireland opted out of the EU Long-Term Residents Directive (2003/109/EC) — a Spanish long-term residence permit has no legal effect in Ireland.',
  'Ireland is outside Schengen. Venezuelan nationals need a separate long-stay D Employment Visa issued by the Irish Embassy in Madrid before travel. Your Spanish TIE gives no entry right to Ireland.',
  'The CSEP (employment permit) is NOT immigration permission. Holding a CSEP does not authorise you to live in Ireland. You must register with Irish immigration (IRP/Stamp 1) at Burgh Quay within 90 days of arrival.',
];

function TimelineTab() {
  return (
    <div>
      {/* Header block + feasibility indicator */}
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
        <div style={{ minWidth: 260, flex: '1 1 320px' }}>
          <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#6B7280' }}>Madrid → Dublin</div>
          <h2 style={{ margin: '4px 0 0', fontSize: 20, fontWeight: 800, color: '#111827', letterSpacing: '-0.01em' }}>
            Critical Skills Employment Permit (CSEP)
          </h2>
          <div style={{ marginTop: 4, fontSize: 13, fontStyle: 'italic', color: '#6B7280', lineHeight: 1.5 }}>
            This is an Employment Permit corridor — not EEA free movement. The employer applies for the permit.
          </div>
        </div>

        {/* Feasibility indicator (top-right of the timeline) */}
        <div style={{ flex: '0 1 320px', minWidth: 260 }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              background: '#D1FAE5',
              color: '#065F46',
              border: '1px solid #6EE7B7',
              borderRadius: 999,
              padding: '7px 14px',
              fontSize: 13,
              fontWeight: 700,
            }}
          >
            ✓ Timeline viable — {WEEKS_TO_TARGET} weeks to target start
          </div>
          <div style={{ marginTop: 6, fontSize: 12, color: '#6B7280', lineHeight: 1.5 }}>
            A Critical Skills Employment Permit typically requires 20+ weeks from contract signing to arrival. The timeline below is based on your stated dates.
          </div>
        </div>
      </div>

      {/* Moat-fact callout cards */}
      <div style={{ marginTop: 18, display: 'grid', gap: 10 }}>
        {MOAT_FACTS.map((fact, i) => (
          <MoatCallout key={i}>{fact}</MoatCallout>
        ))}
      </div>

      {/* Vertical timeline */}
      <div style={{ marginTop: 26 }}>
        {TIMELINE_STEPS.map((step, i) => (
          <div key={step.id} style={{ display: 'flex', gap: 14 }}>
            {/* Rail */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 28, flexShrink: 0 }}>
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 999,
                  background: '#111827',
                  color: '#FFFFFF',
                  fontSize: 12,
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                {i + 1}
              </div>
              {i < TIMELINE_STEPS.length - 1 && <div style={{ width: 2, flex: 1, background: '#E5E7EB', minHeight: 24 }} />}
            </div>

            {/* Step card */}
            <div style={{ flex: 1, minWidth: 0, paddingBottom: 22 }}>
              <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.08em', color: '#6B7280', textTransform: 'uppercase' }}>{step.week}</div>
              <div style={{ marginTop: 6, background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: 10, padding: '14px 16px' }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '6px 10px' }}>
                  <h3 style={{ margin: 0, fontSize: 15.5, fontWeight: 700, color: '#111827' }}>{step.label}</h3>
                  <OwnerBadge kind={step.owner} />
                </div>

                {(step.authority || step.cost || step.leadTime) && (
                  <div style={{ marginTop: 8, display: 'grid', gap: 3, fontSize: 12.5, color: '#4B5563' }}>
                    {step.authority && (
                      <div>
                        <span style={{ fontWeight: 600, color: '#374151' }}>Authority:</span> {step.authority}
                      </div>
                    )}
                    {step.cost && (
                      <div>
                        <span style={{ fontWeight: 600, color: '#374151' }}>Cost:</span> {step.cost}
                      </div>
                    )}
                    {step.leadTime && (
                      <div>
                        <span style={{ fontWeight: 600, color: '#374151' }}>Lead time:</span> {step.leadTime}
                      </div>
                    )}
                  </div>
                )}

                {step.leadTimeWarning && (
                  <div style={{ marginTop: 10 }}>
                    <AmberNote>{step.leadTimeWarning}</AmberNote>
                  </div>
                )}

                {step.note && <div style={{ marginTop: 10, fontSize: 13, color: '#374151', lineHeight: 1.55 }}>{step.note}</div>}

                {step.noteAmber && (
                  <div style={{ marginTop: 10 }}>
                    <AmberNote>{step.noteAmber}</AmberNote>
                  </div>
                )}

                {step.warningRed && (
                  <div style={{ marginTop: 10 }}>
                    <RedNote>{step.warningRed}</RedNote>
                  </div>
                )}
              </div>

              {/* Parallel track — side branch */}
              {step.parallelBranch && (
                <div style={{ marginTop: 10, marginLeft: 18, display: 'flex', gap: 10 }}>
                  <div style={{ width: 18, flexShrink: 0, borderLeft: '2px dashed #D1D5DB', borderBottom: '2px dashed #D1D5DB', borderBottomLeftRadius: 10, height: 34 }} />
                  <div style={{ flex: 1, minWidth: 0, background: '#FFFFFF', border: '1px dashed #D1D5DB', borderRadius: 10, padding: '12px 14px' }}>
                    <div style={{ fontSize: 10.5, fontWeight: 800, letterSpacing: '0.08em', color: '#9CA3AF', textTransform: 'uppercase' }}>Parallel track</div>
                    <div style={{ marginTop: 5, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '6px 10px' }}>
                      <h4 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#111827' }}>{step.parallelBranch.label}</h4>
                      <OwnerBadge kind={step.parallelBranch.owner} />
                    </div>
                    <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', gap: 8 }}>
                      <ConsultBadge />
                      <div style={{ flex: '1 1 220px', fontSize: 13, color: '#374151', lineHeight: 1.5 }}>{step.parallelBranch.note}</div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Danger state — shown at the very bottom of the timeline */}
      <div style={{ marginTop: 6, background: '#FEF2F2', border: '1px solid #FCA5A5', borderRadius: 10, padding: '14px 16px' }}>
        <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#B91C1C' }}>
          If target start is &lt; 20 weeks from contract signing:
        </div>
        <div style={{ marginTop: 6, fontSize: 13.5, color: '#991B1B', lineHeight: 1.55 }}>
          ⛔ CSEP window at risk — typical processing time is 12–16 weeks for the permit alone, plus 4–8 weeks for the D-visa. At this timeline, payroll start may be delayed. Raise with your relocation agent immediately.
        </div>
      </div>
    </div>
  );
}

// ── TAB 2 · Compliance Flags ────────────────────────────────────────

interface ComplianceRow {
  label: string;
  rationale: string;
  linkText?: string;
}

const COMPLIANCE_ROWS: ComplianceRow[] = [
  {
    label: 'Critical Skills Occupations List (CSOL) category',
    rationale:
      'Determines the applicable salary floor (€40,904 + degree on CSOL / €68,911 not on CSOL / €36,848 recent grad). DETE updates the list annually. HR must verify the job title against the current published list before lodging the permit application.',
    linkText: 'Check current CSOL at enterprise.gov.ie',
  },
  {
    label: 'Irish tax residency status',
    rationale:
      'Ireland uses a 183-day rule AND a domicile/centre-of-life test. Venezuelan national with no Irish domicile: facts-and-circumstances analysis. → Tax advisor.',
  },
  {
    label: 'PRSI / social insurance — which country applies',
    rationale:
      'EU Regulation 883/2004 applies (Ireland is EU). Venezuelan nationality + prior Spanish contributions may trigger bilateral social security agreement complexity. → Social security specialist.',
  },
  {
    label: 'Shadow payroll requirement',
    rationale:
      'Depends on whether the Spanish employer continues payroll during the transition and how the social insurance determination resolves. → HR/legal.',
  },
  {
    label: 'Employer permanent establishment (PE) risk',
    rationale:
      'If the Spanish employer (multinational) directs work from Ireland without an Irish entity, PE risk analysis required before the employment structure is finalised. → Tax lawyer.',
  },
];

function ComplianceTab() {
  return (
    <div>
      <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: '#111827', letterSpacing: '-0.01em' }}>
        Regulated determinations — never pre-filled by ReloPass
      </h2>
      <div style={{ marginTop: 4, fontSize: 13, fontStyle: 'italic', color: '#6B7280', lineHeight: 1.5 }}>
        These five determinations must be made by a regulated professional. ReloPass surfaces that the question exists — it does not answer it.
      </div>

      <div style={{ marginTop: 18, background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 10, overflow: 'hidden' }}>
        {COMPLIANCE_ROWS.map((row, i) => (
          <div key={row.label} style={{ padding: '14px 16px', borderTop: i === 0 ? 'none' : '1px solid #F3F4F6' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '6px 12px' }}>
              <div style={{ fontSize: 14.5, fontWeight: 700, color: '#111827', flex: '1 1 260px', minWidth: 0 }}>{row.label}</div>
              <ConsultBadge />
            </div>
            <div style={{ marginTop: 6, fontSize: 13, color: '#4B5563', lineHeight: 1.55 }}>{row.rationale}</div>
            {row.linkText && (
              <div style={{ marginTop: 6, fontSize: 13, fontWeight: 600, color: '#1D4ED8', textDecoration: 'underline', cursor: 'default' }}>
                {row.linkText}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── TAB 3 · Dublin: Living + Services ───────────────────────────────

interface Neighbourhood {
  name: string;
  character: string;
  transit: string;
  price: '€' | '€€' | '€€€';
}

const NEIGHBOURHOODS: Neighbourhood[] = [
  { name: 'Grand Canal Dock', character: 'Tech hub, modern apartment blocks', transit: 'On-site', price: '€€€' },
  { name: 'Sandymount', character: 'Coastal, quiet, family-friendly', transit: 'DART 12 min', price: '€€€' },
  { name: 'Ranelagh', character: 'Lively, café culture, walkable', transit: 'Bus/Luas 20 min', price: '€€€' },
  { name: 'Portobello', character: 'Canal-side, trendy, tight supply', transit: 'Luas/bike 20 min', price: '€€' },
  { name: 'Stoneybatter', character: 'Bohemian, up-and-coming, more affordable', transit: 'Bus 25 min', price: '€€' },
  { name: 'Clontarf', character: 'Coastal, family, quieter', transit: 'DART 20 min', price: '€€' },
  { name: 'Drumcondra', character: 'Transit hub, mid-range, good value', transit: 'Bus 20 min', price: '€' },
  { name: 'Dún Laoghaire', character: 'Upmarket, coastal, further out', transit: 'DART 35 min', price: '€€€' },
];

interface ServiceTile {
  category: string;
  lines: { heading: string; value: string }[];
  note: string;
}

const SERVICES: ServiceTile[] = [
  {
    category: 'Banking',
    lines: [
      { heading: 'Traditional', value: 'AIB, Bank of Ireland, PTSB' },
      { heading: 'Digital (no proof of address)', value: 'Revolut, N26, Wise' },
    ],
    note: 'Open Revolut or N26 on arrival. Use as your primary account until you have a utility bill or lease for the traditional bank application.',
  },
  {
    category: 'Health',
    lines: [{ heading: 'Private insurers', value: 'VHI, Laya, Irish Life' }],
    note: 'Non-ordinarily-resident on arrival — you must have private health insurance to access GP and specialist care until the ordinarily-resident test is satisfied (183 days). Arrange before travel.',
  },
  {
    category: 'Movers',
    lines: [{ heading: 'Type', value: 'Intra-EU sea/road freight' }],
    note: 'Spain → Ireland is intra-EU. No customs clearance needed. Logistics involve sea crossing (typically Santander or Bilbao → Cork or Dublin). Allow extra transit time vs. land corridors.',
  },
  {
    category: 'Utilities',
    lines: [{ heading: 'Providers', value: 'Electric Ireland, Bord Gáis Energy, SSE Airtricity, Energia' }],
    note: 'Utility bills are the standard proof of address for Irish banks — set up in your own name as soon as possible after taking a property.',
  },
  {
    category: 'Telecom',
    lines: [{ heading: 'Providers', value: 'Eir, Vodafone, Three, Virgin Media' }],
    note: 'SIM-only contracts are easiest on arrival without Irish credit history. Eir and Three offer good coverage; Virgin Media for broadband.',
  },
  {
    category: 'Transport',
    lines: [{ heading: 'Leap card', value: 'Covers DART, Luas, Dublin Bus, Go-Ahead Ireland on a single card' }],
    note: 'Buy a Leap card at any convenience store or online. Load online or at Luas/DART machines. Reduces per-journey cost vs. cash fares.',
  },
];

function PriceBand({ band }: { band: '€' | '€€' | '€€€' }) {
  return (
    <span style={{ fontSize: 13, fontWeight: 800, letterSpacing: '0.05em', color: '#111827' }}>
      {band}
      <span style={{ color: '#D1D5DB' }}>{'€'.repeat(3 - band.length)}</span>
    </span>
  );
}

function DublinTab() {
  return (
    <div>
      {/* Rental shortage banner */}
      <div
        style={{
          background: '#FEF2F2',
          border: '1px solid #FCA5A5',
          borderLeft: '4px solid #DC2626',
          borderRadius: 10,
          padding: '14px 16px',
          fontSize: 13.5,
          fontWeight: 600,
          color: '#991B1B',
          lineHeight: 1.55,
        }}
      >
        ⛔ Dublin rental shortage — allow 4–8 weeks to secure accommodation before your start date. Do not book flights or hand in notice until you have a signed lease or confirmed temporary housing.
      </div>

      {/* Neighbourhoods */}
      <h2 style={{ margin: '24px 0 0', fontSize: 18, fontWeight: 800, color: '#111827', letterSpacing: '-0.01em' }}>Neighbourhoods</h2>
      <div style={{ marginTop: 4, fontSize: 12.5, color: '#6B7280' }}>Transit times shown to Grand Canal Dock.</div>
      <div
        style={{
          marginTop: 14,
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(270px, 1fr))',
          gap: 12,
        }}
      >
        {NEIGHBOURHOODS.map((n) => (
          <div key={n.name} style={{ background: '#F9FAFB', border: '1px solid #E5E7EB', borderRadius: 10, padding: '14px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#111827' }}>{n.name}</div>
              <PriceBand band={n.price} />
            </div>
            <div style={{ marginTop: 4, fontSize: 13, color: '#4B5563', lineHeight: 1.5 }}>{n.character}</div>
            <div style={{ marginTop: 8, display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontWeight: 600, color: '#374151', background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 999, padding: '3px 10px' }}>
              🚉 {n.transit}
            </div>
          </div>
        ))}
      </div>

      {/* Services grid */}
      <h2 style={{ margin: '28px 0 0', fontSize: 18, fontWeight: 800, color: '#111827', letterSpacing: '-0.01em' }}>Services</h2>
      <div
        style={{
          marginTop: 14,
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: 12,
        }}
      >
        {SERVICES.map((s) => (
          <div key={s.category} style={{ background: '#FFFFFF', border: '1px solid #E5E7EB', borderRadius: 10, padding: '14px 16px', display: 'flex', flexDirection: 'column' }}>
            <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: '0.07em', textTransform: 'uppercase', color: '#6B7280' }}>{s.category}</div>
            <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
              {s.lines.map((line) => (
                <div key={line.heading} style={{ fontSize: 13, lineHeight: 1.5 }}>
                  <span style={{ fontWeight: 700, color: '#111827' }}>{line.heading}:</span>{' '}
                  <span style={{ color: '#374151' }}>{line.value}</span>
                </div>
              ))}
            </div>
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px dashed #E5E7EB', fontSize: 12.5, color: '#6B7280', lineHeight: 1.55 }}>{s.note}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Root ────────────────────────────────────────────────────────────

const TABS: { id: TabId; label: string }[] = [
  { id: 'timeline', label: 'Timeline & SLA' },
  { id: 'compliance', label: 'Compliance flags' },
  { id: 'dublin', label: 'Dublin: living + services' },
];

export default function ESIECaseJourneyPrototype() {
  const [tab, setTab] = useState<TabId>('timeline');

  return (
    <div style={{ height: '100%', overflow: 'auto', background: '#FFFFFF', fontFamily: FONT, color: '#111827' }}>
      <div style={{ maxWidth: 920, margin: '0 auto', padding: '24px 20px 72px' }}>
        {/* App header */}
        <div style={{ paddingBottom: 14, borderBottom: '2px solid #111827' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: '4px 16px' }}>
            <div>
              <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.02em' }}>ReloPass</div>
              <div style={{ fontSize: 13, color: '#6B7280' }}>ES_IE Case Journey Prototype</div>
            </div>
            <div style={{ fontSize: 12, color: '#6B7280' }}>
              Ana García · Venezuelan national · Long-term legal resident, Madrid · Relocating to Dublin (multinational tech team) · Relocation agent engaged
            </div>
          </div>
          <div style={{ marginTop: 8, display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: '#9CA3AF' }}>
            <Info size={13} /> Throwaway UX prototype — all data hardcoded and fictional. Not legal, tax, or immigration advice.
          </div>
        </div>

        {/* Tab bar */}
        <div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', gap: 6, borderBottom: '1px solid #E5E7EB', paddingBottom: 0 }}>
          {TABS.map((t) => {
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                style={{
                  appearance: 'none',
                  border: 'none',
                  borderBottom: active ? '3px solid #111827' : '3px solid transparent',
                  background: 'transparent',
                  padding: '10px 14px',
                  fontSize: 14,
                  fontWeight: active ? 800 : 600,
                  color: active ? '#111827' : '#6B7280',
                  cursor: 'pointer',
                  fontFamily: FONT,
                }}
              >
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Active tab */}
        <div style={{ marginTop: 22 }}>
          {tab === 'timeline' && <TimelineTab />}
          {tab === 'compliance' && <ComplianceTab />}
          {tab === 'dublin' && <DublinTab />}
        </div>
      </div>
    </div>
  );
}
