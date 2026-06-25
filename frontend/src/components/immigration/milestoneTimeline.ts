/**
 * milestoneTimeline — IMM-14
 *
 * Pure timeline maths + canonical milestone definitions for the immigration
 * application tracker. Kept free of any API/React imports so it can be unit
 * tested in isolation. All date arithmetic is done on calendar dates in UTC so
 * results are deterministic regardless of the runner's timezone.
 */

export interface MilestoneDef {
  type: string;
  label: string;
  /** Offset in days from the move date (arrival == move date == 0). */
  offset: number;
  note?: string;
  conditional?: boolean;
}

// Canonical milestone sequence (IMM-14 spec). Offsets are relative to move date.
export const MILESTONE_DEFS: MilestoneDef[] = [
  { type: 'dossier_assembly_start', label: 'Dossier assembly start', offset: -60 },
  { type: 'criminal_record_check', label: 'Criminal record check ordered', offset: -55,
    note: 'Must be under 3 months old at submission.' },
  { type: 'application_filed', label: 'Application filed', offset: -30 },
  { type: 'biometric_appointment', label: 'Biometric appointment', offset: -20,
    conditional: true, note: 'If required for this corridor.' },
  { type: 'visa_decision_expected', label: 'Visa decision expected', offset: -5 },
  { type: 'arrival', label: 'Arrival', offset: 0 },
  { type: 'local_registration', label: 'Local registration', offset: 14,
    note: 'DE Anmeldung / FR OFII — within 14 days of arrival.' },
  { type: 'work_permit_issued', label: 'Work permit issued', offset: 30,
    note: 'Estimated 30 days after arrival.' },
];

// Corridors that warrant an early-booking alert. Key = `${from}>${to}`.
export const BOOK_EARLY_ALERTS: Record<string, string> = {
  'IN>DE': 'BfA pre-approval typically takes 4–6 weeks — start immediately.',
};

const MS_PER_DAY = 86_400_000;

/** Parse an ISO date (or datetime) to UTC midnight of its calendar date. */
export function parseISODate(iso: string): Date {
  const [y = NaN, m = NaN, d = NaN] = iso.slice(0, 10).split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

/** Today's calendar date (local) as a 'YYYY-MM-DD' string. */
export function todayISODate(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function addDaysISO(iso: string, days: number): string {
  const base = parseISODate(iso);
  return new Date(base.getTime() + days * MS_PER_DAY).toISOString().slice(0, 10);
}

/** Whole days from `bISO` to `aISO` (a - b). Positive = a is later. */
export function diffDaysISO(aISO: string, bISO: string): number {
  return Math.round((parseISODate(aISO).getTime() - parseISODate(bISO).getTime()) / MS_PER_DAY);
}

export function formatISODate(iso: string): string {
  return parseISODate(iso).toLocaleDateString(undefined, {
    day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC',
  });
}

/**
 * Canonical milestone target dates computed from a move date. Exported for
 * unit testing the timeline maths (IMM-14 validation criterion 1).
 */
export function computeMilestoneTargets(
  moveDateISO: string,
): Array<{ type: string; label: string; offset: number; targetISO: string }> {
  return MILESTONE_DEFS.map((def) => ({
    type: def.type,
    label: def.label,
    offset: def.offset,
    targetISO: addDaysISO(moveDateISO, def.offset),
  }));
}

/** Whole days a target is overdue relative to today (0 if not overdue / completed). */
export function daysOverdue(targetISO: string, todayISO: string, completed: boolean): number {
  if (completed) return 0;
  const diff = diffDaysISO(todayISO, targetISO);
  return diff > 0 ? diff : 0;
}
