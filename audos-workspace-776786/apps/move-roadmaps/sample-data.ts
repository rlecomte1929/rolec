/**
 * ReloPass Move Roadmaps — flagship demo relocation journeys
 * Sarah Chen · Singapore → London is the primary showcase case.
 */

export type PhaseId = 'pre-move' | 'in-transit' | 'post-arrival';
export type RoadmapStatus = 'On track' | 'At risk' | 'Completed';
export type MilestoneStatus = 'completed' | 'in_progress' | 'pending' | 'blocked';
export type CheckpointStatus = 'passed' | 'pending' | 'at_risk' | 'blocked';
export type VendorStatus = 'assigned' | 'in_progress' | 'pending';

export interface EmployeeProfile {
  name: string;
  role: string;
  department: string;
  origin: string;
  originCode: string;
  destination: string;
  destinationCode: string;
  moveDate: string;
  dependents: number;
  policyTier: string;
  coordinator: string;
}

export interface Milestone {
  id: string;
  title: string;
  description: string;
  status: MilestoneStatus;
  dueDate: string;
  owner: string;
  category: 'immigration' | 'tax' | 'logistics' | 'compliance' | 'housing' | 'vendor';
}

export interface RoadmapPhase {
  id: PhaseId;
  name: string;
  description: string;
  milestones: Milestone[];
}

export interface ComplianceCheckpoint {
  id: string;
  phaseId: PhaseId;
  title: string;
  description: string;
  status: CheckpointStatus;
  dueDate?: string;
  regulation?: string;
  linkedMilestone?: string;
}

export interface VendorSlot {
  id: string;
  phaseId: PhaseId;
  category: string;
  description: string;
  vendorName?: string;
  vendorStatus: VendorStatus;
  contact?: string;
  nextMilestone?: string;
}

export interface MoveRoadmap {
  id: string;
  employee: EmployeeProfile;
  summary: string;
  status: RoadmapStatus;
  currentPhase: PhaseId;
  phases: RoadmapPhase[];
  complianceCheckpoints: ComplianceCheckpoint[];
  vendors: VendorSlot[];
  keyDates: { label: string; date: string }[];
  riskFlags: string[];
}

export interface RoadmapSummary {
  id: string;
  employeeName: string;
  role: string;
  origin: string;
  originCode: string;
  destination: string;
  destinationCode: string;
  status: RoadmapStatus;
  currentPhase: PhaseId;
  coordinator: string;
  moveDate: string;
  progress: number;
  riskNote?: string;
}

export const PHASE_ORDER: PhaseId[] = ['pre-move', 'in-transit', 'post-arrival'];

export const PHASE_META: Record<PhaseId, { label: string; shortLabel: string }> = {
  'pre-move': { label: 'Pre-Move', shortLabel: 'Pre-Move' },
  'in-transit': { label: 'In-Transit', shortLabel: 'Transit' },
  'post-arrival': { label: 'Post-Arrival', shortLabel: 'Arrival' },
};

export const SARAH_CHEN_ROADMAP: MoveRoadmap = {
  id: 'roadmap-sarah-chen',
  employee: {
    name: 'Sarah Chen',
    role: 'Senior Product Manager',
    department: 'Product',
    origin: 'Singapore',
    originCode: 'SG',
    destination: 'London',
    destinationCode: 'UK',
    moveDate: '2026-08-15',
    dependents: 2,
    policyTier: 'Plus',
    coordinator: 'Thomas Keller',
  },
  status: 'At risk',
  summary:
    'Intra-company transfer from Singapore HQ to London office. Skilled Worker visa route with spouse and one school-age child. Policy covers immigration, household goods, 30 days temporary housing, and school search. Critical path: Certificate of Sponsorship → visa filing → UK arrival compliance within 10 days.',
  currentPhase: 'pre-move',
  phases: [
    {
      id: 'pre-move',
      name: 'Pre-Move',
      description: 'Visa, policy, and departure preparation — typically 8–12 weeks before move date',
      milestones: [
        {
          id: 'pm-1',
          title: 'Confirm relocation policy & budget',
          description: 'Plus tier approved: visa support, HHG shipment (40 ft), 30 days temp housing, school placement assistance.',
          status: 'completed',
          dueDate: '2026-05-20',
          owner: 'HR / Mobility',
          category: 'compliance',
        },
        {
          id: 'pm-2',
          title: 'Issue Certificate of Sponsorship (CoS)',
          description: 'UK sponsor licence holder assigns CoS for Skilled Worker route. CoS number required before visa application.',
          status: 'completed',
          dueDate: '2026-06-01',
          owner: 'Immigration counsel',
          category: 'immigration',
        },
        {
          id: 'pm-3',
          title: 'File Skilled Worker visa (main applicant + dependants)',
          description: 'Online application via UKVI. Biometrics at VFS Singapore. Priority service — 5 working day decision target.',
          status: 'in_progress',
          dueDate: '2026-07-28',
          owner: 'Employee + Fragomen',
          category: 'immigration',
        },
        {
          id: 'pm-4',
          title: 'Singapore tax clearance & IRAS filing',
          description: 'File Form IR21 for tax clearance before departure. Employer must withhold final salary until clearance received.',
          status: 'in_progress',
          dueDate: '2026-07-15',
          owner: 'Deloitte Mobility',
          category: 'tax',
        },
        {
          id: 'pm-5',
          title: 'Book household goods survey & shipment',
          description: 'Crown Relocations survey scheduled. Sea freight ~6 weeks transit SG→UK. Target pack date 4 weeks before move.',
          status: 'pending',
          dueDate: '2026-07-18',
          owner: 'Crown Relocations',
          category: 'logistics',
        },
        {
          id: 'pm-6',
          title: 'Secure temporary housing in London',
          description: 'Serviced apartment in Canary Wharf for 30 days per policy. School catchment research for dependent child (Year 5).',
          status: 'pending',
          dueDate: '2026-07-25',
          owner: 'Crown Relocations',
          category: 'housing',
        },
        {
          id: 'pm-7',
          title: 'Cancel Singapore utilities & tenancy',
          description: '90-day notice on condo lease. Transfer utilities, cancel subscriptions, deregister with IRAS.',
          status: 'pending',
          dueDate: '2026-08-01',
          owner: 'Employee',
          category: 'logistics',
        },
      ],
    },
    {
      id: 'in-transit',
      name: 'In-Transit',
      description: 'Travel week logistics and handover between origin and destination teams',
      milestones: [
        {
          id: 'it-1',
          title: 'Collect BRP collection letter',
          description: 'Decision letter confirms BRP must be collected within 10 days of UK entry at designated Post Office.',
          status: 'pending',
          dueDate: '2026-08-15',
          owner: 'Employee',
          category: 'immigration',
        },
        {
          id: 'it-2',
          title: 'Depart Singapore — final payroll & benefits handover',
          description: 'Last Singapore paycheck processed after IR21 clearance. CPF cessation and medical insurance termination.',
          status: 'pending',
          dueDate: '2026-08-14',
          owner: 'HR / Payroll',
          category: 'tax',
        },
        {
          id: 'it-3',
          title: 'Arrive UK & check into temporary housing',
          description: 'Flight SIN→LHR. Relocation vendor meet-and-greet at airport. Keys to serviced apartment.',
          status: 'pending',
          dueDate: '2026-08-15',
          owner: 'Employee + Crown Relocations',
          category: 'logistics',
        },
        {
          id: 'it-4',
          title: 'Notify UK employer of arrival',
          description: 'HR confirms start date. IT equipment issued. Right-to-work check completed with visa vignette.',
          status: 'pending',
          dueDate: '2026-08-16',
          owner: 'UK HR',
          category: 'compliance',
        },
      ],
    },
    {
      id: 'post-arrival',
      name: 'Post-Arrival',
      description: 'Settlement, compliance, and integration — first 90 days in the UK',
      milestones: [
        {
          id: 'pa-1',
          title: 'Collect Biometric Residence Permit (BRP)',
          description: 'Must collect within 10 days of UK entry. Bring passport and decision letter to designated Post Office.',
          status: 'pending',
          dueDate: '2026-08-25',
          owner: 'Employee',
          category: 'immigration',
        },
        {
          id: 'pa-2',
          title: 'Apply for National Insurance number',
          description: 'Required for UK payroll and tax. Apply online after BRP received. Processing 2–4 weeks.',
          status: 'pending',
          dueDate: '2026-08-30',
          owner: 'Employee',
          category: 'tax',
        },
        {
          id: 'pa-3',
          title: 'Register with GP & NHS',
          description: 'Register at local GP practice for family. Required for NHS access and school health records.',
          status: 'pending',
          dueDate: '2026-09-01',
          owner: 'Employee',
          category: 'compliance',
        },
        {
          id: 'pa-4',
          title: 'School enrollment for dependent',
          description: 'Apply to state primary school in catchment area. Bring proof of address, BRP, and previous school records.',
          status: 'pending',
          dueDate: '2026-09-15',
          owner: 'Employee + Relocate Global',
          category: 'housing',
        },
        {
          id: 'pa-5',
          title: 'Secure permanent housing',
          description: 'Begin rental search after temp housing. Budget £3,200/mo per policy cap. Right-to-rent check required.',
          status: 'pending',
          dueDate: '2026-09-30',
          owner: 'Employee + Crown Relocations',
          category: 'housing',
        },
        {
          id: 'pa-6',
          title: 'UK tax registration & split-year treatment',
          description: 'HMRC starter checklist. Split-year treatment for Singapore→UK move. Tax equalisation per policy.',
          status: 'pending',
          dueDate: '2026-09-15',
          owner: 'Deloitte Mobility',
          category: 'tax',
        },
      ],
    },
  ],
  complianceCheckpoints: [
    {
      id: 'cc-pm-1',
      phaseId: 'pre-move',
      title: 'Sponsor licence & CoS valid',
      description: 'UK entity holds active sponsor licence. CoS assigned and not expired before visa filing.',
      status: 'passed',
      regulation: 'UK Home Office Sponsor Guidance',
      linkedMilestone: 'Issue Certificate of Sponsorship (CoS)',
    },
    {
      id: 'cc-pm-2',
      phaseId: 'pre-move',
      title: 'Singapore tax clearance (IR21)',
      description: 'Employer must obtain IRAS tax clearance before final salary release. Blocks departure payroll.',
      status: 'at_risk',
      dueDate: '2026-07-15',
      regulation: 'IRAS Section 68',
      linkedMilestone: 'Singapore tax clearance & IRAS filing',
    },
    {
      id: 'cc-pm-3',
      phaseId: 'pre-move',
      title: 'Dependent visas linked to main applicant',
      description: 'Spouse and child visas must be granted before family travels. Single application batch recommended.',
      status: 'pending',
      dueDate: '2026-08-10',
      regulation: 'UKVI Dependant Rules',
      linkedMilestone: 'File Skilled Worker visa (main applicant + dependants)',
    },
    {
      id: 'cc-pm-4',
      phaseId: 'pre-move',
      title: 'Policy cap — housing budget',
      description: 'Temporary and permanent housing must stay within Plus tier monthly cap (£3,200).',
      status: 'passed',
      regulation: 'Internal mobility policy',
    },
    {
      id: 'cc-it-1',
      phaseId: 'in-transit',
      title: 'Right to work in UK verified',
      description: 'Skilled Worker visa vignette or eVisa confirms legal work authorization before start date.',
      status: 'pending',
      dueDate: '2026-08-16',
      regulation: 'UK Immigration Act 2016',
      linkedMilestone: 'Notify UK employer of arrival',
    },
    {
      id: 'cc-it-2',
      phaseId: 'in-transit',
      title: 'Singapore departure clearance',
      description: 'IR21 clearance and CPF cessation confirmed before final departure from Singapore.',
      status: 'pending',
      dueDate: '2026-08-14',
      regulation: 'IRAS / CPF Board',
      linkedMilestone: 'Depart Singapore — final payroll & benefits handover',
    },
    {
      id: 'cc-pa-1',
      phaseId: 'post-arrival',
      title: 'BRP collected within 10-day window',
      description: 'Failure to collect BRP is a civil penalty risk and may affect future visa renewals.',
      status: 'pending',
      dueDate: '2026-08-25',
      regulation: 'UKVI BRP Policy',
      linkedMilestone: 'Collect Biometric Residence Permit (BRP)',
    },
    {
      id: 'cc-pa-2',
      phaseId: 'post-arrival',
      title: 'Right-to-rent documentation',
      description: 'BRP and proof of address required for permanent housing lease. Landlord compliance check.',
      status: 'pending',
      dueDate: '2026-09-30',
      regulation: 'Immigration Act 2014',
      linkedMilestone: 'Secure permanent housing',
    },
  ],
  vendors: [
    {
      id: 'v-pm-1',
      phaseId: 'pre-move',
      category: 'Immigration',
      description: 'Skilled Worker visa, CoS, dependant applications',
      vendorName: 'Fragomen LLP',
      vendorStatus: 'in_progress',
      contact: 'james.walsh@fragomen.com',
      nextMilestone: 'Visa decision expected 28 Jul',
    },
    {
      id: 'v-pm-2',
      phaseId: 'pre-move',
      category: 'Relocation',
      description: 'HHG shipment, temp housing, settling-in support',
      vendorName: 'Crown Relocations',
      vendorStatus: 'assigned',
      contact: 'sophie.martin@crownrelo.com',
      nextMilestone: 'Home survey 18 Jul',
    },
    {
      id: 'v-pm-3',
      phaseId: 'pre-move',
      category: 'Tax Advisory',
      description: 'SG clearance, UK registration, equalisation',
      vendorName: 'Deloitte Mobility',
      vendorStatus: 'in_progress',
      contact: 'anna.meijer@deloitte.nl',
      nextMilestone: 'IR21 filing — target 15 Jul',
    },
    {
      id: 'v-pa-1',
      phaseId: 'post-arrival',
      category: 'School Search',
      description: 'State school placement & enrollment support',
      vendorStatus: 'pending',
      nextMilestone: 'Assign vendor before Aug — term starts 2 Sep',
    },
  ],
  keyDates: [
    { label: 'Visa decision target', date: '2026-07-28' },
    { label: 'HHG pack date', date: '2026-07-18' },
    { label: 'Singapore departure', date: '2026-08-14' },
    { label: 'UK arrival', date: '2026-08-15' },
    { label: 'BRP collection deadline', date: '2026-08-25' },
    { label: 'UK start date', date: '2026-08-18' },
  ],
  riskFlags: [
    'IR21 tax clearance at risk — may delay final Singapore payroll and departure',
    'Dependent visas must be approved before 10 Aug family travel booking',
    'School term starts 2 Sep — enrollment deadline 15 Sep is tight if housing not secured',
  ],
};

export const ROADMAP_DETAILS: Record<string, MoveRoadmap> = {
  'roadmap-sarah-chen': SARAH_CHEN_ROADMAP,
};

export const DEMO_ROADMAPS: RoadmapSummary[] = [
  {
    id: 'roadmap-sarah-chen',
    employeeName: 'Sarah Chen',
    role: 'Senior Product Manager',
    origin: 'Singapore',
    originCode: 'SG',
    destination: 'London',
    destinationCode: 'UK',
    status: 'At risk',
    currentPhase: 'pre-move',
    coordinator: 'Thomas Keller',
    moveDate: '2026-08-15',
    progress: overallProgress(SARAH_CHEN_ROADMAP),
    riskNote: 'IR21 tax clearance at risk — may block departure payroll',
  },
  {
    id: 'roadmap-marcus-obi',
    employeeName: 'Marcus Obi',
    role: 'VP Engineering',
    origin: 'Lagos',
    originCode: 'NG',
    destination: 'Amsterdam',
    destinationCode: 'NL',
    status: 'At risk',
    currentPhase: 'pre-move',
    coordinator: 'Amara Diallo',
    moveDate: '2026-08-15',
    progress: 38,
    riskNote: 'Dependent apostille delayed — may miss IND filing window',
  },
  {
    id: 'roadmap-priya-sharma',
    employeeName: 'Priya Sharma',
    role: 'Director, Finance',
    origin: 'Mumbai',
    originCode: 'IN',
    destination: 'Berlin',
    destinationCode: 'DE',
    status: 'On track',
    currentPhase: 'pre-move',
    coordinator: 'Thomas Keller',
    moveDate: '2026-09-01',
    progress: 52,
  },
  {
    id: 'roadmap-elena-novak',
    employeeName: 'Elena Novak',
    role: 'Regional Sales Lead',
    origin: 'Warsaw',
    originCode: 'PL',
    destination: 'Dublin',
    destinationCode: 'IE',
    status: 'At risk',
    currentPhase: 'in-transit',
    coordinator: 'Siobhan Murphy',
    moveDate: '2026-07-20',
    progress: 71,
    riskNote: 'Housing exception pending CFO sign-off',
  },
  {
    id: 'roadmap-sofia-lindstrom',
    employeeName: 'Sofia Lindström',
    role: 'Head of Marketing',
    origin: 'Stockholm',
    originCode: 'SE',
    destination: 'Singapore',
    destinationCode: 'SG',
    status: 'Completed',
    currentPhase: 'post-arrival',
    coordinator: 'Thomas Keller',
    moveDate: '2026-03-01',
    progress: 100,
  },
  {
    id: 'roadmap-james-okafor',
    employeeName: 'James Okafor',
    role: 'Product Manager',
    origin: 'Nairobi',
    originCode: 'KE',
    destination: 'Toronto',
    destinationCode: 'CA',
    status: 'On track',
    currentPhase: 'pre-move',
    coordinator: 'Amara Diallo',
    moveDate: '2026-10-10',
    progress: 24,
  },
];

export function getRoadmapDetail(roadmapId: string): MoveRoadmap | null {
  if (ROADMAP_DETAILS[roadmapId]) return ROADMAP_DETAILS[roadmapId];
  const summary = DEMO_ROADMAPS.find((r) => r.id === roadmapId);
  if (!summary) return null;
  return buildGenericRoadmap(summary);
}

function buildGenericRoadmap(summary: RoadmapSummary): MoveRoadmap {
  const phaseIdx = PHASE_ORDER.indexOf(summary.currentPhase);
  const phases: RoadmapPhase[] = PHASE_ORDER.map((phaseId, idx) => ({
    id: phaseId,
    name: PHASE_META[phaseId].label,
    description:
      phaseId === 'pre-move'
        ? 'Visa, policy, and departure preparation'
        : phaseId === 'in-transit'
          ? 'Travel week logistics and handover'
          : 'Settlement, compliance, and integration — first 90 days',
    milestones: [
      {
        id: `${summary.id}-${phaseId}-1`,
        title:
          phaseId === 'pre-move'
            ? 'Immigration & policy setup'
            : phaseId === 'in-transit'
              ? 'Travel & arrival logistics'
              : 'Settlement & compliance',
        description: `${summary.employeeName}'s ${PHASE_META[phaseId].label.toLowerCase()} workstream managed by ${summary.coordinator}.`,
        status:
          idx < phaseIdx ? 'completed' : idx === phaseIdx ? 'in_progress' : 'pending',
        dueDate: summary.moveDate,
        owner: summary.coordinator,
        category: phaseId === 'pre-move' ? 'immigration' : phaseId === 'in-transit' ? 'logistics' : 'compliance',
      },
    ],
  }));

  return {
    id: summary.id,
    employee: {
      name: summary.employeeName,
      role: summary.role,
      department: '—',
      origin: summary.origin,
      originCode: summary.originCode,
      destination: summary.destination,
      destinationCode: summary.destinationCode,
      moveDate: summary.moveDate,
      dependents: 0,
      policyTier: 'Standard',
      coordinator: summary.coordinator,
    },
    summary: `Relocation from ${summary.origin} to ${summary.destination}. Managed by ${summary.coordinator}.`,
    status: summary.status,
    currentPhase: summary.currentPhase,
    phases,
    complianceCheckpoints: [
      {
        id: `${summary.id}-cc`,
        phaseId: summary.currentPhase,
        title: 'Phase compliance review',
        description: 'Full compliance checklist available in detailed roadmap view.',
        status: summary.status === 'At risk' ? 'at_risk' : summary.status === 'Completed' ? 'passed' : 'pending',
      },
    ],
    vendors: [
      {
        id: `${summary.id}-v`,
        phaseId: summary.currentPhase,
        category: 'Immigration',
        description: 'Visa and work authorization support',
        vendorStatus: 'assigned',
        vendorName: 'Preferred vendor',
      },
    ],
    keyDates: [{ label: 'Target move date', date: summary.moveDate }],
    riskFlags: summary.riskNote ? [summary.riskNote] : [],
  };
}

export function phaseProgress(phase: RoadmapPhase): number {
  if (phase.milestones.length === 0) return 0;
  const done = phase.milestones.filter((m) => m.status === 'completed').length;
  return Math.round((done / phase.milestones.length) * 100);
}

export function overallProgress(roadmap: MoveRoadmap): number {
  const all = roadmap.phases.flatMap((p) => p.milestones);
  if (all.length === 0) return 0;
  const done = all.filter((m) => m.status === 'completed').length;
  const inProg = all.filter((m) => m.status === 'in_progress').length;
  return Math.round(((done + inProg * 0.5) / all.length) * 100);
}

export function countByStatus(roadmap: MoveRoadmap) {
  const all = roadmap.phases.flatMap((p) => p.milestones);
  return {
    completed: all.filter((m) => m.status === 'completed').length,
    inProgress: all.filter((m) => m.status === 'in_progress').length,
    pending: all.filter((m) => m.status === 'pending').length,
    blocked: all.filter((m) => m.status === 'blocked').length,
    total: all.length,
  };
}

export function countRoadmapsByStatus(roadmaps: RoadmapSummary[]) {
  return {
    onTrack: roadmaps.filter((r) => r.status === 'On track').length,
    atRisk: roadmaps.filter((r) => r.status === 'At risk').length,
    completed: roadmaps.filter((r) => r.status === 'Completed').length,
    total: roadmaps.length,
  };
}

export function complianceForPhase(roadmap: MoveRoadmap, phaseId: PhaseId): ComplianceCheckpoint[] {
  return roadmap.complianceCheckpoints.filter((c) => c.phaseId === phaseId);
}

export function vendorsForPhase(roadmap: MoveRoadmap, phaseId: PhaseId): VendorSlot[] {
  return roadmap.vendors.filter((v) => v.phaseId === phaseId);
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
