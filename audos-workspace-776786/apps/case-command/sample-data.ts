/**
 * ReloPass Case Command — demo relocation cases
 * Pre-loaded so mobility teams see a credible ops dashboard immediately.
 */

export type CaseStatus = 'Active' | 'At Risk' | 'Completed';
export type TimelineEventStatus = 'completed' | 'current' | 'upcoming' | 'blocked';
export type ComplianceStatus = 'passed' | 'pending' | 'at_risk' | 'blocked';
export type VendorStatus = 'assigned' | 'in_progress' | 'pending';
export type ApprovalStatus = 'approved' | 'pending' | 'rejected' | 'escalated';

export interface RelocationCase {
  id: string;
  employeeName: string;
  role: string;
  origin: string;
  originCode: string;
  destination: string;
  destinationCode: string;
  status: CaseStatus;
  coordinator: string;
  moveDate: string;
  deadlineDate: string;
  policyTier: string;
  dependents: number;
  department: string;
  summary: string;
  riskNote?: string;
}

export interface TimelineEvent {
  id: string;
  date: string;
  title: string;
  description: string;
  status: TimelineEventStatus;
  owner: string;
  category: 'immigration' | 'tax' | 'logistics' | 'compliance' | 'housing' | 'hr';
}

export interface ComplianceItem {
  id: string;
  title: string;
  description: string;
  status: ComplianceStatus;
  dueDate?: string;
  regulation?: string;
  linkedMilestone?: string;
}

export interface VendorAssignment {
  id: string;
  category: string;
  description: string;
  vendorName?: string;
  status: VendorStatus;
  contact?: string;
  nextMilestone?: string;
}

export interface ApprovalEntry {
  id: string;
  date: string;
  item: string;
  approver: string;
  role: string;
  status: ApprovalStatus;
  notes?: string;
}

export interface CaseDetail {
  case: RelocationCase;
  timeline: TimelineEvent[];
  compliance: ComplianceItem[];
  vendors: VendorAssignment[];
  approvals: ApprovalEntry[];
}

export const DEMO_CASES: RelocationCase[] = [
  {
    id: 'case-marcus-obi',
    employeeName: 'Marcus Obi',
    role: 'VP Engineering',
    origin: 'Lagos',
    originCode: 'NG',
    destination: 'Amsterdam',
    destinationCode: 'NL',
    status: 'At Risk',
    coordinator: 'Amara Diallo',
    moveDate: '2026-08-15',
    deadlineDate: '2026-07-18',
    policyTier: 'Executive',
    dependents: 3,
    department: 'Engineering',
    summary:
      'Intra-company transfer to Amsterdam tech hub. Highly Skilled Migrant route with spouse and two school-age children. Critical path blocked on apostilled birth certificates for dependants.',
    riskNote: 'Dependent document apostille delayed — may miss IND filing window',
  },
  {
    id: 'case-priya-sharma',
    employeeName: 'Priya Sharma',
    role: 'Director, Finance',
    origin: 'Mumbai',
    originCode: 'IN',
    destination: 'Berlin',
    destinationCode: 'DE',
    status: 'Active',
    coordinator: 'Thomas Keller',
    moveDate: '2026-09-01',
    deadlineDate: '2026-07-25',
    policyTier: 'Plus',
    dependents: 1,
    department: 'Finance',
    summary: 'Blue Card EU route. Tax equalisation in progress. Household goods survey booked.',
  },
  {
    id: 'case-elena-novak',
    employeeName: 'Elena Novak',
    role: 'Regional Sales Lead',
    origin: 'Warsaw',
    originCode: 'PL',
    destination: 'Dublin',
    destinationCode: 'IE',
    status: 'At Risk',
    coordinator: 'Siobhan Murphy',
    moveDate: '2026-07-20',
    deadlineDate: '2026-07-05',
    policyTier: 'Standard',
    dependents: 0,
    department: 'Sales',
    summary: 'EU free movement. Housing budget approval escalated — Dublin rent exceeds policy cap.',
    riskNote: 'Housing exception pending CFO sign-off',
  },
  {
    id: 'case-james-okafor',
    employeeName: 'James Okafor',
    role: 'Product Manager',
    origin: 'Nairobi',
    originCode: 'KE',
    destination: 'Toronto',
    destinationCode: 'CA',
    status: 'Active',
    coordinator: 'Amara Diallo',
    moveDate: '2026-10-10',
    deadlineDate: '2026-08-01',
    policyTier: 'Plus',
    dependents: 2,
    department: 'Product',
    summary: 'LMIA-backed work permit. Immigration counsel engaged. School search vendor to be assigned.',
  },
  {
    id: 'case-sofia-lindstrom',
    employeeName: 'Sofia Lindström',
    role: 'Head of Marketing',
    origin: 'Stockholm',
    originCode: 'SE',
    destination: 'Singapore',
    destinationCode: 'SG',
    status: 'Completed',
    coordinator: 'Thomas Keller',
    moveDate: '2026-03-01',
    deadlineDate: '2026-02-28',
    policyTier: 'Executive',
    dependents: 1,
    department: 'Marketing',
    summary: 'Completed relocation. All compliance checkpoints passed. Case closed 15 Mar 2026.',
  },
  {
    id: 'case-yuki-tanaka',
    employeeName: 'Yuki Tanaka',
    role: 'Senior Data Scientist',
    origin: 'Tokyo',
    originCode: 'JP',
    destination: 'Sydney',
    destinationCode: 'AU',
    status: 'At Risk',
    coordinator: 'Siobhan Murphy',
    moveDate: '2026-08-28',
    deadlineDate: '2026-07-10',
    policyTier: 'Plus',
    dependents: 0,
    department: 'Data & AI',
    summary: 'TSS visa subclass 482. Skills assessment submitted — outcome overdue by 5 days.',
    riskNote: 'VETASSESS outcome overdue',
  },
];

export const MARCUS_OBI_DETAIL: CaseDetail = {
  case: DEMO_CASES[0],
  timeline: [
    {
      id: 'tl-1',
      date: '2026-05-12',
      title: 'Relocation policy confirmed',
      description: 'Executive tier approved: full immigration support, 60 days temp housing, school placement, tax equalisation.',
      status: 'completed',
      owner: 'HR / Mobility',
      category: 'hr',
    },
    {
      id: 'tl-2',
      date: '2026-05-28',
      title: 'IND sponsor licence verified',
      description: 'Dutch entity confirmed as recognised sponsor. No cap restrictions for Highly Skilled Migrant route.',
      status: 'completed',
      owner: 'Immigration counsel',
      category: 'immigration',
    },
    {
      id: 'tl-3',
      date: '2026-06-10',
      title: 'Salary threshold & job description filed',
      description: 'Gross salary €5,688/mo meets 30+ age HSM threshold. Role mapped to ISCO 1330.',
      status: 'completed',
      owner: 'HR Netherlands',
      category: 'compliance',
    },
    {
      id: 'tl-4',
      date: '2026-06-20',
      title: 'Main applicant MVV application submitted',
      description: 'Application lodged at Dutch embassy Lagos. Biometrics completed. Priority processing requested.',
      status: 'completed',
      owner: 'Fragomen',
      category: 'immigration',
    },
    {
      id: 'tl-5',
      date: '2026-06-25',
      title: 'Dependent documents — apostille pending',
      description: 'Birth certificates for two dependants submitted to Ministry of Foreign Affairs for apostille. Standard turnaround 3–4 weeks; currently at week 5.',
      status: 'current',
      owner: 'Employee + Local agent',
      category: 'immigration',
    },
    {
      id: 'tl-6',
      date: '2026-07-18',
      title: 'IND dependent filing deadline',
      description: 'Dependant MVV applications must be lodged before main applicant travels. Blocks family relocation if missed.',
      status: 'upcoming',
      owner: 'Fragomen',
      category: 'immigration',
    },
    {
      id: 'tl-7',
      date: '2026-07-25',
      title: 'Household goods survey',
      description: 'Sirva scheduled pack survey in Lagos. Sea freight ~8 weeks to Rotterdam.',
      status: 'upcoming',
      owner: 'Sirva',
      category: 'logistics',
    },
    {
      id: 'tl-8',
      date: '2026-08-01',
      title: 'Temporary housing secured — Amsterdam Zuid',
      description: 'Serviced apartment booked for 60 days per Executive policy. School catchment confirmed for International School of Amsterdam.',
      status: 'upcoming',
      owner: 'Sirva',
      category: 'housing',
    },
    {
      id: 'tl-9',
      date: '2026-08-15',
      title: 'Target arrival & start date',
      description: 'Flight LOS→AMS. BRP appointment within 5 days of arrival. 30% ruling application within 4 months.',
      status: 'upcoming',
      owner: 'Employee',
      category: 'logistics',
    },
    {
      id: 'tl-10',
      date: '2026-08-22',
      title: 'Municipality registration (gemeente)',
      description: 'Register at Amsterdam city hall within 5 days of arrival. Required for BSN and healthcare.',
      status: 'upcoming',
      owner: 'Employee + Relocation vendor',
      category: 'compliance',
    },
  ],
  compliance: [
    {
      id: 'cp-1',
      title: 'Recognised sponsor status active',
      description: 'Dutch entity holds valid IND sponsor licence for Highly Skilled Migrant route.',
      status: 'passed',
      regulation: 'IND Sponsor Requirements',
    },
    {
      id: 'cp-2',
      title: 'Salary threshold met (30+ HSM)',
      description: 'Gross monthly salary €5,688 exceeds 2026 threshold of €5,688 for applicants 30+.',
      status: 'passed',
      regulation: 'IND Salary Criteria 2026',
    },
    {
      id: 'cp-3',
      title: 'Dependent MVV documentation',
      description: 'Apostilled birth certificates required for both dependants before IND filing. Currently blocked.',
      status: 'at_risk',
      dueDate: '2026-07-18',
      regulation: 'IND Family Reunification',
      linkedMilestone: 'Dependent documents — apostille pending',
    },
    {
      id: 'cp-4',
      title: '30% ruling eligibility review',
      description: 'Expat tax facility application must be filed within 4 months of start date. Salary and distance criteria met.',
      status: 'pending',
      dueDate: '2026-12-15',
      regulation: 'Dutch Tax Authority',
    },
    {
      id: 'cp-5',
      title: 'Nigeria tax clearance certificate',
      description: 'FIRS tax clearance required before final Nigeria payroll release.',
      status: 'pending',
      dueDate: '2026-08-01',
      regulation: 'FIRS Regulations',
    },
    {
      id: 'cp-6',
      title: 'Policy cap — housing budget',
      description: 'Temporary housing within Executive tier cap (€4,500/mo). Permanent housing search budget approved.',
      status: 'passed',
      regulation: 'Internal mobility policy',
    },
  ],
  vendors: [
    {
      id: 'v-1',
      category: 'Immigration',
      description: 'HSM permit, MVV, dependant applications, 30% ruling',
      vendorName: 'Fragomen',
      status: 'in_progress',
      contact: 'lotte.van.der.berg@fragomen.com',
      nextMilestone: 'Dependent MVV filing — target 18 Jul',
    },
    {
      id: 'v-2',
      category: 'Relocation',
      description: 'HHG shipment, temp housing, settling-in',
      vendorName: 'Sirva',
      status: 'assigned',
      contact: 'peter.de.vries@sirva.com',
      nextMilestone: 'Home survey 25 Jul',
    },
    {
      id: 'v-3',
      category: 'Tax Advisory',
      description: 'Nigeria clearance, NL registration, 30% ruling, equalisation',
      vendorName: 'Deloitte Mobility',
      status: 'assigned',
      contact: 'anna.meijer@deloitte.nl',
      nextMilestone: 'FIRS clearance kickoff 1 Jul',
    },
    {
      id: 'v-4',
      category: 'School Search',
      description: 'International school placement for two children',
      vendorName: 'Relocate Global',
      status: 'in_progress',
      contact: 'sarah.okonkwo@relocateglobal.com',
      nextMilestone: 'ISA enrollment confirmation 5 Aug',
    },
  ],
  approvals: [
    {
      id: 'ap-1',
      date: '2026-05-10',
      item: 'Executive relocation policy tier',
      approver: 'David Chen',
      role: 'CHRO',
      status: 'approved',
      notes: 'Approved per executive mobility matrix. Full immigration and family support.',
    },
    {
      id: 'ap-2',
      date: '2026-05-15',
      item: 'Relocation budget — €142,000',
      approver: 'Nina Patel',
      role: 'CFO',
      status: 'approved',
      notes: 'Includes immigration, HHG, 60-day temp housing, school fees contribution.',
    },
    {
      id: 'ap-3',
      date: '2026-06-01',
      item: 'Salary package — Amsterdam VP Engineering',
      approver: 'David Chen',
      role: 'CHRO',
      status: 'approved',
    },
    {
      id: 'ap-4',
      date: '2026-06-18',
      item: 'Immigration counsel engagement — Fragomen',
      approver: 'Amara Diallo',
      role: 'Mobility Lead',
      status: 'approved',
      notes: 'Preferred vendor for NL corridor. SOW signed.',
    },
    {
      id: 'ap-5',
      date: '2026-06-28',
      item: 'Apostille expedite request — dependant documents',
      approver: 'Amara Diallo',
      role: 'Mobility Lead',
      status: 'escalated',
      notes: 'Escalated to embassy liaison. Premium processing fee approved €850.',
    },
    {
      id: 'ap-6',
      date: '2026-07-02',
      item: 'Move date extension (+2 weeks)',
      approver: 'David Chen',
      role: 'CHRO',
      status: 'pending',
      notes: 'Requested if apostille not received by 10 Jul. Awaiting business justification from hiring manager.',
    },
  ],
};

export const CASE_DETAILS: Record<string, CaseDetail> = {
  'case-marcus-obi': MARCUS_OBI_DETAIL,
};

export function getCaseDetail(caseId: string): CaseDetail | null {
  if (CASE_DETAILS[caseId]) return CASE_DETAILS[caseId];
  const c = DEMO_CASES.find((x) => x.id === caseId);
  if (!c) return null;
  return {
    case: c,
    timeline: [
      {
        id: 'generic-1',
        date: c.moveDate,
        title: 'Target move date',
        description: c.summary,
        status: c.status === 'Completed' ? 'completed' : 'upcoming',
        owner: c.coordinator,
        category: 'logistics',
      },
    ],
    compliance: [
      {
        id: 'generic-cp',
        title: 'Case compliance review',
        description: 'Full compliance checklist available in detailed case view.',
        status: c.status === 'At Risk' ? 'at_risk' : c.status === 'Completed' ? 'passed' : 'pending',
      },
    ],
    vendors: [],
    approvals: [
      {
        id: 'generic-ap',
        date: c.deadlineDate,
        item: 'Relocation policy approval',
        approver: c.coordinator,
        role: 'Mobility Coordinator',
        status: c.status === 'Completed' ? 'approved' : 'approved',
      },
    ],
  };
}

export function daysUntil(dateStr: string): number | null {
  try {
    const d = new Date(dateStr + 'T12:00:00');
    if (isNaN(d.getTime())) return null;
    return Math.ceil((d.getTime() - Date.now()) / (1000 * 60 * 60 * 24));
  } catch {
    return null;
  }
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr + 'T12:00:00');
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

export function countByStatus(cases: RelocationCase[]) {
  return {
    active: cases.filter((c) => c.status === 'Active').length,
    atRisk: cases.filter((c) => c.status === 'At Risk').length,
    completed: cases.filter((c) => c.status === 'Completed').length,
    total: cases.length,
  };
}
