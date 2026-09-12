/** Work & Place step — BUG-260828-87B8. Intake-only work_mode axis. */

export type WorkMode = 'employed' | 'self_employed' | 'digital_nomad';

export const WORK_MODES: readonly WorkMode[] = ['employed', 'self_employed', 'digital_nomad'];

export const WORK_MODE_OPTIONS: { value: WorkMode; label: string }[] = [
  { value: 'employed', label: 'Employed by a company' },
  { value: 'self_employed', label: 'Entrepreneur / self-employed' },
  { value: 'digital_nomad', label: 'Digital nomad / remote' },
];

export const WORK_MODE_HELP: Record<WorkMode, string> = {
  employed:
    'Your employer is sending you. We use contract dates and the destination office for commute, housing, and work-permit checks.',
  self_employed:
    'You are moving your own activity. No employer contract is required. Office is optional — skip it if you work from home or a coworking space.',
  digital_nomad:
    'You keep working remotely (home employer or your own company) while living in the destination. We will not ask for a local office or a local employment contract.',
};

export const SELF_EMPLOYED_CONTRACT = 'Self-employed / entrepreneur';
export const OFFICE_UNKNOWN = 'Not known yet';

export function isWorkMode(value: string): value is WorkMode {
  return (WORK_MODES as readonly string[]).includes(value);
}

export function needsContractStart(mode: WorkMode): boolean {
  return mode === 'employed';
}

export function needsOffice(mode: WorkMode): boolean {
  return mode === 'employed';
}

export function workModeLabel(mode: WorkMode): string {
  return WORK_MODE_OPTIONS.find((o) => o.value === mode)?.label ?? mode;
}

type WorkFields = {
  work_mode: WorkMode;
  job_title: string;
  contract_type: string;
  contract_start: string;
  office_address: string;
  work_pattern: string;
  salary_band: string;
  assignment_type: string;
};

/** Patch related fields when the user picks a work mode. Does not wipe typed office/start. */
export function applyWorkModePatch<T extends WorkFields>(data: T, mode: WorkMode): T {
  const next: T = { ...data, work_mode: mode };
  if (mode === 'employed') {
    if (data.contract_type === SELF_EMPLOYED_CONTRACT || !data.contract_type) {
      next.contract_type = 'Permanent';
    }
  } else if (mode === 'self_employed') {
    next.contract_type = SELF_EMPLOYED_CONTRACT;
  } else {
    next.contract_type = '';
    next.work_pattern = 'Fully remote';
    if (data.assignment_type === 'LTA') next.assignment_type = 'STA';
  }
  return next;
}

/** Restore work_mode on drafts saved before the field existed. */
export function hydrateWorkMode<T extends { work_mode?: string; contract_type?: string }>(
  data: T,
): T {
  const mode = data.work_mode ?? '';
  if (isWorkMode(mode) && !(mode === 'employed' && data.contract_type === SELF_EMPLOYED_CONTRACT)) {
    return data;
  }
  const inferred: WorkMode =
    data.contract_type === SELF_EMPLOYED_CONTRACT ? 'self_employed' : 'employed';
  return { ...data, work_mode: inferred };
}

export function workAndPlaceComplete(data: {
  work_mode?: string;
  job_title: string;
  contract_type: string;
  contract_start: string;
  office_address: string;
  work_pattern: string;
  salary_band: string;
}): boolean {
  const raw = data.work_mode ?? '';
  const mode: WorkMode = isWorkMode(raw) ? raw : 'employed';
  if (!data.job_title.trim() || !data.salary_band.trim()) return false;
  if (mode === 'digital_nomad') return true;
  if (!data.work_pattern.trim()) return false;
  if (mode === 'self_employed') return true;
  return Boolean(
    data.contract_type.trim() &&
      data.contract_start.trim() &&
      data.office_address.trim(),
  );
}
