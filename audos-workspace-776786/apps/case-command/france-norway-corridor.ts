/**
 * France → Norway corridor knowledge base for Case Command v0.
 * Structured timeline with non-obvious requirements flagged inline.
 */

export type EmployeeType = 'eea' | 'non-eea';
export type CorridorId = 'france-norway';

export interface TimelineItem {
  id: string;
  title: string;
  description: string;
  /** ISO date or relative label when move date unknown */
  deadline?: string;
  deadlineLabel?: string;
  /** Explicit dependency chain — e.g. blocks payroll */
  deadlineDependency?: string;
  owner: string;
  isNonObvious: boolean;
  flagReason?: string;
  /** Shown only for this employee type when set */
  employeeTypes?: EmployeeType[];
}

export interface TimelinePhase {
  id: string;
  name: string;
  description: string;
  items: TimelineItem[];
}

export interface MoveTimeline {
  corridor: CorridorId;
  corridorLabel: string;
  employeeType: EmployeeType;
  employeeTypeLabel: string;
  moveDate: string;
  generatedAt: string;
  phases: TimelinePhase[];
  insiderFlags: string[];
}

export const CORRIDOR_OPTIONS = [
  { id: 'france-norway' as const, label: 'France → Norway', origin: 'France', destination: 'Norway' },
];

export const EMPLOYEE_TYPE_OPTIONS: { id: EmployeeType; label: string; description: string }[] = [
  {
    id: 'eea',
    label: 'EEA national',
    description: 'EU/EEA citizen (e.g. French national) — right to reside, but Norway-specific steps still apply',
  },
  {
    id: 'non-eea',
    label: 'Non-EEA national',
    description: 'Requires a Norwegian residence permit before or upon arrival — longer lead time',
  },
];

function addDays(isoDate: string, days: number): string {
  const d = new Date(isoDate + 'T12:00:00');
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function appliesToEmployee(item: TimelineItem, employeeType: EmployeeType): boolean {
  if (!item.employeeTypes || item.employeeTypes.length === 0) return true;
  return item.employeeTypes.includes(employeeType);
}

/** Build the France → Norway move timeline with corridor-specific insider flags. */
export function generateFranceNorwayTimeline(
  employeeType: EmployeeType,
  moveDate: string,
): MoveTimeline {
  const employeeTypeLabel =
    employeeType === 'eea' ? 'EEA national' : 'Non-EEA national';

  const firstPaycheckDate = addDays(moveDate, 14);

  const allPhases: TimelinePhase[] = [
    {
      id: 'pre-departure',
      name: 'Pre-departure',
      description: 'Actions in France before the employee boards — permit lead times and employer prep',
      items: [
        {
          id: 'eea-quirk-norway-not-eu',
          title: 'Norway is EEA, not EU — don\'t assume EU free-movement rules',
          description:
            'Norway is in the EEA but left the EU. French employees often expect Schengen/EU rules to cover everything. Norway still requires Folkeregister registration, a D-number, tax card, and (for EEA nationals) police registration — none of which are automatic from an EU passport alone.',
          deadline: addDays(moveDate, -30),
          deadlineLabel: 'Review before move — 30 days out',
          owner: 'HR',
          isNonObvious: true,
          flagReason: 'EEA-but-not-EU quirk — rules differ from intra-EU relocations',
          employeeTypes: ['eea'],
        },
        {
          id: 'residence-permit-non-eea',
          title: 'Apply for Norwegian residence permit (UDI)',
          description:
            'Non-EEA nationals need a valid residence permit tied to employment before relocating. Processing can take 4–8 weeks (sometimes longer). The employee cannot legally start work in Norway without it.',
          deadline: addDays(moveDate, -60),
          deadlineLabel: 'Target 60+ days before move',
          owner: 'Employee + Immigration counsel',
          isNonObvious: false,
          employeeTypes: ['non-eea'],
        },
        {
          id: 'a1-certificate',
          title: 'Obtain A1 certificate (social security) from French authorities',
          description:
            'If the employee remains on French payroll temporarily, request an A1 certificate from URSSAF. Norway is EEA so coordination applies, but the certificate must be in place before the move to avoid dual contributions.',
          deadline: addDays(moveDate, -21),
          deadlineLabel: '21 days before move',
          owner: 'HR / Payroll',
          isNonObvious: false,
        },
        {
          id: 'employer-prep-d-number',
          title: 'Brief employee: D-number is the first Norwegian ID to secure',
          description:
            'Before opening a bank account, signing a lease, or receiving payroll, the employee needs a D-number (temporary national ID) from Skatteetaten. HR should schedule the Skatteetaten appointment before arrival week — many downstream steps are blocked without it.',
          deadline: addDays(moveDate, -14),
          deadlineLabel: '14 days before move',
          owner: 'HR',
          isNonObvious: true,
          flagReason: 'D-number blocks bank, tax, and payroll — surface early',
        },
      ],
    },
    {
      id: 'arrival-week',
      name: 'Arrival week',
      description: 'First days in Norway — identity, registration, and housing',
      items: [
        {
          id: 'd-number-application',
          title: 'Apply for D-number at Skatteetaten (tax office)',
          description:
            'Book an appointment at Skatteetaten or a service centre (by appointment only in most municipalities). Bring passport, employment contract, and Norwegian address proof if available. The D-number is required before bank account, tax card, and most contracts.',
          deadline: addDays(moveDate, 3),
          deadlineLabel: 'Within 3 days of arrival',
          deadlineDependency: 'Blocks: bank account, tax card, Folkeregister',
          owner: 'Employee',
          isNonObvious: true,
          flagReason: 'D-number — required before many downstream steps',
        },
        {
          id: 'police-registration-eea',
          title: 'Police registration (EEA nationals only)',
          description:
            'EEA citizens must register with the police in their municipality of residence within 3 months of arrival. This is separate from Folkeregister and is commonly missed — many assume an EU passport alone is sufficient. Failure to register can affect residence rights.',
          deadline: addDays(moveDate, 14),
          deadlineLabel: 'Within 14 days of arrival (must complete within 3 months)',
          owner: 'Employee',
          isNonObvious: true,
          flagReason: 'Police registration — required for EEA nationals, often assumed unnecessary',
          employeeTypes: ['eea'],
        },
        {
          id: 'folkeregister',
          title: 'Register address in Folkeregisteret',
          description:
            'Register residential address with the National Population Register. Requires D-number and a Norwegian address. Needed for healthcare (fastlege), municipal services, and official correspondence.',
          deadline: addDays(moveDate, 7),
          deadlineLabel: 'Within 7 days of securing housing',
          deadlineDependency: 'Requires D-number',
          owner: 'Employee',
          isNonObvious: false,
        },
        {
          id: 'bank-account',
          title: 'Open Norwegian bank account',
          description:
            'Norwegian banks require a D-number and proof of address. Payroll cannot be paid to a foreign account long-term. Plan 1–2 weeks after D-number issuance.',
          deadline: addDays(moveDate, 10),
          deadlineLabel: 'Within 10 days of arrival',
          deadlineDependency: 'Requires D-number',
          owner: 'Employee',
          isNonObvious: false,
        },
      ],
    },
    {
      id: 'employment-payroll',
      name: 'Employment & payroll',
      description: 'Tax and payroll setup — timing is critical for first paycheck',
      items: [
        {
          id: 'tax-card-skattkort',
          title: 'Obtain tax card (skattekort) before first paycheck',
          description:
            'The employee must apply for a tax card via Skatteetaten (Altinn or in person) after receiving a D-number. Without it, the employer must withhold 50% of salary. Apply at least 2 weeks before the first payroll date.',
          deadline: addDays(firstPaycheckDate, -14),
          deadlineLabel: `14 days before first paycheck (${firstPaycheckDate})`,
          deadlineDependency: 'Must complete before first paycheck — employer withholds 50% without tax card',
          owner: 'Employee + HR',
          isNonObvious: true,
          flagReason: 'Tax card timing — payroll dependency most HR generalists miss',
        },
        {
          id: 'first-paycheck',
          title: 'First Norwegian paycheck',
          description:
            'Confirm tax card is active in Altinn before payroll run. If no tax card, expect 50% emergency withholding — employee will need to file for refund.',
          deadline: firstPaycheckDate,
          deadlineLabel: 'First payroll date',
          deadlineDependency: 'Depends on tax card being issued',
          owner: 'HR / Payroll',
          isNonObvious: false,
        },
        {
          id: 'id-porten',
          title: 'Set up ID-porten / BankID',
          description:
            'Norwegian digital identity for accessing Altinn, tax services, and government portals. Usually obtained through a Norwegian bank.',
          deadline: addDays(moveDate, 21),
          deadlineLabel: 'Within 3 weeks of arrival',
          owner: 'Employee',
          isNonObvious: false,
        },
      ],
    },
    {
      id: 'settling-in',
      name: 'Settling in',
      description: 'Healthcare, housing, and ongoing compliance',
      items: [
        {
          id: 'fastlege',
          title: 'Register with a GP (fastlege)',
          description:
            'After Folkeregister registration, the employee can choose a general practitioner via helsenorge.no. Waiting lists vary by municipality — Oslo and Bergen can take weeks.',
          deadline: addDays(moveDate, 30),
          deadlineLabel: 'Within 30 days of arrival',
          owner: 'Employee',
          isNonObvious: false,
        },
        {
          id: 'driving-licence',
          title: 'Exchange French driving licence (if applicable)',
          description:
            'EU/EEA licences can be used temporarily. Exchange to Norwegian licence within 12 months if becoming permanent resident. Not required immediately but plan before expiry.',
          deadline: addDays(moveDate, 90),
          deadlineLabel: 'Within 90 days if driving',
          owner: 'Employee',
          isNonObvious: false,
          employeeTypes: ['eea'],
        },
        {
          id: 'permanent-residence-check',
          title: 'Track residence permit renewal / permanent basis',
          description:
            'Non-EEA permits are time-limited. Calendar renewal 3 months before expiry. After 3 years of continuous legal residence, may qualify for permanent residence.',
          deadline: addDays(moveDate, 335),
          deadlineLabel: '11 months after arrival — plan renewal',
          owner: 'HR + Employee',
          isNonObvious: false,
          employeeTypes: ['non-eea'],
        },
      ],
    },
  ];

  const phases = allPhases
    .map((phase) => ({
      ...phase,
      items: phase.items.filter((item) => appliesToEmployee(item, employeeType)),
    }))
    .filter((phase) => phase.items.length > 0);

  const insiderFlags = phases
    .flatMap((p) => p.items)
    .filter((item) => item.isNonObvious)
    .map((item) => item.flagReason || item.title);

  return {
    corridor: 'france-norway',
    corridorLabel: 'France → Norway',
    employeeType,
    employeeTypeLabel,
    moveDate,
    generatedAt: new Date().toISOString(),
    phases,
    insiderFlags,
  };
}

export function parseTimeline(raw: string | undefined | null): MoveTimeline | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && Array.isArray(parsed.phases)) return parsed as MoveTimeline;
    return null;
  } catch {
    return null;
  }
}

export function getFirstAction(timeline: MoveTimeline): { action: string; deadline: string } {
  const firstItem = timeline.phases[0]?.items[0];
  return {
    action: firstItem?.title || 'Review move timeline',
    deadline: firstItem?.deadline || timeline.moveDate,
  };
}
