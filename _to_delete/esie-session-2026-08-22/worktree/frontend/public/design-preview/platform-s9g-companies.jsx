// platform-s9g-companies.jsx — Admin Companies Overview
// High-fidelity mock of the spec'd page. Overrides the s9-admin stub.
(function() {
const { useState, useMemo, useRef, useEffect } = React;
const I = window.PlatformIcon;

// ── Mock data (shape matches AdminCompany from rolec/types.ts) ────────
const COMPANIES = [
  {
    id: 'co_aurora',  name: 'Aurora Energy',           legal_name: 'Aurora Energy AS',
    country: 'France',      size_band: '200–1000',  industry: 'Energy',
    status: 'active', plan_tier: 'premium',
    hr_users_count: 5,  hr_seat_limit: 8,
    employee_count: 142, employee_seat_limit: 500,
    assignments_count: 12,
    primary_contact_name: 'Helena Müller', hr_contact: 'helena.muller@aurora-energy.com',
    support_email: 'mobility@aurora-energy.com', phone: '+33 1 4502 8821',
    website: 'aurora-energy.com', hq_city: 'Paris',
    created_at: '2024-09-12', updated_at: '2026-05-14',
    address: '12 Avenue de Friedland, 75008 Paris, France',
    tone: 'a',
  },
  {
    id: 'co_helix',   name: 'Helix Bio',               legal_name: 'Helix Bio Holdings PLC',
    country: 'Germany',     size_band: '1000+',     industry: 'Pharma / Biotech',
    status: 'active', plan_tier: 'premium',
    hr_users_count: 8,  hr_seat_limit: 12,
    employee_count: 387, employee_seat_limit: 1500,
    assignments_count: 28,
    primary_contact_name: 'Dr. Stefan Wolff', hr_contact: 'stefan.wolff@helixbio.de',
    support_email: 'people@helixbio.de', phone: '+49 89 5400 1100',
    website: 'helixbio.de', hq_city: 'Munich',
    created_at: '2024-03-04', updated_at: '2026-05-12',
    address: 'Bavariaring 17, 80336 München, Germany',
    tone: 'b',
  },
  {
    id: 'co_northpeak', name: 'Northpeak Capital',     legal_name: 'Northpeak Capital LLP',
    country: 'United Kingdom', size_band: '200–1000', industry: 'Finance',
    status: 'active', plan_tier: 'medium',
    hr_users_count: 4,  hr_seat_limit: 6,
    employee_count: 78,  employee_seat_limit: 300,
    assignments_count: 6,
    primary_contact_name: 'James Holt', hr_contact: 'j.holt@northpeak.co.uk',
    support_email: 'ops@northpeak.co.uk', phone: '+44 20 7946 0123',
    website: 'northpeak.co.uk', hq_city: 'London',
    created_at: '2024-11-18', updated_at: '2026-04-22',
    address: '88 Wood Street, London EC2V 7RS, United Kingdom',
    tone: 'c',
  },
  {
    id: 'co_meridian', name: 'Meridian Logistics',     legal_name: 'Meridian Logistics B.V.',
    country: 'Netherlands', size_band: '200–1000',  industry: 'Logistics',
    status: 'active', plan_tier: 'medium',
    hr_users_count: 3,  hr_seat_limit: 5,
    employee_count: 95,  employee_seat_limit: 250,
    assignments_count: 9,
    primary_contact_name: 'Olivia Janssen', hr_contact: 'olivia@meridian-log.nl',
    support_email: 'hr@meridian-log.nl', phone: '+31 20 240 5566',
    website: 'meridian-log.nl', hq_city: 'Rotterdam',
    created_at: '2025-01-22', updated_at: '2026-03-18',
    address: 'Wilhelminakade 308, 3072 AR Rotterdam',
    tone: 'd',
  },
  {
    id: 'co_cobalt', name: 'Cobalt Robotics',          legal_name: 'Cobalt Robotics Inc.',
    country: 'United States', size_band: '50–200',  industry: 'Robotics',
    status: 'active', plan_tier: 'premium',
    hr_users_count: 2,  hr_seat_limit: 4,
    employee_count: 47,  employee_seat_limit: 100,
    assignments_count: 4,
    primary_contact_name: 'Sarah Kim', hr_contact: 'sarah@cobaltrobotics.com',
    support_email: 'people@cobaltrobotics.com', phone: '+1 415 555 0188',
    website: 'cobaltrobotics.com', hq_city: 'San Francisco',
    created_at: '2025-02-10', updated_at: '2026-05-01',
    address: '1455 Market St, San Francisco, CA 94103',
    tone: 'f',
  },
  {
    id: 'co_verdant', name: 'Verdant AgriTech',        legal_name: 'Verdant AgriTech S.r.l.',
    country: 'Italy',       size_band: '50–200',   industry: 'AgriTech',
    status: 'active', plan_tier: 'low',
    hr_users_count: 1,  hr_seat_limit: 3,
    employee_count: 12,  employee_seat_limit: 50,
    assignments_count: 1,
    primary_contact_name: 'Elena Morelli', hr_contact: 'elena.morelli@verdant-agri.it',
    support_email: null, phone: '+39 06 4555 9912',
    website: 'verdant-agri.it', hq_city: 'Bologna',
    created_at: '2025-08-04', updated_at: '2026-02-09',
    address: 'Via San Vitale 12, 40125 Bologna BO',
    tone: 'b',
  },
  {
    id: 'co_nimbus', name: 'Nimbus Cloud',             legal_name: 'Nimbus Cloud Ltd.',
    country: 'Ireland',     size_band: '200–1000',  industry: 'SaaS',
    status: 'inactive', plan_tier: 'medium',
    hr_users_count: 0,  hr_seat_limit: 5,
    employee_count: 0,   employee_seat_limit: 300,
    assignments_count: 0,
    primary_contact_name: 'Aoife Brennan', hr_contact: 'aoife@nimbuscloud.ie',
    support_email: 'billing@nimbuscloud.ie', phone: '+353 1 224 8800',
    website: 'nimbuscloud.ie', hq_city: 'Dublin',
    created_at: '2024-10-30', updated_at: '2026-04-30',
    address: 'IFSC, North Wall Quay, Dublin 1',
    tone: 'c',
  },
  {
    id: 'co_sable', name: 'Sable Maritime',            legal_name: 'Sable Maritime ASA',
    country: 'Norway',      size_band: '200–1000',  industry: 'Shipping',
    status: 'archived', plan_tier: 'low',
    hr_users_count: 0,  hr_seat_limit: 3,
    employee_count: 0,   employee_seat_limit: 100,
    assignments_count: 0,
    primary_contact_name: 'Magnus Berg', hr_contact: null,
    support_email: null, phone: null,
    website: 'sable-maritime.no', hq_city: 'Bergen',
    created_at: '2023-06-19', updated_at: '2025-09-04',
    address: 'Bryggen 41, 5003 Bergen',
    tone: 'e',
  },
  {
    id: 'co_aether', name: 'Aether Pharmaceuticals',   legal_name: 'Aether Pharma AG',
    country: 'Switzerland', size_band: '1000+',     industry: 'Pharma',
    status: 'active', plan_tier: 'premium',
    hr_users_count: 6,  hr_seat_limit: 10,
    employee_count: 246, employee_seat_limit: 800,
    assignments_count: 18,
    primary_contact_name: 'Dr. Anya Petrov', hr_contact: 'a.petrov@aether-pharma.ch',
    support_email: 'mobility@aether-pharma.ch', phone: '+41 44 555 0040',
    website: 'aether-pharma.ch', hq_city: 'Zurich',
    created_at: '2024-04-22', updated_at: '2026-05-09',
    address: 'Bahnhofstrasse 45, 8001 Zürich',
    tone: 'a',
  },
  {
    id: 'co_lattice', name: 'Lattice Networks',        legal_name: 'Lattice Networks Pte Ltd',
    country: 'Singapore',   size_band: '200–1000',  industry: 'Telecom',
    status: 'active', plan_tier: 'medium',
    hr_users_count: 3,  hr_seat_limit: 5,
    employee_count: 64,  employee_seat_limit: 300,
    assignments_count: 7,
    primary_contact_name: 'Saanvi Mehra', hr_contact: 'saanvi@lattice.sg',
    support_email: 'hr@lattice.sg', phone: '+65 6920 4100',
    website: 'lattice.sg', hq_city: 'Singapore',
    created_at: '2025-03-15', updated_at: '2026-04-28',
    address: '8 Marina Boulevard, Singapore 018981',
    tone: 'b',
  },
  {
    id: 'co_quill', name: 'Quill & Co',                legal_name: 'Quill et Compagnie SARL',
    country: 'France',      size_band: '10–50',    industry: 'Media',
    status: 'active', plan_tier: 'low',
    hr_users_count: 1,  hr_seat_limit: 2,
    employee_count: 8,   employee_seat_limit: 30,
    assignments_count: 0,
    primary_contact_name: 'Margaux Lefèvre', hr_contact: 'margaux@quill.fr',
    support_email: 'admin@quill.fr', phone: '+33 1 4290 1124',
    website: 'quill.fr', hq_city: 'Lyon',
    created_at: '2025-09-08', updated_at: '2026-01-14',
    address: '14 Rue de la République, 69002 Lyon',
    tone: 'd',
    missing_from_registry: true,
  },
  {
    id: 'co_solstice', name: 'Solstice Foods',         legal_name: 'Solstice Alimentaria S.L.',
    country: 'Spain',       size_band: '50–200',   industry: 'Food & Beverage',
    status: 'active', plan_tier: 'low',
    hr_users_count: 2,  hr_seat_limit: 3,
    employee_count: 22,  employee_seat_limit: 80,
    assignments_count: 2,
    primary_contact_name: 'Carlos Ruiz', hr_contact: 'c.ruiz@solstice-foods.es',
    support_email: 'rrhh@solstice-foods.es', phone: '+34 91 555 0220',
    website: 'solstice-foods.es', hq_city: 'Madrid',
    created_at: '2025-05-19', updated_at: '2026-03-30',
    address: 'Calle de Serrano 88, 28006 Madrid',
    tone: 'f',
  },
  {
    id: 'co_tessera', name: 'Tessera Design',          legal_name: 'Tessera Design Inc.',
    country: 'Canada',      size_band: '50–200',   industry: 'Design Agency',
    status: 'active', plan_tier: 'medium',
    hr_users_count: 2,  hr_seat_limit: 4,
    employee_count: 35,  employee_seat_limit: 100,
    assignments_count: 3,
    primary_contact_name: 'Tara Singh', hr_contact: 'tara@tessera.studio',
    support_email: null, phone: '+1 416 555 7702',
    website: 'tessera.studio', hq_city: 'Toronto',
    created_at: '2025-06-27', updated_at: '2026-05-02',
    address: '64 Bathurst St, Toronto, ON M5V 0E5',
    tone: 'c',
  },
  {
    id: 'co_atlas', name: 'Atlas Manufacturing',       legal_name: 'Atlas Manufacturing K.K.',
    country: 'Japan',       size_band: '1000+',     industry: 'Manufacturing',
    status: 'active', plan_tier: 'premium',
    hr_users_count: 7,  hr_seat_limit: 10,
    employee_count: 412, employee_seat_limit: 2000,
    assignments_count: 22,
    primary_contact_name: 'Yuki Tanaka', hr_contact: 'y.tanaka@atlas-mfg.jp',
    support_email: 'mobility@atlas-mfg.jp', phone: '+81 3 5577 1180',
    website: 'atlas-mfg.jp', hq_city: 'Tokyo',
    created_at: '2024-05-30', updated_at: '2026-05-15',
    address: '3-2-1 Marunouchi, Chiyoda-ku, Tokyo',
    tone: 'e',
  },
  {
    id: 'co_bramble', name: 'Bramble Labs',            legal_name: 'Bramble Labs LLC',
    country: 'United States', size_band: '10–50',  industry: 'Biotech',
    status: 'active', plan_tier: 'low',
    hr_users_count: 1,  hr_seat_limit: 2,
    employee_count: 6,   employee_seat_limit: 30,
    assignments_count: 1,
    primary_contact_name: 'Camille Fontaine', hr_contact: 'cam@bramble-labs.co',
    support_email: null, phone: '+1 617 555 0309',
    website: 'bramble-labs.co', hq_city: 'Cambridge, MA',
    created_at: '2025-10-12', updated_at: '2026-04-18',
    address: '245 Main St, Cambridge, MA 02142',
    tone: 'a',
  },
  {
    id: 'co_polar', name: 'Polar Robotics',            legal_name: 'Polar Robotics Oy',
    country: 'Finland',     size_band: '50–200',   industry: 'Robotics',
    status: 'active', plan_tier: 'medium',
    hr_users_count: 2,  hr_seat_limit: 4,
    employee_count: 28,  employee_seat_limit: 100,
    assignments_count: 3,
    primary_contact_name: 'Linnea Korpela', hr_contact: 'linnea@polar-robotics.fi',
    support_email: 'hr@polar-robotics.fi', phone: '+358 9 555 4400',
    website: 'polar-robotics.fi', hq_city: 'Helsinki',
    created_at: '2025-04-08', updated_at: '2026-03-12',
    address: 'Mannerheimintie 22, 00100 Helsinki',
    tone: 'b',
    missing_from_companies_table: 2,
  },
  {
    id: 'co_vector', name: 'Vector AI',                legal_name: 'Vector AI Corp.',
    country: 'United States', size_band: '200–1000', industry: 'AI / ML',
    status: 'active', plan_tier: 'premium',
    hr_users_count: 5,  hr_seat_limit: 8,
    employee_count: 134, employee_seat_limit: 400,
    assignments_count: 14,
    primary_contact_name: 'Marcus Webb', hr_contact: 'marcus@vector-ai.com',
    support_email: 'people@vector-ai.com', phone: '+1 650 555 1122',
    website: 'vector-ai.com', hq_city: 'Palo Alto',
    created_at: '2024-12-04', updated_at: '2026-05-13',
    address: '500 Hamilton Ave, Palo Alto, CA 94301',
    tone: 'c',
  },
  {
    id: 'co_hyper', name: 'Hyper Couriers',            legal_name: 'Hyper Couriers Pvt Ltd',
    country: 'India',       size_band: '50–200',   industry: 'Logistics',
    status: 'inactive', plan_tier: 'low',
    hr_users_count: 0,  hr_seat_limit: 3,
    employee_count: 0,   employee_seat_limit: 100,
    assignments_count: 0,
    primary_contact_name: 'Raj Desai', hr_contact: null,
    support_email: null, phone: null,
    website: 'hypercouriers.in', hq_city: 'Mumbai',
    created_at: '2025-07-22', updated_at: '2026-02-04',
    address: 'BKC, Bandra East, Mumbai 400051',
    tone: 'd',
  },
];

// Detail packets (used when a row is "expanded" into the side panel)
const DETAILS = {
  co_aurora: {
    hr_users: [
      { id: 'hr1', name: 'Helena Müller',     email: 'helena.muller@aurora-energy.com', status: 'active', created_at: '2024-09-12' },
      { id: 'hr2', name: 'Lukas Schreiber',  email: 'lukas@aurora-energy.com',          status: 'active', created_at: '2025-01-08' },
      { id: 'hr3', name: 'Camille Brunet',   email: 'camille@aurora-energy.com',        status: 'active', created_at: '2025-04-19' },
      { id: 'hr4', name: 'Tomás Weber',      email: 'tomas@aurora-energy.com',          status: 'active', created_at: '2025-06-02' },
      { id: 'hr5', name: 'Sofie Andersen',   email: 'sofie@aurora-energy.com',          status: 'invited', created_at: '2026-05-10' },
    ],
    employees: [
      { id: 'e1', name: 'Marc Bouchard',  email: 'marc@aurora-energy.com',  band: 'Senior Eng',     assignment_type: 'Permanent', status: 'in-progress', created_at: '2025-06-10' },
      { id: 'e2', name: 'Priya Nair',     email: 'priya@aurora-energy.com', band: 'PM',             assignment_type: 'Permanent', status: 'discovery',  created_at: '2025-09-04' },
      { id: 'e3', name: 'Aïcha Idrissi',  email: 'aicha@aurora-energy.com', band: 'Senior Designer',assignment_type: 'Permanent', status: 'roadmap',     created_at: '2025-11-22' },
      { id: 'e4', name: 'Yuki Tanaka',    email: 'yuki@aurora-energy.com',  band: 'Researcher',     assignment_type: 'Contract',  status: 'at-risk',     created_at: '2026-01-19' },
      { id: 'e5', name: 'Elena Morelli',  email: 'elena@aurora-energy.com', band: 'Senior Counsel', assignment_type: 'Permanent', status: 'discovery',  created_at: '2026-03-08' },
    ],
    assignments: [
      { id: 'a1', employee: 'Marc Bouchard', destination: 'FR → NO', type: 'Skilled Worker', status: 'visa submitted', created_at: '2025-06-10' },
      { id: 'a2', employee: 'Priya Nair',    destination: 'IN → DE', type: 'EU Blue Card',  status: 'discovery',       created_at: '2025-09-04' },
      { id: 'a3', employee: 'Yuki Tanaka',   destination: 'JP → DE', type: 'EU Blue Card',  status: 'blocked',         created_at: '2026-01-19' },
      { id: 'a4', employee: 'Tomás Weber',   destination: 'BR → NL', type: 'HSM Permit',    status: 'housing',         created_at: '2025-12-02' },
    ],
    policies: [
      { id: 'p1', title: 'Tier 2 — Director-level relocation', version_number: 4, status: 'published', published_at: '2026-02-12' },
      { id: 'p2', title: 'Tier 1 — Engineer permanent transfer', version_number: 7, status: 'published', published_at: '2025-11-20' },
      { id: 'p3', title: 'School allowance exception policy',     version_number: 2, status: 'review_required', published_at: null },
      { id: 'p4', title: 'Family pet relocation addendum',         version_number: 1, status: 'draft', published_at: null },
    ],
  },
  co_helix: {
    hr_users: [
      { id: 'hr1', name: 'Dr. Stefan Wolff', email: 'stefan.wolff@helixbio.de', status: 'active', created_at: '2024-03-04' },
      { id: 'hr2', name: 'Anna Schreiber',   email: 'a.schreiber@helixbio.de',  status: 'active', created_at: '2024-05-12' },
      { id: 'hr3', name: 'Mathilde Roux',    email: 'm.roux@helixbio.de',       status: 'active', created_at: '2024-09-21' },
    ],
    employees: [],
    assignments: [
      { id: 'a1', employee: 'Sarah Becker',    destination: 'DE → US', type: 'H-1B',          status: 'visa-prep', created_at: '2026-01-04' },
      { id: 'a2', employee: 'Hiroshi Yamada',  destination: 'JP → DE', type: 'EU Blue Card',  status: 'in-flight', created_at: '2026-02-18' },
      { id: 'a3', employee: 'Mariana Souza',   destination: 'BR → CH', type: 'L-residence',   status: 'housing',   created_at: '2026-03-10' },
    ],
    policies: [
      { id: 'p1', title: 'Global mobility framework — Helix Bio', version_number: 12, status: 'published', published_at: '2026-03-01' },
      { id: 'p2', title: 'Researcher transfer policy',             version_number: 5,  status: 'reviewed', published_at: null },
    ],
  },
};

// Generic fallback detail (gives every company a believable people/cases payload)
function fallbackDetail(co) {
  const seed = co.id.length;
  return {
    hr_users: Array.from({ length: co.hr_users_count }).map((_, i) => ({
      id: `hr-${co.id}-${i}`,
      name: ['Alex','Jordan','Sam','Riley','Casey','Morgan','Avery','Skyler'][i % 8] + ' ' +
            ['Lin','Park','Chen','Garcia','Patel','Smith','Cohen','Aydın'][(i+seed) % 8],
      email: `hr${i+1}@${co.website || 'company.com'}`,
      status: i === co.hr_users_count - 1 && co.hr_users_count > 1 ? 'invited' : 'active',
      created_at: '2025-0' + (((i + 1) % 9) + 1) + '-15',
    })),
    employees: Array.from({ length: Math.min(co.employee_count, 8) }).map((_, i) => ({
      id: `e-${co.id}-${i}`,
      name: ['Marc','Priya','Aïcha','Yuki','Elena','Tomás','James','Saanvi'][i % 8] + ' ' +
            ['Bouchard','Nair','Idrissi','Tanaka','Morelli','Weber','Holt','Mehra'][i % 8],
      email: `emp${i+1}@${co.website || 'company.com'}`,
      band: ['Engineer','Senior Eng','PM','Designer','Researcher','Director'][i % 6],
      assignment_type: i % 3 === 2 ? 'Contract' : 'Permanent',
      status: ['discovery','roadmap','in-progress','at-risk','done'][i % 5],
      created_at: '2025-0' + (((i + 2) % 9) + 1) + '-22',
    })),
    assignments: Array.from({ length: Math.min(co.assignments_count, 6) }).map((_, i) => ({
      id: `a-${co.id}-${i}`,
      employee: ['Marc Bouchard','Priya Nair','Aïcha Idrissi','Yuki Tanaka','Elena Morelli','Tomás Weber'][i % 6],
      destination: ['FR → NO','IN → DE','ES → CA','JP → DE','IT → GB','BR → NL'][i % 6],
      type: ['Skilled Worker','EU Blue Card','Express Entry','HSM Permit','Highly Skilled','O-1'][i % 6],
      status: ['visa-submitted','discovery','roadmap','housing','dossier','done'][i % 6],
      created_at: '2026-0' + (((i + 1) % 5) + 1) + '-08',
    })),
    policies: [
      { id: 'p1', title: 'Standard relocation policy', version_number: 3, status: co.plan_tier === 'premium' ? 'published' : 'reviewed', published_at: co.plan_tier === 'premium' ? '2026-03-01' : null },
      { id: 'p2', title: 'Family relocation addendum',  version_number: 1, status: co.assignments_count > 0 ? 'draft' : 'no_policy', published_at: null },
    ],
  };
}

// ── Helpers ──────────────────────────────────────────────────────────
function relativeDate(iso) {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return 'Today';
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

function logoInitials(name) {
  return name.split(/\s|&/).filter(Boolean).slice(0, 2).map(s => s[0]).join('').toUpperCase();
}

const PLAN_TONE   = { premium: 'success', medium: 'warning', low: 'neutral' };
const STATUS_TONE = { active: 'success',  inactive: 'warning', archived: 'neutral' };
const POLICY_TONE = { published: 'success', reviewed: 'accent', review_required: 'warning', draft: 'neutral', no_policy: 'danger' };
const POLICY_LABEL = { published: 'Published', reviewed: 'Reviewed', review_required: 'Review required', draft: 'Draft', no_policy: 'No policy' };

// ── KPI Card ─────────────────────────────────────────────────────────
function KPI({ k, v, s, ico, tone }) {
  return (
    <div className={`cos-kpi ${tone || ''}`}>
      <div className="ic"><I n={ico} s={11}/></div>
      <div className="k">{k}</div>
      <div className="v">{v}</div>
      <div className="s">{s}</div>
    </div>
  );
}

// ── Filter Bar ───────────────────────────────────────────────────────
function FilterSelect({ value, onChange, options, label }) {
  return (
    <div className={`cos-select${value ? ' active' : ''}`}>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{label}</option>
        {options.map(o =>
          typeof o === 'string'
            ? <option key={o} value={o}>{o}</option>
            : <option key={o.value} value={o.value}>{o.label}</option>
        )}
      </select>
    </div>
  );
}

// ── Detail panel ─────────────────────────────────────────────────────
function CompanyDetailPanel({ company, detail, loading, onClose }) {
  const [tab, setTab] = useState('overview');
  const [editing, setEditing] = useState(false);

  // Reset edit state when switching companies
  useEffect(() => { setEditing(false); setTab('overview'); }, [company?.id]);

  if (!company) return null;
  const hrPct  = company.hr_seat_limit ? Math.min(100, Math.round(company.hr_users_count / company.hr_seat_limit * 100)) : 0;
  const empPct = company.employee_seat_limit ? Math.min(100, Math.round(company.employee_count / company.employee_seat_limit * 100)) : 0;
  const hasIssue = company.missing_from_registry || (company.missing_from_companies_table || 0) > 0;

  return (
    <>
      <div className="cos-panel-backdrop" onClick={onClose}/>
      <aside className="cos-panel" role="dialog" aria-label={`${company.name} detail`}>
        <div className="cos-panel-hd">
          <div className={`cos-co-logo logo-lg tone-${company.tone || 'a'}`}>{logoInitials(company.name)}</div>
          <div className="meta">
            <div className="nm">{company.name}</div>
            <div className="legal">{company.legal_name || company.name}</div>
            <div className="badges">
              <span className={`cos-badge dot ${STATUS_TONE[company.status]}`}>{company.status}</span>
              <span className={`cos-badge ${PLAN_TONE[company.plan_tier]}`}>{company.plan_tier}</span>
              <span className="cos-badge neutral">{company.industry}</span>
            </div>
          </div>
          <button className="close" onClick={onClose}><I n="x" s={14}/></button>
        </div>

        <div className="cos-tabs">
          <div className={`cos-tab${tab === 'overview' ? ' active' : ''}`} onClick={() => setTab('overview')}>
            Overview
          </div>
          <div className={`cos-tab${tab === 'people' ? ' active' : ''}`} onClick={() => setTab('people')}>
            People <span className="ct">{company.hr_users_count + company.employee_count}</span>
          </div>
          <div className={`cos-tab${tab === 'cases' ? ' active' : ''}`} onClick={() => setTab('cases')}>
            Cases <span className="ct">{company.assignments_count}</span>
          </div>
          <div className={`cos-tab${tab === 'policies' ? ' active' : ''}`} onClick={() => setTab('policies')}>
            Policies <span className="ct">{detail?.policies?.length ?? '—'}</span>
          </div>
        </div>

        {loading || !detail ? (
          <div className="cos-panel-loading">
            <div className="spin"/>
            <div>Loading detail…</div>
          </div>
        ) : (
          <div className="cos-panel-body">
            {tab === 'overview' && (
              <>
                {hasIssue && (
                  <div className="cos-warn">
                    <I n="alert" s={16} className="ico"/>
                    <div>
                      <strong>Data quality flags.</strong>
                      <div style={{ marginTop: 4 }}>
                        {company.missing_from_registry && <div>· Company is missing from external registry — refresh feed.</div>}
                        {(company.missing_from_companies_table || 0) > 0 &&
                          <div>· {company.missing_from_companies_table} orphan profile{company.missing_from_companies_table > 1 ? 's' : ''} referencing this tenant.</div>}
                      </div>
                    </div>
                  </div>
                )}

                {editing && (
                  <div className="cos-edit-bar">
                    <I n="edit" s={13}/>
                    Editing company. Changes save via PATCH /api/admin/companies/{company.id}.
                    <div className="spc"/>
                    <button className="cancel" onClick={() => setEditing(false)}>Cancel</button>
                    <button className="save" onClick={() => setEditing(false)}>Save changes</button>
                  </div>
                )}

                <div className="cos-section-hd">
                  Identity
                  <span className="right" onClick={() => setEditing(e => !e)}>
                    <I n="edit" s={11} style={{ verticalAlign: -1 }}/> {editing ? 'Done' : 'Edit'}
                  </span>
                </div>
                <div className="cos-field-grid">
                  <div className="cos-field"><div className="k">Display name</div><div className="v">{company.name}</div></div>
                  <div className="cos-field"><div className="k">Legal name</div><div className="v">{company.legal_name || <span className="muted">—</span>}</div></div>
                  <div className="cos-field"><div className="k">Industry</div><div className="v">{company.industry}</div></div>
                  <div className="cos-field"><div className="k">Size band</div><div className="v">{company.size_band || <span className="muted">—</span>}</div></div>
                  <div className="cos-field"><div className="k">HQ city</div><div className="v">{company.hq_city}</div></div>
                  <div className="cos-field"><div className="k">Country</div><div className="v">{company.country}</div></div>
                  <div className="cos-field full"><div className="k">Address</div><div className="v">{company.address || <span className="muted">—</span>}</div></div>
                  <div className="cos-field"><div className="k">Website</div><div className="v link">{company.website || <span className="muted">—</span>}</div></div>
                  <div className="cos-field"><div className="k">Phone</div><div className="v">{company.phone || <span className="muted">—</span>}</div></div>
                </div>

                <div className="cos-section-hd">Plan &amp; seats</div>
                <div className="cos-field-grid">
                  <div className="cos-field">
                    <div className="k">Status</div>
                    <div className="v"><span className={`cos-badge dot ${STATUS_TONE[company.status]}`}>{company.status}</span></div>
                  </div>
                  <div className="cos-field">
                    <div className="k">Plan tier</div>
                    <div className="v"><span className={`cos-badge ${PLAN_TONE[company.plan_tier]}`}>{company.plan_tier}</span></div>
                  </div>
                  <div className="cos-field">
                    <div className="k">HR seats</div>
                    <div className="v">
                      <div className={`cos-seat ${hrPct > 90 ? 'full' : hrPct > 75 ? 'near' : ''}`}>
                        <div className="nums">{company.hr_users_count}{company.hr_seat_limit ? <><span className="of">/ {company.hr_seat_limit}</span></> : <span className="none">/ no limit</span>}</div>
                        {company.hr_seat_limit && <div className="bar"><div style={{ width: hrPct + '%' }}/></div>}
                      </div>
                    </div>
                  </div>
                  <div className="cos-field">
                    <div className="k">Employee seats</div>
                    <div className="v">
                      <div className={`cos-seat ${empPct > 90 ? 'full' : empPct > 75 ? 'near' : ''}`}>
                        <div className="nums">{company.employee_count}{company.employee_seat_limit ? <><span className="of">/ {company.employee_seat_limit}</span></> : <span className="none">/ no limit</span>}</div>
                        {company.employee_seat_limit && <div className="bar"><div style={{ width: empPct + '%' }}/></div>}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="cos-section-hd">Primary contact</div>
                <div className="cos-field-grid">
                  <div className="cos-field"><div className="k">Name</div><div className="v">{company.primary_contact_name || <span className="muted">—</span>}</div></div>
                  <div className="cos-field"><div className="k">HR contact</div><div className="v link">{company.hr_contact || <span className="muted">—</span>}</div></div>
                  <div className="cos-field full"><div className="k">Support email</div><div className="v link">{company.support_email || <span className="muted">—</span>}</div></div>
                </div>

                <div className="cos-section-hd">Timeline</div>
                <div className="cos-field-grid">
                  <div className="cos-field"><div className="k">Created</div><div className="v">{relativeDate(company.created_at)} <span style={{ color:'var(--text-3)', fontWeight:400 }}>· {company.created_at}</span></div></div>
                  <div className="cos-field"><div className="k">Updated</div><div className="v">{relativeDate(company.updated_at)} <span style={{ color:'var(--text-3)', fontWeight:400 }}>· {company.updated_at || '—'}</span></div></div>
                </div>
              </>
            )}

            {tab === 'people' && (
              <>
                <div className="cos-section-hd">
                  HR users <span className="ct">({detail.hr_users.length})</span>
                  <span className="right">+ Invite HR</span>
                </div>
                {detail.hr_users.length === 0 ? (
                  <div style={{ padding:'18px 4px', color:'var(--text-3)', fontSize:12.5, fontStyle:'italic' }}>No HR users provisioned for this tenant.</div>
                ) : (
                  <div className="cos-mini-tbl-wrap" style={{ marginBottom: 20 }}>
                    <table className="cos-mini-tbl">
                      <thead><tr><th>Name</th><th>Email</th><th>Status</th><th>Created</th></tr></thead>
                      <tbody>
                        {detail.hr_users.map(u => (
                          <tr key={u.id}>
                            <td><div className="nm"><div className="avatar">{logoInitials(u.name)}</div>{u.name}</div></td>
                            <td className="em">{u.email}</td>
                            <td><span className={`cos-badge dot ${u.status === 'active' ? 'success' : u.status === 'invited' ? 'accent' : 'neutral'}`}>{u.status}</span></td>
                            <td className="em">{relativeDate(u.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <div className="cos-section-hd">
                  Employees <span className="ct">({company.employee_count})</span>
                  <span className="right">View all →</span>
                </div>
                {detail.employees.length === 0 ? (
                  <div style={{ padding:'18px 4px', color:'var(--text-3)', fontSize:12.5, fontStyle:'italic' }}>No employees onboarded yet.</div>
                ) : (
                  <>
                    <div className="cos-mini-tbl-wrap">
                      <table className="cos-mini-tbl">
                        <thead><tr><th>Name</th><th>Email</th><th>Band</th><th>Type</th><th>Status</th></tr></thead>
                        <tbody>
                          {detail.employees.map(e => (
                            <tr key={e.id}>
                              <td><div className="nm"><div className="avatar">{logoInitials(e.name)}</div>{e.name}</div></td>
                              <td className="em">{e.email}</td>
                              <td className="em">{e.band}</td>
                              <td className="em">{e.assignment_type}</td>
                              <td><span className={`cos-badge ${e.status === 'at-risk' ? 'warning' : e.status === 'done' ? 'success' : 'neutral'}`}>{e.status}</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {company.employee_count > detail.employees.length && (
                      <div style={{ textAlign:'center', padding:'10px 0 0', color:'var(--text-3)', fontSize: 11.5 }}>
                        Showing {detail.employees.length} of {company.employee_count} · sample only
                      </div>
                    )}
                  </>
                )}
              </>
            )}

            {tab === 'cases' && (
              <>
                <div className="cos-section-hd">
                  Active &amp; recent cases <span className="ct">({company.assignments_count})</span>
                </div>
                {detail.assignments.length === 0 ? (
                  <div style={{ padding:'18px 4px', color:'var(--text-3)', fontSize:12.5, fontStyle:'italic' }}>No relocation cases for this tenant.</div>
                ) : (
                  <div className="cos-mini-tbl-wrap">
                    <table className="cos-mini-tbl">
                      <thead><tr><th>Employee</th><th>Destination</th><th>Type</th><th>Status</th><th>Created</th></tr></thead>
                      <tbody>
                        {detail.assignments.map(a => (
                          <tr key={a.id}>
                            <td><div className="nm">{a.employee}</div></td>
                            <td className="em" style={{ fontFamily:'var(--mono)', fontSize:11 }}>{a.destination}</td>
                            <td className="em">{a.type}</td>
                            <td><span className={`cos-badge ${a.status === 'blocked' || a.status === 'at-risk' ? 'warning' : a.status === 'done' ? 'success' : 'neutral'}`}>{a.status}</span></td>
                            <td className="em">{relativeDate(a.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}

            {tab === 'policies' && (
              <>
                <div className="cos-section-hd">
                  Policies <span className="ct">({detail.policies.length})</span>
                  <span className="right">+ New policy</span>
                </div>
                {detail.policies.length === 0 ? (
                  <div style={{ padding:'18px 4px', color:'var(--text-3)', fontSize:12.5, fontStyle:'italic' }}>No policies on file. Tenant runs on platform defaults.</div>
                ) : (
                  <div className="cos-mini-tbl-wrap">
                    <table className="cos-mini-tbl">
                      <thead><tr><th>Title</th><th>Version</th><th>Status</th><th>Published</th></tr></thead>
                      <tbody>
                        {detail.policies.map(p => (
                          <tr key={p.id}>
                            <td><div className="nm">{p.title}</div></td>
                            <td className="em" style={{ fontFamily:'var(--mono)', fontSize:11 }}>v{p.version_number}</td>
                            <td><span className={`cos-badge dot ${POLICY_TONE[p.status]}`}>{POLICY_LABEL[p.status]}</span></td>
                            <td className="em">{p.published_at ? relativeDate(p.published_at) : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </aside>
    </>
  );
}

// ── Main screen ──────────────────────────────────────────────────────
const DEFAULT_COL_ORDER  = ['name','plan','status','country','size','hr','emp','cases','contact','created'];
const DEFAULT_COL_WIDTHS = { name: 280, plan: 92, status: 92, country: 100, size: 90, hr: 116, emp: 130, cases: 80, contact: 170, created: 96 };
const COL_LABELS         = { name: 'Company', plan: 'Plan', status: 'Status', country: 'Country', size: 'Size', hr: 'HR seats', emp: 'Employee seats', cases: 'Cases', contact: 'Primary contact', created: 'Created' };
const COL_SORT_KEY       = { name: 'name', plan: 'plan_tier', status: 'status', country: 'country', size: 'size_band', hr: 'hr_users_count', emp: 'employee_count', cases: 'assignments_count', created: 'created_at' };
const COL_NUMERIC        = { cases: true };
const COL_MIN_W          = { name: 180, plan: 70, status: 70, country: 80, size: 70, hr: 90, emp: 100, cases: 64, contact: 120, created: 80 };
const COL_MAX_W          = 520;

function CompaniesScreen({ initialState = 'idle' }) {
  // Loading / error states (driven by Tweaks)
  const [state, setState] = useState(initialState); // 'idle' | 'loading' | 'error'
  useEffect(() => setState(initialState), [initialState]);

  // Filter state
  const [search, setSearch]               = useState('');
  const [statusFilter, setStatusFilter]   = useState('');
  const [planFilter, setPlanFilter]       = useState('');
  const [countryFilter, setCountryFilter] = useState('');
  const [sizeFilter, setSizeFilter]       = useState('');
  const [issuesOnly, setIssuesOnly]       = useState(false);

  // Sort state
  const [sortKey, setSortKey] = useState('name');
  const [sortDir, setSortDir] = useState('asc');

  // Reusable column reorder + resize
  const cols = useMovableColumns({
    storageKey: 'companies',
    defaultOrder: DEFAULT_COL_ORDER,
    defaultWidths: DEFAULT_COL_WIDTHS,
    minWidths: COL_MIN_W,
    maxWidth: COL_MAX_W,
  });

  // Selection
  const [selected, setSelected] = useState(() => new Set());
  const toggleSel = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelected(next);
  };

  // Active company / detail
  const [activeId, setActiveId] = useState(null);
  const detailCache = useRef(new Map());
  const [detailLoading, setDetailLoading] = useState(false);
  const [activeDetail, setActiveDetail] = useState(null);

  const openCompany = (co) => {
    setActiveId(co.id);
    const cached = detailCache.current.get(co.id);
    if (cached) {
      setActiveDetail(cached);
      return;
    }
    setActiveDetail(null);
    setDetailLoading(true);
    // Simulate API call. Real code: adminAPI.getCompanyDetail(co.id)
    const t = setTimeout(() => {
      const detail = DETAILS[co.id] || fallbackDetail(co);
      detailCache.current.set(co.id, detail);
      setActiveDetail(detail);
      setDetailLoading(false);
    }, 380);
    return () => clearTimeout(t);
  };

  // Action menu
  const [openMenuId, setOpenMenuId] = useState(null);
  useEffect(() => {
    if (!openMenuId) return;
    const handler = () => setOpenMenuId(null);
    window.addEventListener('click', handler);
    return () => window.removeEventListener('click', handler);
  }, [openMenuId]);

  // Derived options
  const countries = useMemo(() => [...new Set(COMPANIES.map(c => c.country).filter(Boolean))].sort(), []);
  const sizes     = useMemo(() => [...new Set(COMPANIES.map(c => c.size_band).filter(Boolean))].sort(), []);

  // KPI computations
  const kpis = useMemo(() => {
    const sum = (k) => COMPANIES.reduce((a, c) => a + (c[k] || 0), 0);
    return {
      total:    COMPANIES.length,
      active:   COMPANIES.filter(c => c.status === 'active').length,
      inactive: COMPANIES.filter(c => c.status === 'inactive').length,
      archived: COMPANIES.filter(c => c.status === 'archived').length,
      premium:  COMPANIES.filter(c => c.plan_tier === 'premium').length,
      hr:       sum('hr_users_count'),
      emp:      sum('employee_count'),
      cases:    sum('assignments_count'),
      issues:   COMPANIES.filter(c => c.missing_from_registry || (c.missing_from_companies_table || 0) > 0).length,
    };
  }, []);

  // Filter + sort
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let arr = COMPANIES.filter(c => {
      if (q) {
        const hay = [c.name, c.legal_name, c.primary_contact_name, c.hr_contact, c.support_email]
          .filter(Boolean).join(' ').toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (statusFilter  && c.status     !== statusFilter)  return false;
      if (planFilter    && c.plan_tier  !== planFilter)    return false;
      if (countryFilter && c.country    !== countryFilter) return false;
      if (sizeFilter    && c.size_band  !== sizeFilter)    return false;
      if (issuesOnly && !(c.missing_from_registry || (c.missing_from_companies_table || 0) > 0)) return false;
      return true;
    });
    arr.sort((a, b) => {
      const av = a[sortKey] ?? '';
      const bv = b[sortKey] ?? '';
      let r;
      if (typeof av === 'number' && typeof bv === 'number') r = av - bv;
      else r = String(av).localeCompare(String(bv));
      return sortDir === 'asc' ? r : -r;
    });
    return arr;
  }, [search, statusFilter, planFilter, countryFilter, sizeFilter, issuesOnly, sortKey, sortDir]);

  const anyFilter = !!(search || statusFilter || planFilter || countryFilter || sizeFilter || issuesOnly);
  const clearAll = () => {
    setSearch(''); setStatusFilter(''); setPlanFilter('');
    setCountryFilter(''); setSizeFilter(''); setIssuesOnly(false);
  };

  const toggleSort = (k) => {
    if (sortKey === k) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(k); setSortDir('asc'); }
  };
  const sortIcon = (k) => sortKey !== k ? null : <span className="sort-i">{sortDir === 'asc' ? '↑' : '↓'}</span>;

  // Bulk header checkbox state
  const allSelected = filtered.length > 0 && filtered.every(c => selected.has(c.id));
  const someSelected = filtered.some(c => selected.has(c.id));
  const headerCheckRef = useRef(null);
  useEffect(() => {
    if (headerCheckRef.current) headerCheckRef.current.indeterminate = someSelected && !allSelected;
  }, [someSelected, allSelected]);
  const toggleAll = () => {
    if (allSelected) {
      const next = new Set(selected);
      filtered.forEach(c => next.delete(c.id));
      setSelected(next);
    } else {
      const next = new Set(selected);
      filtered.forEach(c => next.add(c.id));
      setSelected(next);
    }
  };

  const activeCompany = activeId ? COMPANIES.find(c => c.id === activeId) : null;

  // Cell renderer — one switch keeps the column system honest
  const renderCell = (c, colId) => {
    switch (colId) {
      case 'name': return (
        <div className="cos-co-name">
          <div className={`cos-co-logo tone-${c.tone || 'a'}`}>{logoInitials(c.name)}</div>
          <div style={{ minWidth: 0 }}>
            <div className="nm">{c.name}</div>
            {c.legal_name && c.legal_name !== c.name &&
              <div className="legal">{c.legal_name}</div>}
          </div>
        </div>
      );
      case 'plan': return <span className={`cos-badge ${PLAN_TONE[c.plan_tier]}`}>{c.plan_tier}</span>;
      case 'status': return <span className={`cos-badge dot ${STATUS_TONE[c.status]}`}>{c.status}</span>;
      case 'country': return <span style={{ color:'var(--text-2)' }}>{c.country || '—'}</span>;
      case 'size': return <span style={{ color:'var(--text-2)' }}>{c.size_band || '—'}</span>;
      case 'hr': {
        const hrPct = c.hr_seat_limit ? Math.min(100, Math.round(c.hr_users_count / c.hr_seat_limit * 100)) : 0;
        return (
          <div className={`cos-seat ${hrPct > 90 ? 'full' : hrPct > 75 ? 'near' : ''}`}>
            <div className="nums">{c.hr_users_count}{c.hr_seat_limit ? <><span className="of">/ {c.hr_seat_limit}</span></> : <span className="none">/ —</span>}</div>
            {c.hr_seat_limit && <div className="bar"><div style={{ width: hrPct + '%' }}/></div>}
          </div>
        );
      }
      case 'emp': {
        const empPct = c.employee_seat_limit ? Math.min(100, Math.round(c.employee_count / c.employee_seat_limit * 100)) : 0;
        return (
          <div className={`cos-seat ${empPct > 90 ? 'full' : empPct > 75 ? 'near' : ''}`}>
            <div className="nums">{c.employee_count}{c.employee_seat_limit ? <><span className="of">/ {c.employee_seat_limit}</span></> : <span className="none">/ —</span>}</div>
            {c.employee_seat_limit && <div className="bar"><div style={{ width: empPct + '%' }}/></div>}
          </div>
        );
      }
      case 'cases': return <span style={{ fontWeight: 600 }}>{c.assignments_count}</span>;
      case 'contact': return (
        <div className={`cos-contact${c.primary_contact_name ? '' : ' empty'}`}>
          {c.primary_contact_name || '—'}
          {c.hr_contact && <div className="sub" style={{ whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{c.hr_contact}</div>}
        </div>
      );
      case 'created': return <span className="cos-date">{relativeDate(c.created_at)}</span>;
      default: return null;
    }
  };

  // Header drag handlers are provided by the useMovableColumns hook.

  return (
    <div className="page wide">
      <div className="page-hd">
        <div className="page-eyebrow">ReloPass · /admin/companies/overview</div>
        <div style={{ display:'flex', alignItems:'flex-end', gap: 12 }}>
          <h1 className="page-h">Companies</h1>
          <div style={{ flex: 1 }}/>
          <span className="pill warning"><I n="shield" s={11}/> admin · @relopass.com</span>
          <button className="btn"><I n="download" s={12}/> Export CSV</button>
          <button className="btn primary"><I n="plus" s={12}/> Add tenant</button>
        </div>
        <div className="page-sub">
          Every tenant on the platform — people, activity, policy health and data quality, in one view. Click any row to inspect.
        </div>
      </div>

      {/* KPI strip */}
      <div className="cos-kpis">
        <KPI k="Total"      v={kpis.total}    s="all tenants"        ico="globe"  />
        <KPI k="Active"     v={kpis.active}   s="live on platform"   ico="check2" tone="success"/>
        <KPI k="Inactive"   v={kpis.inactive} s="paused"             ico="clock"  tone="warning"/>
        <KPI k="Archived"   v={kpis.archived} s="soft-deleted"       ico="files"  />
        <KPI k="Premium"    v={kpis.premium}  s="top tier"           ico="star"   tone="accent"/>
        <KPI k="HR users"   v={kpis.hr}       s="across all tenants" ico="users"  tone="teal"/>
        <KPI k="Employees"  v={kpis.emp.toLocaleString()} s="across all tenants" ico="user" tone="teal"/>
        <KPI k="Open cases" v={kpis.cases}    s="active mobility"    ico="pulse"  tone="accent"/>
        <KPI k="Data issues" v={kpis.issues}  s="orphan / registry"  ico="alert"  tone={kpis.issues > 0 ? 'warning' : ''}/>
      </div>

      {/* Filter bar */}
      <div className="cos-filter">
        <div className="cos-search">
          <I n="search" s={13}/>
          <input
            placeholder="Search by company name, contact, email…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && <I n="x" s={12} style={{ cursor:'pointer' }} onClick={() => setSearch('')}/>}
        </div>
        <FilterSelect label="Status"  value={statusFilter}  onChange={setStatusFilter}
                      options={[{value:'active',label:'Active'},{value:'inactive',label:'Inactive'},{value:'archived',label:'Archived'}]}/>
        <FilterSelect label="Plan"    value={planFilter}    onChange={setPlanFilter}
                      options={[{value:'low',label:'Low'},{value:'medium',label:'Medium'},{value:'premium',label:'Premium'}]}/>
        <FilterSelect label="Country" value={countryFilter} onChange={setCountryFilter} options={countries}/>
        <FilterSelect label="Size"    value={sizeFilter}    onChange={setSizeFilter}    options={sizes}/>
        <label className={`cos-check${issuesOnly ? ' on' : ''}`}>
          <input type="checkbox" checked={issuesOnly} onChange={(e) => setIssuesOnly(e.target.checked)}/>
          Issues only
        </label>
        <button className="cos-clear" disabled={!anyFilter} onClick={clearAll}>
          Clear filters
        </button>
      </div>

      {/* Active filter chips */}
      {anyFilter && (
        <div className="cos-chips">
          {search        && <Chip label="Search" value={`"${search}"`} onClear={() => setSearch('')}/>}
          {statusFilter  && <Chip label="Status" value={statusFilter} onClear={() => setStatusFilter('')}/>}
          {planFilter    && <Chip label="Plan" value={planFilter} onClear={() => setPlanFilter('')}/>}
          {countryFilter && <Chip label="Country" value={countryFilter} onClear={() => setCountryFilter('')}/>}
          {sizeFilter    && <Chip label="Size" value={sizeFilter} onClear={() => setSizeFilter('')}/>}
          {issuesOnly    && <Chip label="" value="Data issues only" onClear={() => setIssuesOnly(false)}/>}
        </div>
      )}

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="cos-bulk">
          <span className="count">{selected.size} compan{selected.size === 1 ? 'y' : 'ies'} selected</span>
          <div className="spacer"/>
          <button className="cos-bulk-btn">Archive selected</button>
          <button className="cos-bulk-btn">Deactivate selected</button>
          <button className="cos-bulk-btn ghost" onClick={() => setSelected(new Set())}>Clear selection</button>
        </div>
      )}

      {/* Table */}
      <div className="cos-table-wrap movable-tbl-wrap">
        <table className="cos-table movable-tbl">
          <thead>
            <tr>
              <th className="col-check">
                <input
                  ref={headerCheckRef}
                  type="checkbox"
                  className="cos-cb"
                  checked={allSelected}
                  onChange={toggleAll}
                  aria-label="Select all visible"
                />
              </th>
              {cols.order.map(colId => (
                <MovableTh
                  key={colId}
                  colId={colId}
                  ctx={cols}
                  label={COL_LABELS[colId]}
                  sortable
                  sortKey={COL_SORT_KEY[colId]}
                  currentSortKey={sortKey}
                  sortDir={sortDir}
                  onSort={toggleSort}
                  numeric={!!COL_NUMERIC[colId]}
                />
              ))}
              <th className="col-flag center" title="Data quality"></th>
              <th className="col-act"></th>
            </tr>
          </thead>
          <tbody>
            {state === 'loading' && Array.from({ length: 6 }).map((_, i) => (
              <tr key={`sk-${i}`} className="cos-skel">
                <td><span className="cos-skel-bar w-xs"/></td>
                {cols.order.map(colId => (
                  <td key={colId} style={cols.cellStyle(colId)}>
                    {colId === 'name'
                      ? <div style={{ display:'flex', alignItems:'center', gap:10 }}><span className="cos-skel-circ"/><span className="cos-skel-bar w-md"/></div>
                      : colId === 'hr' || colId === 'emp' || colId === 'contact'
                        ? <span className="cos-skel-bar w-md"/>
                        : <span className="cos-skel-bar w-sm"/>}
                  </td>
                ))}
                <td><span className="cos-skel-bar w-xs"/></td>
                <td><span className="cos-skel-bar w-xs"/></td>
              </tr>
            ))}
            {state === 'idle' && filtered.map(c => {
              const isSel = selected.has(c.id);
              const isActive = activeId === c.id;
              const hasIssue = c.missing_from_registry || (c.missing_from_companies_table || 0) > 0;
              return (
                <tr key={c.id}
                    className={`${isSel ? 'selected' : ''} ${isActive ? 'active' : ''}`}
                    onClick={() => openCompany(c)}>
                  <td className="col-check" onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" className="cos-cb"
                           checked={isSel}
                           onChange={() => toggleSel(c.id)}
                           aria-label={`Select ${c.name}`}/>
                  </td>
                  {cols.order.map(colId => (
                    <td key={colId}
                        style={cols.cellStyle(colId)}
                        className={COL_NUMERIC[colId] ? 'numeric' : ''}>
                      {renderCell(c, colId)}
                    </td>
                  ))}
                  <td className="center" onClick={(e) => e.stopPropagation()}>
                    {hasIssue ? (
                      <div className="cos-flag" title={
                        c.missing_from_registry
                          ? 'Missing from external registry'
                          : `${c.missing_from_companies_table} orphan profile(s)`
                      }>
                        <I n="alert" s={12}/>
                      </div>
                    ) : null}
                  </td>
                  <td className="center" onClick={(e) => e.stopPropagation()}>
                    <div className="cos-act-wrap">
                      <button className="cos-act" onClick={(e) => {
                        e.stopPropagation();
                        setOpenMenuId(m => m === c.id ? null : c.id);
                      }}>
                        <span style={{ fontSize: 18, letterSpacing: 1, lineHeight: 0.5 }}>···</span>
                      </button>
                      {openMenuId === c.id && (
                        <div className="cos-act-menu" onClick={(e) => e.stopPropagation()}>
                          <div className="cos-act-item" onClick={() => { openCompany(c); setOpenMenuId(null); }}><I n="eye" s={13}/> View detail</div>
                          <div className="cos-act-item"><I n="edit" s={13}/> Edit</div>
                          <div className="cos-act-divider"/>
                          <div className="cos-act-item"><I n="clock" s={13}/> Deactivate</div>
                          <div className="cos-act-item"><I n="files" s={13}/> Archive</div>
                          <div className="cos-act-item danger"><I n="x" s={13}/> Delete</div>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}

            {state === 'idle' && filtered.length === 0 && (
              <tr><td colSpan={cols.order.length + 3}>
                <div className="cos-empty">
                  <div className="glyph"><I n="search" s={22}/></div>
                  <div className="t">No companies match these filters</div>
                  <div className="s">Try widening your filters or clearing them to see every tenant on the platform.</div>
                  <span className="lnk" onClick={clearAll}>Clear filters</span>
                </div>
              </td></tr>
            )}

            {state === 'error' && (
              <tr><td colSpan={cols.order.length + 3}>
                <div className="cos-error-state">
                  <div className="glyph"><I n="alert" s={22}/></div>
                  <div className="t">Couldn't load companies</div>
                  <div className="s">The admin API returned a 5xx error. Check the gateway status or retry.</div>
                  <span className="lnk" onClick={() => setState('idle')}>Retry</span>
                </div>
              </td></tr>
            )}
          </tbody>
        </table>

        {state === 'idle' && filtered.length > 0 && (
          <div className="cos-foot">
            <span>{filtered.length} of {COMPANIES.length} compan{COMPANIES.length === 1 ? 'y' : 'ies'}</span>
            <div className="right">
              <span>Sorted by <strong style={{ color:'var(--text-2)' }}>{sortKey}</strong> · {sortDir}</span>
              <span>·</span>
              <span className="mt-reset" onClick={cols.reset} title="Restore default column order and widths">
                Reset columns
              </span>
              <span>·</span>
              <span>Last sync 3m ago</span>
            </div>
          </div>
        )}
      </div>

      {activeCompany && (
        <CompanyDetailPanel
          company={activeCompany}
          detail={activeDetail}
          loading={detailLoading}
          onClose={() => { setActiveId(null); setActiveDetail(null); }}
        />
      )}
    </div>
  );
}

function Chip({ label, value, onClear }) {
  return (
    <span className="cos-chip">
      {label && <>{label}: </>}
      <strong>{value}</strong>
      <span className="x" onClick={onClear}><I n="x" s={10}/></span>
    </span>
  );
}

window.CompaniesScreen = CompaniesScreen;
})();
