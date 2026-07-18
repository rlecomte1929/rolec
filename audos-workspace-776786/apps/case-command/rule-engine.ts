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
  corridor: 'france-norway';
  corridorLabel: string;
  employeeType: EmployeeType;
  employeeTypeLabel: string;
  moveDate: string;
  today: string;
  /** Non-EEA + move date < 6 weeks away → shown ABOVE the requirements list. */
  criticalBanner: string | null;
  /** Move date already in the past. */
  moveDatePassedWarning: string | null;
  /** Move date today or within 1 week → overdue/urgent summary. */
  urgentSummary: string | null;
  requirements: CaseRequirement[];
  counts: { green: number; amber: number; red: number; total: number };
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

function offsetLabel(offsetWeeks: number): string {
  if (offsetWeeks === 0) return 'T\u22120 (move date)';
  if (offsetWeeks < 0) return `T\u2212${Math.abs(offsetWeeks)} weeks`;
  return `T+${offsetWeeks} weeks`;
}

function feasibilityFor(actionByDays: number, todayDays: number): Feasibility {
  if (actionByDays <= todayDays) return 'red';
  if (actionByDays < todayDays + 7) return 'amber';
  return 'green';
}

// ─── The engine ──────────────────────────────────────────────────────────────

/**
 * Run the deterministic case check. Pure function: same (employeeType,
 * moveDate, today) always returns the exact same result object.
 *
 * @param employeeType 'eea' | 'non-eea'
 * @param moveDate ISO 'YYYY-MM-DD' — the date the employee starts in Norway
 * @param today ISO 'YYYY-MM-DD' — the evaluation date (defaults to local today)
 */
export function runCaseCheck(
  employeeType: EmployeeType,
  moveDate: string,
  today: string = localTodayIso(),
): CaseCheckResult {
  const moveDays = isoToEpochDays(moveDate);
  const todayDays = isoToEpochDays(today);

  const requirements: CaseRequirement[] = FRANCE_NORWAY_REQUIREMENTS
    .map((rule, authoredIndex) => ({ rule, authoredIndex }))
    .filter(({ rule }) => rule.appliesTo === 'all' || rule.appliesTo === employeeType)
    .map(({ rule, authoredIndex }) => {
      const actionByDays = moveDays + rule.offsetWeeks * 7;
      return {
        ...rule,
        actionByDate: epochDaysToIso(actionByDays),
        offsetLabel: offsetLabel(rule.offsetWeeks),
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

  const daysToMove = moveDays - todayDays;

  const criticalBanner =
    employeeType === 'non-eea' && daysToMove < 42
      ? 'Work permit processing typically takes 8\u201316 weeks. This timeline may not be achievable. Consult an immigration lawyer before proceeding.'
      : null;

  const moveDatePassedWarning =
    daysToMove < 0
      ? `This move date has passed. Showing requirements as of ${moveDate} for reference.`
      : null;

  const overdueOrUrgent = counts.red + counts.amber;
  const urgentSummary =
    daysToMove >= 0 && daysToMove <= 7 && overdueOrUrgent > 0
      ? `${overdueOrUrgent} requirement${overdueOrUrgent === 1 ? ' is' : 's are'} overdue or critically urgent.`
      : null;

  return {
    corridor: 'france-norway',
    corridorLabel: 'France \u2192 Norway',
    employeeType,
    employeeTypeLabel: employeeType === 'eea' ? 'EEA national' : 'Non-EEA national (resident in France)',
    moveDate,
    today,
    criticalBanner,
    moveDatePassedWarning,
    urgentSummary,
    requirements,
    counts,
  };
}
