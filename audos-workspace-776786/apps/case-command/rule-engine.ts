/**
 * Case Command deterministic rule engine — France → Norway corridor (v0).
 *
 * ALL requirements are hardcoded authored constants. No LLM is involved in
 * deciding what appears, in what order, or with what tags. Identical inputs
 * (employee type + move date + today) always produce identical output.
 *
 * Feasibility logic (per build brief):
 *   action_by_date = move_date + offset_weeks * 7 days
 *   red   → action_by_date <= today (window already passed)
 *   amber → action_by_date < today + 7 days (tight, < 7 days of buffer)
 *   green → otherwise (on track)
 *   critical banner → employee is non-EEA AND move_date − today < 42 days
 */

export type EmployeeType = 'eea' | 'non-eea';
export type Owner = 'HR' | 'Employee' | 'Both';
export type Feasibility = 'green' | 'amber' | 'red';

/** Corridors the engine can run. */
export type CorridorId = 'france-norway' | 'spain-ireland';

/**
 * What the requirement offsets are measured FROM.
 *
 * Free-movement corridors are 'move-date': the employee travels, then registers,
 * so everything hangs off the day they arrive. Employment-permit corridors are
 * 'contract-signed': the permit and entry visa must both be granted BEFORE travel,
 * so the clock starts at contract signature and the move date is an OUTPUT of that
 * chain rather than its anchor. Mixing the two is exactly what makes a permit case
 * look fine at six weeks out when it is already unrecoverable.
 */
export type AnchorKind = 'move-date' | 'contract-signed';

export interface RequirementRule {
  id: string;
  title: string;
  description: string;
  /** Weeks relative to the move date. Negative = before, positive = after, 0 = move date. */
  offsetWeeks: number;
  owner: Owner;
  /** Marked with a distinct visual treatment — the items HR generalists miss. */
  nonObvious: boolean;
  /** Long-lead-time permit items (non-EEA UDI track). */
  criticalLeadTime?: boolean;
  /** Explicit dependency chain note. */
  dependencyNote?: string;
  /** 'all' applies to every employee type; 'non-eea' only to non-EEA nationals. */
  appliesTo: 'all' | 'non-eea';
}

export interface CaseRequirement extends RequirementRule {
  /** ISO date (YYYY-MM-DD) the action must be started/completed by. */
  actionByDate: string;
  /** Human label for the offset, e.g. "T−8 weeks" / "T+2 weeks" / "T−0 (move date)". */
  offsetLabel: string;
  feasibility: Feasibility;
}

export interface CaseCheckResult {
  corridor: CorridorId;
  corridorLabel: string;
  employeeType: EmployeeType;
  employeeTypeLabel: string;
  /**
   * The anchor date the check was run against. Named `moveDate` for backwards
   * compatibility with CorridorCheck.tsx; for a 'contract-signed' corridor it is
   * the contract-signature date. `anchorKind` says which.
   */
  moveDate: string;
  anchorKind: AnchorKind;
  today: string;
  /** Timeline is not achievable → shown ABOVE the requirements list. */
  criticalBanner: string | null;
  /** Anchor date already in the past. */
  moveDatePassedWarning: string | null;
  /** Anchor date today or within 1 week → overdue/urgent summary. */
  urgentSummary: string | null;
  requirements: CaseRequirement[];
  counts: { green: number; amber: number; red: number; total: number };
}

/** A corridor's authored ruleset plus how its timeline is anchored. */
export interface CorridorDefinition {
  id: CorridorId;
  label: string;
  anchor: AnchorKind;
  requirements: RequirementRule[];
  employeeTypeLabel: (t: EmployeeType) => string;
  /**
   * Days of runway below which the timeline is flagged as not achievable.
   *
   * Per-corridor on purpose: before AIQ-1752 a single hardcoded 42 was applied to
   * every case, which is a six-week rule of thumb for the Norwegian UDI track and
   * badly wrong for an Irish employment permit. See each corridor's own note.
   */
  criticalRunwayDays: number;
  /** Whether the banner applies to this employee type at all. */
  criticalBannerApplies: (t: EmployeeType) => boolean;
  criticalBannerText: string;
}

export const EMPLOYEE_TYPE_OPTIONS: { id: EmployeeType; label: string; description: string }[] = [
  {
    id: 'eea',
    label: 'EEA national',
    description: 'EU/EEA citizen (e.g. French national) — right to reside, but Norway-specific steps still apply',
  },
  {
    id: 'non-eea',
    label: 'Non-EEA national resident in France',
    description: 'Requires a Norwegian residence permit via UDI before starting work — much longer lead time',
  },
];

/**
 * The authoritative France → Norway requirement set. Authored order is the
 * deterministic tie-breaker when two items share the same action-by date.
 */
export const FRANCE_NORWAY_REQUIREMENTS: RequirementRule[] = [
  {
    id: 'udi-work-permit',
    title: 'Apply for Norwegian work permit / residence permit for skilled workers via UDI',
    description:
      'Non-EEA nationals cannot legally start work in Norway without a residence permit for skilled workers. UDI processing typically takes 8–16 weeks — this is the single longest lead-time item in the whole move.',
    offsetWeeks: -16,
    owner: 'Both',
    nonObvious: false,
    criticalLeadTime: true,
    dependencyNote: 'Blocks the entire move — nothing else matters if the permit is late',
    appliesTo: 'non-eea',
  },
  {
    id: 'udi-employer-letter',
    title: 'Provide employer letter of employment confirmation for the UDI application',
    description:
      'UDI requires a formal offer/confirmation of employment from the Norwegian employer as part of the skilled-worker application. Prepare and send it early so it never blocks the permit file.',
    offsetWeeks: -14,
    owner: 'HR',
    nonObvious: false,
    appliesTo: 'non-eea',
  },
  {
    id: 'passport-validity',
    title: 'Check passport validity',
    description:
      'Confirm the employee\u2019s passport is valid well beyond the move date. Renewals from abroad add weeks — check now, not at the airport.',
    offsetWeeks: -12,
    owner: 'Employee',
    nonObvious: false,
    appliesTo: 'all',
  },
  {
    id: 'credential-recognition',
    title: 'Educational credential recognition (if applicable)',
    description:
      'Some roles require Norwegian recognition of foreign qualifications (NOKUT or sector regulator). Confirm whether the role needs it and start the assessment now.',
    offsetWeeks: -12,
    owner: 'Employee',
    nonObvious: false,
    appliesTo: 'non-eea',
  },
  {
    id: 'norway-eea-not-eu',
    title: 'Norway is EEA, not EU — don\u2019t assume EU free-movement rules cover everything',
    description:
      'Norway left EU accession on the table decades ago: it is in the EEA and Schengen, but NOT the EU. French employees (and HR) often assume intra-EU rules apply. Norway still requires a D-number, skattekort, and — for EEA nationals — police registration. None of these are automatic from an EU passport.',
    offsetWeeks: -12,
    owner: 'HR',
    nonObvious: true,
    appliesTo: 'all',
  },
  {
    id: 'housing-research',
    title: 'Research housing options',
    description:
      'Start the housing search in the destination city. Rental markets in Oslo, Bergen and Stavanger move fast, and a Norwegian address is needed for several registrations later in the timeline.',
    offsetWeeks: -10,
    owner: 'Both',
    nonObvious: false,
    appliesTo: 'all',
  },
  {
    id: 'supporting-documents',
    title: 'Gather supporting documents — French police clearance, medical certificate if required',
    description:
      'Collect the documents the UDI application and onboarding may require: French police clearance (casier judiciaire), medical certificate if the role requires it, and certified translations where needed.',
    offsetWeeks: -10,
    owner: 'Employee',
    nonObvious: false,
    appliesTo: 'non-eea',
  },
  {
    id: 'd-number',
    title: 'Apply for D-number at the Norwegian Tax Administration (Skatteetaten)',
    description:
      'The D-number is the temporary Norwegian ID everything else hangs off: no D-number means no bank account, no skattekort, and no payroll. Book the Skatteetaten appointment now — HR coordinates, the employee attends with passport and employment contract.',
    offsetWeeks: -8,
    owner: 'Both',
    nonObvious: true,
    dependencyNote: 'Blocks: bank account, skattekort, payroll',
    appliesTo: 'all',
  },
  {
    id: 'eea-right-of-residence',
    title: 'Register EU/EEA right of residence at Skattekontoret',
    description:
      'EEA nationals must register their right of residence with the tax office (Skattekontoret) — an EU passport alone is not enough. This step is routinely missed because it has no equivalent in intra-EU moves.',
    offsetWeeks: -8,
    owner: 'Employee',
    nonObvious: true,
    appliesTo: 'all',
  },
  {
    id: 'bank-account',
    title: 'Open Norwegian bank account',
    description:
      'Norwegian banks require a D-number before opening an account, and payroll cannot be paid to a foreign account long-term. Start as soon as the D-number is issued.',
    offsetWeeks: -6,
    owner: 'Employee',
    nonObvious: false,
    dependencyNote: 'Requires D-number',
    appliesTo: 'all',
  },
  {
    id: 'bronnoysund-registration',
    title: 'Verify Norwegian employer Brønnøysund registration is complete',
    description:
      'Confirm the employing entity is properly registered in the Brønnøysund Register Centre. Payroll reporting (A-melding) and withholding tax registration both depend on it.',
    offsetWeeks: -6,
    owner: 'HR',
    nonObvious: false,
    appliesTo: 'all',
  },
  {
    id: 'a-melding',
    title: 'Set up A-melding (employer payroll reporting)',
    description:
      'A-melding is Norway\u2019s mandatory monthly employer report of salary, tax deductions and employment to the authorities. It MUST be active before the first paycheck runs — setting it up after the fact is a compliance breach, not a formality.',
    offsetWeeks: -5,
    owner: 'HR',
    nonObvious: true,
    dependencyNote: 'Must be active before first paycheck',
    appliesTo: 'all',
  },
  {
    id: 'skattekort',
    title: 'Apply for skattekort (tax card)',
    description:
      'The skattekort must be in place BEFORE the first paycheck, not after. Without it the employer is legally required to withhold 50% of salary. Apply via Skatteetaten once the D-number exists — HR coordinates the timing against the payroll calendar.',
    offsetWeeks: -4,
    owner: 'Both',
    nonObvious: true,
    dependencyNote: 'Requires D-number · must precede first paycheck',
    appliesTo: 'all',
  },
  {
    id: 'police-registration',
    title: 'Police registration for EEA nationals',
    description:
      'EEA nationals are legally required to register with the Norwegian police within 3 months of arrival. Appointment slots in Oslo can run out weeks ahead — book now. This is the item HR teams most often assume an EU passport makes unnecessary.',
    offsetWeeks: -4,
    owner: 'Employee',
    nonObvious: true,
    dependencyNote: 'Legal deadline: within 3 months of arrival',
    appliesTo: 'all',
  },
  {
    id: 'withholding-tax',
    title: 'Withholding tax registration',
    description:
      'Register the employment for Norwegian withholding tax so deductions run correctly from the first payroll cycle.',
    offsetWeeks: -3,
    owner: 'HR',
    nonObvious: false,
    appliesTo: 'all',
  },
  {
    id: 'right-to-work',
    title: 'Right-to-work verification',
    description:
      'Verify and document the employee\u2019s right to work in Norway before the start date — permit or registered EEA residence, checked and filed.',
    offsetWeeks: -2,
    owner: 'HR',
    nonObvious: false,
    appliesTo: 'all',
  },
  {
    id: 'payroll-readiness',
    title: 'Confirm D-number received and skattekort active',
    description:
      'Move-date gate check: payroll cannot run without BOTH the D-number and an active skattekort. Confirm both are in place today, before the first payroll cycle starts.',
    offsetWeeks: 0,
    owner: 'HR',
    nonObvious: false,
    dependencyNote: 'Payroll cannot run without both',
    appliesTo: 'all',
  },
  {
    id: 'police-registration-confirm',
    title: 'Confirm police registration completed',
    description:
      'Post-arrival check: confirm the police registration appointment actually happened and the confirmation document is on file.',
    offsetWeeks: 2,
    owner: 'Employee',
    nonObvious: false,
    appliesTo: 'all',
  },
  {
    id: 'first-paycheck-check',
    title: 'Verify first paycheck has correct tax deduction',
    description:
      'Check the first Norwegian payslip: correct skattekort rate applied, no 50% emergency withholding. If deductions are wrong, fix them in the next A-melding cycle immediately.',
    offsetWeeks: 4,
    owner: 'HR',
    nonObvious: false,
    appliesTo: 'all',
  },
];

/**
 * Spain → Ireland, Critical Skills Employment Permit (AIQ-1752).
 *
 * ⚠️ REPRESENTATIVE / AUTHORING content, not SME-verified — mirrors the caveat on
 * corridors/ES_IE/pathways/CSEP_2026/v1.yaml, from which these durations are taken.
 * Nothing here may be rendered as legal advice in ReloPass's own voice.
 *
 * Offsets run FORWARD from contract signature (T+n), the inverse of France→Norway.
 * The step durations mirror the backend corridor: permit application 35d, grant 7d,
 * 'D' visa application 40d, grant 7d, travel 1d — 104 days to arrival before any
 * in-country step begins.
 *
 * THE LOAD-BEARING FACT: the employment permit is the EMPLOYER's application to
 * DETE, not the employee's. The backend already models this
 * (responsible_party: EMPLOYER on JOB_OFFER_CONTRACT and
 * EMPLOYMENT_PERMIT_APPLICATION, resolved by relopass/corridors/responsibility.py);
 * this prototype was the only surface still missing it.
 */
export const SPAIN_IRELAND_REQUIREMENTS: RequirementRule[] = [
  {
    id: 'csep-contract-signed',
    title: 'Signed employment contract (2-year minimum, direct employment)',
    description:
      'A Critical Skills permit requires a contract of at least 24 months with the Irish entity directly. Contractor or agency structures do not qualify. Everything below is measured from the day this is signed.',
    offsetWeeks: 0,
    owner: 'HR',
    nonObvious: false,
    appliesTo: 'non-eea',
  },
  {
    id: 'csep-permit-application',
    title: 'Submit the Critical Skills Employment Permit application to DETE',
    description:
      'Filed via Employment Permits Online. This is the EMPLOYER’s application, not the employee’s — HR owns it. Typical processing runs several weeks and nothing downstream can start until it is granted.',
    offsetWeeks: 1,
    owner: 'HR',
    nonObvious: true,
    criticalLeadTime: true,
    dependencyNote: 'Blocks the visa application, which blocks travel',
    appliesTo: 'non-eea',
  },
  {
    id: 'csep-permit-granted',
    title: 'Employment permit granted by DETE',
    description:
      'NON-OBVIOUS: the permit is a labour authorisation from DETE, not immigration permission. It does not by itself allow entry to or residence in Ireland — the entry visa is a separate application to a different authority.',
    offsetWeeks: 6,
    owner: 'HR',
    nonObvious: true,
    criticalLeadTime: true,
    appliesTo: 'non-eea',
  },
  {
    id: 'ie-d-visa-application',
    title: 'Apply for the long-stay ‘D’ Employment visa',
    description:
      'NON-OBVIOUS: Ireland is outside Schengen, so a Spanish residence card grants no entry right. A visa-required national must hold the ‘D’ visa BEFORE travelling — a mover who has lived in the EU for years will not expect this.',
    offsetWeeks: 7,
    owner: 'Employee',
    nonObvious: true,
    criticalLeadTime: true,
    dependencyNote: 'Cannot start until the permit is granted',
    appliesTo: 'non-eea',
  },
  {
    id: 'ie-d-visa-granted',
    title: '‘D’ Employment visa granted (entry authorisation)',
    description:
      'The entry authorisation itself. Travel booked before this is granted is at risk.',
    offsetWeeks: 13,
    owner: 'Employee',
    nonObvious: false,
    criticalLeadTime: true,
    appliesTo: 'non-eea',
  },
  {
    id: 'ie-spanish-ltr-does-not-transfer',
    title: 'Confirm the employee understands Spanish residence does not transfer',
    description:
      'NON-OBVIOUS: Ireland is not bound by the EU Long-Term Residents Directive 2003/109/EC, so EU long-term residence or a TIE held in Spain confers no entry or work right in Ireland. The full permit + visa + registration sequence still applies.',
    offsetWeeks: 1,
    owner: 'HR',
    nonObvious: true,
    appliesTo: 'non-eea',
  },
  {
    id: 'ie-travel',
    title: 'Travel to Ireland',
    description:
      'Only now can the employee travel. Everything above had to complete first — this is the point the free-movement mental model gets wrong.',
    offsetWeeks: 15,
    owner: 'Employee',
    nonObvious: false,
    appliesTo: 'non-eea',
  },
  {
    id: 'ie-irp-registration',
    title: 'Register immigration permission — IRP card / Stamp 1',
    description:
      'Registration with Immigration Service Delivery (Burgh Quay for Dublin) within 90 days of arrival. Appointment slots are the constraint, not the paperwork.',
    offsetWeeks: 16,
    owner: 'Employee',
    nonObvious: false,
    appliesTo: 'non-eea',
  },
  {
    id: 'ie-ppsn',
    title: 'Obtain a PPSN (Personal Public Service Number)',
    description:
      'Needed before the employment can be registered with Revenue. Applied for after arrival via the Department of Social Protection.',
    offsetWeeks: 16,
    owner: 'Employee',
    nonObvious: false,
    appliesTo: 'non-eea',
  },
  {
    id: 'ie-revenue-registration',
    title: 'Register the employment with Revenue (myAccount / RPN)',
    description:
      'NON-OBVIOUS: without a Revenue Payroll Notification in place before the first pay run, PAYE is deducted at the emergency rate — the Irish analogue of the "tax card before first pay" trap.',
    offsetWeeks: 18,
    owner: 'Both',
    nonObvious: true,
    dependencyNote: 'Requires the PPSN',
    appliesTo: 'non-eea',
  },
  {
    id: 'ie-bank-account',
    title: 'Open an Irish bank account',
    description:
      'NON-OBVIOUS: proof of address is a chicken-and-egg barrier on arrival. Most movers bridge with a digital account until a traditional one can be opened.',
    offsetWeeks: 18,
    owner: 'Employee',
    nonObvious: true,
    appliesTo: 'non-eea',
  },
  {
    id: 'ie-health-cover',
    title: 'Arrange private health insurance and register with a GP',
    description:
      'NON-OBVIOUS: public healthcare eligibility hinges on an "ordinarily resident" test and GP visits are normally paid out of pocket, so a newcomer is effectively on private cover at first. Proof of cover is also needed for immigration registration.',
    offsetWeeks: 16,
    owner: 'Employee',
    nonObvious: true,
    appliesTo: 'non-eea',
  },
];

// ─── Deterministic date helpers (UTC-day arithmetic, no timezones) ───────────

/** Parse 'YYYY-MM-DD' into an integer count of days since the Unix epoch. */
export function isoToEpochDays(iso: string): number {
  const [y, m, d] = iso.split('-').map((n) => parseInt(n, 10));
  return Math.round(Date.UTC(y, m - 1, d) / 86400000);
}

/** Convert epoch-days back to 'YYYY-MM-DD'. */
export function epochDaysToIso(days: number): string {
  return new Date(days * 86400000).toISOString().slice(0, 10);
}

/** Today's date as 'YYYY-MM-DD' in the viewer's local calendar. */
export function localTodayIso(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function offsetLabel(offsetWeeks: number, anchor: AnchorKind): string {
  const zeroLabel = anchor === 'contract-signed'
    ? 'T\u22120 (contract signed)'
    : 'T\u22120 (move date)';
  if (offsetWeeks === 0) return zeroLabel;
  if (offsetWeeks < 0) return `T\u2212${Math.abs(offsetWeeks)} weeks`;
  return `T+${offsetWeeks} weeks`;
}

function feasibilityFor(actionByDays: number, todayDays: number): Feasibility {
  if (actionByDays <= todayDays) return 'red';
  if (actionByDays < todayDays + 7) return 'amber';
  return 'green';
}

// \u2500\u2500\u2500 Corridor registry \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

/**
 * How many days of runway a corridor needs, derived from its own authored offsets
 * so it can never contradict its own steps.
 *
 * What "runway" means depends on where the timeline is anchored, and getting this
 * backwards is the easy mistake:
 *
 * - 'move-date' \u2014 the anchor is the day the employee starts, and the work sits
 *   BEFORE it at negative offsets. The runway is how far back the earliest one
 *   reaches: |min offset|.
 * - 'contract-signed' \u2014 the anchor is signature, and the work runs FORWARD from it
 *   at positive offsets. The runway is how far the chain extends: max offset.
 *
 * The two are then compared against different intervals \u2014 see runCaseCheck.
 */
function derivedRunwayDays(requirements: RequirementRule[], anchor: AnchorKind): number {
  const offsets = requirements.map((r) => r.offsetWeeks);
  const weeks = anchor === 'contract-signed'
    ? Math.max(0, ...offsets)
    : Math.abs(Math.min(0, ...offsets));
  return weeks * 7;
}

export const CORRIDORS: Record<CorridorId, CorridorDefinition> = {
  'france-norway': {
    id: 'france-norway',
    label: 'France \u2192 Norway',
    anchor: 'move-date',
    requirements: FRANCE_NORWAY_REQUIREMENTS,
    employeeTypeLabel: (t) =>
      t === 'eea' ? 'EEA national' : 'Non-EEA national (resident in France)',
    // DERIVED from this corridor's own offsets: the earliest requirement sits at
    // T−16 weeks (the UDI work permit), so 112 days of runway are needed before the
    // move date. This REPLACES the hardcoded 42 and is a deliberate behaviour change
    // — the v0 6-week figure was shorter than the corridor's own permit step, so the
    // banner could stay silent while the longest-lead item was already unachievable.
    criticalRunwayDays: derivedRunwayDays(FRANCE_NORWAY_REQUIREMENTS, 'move-date'),
    criticalBannerApplies: (t) => t === 'non-eea',
    criticalBannerText:
      'Work permit processing typically takes 8\u201316 weeks. This timeline may not be achievable. Consult an immigration lawyer before proceeding.',
  },
  'spain-ireland': {
    id: 'spain-ireland',
    label: 'Spain \u2192 Ireland',
    anchor: 'contract-signed',
    requirements: SPAIN_IRELAND_REQUIREMENTS,
    employeeTypeLabel: () => 'Non-EEA national (resident in Spain)',
    // DERIVED from this corridor's own offsets. The CSEP chain runs forward from
    // signature to Revenue registration (~18 weeks), of which ~15 must elapse before
    // the employee may even travel. Mirrors the backend's required_lead_time_days for
    // ES_IE; if the authored offsets change, this moves with them.
    criticalRunwayDays: derivedRunwayDays(SPAIN_IRELAND_REQUIREMENTS, 'contract-signed'),
    // Every ES_IE case is a third-country national by construction.
    criticalBannerApplies: () => true,
    criticalBannerText:
      'A Critical Skills Employment Permit plus the long-stay \u2018D\u2019 visa typically take around 15 weeks before the employee can travel. This start date may not be achievable. Confirm with the immigration adviser handling this case before committing to it.',
  },
};

// ─── The engine ──────────────────────────────────────────────────────────────

/**
 * Run the deterministic case check. Pure function: same (employeeType,
 * anchorDate, today, corridorId) always returns the exact same result object.
 *
 * @param employeeType 'eea' | 'non-eea'
 * @param anchorDate   ISO 'YYYY-MM-DD'. For a 'move-date' corridor this is the day
 *                     the employee starts in the destination; for a
 *                     'contract-signed' corridor it is the contract-signature date,
 *                     and arrival becomes an OUTPUT of the chain rather than its
 *                     anchor.
 * @param today        ISO 'YYYY-MM-DD' — the evaluation date (defaults to local today)
 * @param corridorId   defaults to 'france-norway', so existing callers are unchanged
 */
export function runCaseCheck(
  employeeType: EmployeeType,
  anchorDate: string,
  today: string = localTodayIso(),
  corridorId: CorridorId = 'france-norway',
): CaseCheckResult {
  const corridor = CORRIDORS[corridorId];
  const anchorDays = isoToEpochDays(anchorDate);
  const todayDays = isoToEpochDays(today);

  const requirements: CaseRequirement[] = corridor.requirements
    .map((rule, authoredIndex) => ({ rule, authoredIndex }))
    .filter(({ rule }) => rule.appliesTo === 'all' || rule.appliesTo === employeeType)
    .map(({ rule, authoredIndex }) => {
      const actionByDays = anchorDays + rule.offsetWeeks * 7;
      return {
        ...rule,
        actionByDate: epochDaysToIso(actionByDays),
        offsetLabel: offsetLabel(rule.offsetWeeks, corridor.anchor),
        feasibility: feasibilityFor(actionByDays, todayDays),
        _sortDays: actionByDays,
        _authoredIndex: authoredIndex,
      };
    })
    .sort((a, b) => a._sortDays - b._sortDays || a._authoredIndex - b._authoredIndex)
    .map(({ _sortDays, _authoredIndex, ...req }) => req);

  const counts = requirements.reduce(
    (acc, r) => {
      acc[r.feasibility] += 1;
      acc.total += 1;
      return acc;
    },
    { green: 0, amber: 0, red: 0, total: 0 },
  );

  const daysToAnchor = anchorDays - todayDays;

  // Which interval the runway is measured against depends on where the corridor is
  // anchored, and the two run in OPPOSITE directions:
  //
  //   move-date       \u2192 time UNTIL the move. The work sits before it, so a nearer
  //                     move date is the risk.
  //   contract-signed \u2192 time ELAPSED SINCE signature. The chain runs forward from
  //                     it, so a signature that hasn't had time to play out is the
  //                     risk \u2014 including one still in the future, where nothing has
  //                     started at all.
  //
  // Measuring a contract-anchored corridor against "time until" would invert the
  // meaning and make a contract signed further ahead look safer.
  const runwayInterval =
    corridor.anchor === 'contract-signed' ? -daysToAnchor : daysToAnchor;

  const criticalBanner =
    corridor.criticalBannerApplies(employeeType)
      && runwayInterval < corridor.criticalRunwayDays
      ? corridor.criticalBannerText
      : null;

  const anchorNoun = corridor.anchor === 'contract-signed' ? 'contract date' : 'move date';
  const moveDatePassedWarning =
    daysToAnchor < 0
      ? `This ${anchorNoun} has passed. Showing requirements as of ${anchorDate} for reference.`
      : null;

  const overdueOrUrgent = counts.red + counts.amber;
  const urgentSummary =
    daysToAnchor >= 0 && daysToAnchor <= 7 && overdueOrUrgent > 0
      ? `${overdueOrUrgent} requirement${overdueOrUrgent === 1 ? ' is' : 's are'} overdue or critically urgent.`
      : null;

  return {
    corridor: corridor.id,
    corridorLabel: corridor.label,
    employeeType,
    employeeTypeLabel: corridor.employeeTypeLabel(employeeType),
    moveDate: anchorDate,
    anchorKind: corridor.anchor,
    today,
    criticalBanner,
    moveDatePassedWarning,
    urgentSummary,
    requirements,
    counts,
  };
}
